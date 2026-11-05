"""DA3 orchestration unit tests; upstream raw integration remains pending."""
import json
import unittest
from copy import deepcopy
from dataclasses import asdict,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
from m2_support.fixtures import make_expected_publication,make_publication_input,make_gathered,make_raw_tree,make_extraction,make_unified_bibliography,SNAPSHOT
from src.parsing.contracts import ParseConfig,MetricsSummary,VersionMetric,VERSION_STATUSES
from src.parsing import pipeline
from src.parsing.serialization import read_publication

SCRATCH=Path(__file__).resolve().parents[1]/'data/milestone2-dev/danh'
SCRATCH.mkdir(parents=True,exist_ok=True)

def summary_fixture(publications):
    # Hand-calculated unit contract return, NOT a substitute implementation of Khánh's metrics.
    p=publications[0]
    return MetricsSummary(versions=[VersionMetric(arxiv_id=p.arxiv_id,version=v,status=s,error_codes=[],export_ready=p.export_ready) for v,s in p.version_states.items()],status_counts={s:sum(v==s for v in p.version_states.values()) for s in VERSION_STATUSES},publication_count=1,export_ready_publication_count=int(p.export_ready),parse_success_rate=1.,resolved_version_coverage=1.,attempt_coverage=1.,dedup=deepcopy(p.counts_before_after))

def write_metrics_fixture(summary,output_dir,**kwargs):
    output_dir.mkdir(parents=True,exist_ok=True)
    path=output_dir/'run_summary.json';path.write_text(json.dumps(asdict(summary)),encoding='utf-8');return [path]

