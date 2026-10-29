"""Real archive round trips preserve prepared input; no network or parser needed."""
import hashlib
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4
from unittest.mock import patch
import zipfile

from test_m2_preparation import backup
from src.preparation import prepare_corpus, validate_prepared_corpus
from src.preparation.transport import pack_prepared_corpus, stage_prepared_archive


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.root = Path('data/validation') / ('transport-test-' + uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)

    def prepared(self):
        backup(self.root / 'm1', 'full', versions=(1, 2), sources={1: b'\\documentclass{article}\nHello.', 2: None})
        raw = self.root / 'prepared'
        prepare_corpus(self.root / 'm1', raw)
        return raw

    def test_round_trip_snapshot_and_empty_version(self):
        raw = self.prepared()
        archive = self.root / 'input.zip'
        receipt = pack_prepared_corpus(raw, archive)
        self.assertEqual(receipt['snapshot_id'], validate_prepared_corpus(raw)['snapshot_id'])
        self.assertEqual(receipt, json.loads(Path(str(archive) + '.receipt.json').read_text(encoding='utf-8')))
        local = stage_prepared_archive(archive, self.root / 'local', expected_sha256=receipt['sha256'])
        check = validate_prepared_corpus(local)
        self.assertTrue(check['valid'], check['issues'])
        self.assertEqual(check['snapshot_id'], receipt['snapshot_id'])
        self.assertEqual(check['versions_empty_no_tex'], 1)

    def test_bad_hash_never_publishes_local_input(self):
        archive = self.root / 'input.zip'
        pack_prepared_corpus(self.prepared(), archive)
        target = self.root / 'local'
        with self.assertRaises(ValueError):
            stage_prepared_archive(archive, target, expected_sha256='0' * 64)
        self.assertFalse(target.exists())

    def test_unsafe_archive_and_existing_destination_rejected(self):
        archive = self.root / 'unsafe.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('../escape.tex', 'bad')
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            stage_prepared_archive(archive, self.root / 'local', expected_sha256=expected)
        self.assertFalse((self.root / 'escape.tex').exists())
        raw = self.prepared()
        good = self.root / 'good.zip'
        receipt = pack_prepared_corpus(raw, good)
        with self.assertRaises(FileExistsError):
            stage_prepared_archive(good, raw, expected_sha256=receipt['sha256'])
        self.assertTrue(validate_prepared_corpus(raw)['valid'])

    def test_invalid_raw_and_archive_inside_raw_rejected(self):
        raw = self.prepared()
        with self.assertRaises(ValueError):
            pack_prepared_corpus(raw, raw / 'input.zip')
        (raw / 'manifest.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            pack_prepared_corpus(raw, self.root / 'bad.zip')
        self.assertFalse((self.root / 'bad.zip').exists())

    def test_parent_path_alias_cannot_put_archive_inside_raw(self):
        raw = self.prepared()
        alias = self.root / 'alias'
        alias.mkdir()
        destination = alias / '..' / raw.name / 'input.zip'
        original_write = zipfile.ZipFile.write

        def prevent_self_read(zipped, filename, *args, **kwargs):
            # Stop a regression before a growing ZIP reads its own contents.
            if Path(filename).name.startswith('input.zip.tmp-'):
                raise AssertionError('Packer attempted to read its own temporary archive')
            return original_write(zipped, filename, *args, **kwargs)

        with patch.object(zipfile.ZipFile, 'write', prevent_self_read):
            with self.assertRaises(ValueError):
                pack_prepared_corpus(raw, destination)
        self.assertFalse((raw / 'input.zip').exists())

    def test_case_collision_rejected(self):
        archive = self.root / 'collision.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('A.tex', 'a')
            zipped.writestr('a.tex', 'b')
        with self.assertRaises(ValueError):
            stage_prepared_archive(archive, self.root / 'local', expected_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_parser_notebook_stages_prepared_raw_without_running_parser(self):
        import sys
        archive = self.root / 'input.zip'
        pack_prepared_corpus(self.prepared(), archive)
        notebook = json.loads(Path('src/notebooks/milestone2.ipynb').read_text(encoding='utf-8'))
        scope = {}
        old_path = sys.path[:]
        try:
            with redirect_stdout(io.StringIO()):
                for cell in notebook['cells']:
                    if cell['cell_type'] != 'code':
                        continue
                    exec(compile(''.join(cell['source']), cell['id'], 'exec'), scope)
                    if cell['id'] == 'm2-template-01':
                        scope.update(PROJECT_DIR=Path.cwd(), STAGE_INPUT=True, RUN_PARSER=False,
                                     PREPARED_ARCHIVE=archive.resolve(),
                                     RAW_CORPUS_ROOT=(self.root / 'local').resolve(),
                                     OUTPUT_ROOT=(self.root / 'parsed').resolve())
            self.assertTrue(validate_prepared_corpus(scope['RAW_CORPUS_ROOT'])['valid'])
            self.assertFalse(scope['OUTPUT_ROOT'].exists())
        finally:
            sys.path[:] = old_path
