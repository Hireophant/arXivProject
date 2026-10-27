"""Preparation contracts exercised with real nested ZIPs, not network mocks."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tracemalloc
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile


PAPER = '2606.20274'
TEX = b'\\documentclass{article}\n\\begin{document}Original.\\end{document}\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def backup(root, name, *, versions=(1,), sources=None, stub=False, when='2026-10-27T12:00:00+00:00', source_elapsed=1.0):
    """Independent fixture implements the existing M1 archive/receipt shapes."""
    folder = root / name
    folder.mkdir(parents=True)
    sources = sources if sources is not None else {1: TEX}
    downloads = {}
    files = {}
    for version in versions:
        body = sources.get(version, 'missing')
        status = 'failed' if body == 'missing' else 'no_tex' if body is None else 'success'
        result = dict(arxiv_id=PAPER, version=version, status=status,
                      source_bytes_before=len(body) if isinstance(body, bytes) else 0,
                      source_bytes_after=len(body) if isinstance(body, bytes) else 0,
                      archive_bytes=100, file_count=1 if isinstance(body, bytes) else 0,
                      elapsed_seconds=source_elapsed, attempts=1, used_cache=False,
                      error='Verified pdf source without TeX.' if body is None else 'HTTP 429' if body == 'missing' else None)
        downloads[str(version)] = result
        if body == 'missing' or stub:
            continue
        prefix = f'2606-20274/sources/v{version}'
        # Empty directories matter for verified no_tex.
        files[prefix + '/'] = b''
        hashes = {}
        if body is not None:
            files[prefix + '/main.tex'] = body
            hashes['main.tex'] = digest(body)
        receipt = dict(schema_version='3.0', arxiv_id=PAPER, version=version,
                       source_url=f'https://export.arxiv.org/src/{PAPER}v{version}',
                       source_kind='pdf' if body is None else 'tex', result=result,
                       files_sha256=hashes)
        files[f'2606-20274/sources/.v{version}.receipt.json'] = json.dumps(receipt).encode()
    metadata = dict(arxiv_id=PAPER, title='Original title', authors=['A. Author'],
                    submission_date='2026-06-18', revised_dates=['2026-08-22'] * (len(versions)-1), venue=None)
    record = dict(arxiv_id=PAPER, versions=list(versions), metadata=metadata)
    refs = dict(arxiv_id=PAPER, status='success', references={}, all_references=[], pagination_complete=True)
    paper = dict(record=record, metadata_path='2606-20274/metadata.json', downloads=downloads, references=refs)
    manifest = dict(schema_version='3.0', run_id=name.split('/')[-1], updated_at=when,
                    metadata_source='oai-pmh/arXivRaw', papers={PAPER: paper},
                    scope=dict(mode='ids', ids=[PAPER], start_id=None, end_id=None),
                    discovery=dict(papers=[record], issues=[]))
    files['manifest.json'] = json.dumps(manifest).encode()
    if not stub:
        files['2606-20274/metadata.json'] = json.dumps(metadata).encode()
        files['2606-20274/references.json'] = b'{}'
        files['2606-20274/references_all.json'] = b'[]'
    for archive_name, entries in [('corpus', files), ('report', {'manifest.json': files['manifest.json']})]:
        with zipfile.ZipFile(folder / (archive_name + '.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for path, data in entries.items():
                z.writestr(path, data)
    receipt = dict(schema_version='1.0', run_id=manifest['run_id'], created_at_utc=when,
                   archives={key:dict(filename=key+'.zip',bytes=(folder/(key+'.zip')).stat().st_size,
                                      sha256=digest((folder/(key+'.zip')).read_bytes())) for key in ('corpus','report')})
    (folder/'backup_receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    return folder


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / 'data/validation' / ('prepare-test-' + uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.source = self.root / 'Milestone1'
        self.source.mkdir()
        self.output = self.root / 'preparationM2' / 'raw_m1' / 'Danh2'

    def api(self):
        # Import inside the test: the RED stage reports an explicit missing-feature assertion.
        try:
            from src.preparation.milestone2 import prepare_corpus, inspect_backups
        except ImportError:
            self.fail('M2 preparation API has not been implemented')
        return prepare_corpus, inspect_backups

    def manifest(self):
        return json.loads((self.output/'manifest.json').read_text(encoding='utf-8'))

    def validator(self):
        try:
            from src.preparation import validate_prepared_corpus
        except ImportError:
            self.fail('Read-back validation for the M2 input contract has not been implemented')
        return validate_prepared_corpus

    def test_json_reader_keeps_tiny_metadata_memory_bounded(self):
        self.api()
        from src.preparation.milestone2 import _load_json
        path=self.root/'tiny.json'
        path.write_bytes(b'{"value": 1}')
        tracemalloc.start()
        try:
            with path.open('rb') as stream:
                value=_load_json(stream)
            peak=tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(value,{'value':1})
        self.assertLess(peak,4*1024**2,'Tiny metadata must not reserve the maximum manifest size')

    def test_chunked_json_reader_still_rejects_oversized_input(self):
        self.api()
        from src.preparation.milestone2 import _load_json
        with self.assertRaises(ValueError):
            _load_json(io.BytesIO(b'{"value": 1}'),limit=4)

    def test_preparation_publishes_validation_with_stable_snapshot_on_rerun(self):
        prepare,_=self.api()
        backup(self.source,'a',versions=(1,2,3),sources={1:TEX,2:None})
        first=prepare(self.source,self.output)
        path=self.output/'input_validation.json'
        self.assertTrue(path.is_file(),'Preparation must verify the saved input before handoff')
        validation=json.loads(path.read_text())
        self.assertTrue(validation['valid'])
        self.assertFalse(validation['complete'])
        self.assertEqual(validation['run_id'],first['run_id'])
        second=prepare(self.source,self.output)
        rerun=json.loads(path.read_text())
        self.assertEqual(validation['snapshot_id'],rerun['snapshot_id'])
        self.assertNotEqual(first['run_id'],second['run_id'])

    def test_readback_validator_detects_source_damage_after_preparation(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        (self.output/'2606-20274/sources/v1/main.tex').write_bytes(b'changed after save')
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('SOURCE_INTEGRITY',{i['code'] for i in result['issues']})

    def test_readback_validator_rejects_missing_inventory_rows_and_stale_completion(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        path=self.output/'inventory.csv'
        path.write_text(path.read_text().splitlines()[0]+'\n',encoding='utf-8')
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('INVENTORY_MISMATCH',{i['code'] for i in result['issues']})
        prepare(self.source,self.output)
        path=self.output/'preparation.json'
        summary=json.loads(path.read_text())
        summary['status']='in_progress'
        path.write_text(json.dumps(summary))
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('INCOMPLETE_RUN',{i['code'] for i in result['issues']})

    def test_readback_validator_checks_metadata_and_reference_artifacts(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        (self.output/'2606-20274/metadata.json').write_text('{}')
        (self.output/'2606-20274/references_all.json').unlink()
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('METADATA_INTEGRITY',{i['code'] for i in result['issues']})
        self.assertIn('REFERENCE_INTEGRITY',{i['code'] for i in result['issues']})

    def test_readback_validator_cannot_follow_reference_path_outside_corpus(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        manifest=self.manifest()
        manifest['papers'][PAPER]['references']['path']='../../outside.json'
        (self.output/'manifest.json').write_text(json.dumps(manifest))
        self.assertFalse(validate(self.output)['valid'])

    def test_prepared_snapshot_is_portable_to_another_dataset_directory(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a',versions=(1,2),sources={1:TEX,2:None})
        prepared=prepare(self.source,self.output)
        relocated=self.root/'copied-preparationM2'/'raw_m1'/'Danh2'
        shutil.copytree(self.output,relocated)
        checked=validate(relocated)
        self.assertTrue(checked['valid'])
        self.assertTrue(checked['complete'])
        self.assertEqual(checked['snapshot_id'],prepared['snapshot_id'])

    def test_duplicate_source_bytes_keep_manifest_and_written_receipt_consistent(self):
        prepare,_=self.api()
        backup(self.source,'a',source_elapsed=1.0)
        backup(self.source,'b',source_elapsed=2.5)
        result=prepare(self.source,self.output)
        self.assertEqual(result['status'],'ready')
        self.assertTrue(result['input_valid'])
        receipt=json.loads((self.output/'2606-20274/sources/.v1.receipt.json').read_text())
        self.assertEqual(self.manifest()['papers'][PAPER]['downloads']['1'],receipt['result'])

    def test_saved_snapshot_detects_consistent_manual_metadata_edits(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        manifest=self.manifest()
        metadata=manifest['papers'][PAPER]['record']['metadata']
        metadata['title']='Changed consistently in both files'
        (self.output/'manifest.json').write_text(json.dumps(manifest))
        (self.output/'2606-20274/metadata.json').write_text(json.dumps(metadata))
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('SNAPSHOT_MISMATCH',{i['code'] for i in result['issues']})

    def test_readback_validator_rejects_unreadable_provenance(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        (self.output/'provenance.jsonl').write_text('not json\n')
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('AUDIT_INTEGRITY',{i['code'] for i in result['issues']})

    def test_readback_validator_requires_provenance_for_each_usable_version(self):
        prepare,_=self.api()
        validate=self.validator()
        backup(self.source,'a')
        prepare(self.source,self.output)
        path=self.output/'provenance.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows=[row for row in rows if row['decision']=='m1_download_record']
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        result=validate(self.output)
        self.assertFalse(result['valid'])
        self.assertIn('AUDIT_INTEGRITY',{i['code'] for i in result['issues']})

    def test_preparation_retries_transient_file_lock_when_publishing_source(self):
        prepare,_=self.api()
        backup(self.source,'a')
        from src.preparation import milestone2
        real_replace=milestone2.os.replace
        locked=False
        def transient_lock(source,target):
            nonlocal locked
            if Path(source).name=='prepared' and Path(target).name=='v1' and not locked:
                locked=True
                error=PermissionError('Temporary sharing violation')
                error.winerror=32
                raise error
            return real_replace(source,target)
        with patch.object(milestone2.os,'replace',side_effect=transient_lock):
            result=prepare(self.source,self.output)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['backup_errors'],0)
        self.assertEqual((self.output/'2606-20274/sources/v1/main.tex').read_bytes(),TEX)

    def test_combines_partial_retries_and_manifest_stub_without_losing_versions(self):
        prepare, inspect = self.api()
        backup(self.source, 'checkpoints/a', versions=(1,2), sources={1:TEX})
        backup(self.source, 'checkpoints/b', versions=(1,2), sources={2:TEX+b'% v2'}, when='2026-10-27T13:00:00+00:00')
        backup(self.source, 'session-reports/c', versions=(1,2), stub=True, when='2026-10-27T14:00:00+00:00')
        self.assertEqual(inspect(self.source)['backup_count'],3)
        result = prepare(self.source,self.output)
        self.assertEqual((result['status'],result['versions_expected'],result['versions_ready_tex']),('ready',2,2))
        self.assertEqual((self.output/'2606-20274/sources/v1/main.tex').read_bytes(),TEX)
        self.assertEqual((self.output/'2606-20274/sources/v2/main.tex').read_bytes(),TEX+b'% v2')
        self.assertEqual(self.manifest()['papers'][PAPER]['record']['versions'],[1,2])
        self.assertEqual(self.manifest()['schema_version'],'m2-input-1.0')

    def test_keeps_verified_no_tex_and_missing_versions_in_inventory(self):
        prepare,_ = self.api()
        backup(self.source,'checkpoints/a',versions=(1,2,3),sources={1:TEX,2:None})
        result=prepare(self.source,self.output)
        self.assertEqual((result['versions_ready_tex'],result['versions_empty_no_tex'],result['versions_blocked']),(1,1,1))
        self.assertEqual(result['status'],'partial')
        self.assertEqual(self.manifest()['papers'][PAPER]['version_states'],{'1':'ready_tex','2':'empty_no_tex','3':'blocked_input'})
        self.assertTrue((self.output/'2606-20274/sources/v2').is_dir())
        self.assertFalse((self.output/'2606-20274/sources/v3').exists())

    def test_supports_drive_download_zip_and_does_not_change_input(self):
        prepare,_ = self.api()
        backup(self.source,'checkpoints/a')
        outer=self.root/'drive-download.zip'
        with zipfile.ZipFile(outer,'w',zipfile.ZIP_DEFLATED) as z:
            for p in self.source.rglob('*'):
                if p.is_file():z.write(p,p.relative_to(self.root).as_posix())
        before=digest(outer.read_bytes())
        result=prepare(outer,self.output)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(digest(outer.read_bytes()),before)

    def test_rerun_revalidates_and_repairs_damaged_restored_source(self):
        prepare,_ = self.api()
        backup(self.source,'a')
        prepare(self.source,self.output)
        target=self.output/'2606-20274/sources/v1/main.tex'
        target.write_bytes(b'damaged local copy')
        result=prepare(self.source,self.output)
        self.assertEqual(target.read_bytes(),TEX)
        self.assertEqual(result['versions_expected'],1)
        self.assertEqual(result['status'],'ready')

    def test_corrupt_archive_is_reported_without_overwriting_valid_copy(self):
        prepare,_=self.api()
        backup(self.source,'a')
        bad=backup(self.source,'b',sources={1:TEX+b' different'})
        (bad/'corpus.zip').write_bytes(b'corrupted')
        result=prepare(self.source,self.output)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['versions_ready_tex'],1)
        self.assertGreater(result['backup_errors'],0)
        self.assertEqual((self.output/'2606-20274/sources/v1/main.tex').read_bytes(),TEX)

    def test_different_verified_bytes_for_same_version_block_the_version(self):
        prepare,_=self.api()
        backup(self.source,'a')
        backup(self.source,'b',sources={1:TEX+b'% conflict'})
        result=prepare(self.source,self.output)
        self.assertEqual((result['status'],result['versions_ready_tex'],result['versions_blocked']),('partial',0,1))
        self.assertIn('SOURCE_CONFLICT',(self.output/'inventory.csv').read_text())

    def test_stub_only_is_not_a_successful_source_restore(self):
        prepare,_=self.api()
        backup(self.source,'session-reports/a',stub=True)
        result=prepare(self.source,self.output)
        self.assertEqual((result['status'],result['versions_ready_tex'],result['versions_blocked']),('partial',0,1))

    def test_rejects_output_overlap_and_unowned_output(self):
        prepare,_=self.api()
        backup(self.source,'a')
        with self.assertRaises(ValueError):prepare(self.source,self.source/'Milestone2')
        self.output.mkdir(parents=True)
        (self.output/'user.txt').write_text('keep')
        with self.assertRaises(ValueError):prepare(self.source,self.output)
        self.assertEqual((self.output/'user.txt').read_text(),'keep')

    def test_rejects_unsafe_outer_archive_without_writing_outside_output(self):
        prepare,_=self.api()
        outer=self.root/'bad.zip'
        with zipfile.ZipFile(outer,'w') as z:z.writestr('../outside.txt',b'bad')
        with self.assertRaises(ValueError):prepare(outer,self.output)
        self.assertFalse((self.root/'outside.txt').exists())

    def test_empty_input_does_not_report_ready(self):
        prepare,_=self.api()
        with self.assertRaises(ValueError):prepare(self.source,self.output)

    def test_identical_receipt_does_not_hide_corrupt_candidate_source_bytes(self):
        prepare,_=self.api()
        backup(self.source,'a')
        damaged=backup(self.source,'b')
        archive=damaged/'corpus.zip'
        with zipfile.ZipFile(archive) as z:
            entries={n:z.read(n) for n in z.namelist()}
        entries['2606-20274/sources/v1/main.tex']=b'Altered source with stale per-version receipt'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for n,body in entries.items():z.writestr(n,body)
        envelope=json.loads((damaged/'backup_receipt.json').read_text())
        envelope['archives']['corpus'].update(bytes=archive.stat().st_size,sha256=digest(archive.read_bytes()))
        (damaged/'backup_receipt.json').write_text(json.dumps(envelope),encoding='utf-8')
        result=prepare(self.source,self.output)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['backup_errors'],1)
        self.assertIn('SOURCE_INVALID',(self.output/'backup_audit.jsonl').read_text())
        self.assertEqual((self.output/'2606-20274/sources/v1/main.tex').read_bytes(),TEX)

    def test_blocked_versions_keep_original_failed_download_and_backup_evidence(self):
        prepare,_=self.api()
        backup(self.source,'a',versions=(1,2),sources={1:TEX})
        prepare(self.source,self.output)
        result=self.manifest()['papers'][PAPER]['downloads']['2']
        self.assertIsNotNone(result)
        self.assertEqual((result['status'],result['error'],result['attempts']),('failed','HTTP 429',1))
        self.assertIn('HTTP 429',(self.output/'provenance.jsonl').read_text())

    def test_rerun_removes_unexpected_empty_directories_from_no_tex_version(self):
        prepare,_=self.api()
        backup(self.source,'a',sources={1:None})
        prepare(self.source,self.output)
        target=self.output/'2606-20274/sources/v1'
        (target/'unexpected').mkdir()
        result=prepare(self.source,self.output)
        self.assertEqual(result['versions_empty_no_tex'],1)
        self.assertEqual(list(target.iterdir()),[])

    def test_preparation_notebook_executes_locally_against_real_backup_fixture(self):
        self.api()
        backup(self.source,'checkpoints/a',versions=(1,2),sources={1:TEX,2:None})
        repo=Path(__file__).resolve().parents[1]
        notebook_path=repo/'src/notebooks/milestone2_prepare.ipynb'
        self.assertTrue(notebook_path.is_file(),'Preparation notebook has not been implemented')
        notebook=json.loads(notebook_path.read_text(encoding='utf-8'))
        namespace={'__name__':'__main__'}
        config=(f"from pathlib import Path\nSOURCE_PATH=Path({str(self.source)!r})\n"
                f"PREPARATION_DIR=Path({str(self.root/'preparationM2')!r})\n"
                f"PROJECT_DIR=Path({str(repo)!r})\nDATASET_NAME='Danh2'\n"
                "REPOSITORY_URL='unused'\nREPOSITORY_BRANCH='master'\nCLONE_IF_NEEDED=False\nSHOW_PROGRESS_EVERY=10\n")
        with redirect_stdout(io.StringIO()):
            for cell in notebook['cells']:
                if cell['cell_type']!='code':continue
                code=config if 'parameters' in cell.get('metadata',{}).get('tags',[]) else ''.join(cell['source'])
                exec(compile(code,str(notebook_path),'exec'),namespace)
        self.assertEqual(namespace['summary']['status'],'ready')
        self.assertEqual(namespace['summary']['versions_empty_no_tex'],1)
        self.assertEqual((self.output/'2606-20274/sources/v1/main.tex').read_bytes(),TEX)


if __name__=='__main__':unittest.main()