class PipelineTests(unittest.TestCase):
    def test_signature_changes_all_cache_inputs_and_excludes_absolute_path(self):
        p=make_publication_input();c=ParseConfig(code_revision='test-revision')
        original=pipeline.checkpoint_signature(p,c)
        self.assertEqual(original,pipeline.checkpoint_signature(replace(p,corpus_root=Path('/moved')),c))
        for config in (replace(c,strict=False),replace(c,normalization_version='new'),replace(c,code_revision='new')):
            self.assertNotEqual(original,pipeline.checkpoint_signature(p,config))
        changed=deepcopy(p);changed.versions[0].source_fingerprint='changed'
        self.assertNotEqual(original,pipeline.checkpoint_signature(changed,c))
        changed.versions[0].source_fingerprint=p.versions[0].source_fingerprint;changed.versions[0].source_status='blocked'
        self.assertNotEqual(original,pipeline.checkpoint_signature(changed,c))
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            review=Path(tmp)/'r.json';review.write_text('first','utf-8')
            c=replace(c,reference_review_path=review);before=pipeline.checkpoint_signature(p,c)
            review.write_text('second','utf-8');self.assertNotEqual(before,pipeline.checkpoint_signature(p,c))
        with self.assertRaises(ValueError):pipeline.checkpoint_signature(p,ParseConfig())
        with patch('src.parsing.pipeline._code_hash',return_value='changed-code'):
            self.assertNotEqual(original,pipeline.checkpoint_signature(p,ParseConfig(code_revision='test-revision')))

    def test_write_failure_is_audited_without_publishing_good_cache_as_new(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            first=self.execute(tmp)
            with patch('src.parsing.pipeline.write_publication',side_effect=OSError('disk full')):
                second=self.execute(tmp,resume=True)
            self.assertEqual(second.status,'partial')
            record=json.loads(second.manifest_path.read_text('utf-8'))['publications'][0]
            self.assertIsNone(record['working_path']);self.assertIsNone(record['published_path'])
            self.assertFalse(record['export_ready'])
            self.assertIn('OUTPUT_WRITE_FAILED',(second.manifest_path.parent/record['audit_path']).read_text('utf-8'))
            self.assertEqual(json.loads(first.manifest_path.read_text('utf-8'))['status'],'success')

    def test_checkpoint_failure_keeps_local_output_and_continues(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            original=pipeline._atomic_json
            def fail_checkpoint(path,value):
                if path.parent.name=='checkpoints':raise OSError('checkpoint failed')
                return original(path,value)
            with patch('src.parsing.pipeline._atomic_json',side_effect=fail_checkpoint):
                result=self.execute(tmp)
            self.assertEqual(result.status,'partial')
            self.assertTrue(any(d.code=='OUTPUT_WRITE_FAILED' for d in result.diagnostics))

    def test_artifact_hash_failure_never_publishes_or_checkpoints_incomplete_hashes(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            original=pipeline._hash
            def fail_artifact(path):
                if path.name=='elements.jsonl':raise OSError('unreadable artifact')
                return original(path)
            with patch('src.parsing.pipeline._hash',side_effect=fail_artifact):
                result=self.execute(tmp)
            record=json.loads(result.manifest_path.read_text('utf-8'))['publications'][0]
            self.assertEqual(result.status,'partial')
            self.assertFalse(record['export_ready']);self.assertIsNone(record['published_path'])
            self.assertIsNone(record['working_path']);self.assertEqual(record['output_sha256'],{})
            self.assertFalse((result.manifest_path.parent/'checkpoints').exists())

    def test_code_or_review_changed_during_run_quarantines_its_checkpoints(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            with patch('src.parsing.pipeline._code_hash',side_effect=['original-code','changed-code']):
                with self.assertRaises(ValueError):self.execute(tmp)
            with patch('src.parsing.pipeline._code_hash',return_value='original-code'):
                result=self.execute(tmp,resume=True)
            self.assertFalse(json.loads(result.manifest_path.read_text('utf-8'))['publications'][0]['used_cache'])

    def test_bootstrap_failure_releases_writer_lock(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            original=Path.mkdir
            def fail_bootstrap(path,*args,**kwargs):
                if path.name.startswith('m2-'):raise OSError('no run directory')
                return original(path,*args,**kwargs)
            with patch.object(Path,'mkdir',fail_bootstrap):
                with self.assertRaises(OSError):self.execute(tmp)
            self.assertEqual(self.execute(tmp).status,'success')

    def test_interrupted_writer_does_not_leave_a_stale_lock(self):
        import subprocess,sys
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            output=Path(tmp)/'out';output.mkdir()
            # A lock filename alone is not proof that a process still owns the writer.
            (output/'.m2-writer.lock').write_bytes(b'dead writer')
            script=f"from pathlib import Path; import os; from src.parsing.pipeline import _acquire_writer; stream=_acquire_writer(Path({str(output)!r})); os._exit(0)"
            completed=subprocess.run([sys.executable,'-X','utf8','-c',script],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            held=pipeline._acquire_writer(output)
            try:
                with self.assertRaises(OSError):self.execute(tmp)
            finally:pipeline._release_writer(held)
            self.assertEqual(self.execute(tmp).status,'success')

    def execute(self,tmp,publication=None,config=None,resume=False,fail=None):
        p=publication or make_publication_input();c=config or ParseConfig(code_revision='test-revision')
        with patch('src.parsing.inputs.load_publications',return_value=[p]),patch('src.parsing.pipeline.process_publication',side_effect=fail,return_value=make_expected_publication()),patch('src.parsing.metrics.summarize',side_effect=summary_fixture),patch('src.parsing.metrics.write_metrics',side_effect=write_metrics_fixture):
            return pipeline.run(Path(tmp)/'raw',Path(tmp)/'out',c,resume=resume)

    def test_fresh_resume_hash_tamper_and_namespace(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            first=self.execute(tmp);second=self.execute(tmp,resume=True,fail=AssertionError('cache should avoid processing'))
            self.assertEqual(second.status,'success');self.assertNotEqual(first.run_id,second.run_id)
            manifest=json.loads(second.manifest_path.read_text('utf-8'))
            self.assertTrue(manifest['publications'][0]['used_cache'])
            root=second.manifest_path.parent
            self.assertTrue(read_publication(root/manifest['publications'][0]['working_path']).export_ready)
            for run in (first,second):
                m=json.loads(run.manifest_path.read_text('utf-8'));path=run.manifest_path.parent/m['publications'][0]['working_path']/'elements.jsonl';path.write_text('damaged','utf-8')
            third=self.execute(tmp,resume=True)
            self.assertFalse(json.loads(third.manifest_path.read_text('utf-8'))['publications'][0]['used_cache'])

    def test_new_invalid_input_does_not_use_or_replace_good_cache(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            first=self.execute(tmp);p=make_publication_input();p.versions[0].source_fingerprint='new'
            second=self.execute(tmp,publication=p,resume=True,fail=RuntimeError('bad new source'))
            self.assertNotEqual(second.status,'success')
            manifest=json.loads(second.manifest_path.read_text('utf-8'));record=manifest['publications'][0]
            self.assertFalse(record['used_cache']);self.assertIsNone(record['published_path'])
            old=json.loads(first.manifest_path.read_text('utf-8'))['publications'][0]
            self.assertTrue(read_publication(first.manifest_path.parent/old['working_path']).export_ready)

    def test_strict_changes_publish_only(self):
        from src.parsing.contracts import Diagnostic
        from src.parsing.validation import finalize_publication
        p=make_expected_publication();p.diagnostics=[Diagnostic(code='INCLUDE_MISSING',severity='error',message='fixture',arxiv_id=p.arxiv_id,version=2)];p=finalize_publication(p)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            states=[]
            for strict in (True,False):
                with patch('src.parsing.inputs.load_publications',return_value=[make_publication_input()]),patch('src.parsing.pipeline.process_publication',return_value=p),patch('src.parsing.metrics.summarize',side_effect=summary_fixture),patch('src.parsing.metrics.write_metrics',side_effect=write_metrics_fixture):
                    result=pipeline.run(Path(tmp)/'raw',Path(tmp)/'out',ParseConfig(strict=strict,code_revision='test'))
                m=json.loads(result.manifest_path.read_text('utf-8'));r=m['publications'][0]
                states.append(read_publication(result.manifest_path.parent/r['working_path']).version_states)
                self.assertEqual(result.status,'partial')
                self.assertEqual(r['published_path'],None if strict else r['working_path'])
                self.assertFalse(r['export_ready'])
            self.assertEqual(states[0],states[1])

    def test_upstream_not_implemented_is_visible(self):
        with patch('src.parsing.gather.gather_version',side_effect=NotImplementedError('upstream unavailable')):
            with self.assertRaises(NotImplementedError):
                pipeline.process_publication(make_publication_input(),ParseConfig(code_revision='test'))

    def test_owner_version_exception_keeps_other_versions_and_failed_wrapper(self):
        bib=make_unified_bibliography();bib.occurrences=bib.occurrences[:1];bib.key_map={(1,'alpha'):'alpha'};bib.identity_decisions=[]
        def gather(version):
            if version.version==2:raise RuntimeError('version 2 crashed')
            return make_gathered(1)
        def unify(arxiv_id,extractions,review_decisions=None):
            self.assertEqual([e.version for e in extractions],[1,2])
            self.assertEqual(extractions[1].occurrences,[])
            self.assertTrue(extractions[1].diagnostics)
            return bib
        # Owner boundary unit test; actual normalize/assemble/finalize remain real.
        with patch('src.parsing.gather.gather_version',side_effect=gather),patch('src.parsing.hierarchy.parse_version',return_value=make_raw_tree(1)),patch('src.parsing.bibliography.extract_entries',return_value=make_extraction(1)),patch('src.parsing.reference_dedup.unify_entries',side_effect=unify):
            result=pipeline.process_publication(make_publication_input(),ParseConfig(code_revision='test'))
        self.assertEqual(result.version_states,{1:'parsed',2:'failed'})
        self.assertIsNone(result.root_ids[2]);self.assertIsNotNone(result.root_ids[1]);self.assertFalse(result.export_ready)

    def test_batch_backup_restore_and_corruption_rejection(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            result=self.execute(tmp)
            archive=pipeline.backup_run_batch(result.manifest_path.parent,Path(tmp)/'drive')
            receipt=json.loads(Path(str(archive)+'.receipt.json').read_text('utf-8'))
            restored=pipeline.restore_run_batch(archive,Path(tmp)/'restored',expected_sha256=receipt['sha256'])
            self.assertEqual(json.loads((restored/'manifest.json').read_text('utf-8'))['run_id'],result.run_id)
            self.assertIsNone(pipeline.backup_run_batch(result.manifest_path.parent,Path(tmp)/'drive'))
            archive.write_bytes(b'bad')
            with self.assertRaises(ValueError):pipeline.restore_run_batch(archive,Path(tmp)/'bad',expected_sha256=receipt['sha256'])
            self.assertFalse((Path(tmp)/'bad').exists())

    def test_backup_rejects_incomplete_publication_hash_inventory(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            result=self.execute(tmp);root=result.manifest_path.parent
            manifest=json.loads(result.manifest_path.read_text('utf-8'));record=manifest['publications'][0]
            record['output_sha256']={k:v for k,v in record['output_sha256'].items() if k.startswith('audit/')}
            result.manifest_path.write_text(json.dumps(manifest),'utf-8')
            checkpoint=next((root/'checkpoints').glob('*.json'));cp=json.loads(checkpoint.read_text('utf-8'));cp['output_sha256']=record['output_sha256'];checkpoint.write_text(json.dumps(cp),'utf-8')
            with self.assertRaises(ValueError):pipeline.backup_run_batch(root,Path(tmp)/'drive')

    def test_backup_preserves_failed_audits_profiles_and_full_manifest(self):
        import zipfile
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            with patch('src.parsing.pipeline.write_publication',side_effect=OSError('disk full')):
                result=self.execute(tmp)
            manifest=json.loads(result.manifest_path.read_text('utf-8'))
            record=manifest['publications'][0]
            self.assertIsNone(record['working_path'])
            archive=pipeline.backup_run_batch(result.manifest_path.parent,Path(tmp)/'drive')
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(json.loads(bundle.read('run_manifest.json')),manifest)
                self.assertIn(record['audit_path'],bundle.namelist())
                self.assertTrue(any(p.startswith('profile/') for p in bundle.namelist()))
                self.assertIn(b'disk full',bundle.read(record['audit_path']))
            receipt=json.loads(Path(str(archive)+'.receipt.json').read_text('utf-8'))
            self.assertIn('run_manifest.json',receipt['files'])
            restored=pipeline.restore_run_batch(archive,Path(tmp)/'restored',expected_sha256=receipt['sha256'])
            self.assertEqual(json.loads((restored/'run_manifest.json').read_text('utf-8')),manifest)

    def test_failed_only_in_progress_batch_keeps_its_evidence(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            with patch('src.parsing.pipeline.write_publication',side_effect=OSError('disk full')):
                result=self.execute(tmp)
            manifest=json.loads(result.manifest_path.read_text('utf-8'));manifest['status']='in_progress'
            result.manifest_path.write_text(json.dumps(manifest),'utf-8')
            archive=pipeline.backup_run_batch(result.manifest_path.parent,Path(tmp)/'drive')
            self.assertIsNotNone(archive)

    def test_metadata_update_does_not_rezip_unchanged_audit_and_profile(self):
        import zipfile
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            result=self.execute(tmp);root=result.manifest_path.parent
            first=pipeline.backup_run_batch(root,Path(tmp)/'drive')
            (root/'timing.json').write_text('{"wall_seconds":123}','utf-8')
            second=pipeline.backup_run_batch(root,Path(tmp)/'drive')
            self.assertIsNotNone(second)
            with zipfile.ZipFile(second) as bundle:
                self.assertIn('run_manifest.json',bundle.namelist())
                self.assertIn('timing.json',bundle.namelist())
                self.assertFalse(any(p.startswith(('audit/','profile/')) for p in bundle.namelist()))

    def test_interrupted_run_attempts_backup_of_failed_manifest_and_reason(self):
        import zipfile
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            p=make_publication_input()
            with patch('src.parsing.inputs.load_publications',return_value=[p]),patch('src.parsing.pipeline.process_publication',side_effect=KeyboardInterrupt('manual stop')):
                with self.assertRaises(KeyboardInterrupt):
                    pipeline.run_with_backup(Path(tmp)/'raw',Path(tmp)/'out',ParseConfig(code_revision='test'),Path(tmp)/'drive',batch_size=1)
            archives=list((Path(tmp)/'drive').glob('*/*.zip'))
            self.assertEqual(len(archives),1)
            with zipfile.ZipFile(archives[0]) as bundle:
                self.assertEqual(json.loads(bundle.read('run_manifest.json'))['status'],'failed')
                self.assertIn(b'manual stop',bundle.read('run_errors.jsonl'))

    def test_backup_overlaps_next_publication_and_freezes_batch_metadata(self):
        import zipfile
        from src.parsing.continuation import write_queue

        first = make_publication_input()
        second_id = '2606.99999'
        second = replace(first, arxiv_id=second_id,
                         versions=[replace(version, arxiv_id=second_id) for version in first.versions])
        first_upload_started, second_checkpoint_written = Event(), Event()
        original_backup = pipeline.backup_run_batch

        def parse(publication, config):
            parsed = make_expected_publication()
            if publication.arxiv_id == second_id:
                self.assertTrue(first_upload_started.wait(timeout=5))
                parsed.arxiv_id = second_id
                for rows in (parsed.elements, parsed.hierarchy, parsed.bibtex, parsed.occurrences,
                             parsed.bib_occurrences, parsed.diagnostics, parsed.identity_decisions, parsed.conflicts):
                    for row in rows:
                        row.arxiv_id = second_id
                for occurrence in parsed.bib_occurrences:
                    if occurrence.entry is not None:
                        occurrence.entry.arxiv_id = second_id
            return parsed

        def record_queue(root, queue):
            write_queue(root, queue)
            if queue['publications'][1]['attempts'] == 1:
                second_checkpoint_written.set()

        def upload(root, drive, **kwargs):
            if kwargs['arxiv_ids'] == [first.arxiv_id]:
                first_upload_started.set()
                self.assertTrue(second_checkpoint_written.wait(timeout=5))
            return original_backup(root, drive, **kwargs)

        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root = Path(tmp)
            with patch('src.parsing.inputs.load_publications', return_value=[first, second]), \
                 patch('src.parsing.pipeline.process_publication', side_effect=parse), \
                 patch('src.parsing.continuation.write_queue', side_effect=record_queue), \
                 patch('src.parsing.pipeline.backup_run_batch', side_effect=upload):
                result = pipeline.run_with_backup(root/'raw', root/'out', ParseConfig(code_revision='test'),
                                                  root/'drive', batch_size=1, max_publications=2)

            receipts = [json.loads(path.read_text('utf-8')) for path in (root/'drive'/result.run_id).glob('*.receipt.json')]
            batches = sorted(receipts, key=lambda receipt: receipt['batch_number'])
            self.assertEqual([receipt['arxiv_ids'] for receipt in batches], [[first.arxiv_id], [second_id], []])
            with zipfile.ZipFile(root/'drive'/result.run_id/batches[0]['archive']) as bundle:
                manifest = json.loads(bundle.read('run_manifest.json'))
                queue = json.loads(bundle.read('queue.json'))
                self.assertEqual([row['arxiv_id'] for row in manifest['publications']], [first.arxiv_id])
                self.assertEqual(queue['publications'][1]['attempts'], 0)
                self.assertNotIn('audit/'+pipeline._paper_key(second_id)+'.jsonl', bundle.namelist())

    def test_backup_failure_does_not_replace_original_interrupt(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            with patch('src.parsing.inputs.load_publications',return_value=[make_publication_input()]),patch('src.parsing.pipeline.process_publication',side_effect=KeyboardInterrupt('original stop')),patch('src.parsing.pipeline.backup_run_batch',side_effect=KeyError('archive')):
                with self.assertRaisesRegex(KeyboardInterrupt,'original stop'):
                    pipeline.run_with_backup(Path(tmp)/'raw',Path(tmp)/'out',ParseConfig(code_revision='test'),Path(tmp)/'drive',batch_size=1)

    def test_metadata_reversion_still_publishes_current_inventory(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            result=self.execute(tmp);root=result.manifest_path.parent;drive=Path(tmp)/'drive'
            first=pipeline.backup_run_batch(root,drive)
            original=(root/'timing.json').read_bytes()
            (root/'timing.json').write_text('{"wall_seconds":123}','utf-8')
            second=pipeline.backup_run_batch(root,drive)
            (root/'timing.json').write_bytes(original)
            third=pipeline.backup_run_batch(root,drive)
            self.assertIsNotNone(third)
            receipts=[json.loads(Path(str(p)+'.receipt.json').read_text('utf-8')) for p in (first,second,third)]
            self.assertEqual([r['batch_number'] for r in receipts],[1,2,3])
            self.assertEqual(receipts[0]['metadata_files'],receipts[2]['metadata_files'])
            self.assertNotEqual(receipts[1]['metadata_files'],receipts[2]['metadata_files'])

if __name__=='__main__':unittest.main()
