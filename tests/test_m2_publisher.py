import hashlib
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from test_m2_preparation import backup
from src.preparation import prepare_corpus
from src.preparation.publisher import publish_prepared_archive
from src.preparation.transport import pack_prepared_corpus


class _Status:
    def __init__(self, sent): self.sent = sent
    def resumable_progress(self): return self.sent


class _Request:
    def __init__(self, response, size, fail=False):
        self.response, self.size, self.fail, self.calls = response, size, fail, 0
    def next_chunk(self):
        self.calls += 1
        if self.fail: raise OSError('upload interrupted')
        return (_Status(self.size), self.response) if self.calls == 1 else (None, self.response)
    def execute(self): return self.response


class _Files:
    def __init__(self, corrupt=False, corrupt_receipt=False, fail=False):
        self.corrupt, self.corrupt_receipt, self.fail, self.items, self.uploads = corrupt, corrupt_receipt, fail, {}, []
    def create(self, body, media_body, fields):
        path = Path(media_body); file_id = str(len(self.items) + 1)
        item = dict(id=file_id, name=body['name'], size=str(path.stat().st_size),
                    md5Checksum=hashlib.md5(path.read_bytes()).hexdigest())
        self.items[file_id] = item; self.uploads.append(body['name'])
        return _Request(item, path.stat().st_size, self.fail and len(self.uploads) == 1)
    def get(self, fileId, fields):
        item = dict(self.items[fileId])
        if self.corrupt and len(self.uploads) == 1: item['md5Checksum'] = '0' * 32
        if self.corrupt_receipt and len(self.uploads) == 2: item['md5Checksum'] = '0' * 32
        return _Request(item, 0)
    def update(self, fileId, body, fields):
        self.items[fileId]['name'] = body['name']
        return _Request(self.items[fileId], 0)


class _Drive:
    def __init__(self, **kwargs): self.files_api = _Files(**kwargs)
    def files(self): return self.files_api


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.root = Path('data/validation') / ('publisher-test-' + uuid4().hex)
        self.root.mkdir(parents=True); self.addCleanup(shutil.rmtree, self.root)
        backup(self.root / 'm1', 'full')
        raw = self.root / 'raw'; prepare_corpus(self.root / 'm1', raw)
        self.archive = self.root / 'prepared.zip'; pack_prepared_corpus(raw, self.archive)

    def test_receipt_is_uploaded_only_after_remote_archive_verification(self):
        drive, events = _Drive(), []
        result = publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path,
                                          progress=lambda *event: events.append(event))
        self.assertTrue(drive.files_api.uploads[0].startswith('prepared.attempt-'))
        self.assertTrue(drive.files_api.uploads[1].startswith(drive.files_api.uploads[0] + '.receipt.json.pending-'))
        self.assertIn(result['archive']['name'] + '.receipt.json', [item['name'] for item in drive.files_api.items.values()])
        self.assertEqual(result['snapshot_id'], __import__('json').loads(Path(str(self.archive) + '.receipt.json').read_text(encoding='utf-8'))['snapshot_id'])
        self.assertEqual(events[-1][0], 'remote_verified')

    def test_checksum_mismatch_never_uploads_receipt(self):
        drive = _Drive(corrupt=True)
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path)
        self.assertEqual(len(drive.files_api.uploads), 1)

    def test_interrupted_upload_never_uploads_receipt(self):
        drive = _Drive(fail=True)
        with self.assertRaisesRegex(OSError, 'interrupted'):
            publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path)
        self.assertEqual(len(drive.files_api.uploads), 1)

    def test_receipt_mismatch_never_publishes_final_receipt_name(self):
        drive = _Drive(corrupt_receipt=True)
        with self.assertRaisesRegex(ValueError, 'receipt size/checksum'):
            publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path)
        self.assertEqual(len(drive.files_api.uploads), 2)
        self.assertIn('.pending-', drive.files_api.uploads[-1])

    def test_repeated_publish_uses_distinct_archive_and_receipt_names(self):
        drive = _Drive()
        first = publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path)
        second = publish_prepared_archive(self.archive, 'folder', drive, lambda path, resumable: path)
        self.assertNotEqual(first['archive']['name'], second['archive']['name'])
        self.assertEqual(len({item['name'] for item in drive.files_api.items.values()}), 4)
