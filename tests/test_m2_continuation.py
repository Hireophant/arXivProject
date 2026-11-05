"""Durable per-dataset visits; service/fault doubles do not replace integration tests."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from m2_support.fixtures import make_publication_input, make_expected_publication
from src.parsing.contracts import ParseConfig
from src.parsing import pipeline

SCRATCH=Path(__file__).resolve().parents[1]/'data/milestone2-dev/continuation'


class ContinuationTests(unittest.TestCase):
    def visit(self,root,*,fail=False,config=None,resume=False):
        with patch('src.parsing.inputs.load_publications',return_value=[make_publication_input()]), \
             patch('src.parsing.pipeline.process_publication',side_effect=RuntimeError('broken source') if fail else None,
                   return_value=make_expected_publication()) as processor:
            result=pipeline.run_with_backup(root/'raw',root/'out',config or ParseConfig(code_revision='test'),
                                            root/'drive',batch_size=1,max_publications=1,resume=resume)
        return result,processor.call_count

    def test_pending_four_visits_then_deferred_and_deduplicated(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root=Path(tmp)
            for attempt in range(1,5):
                result,calls=self.visit(root,fail=True,resume=True)
                self.assertEqual(calls,1)
                queue=json.loads((result.manifest_path.parent/'queue.json').read_text('utf-8'))
                row,=queue['publications']
                self.assertEqual(row['attempts'],attempt)
                self.assertEqual(row['status'],'deferred' if attempt==4 else 'pending')
            result,calls=self.visit(root)
            self.assertEqual(calls,0)
            self.assertEqual(result.processed_publications,0)
            later=result.manifest_path.parent/'review_later.csv'
            self.assertIn(make_publication_input().arxiv_id,later.read_text('utf-8'))
            self.assertTrue(any('review_later.csv' in json.loads(p.read_text('utf-8'))['files']
                                for p in (root/'drive').glob('*/*.receipt.json')))

    def test_success_skips_next_cold_visit_and_signature_change_retries(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root=Path(tmp);first,calls=self.visit(root)
            self.assertEqual(calls,1)
            manifest=json.loads(first.manifest_path.read_text('utf-8'))
            self.assertEqual(manifest['publications'][0]['expected_versions'],[1,2])
            second,calls=self.visit(root)
            self.assertEqual(calls,0)
            third,calls=self.visit(root,config=ParseConfig(code_revision='new-code'))
            self.assertEqual(calls,1)
            self.assertEqual(json.loads((third.manifest_path.parent/'queue.json').read_text('utf-8'))['publications'][0]['attempts'],1)

    def test_corrupt_backup_stops_instead_of_skipping_or_counting(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root=Path(tmp);self.visit(root)
            archive=next((root/'drive').glob('*/*.zip'));archive.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'checksum'):
                self.visit(root)

    def test_failed_backup_does_not_consume_durable_attempt(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root=Path(tmp)
            with patch('src.parsing.pipeline.backup_run_batch',side_effect=OSError('Drive unavailable')):
                result,_=self.visit(root,fail=True)
            self.assertEqual(result.status,'partial')
            next_result,calls=self.visit(root,fail=True)
            self.assertEqual(calls,1)
            row,=json.loads((next_result.manifest_path.parent/'queue.json').read_text('utf-8'))['publications']
            self.assertEqual(row['attempts'],1)

    def test_transient_background_backup_failure_is_retried_before_return(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root = Path(tmp)
            upload = pipeline.backup_run_batch

            def fail_in_background(run_root, drive, **kwargs):
                if kwargs.get('_snapshot') is not None:
                    raise OSError('Transient upload failure')
                return upload(run_root, drive, **kwargs)

            with patch('src.parsing.pipeline.backup_run_batch', side_effect=fail_in_background):
                result, _ = self.visit(root)
            self.assertEqual(result.status, 'partial')
            self.assertIn('OUTPUT_BACKUP_FAILED', [issue.code for issue in result.diagnostics])
            receipt, = (root/'drive'/result.run_id).glob('*.receipt.json')
            self.assertEqual(json.loads(receipt.read_text('utf-8'))['arxiv_ids'], [make_publication_input().arxiv_id])
            _, calls = self.visit(root)
            self.assertEqual(calls, 0)

    def test_pending_can_recover_and_stop_retrying(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            root=Path(tmp);self.visit(root,fail=True)
            result,calls=self.visit(root)
            self.assertEqual(calls,1)
            row,=json.loads((result.manifest_path.parent/'queue.json').read_text('utf-8'))['publications']
            self.assertEqual((row['attempts'],row['status']),(2,'done'))
            _,calls=self.visit(root)
            self.assertEqual(calls,0)

    def test_queue_prioritizes_pending_keeps_all_versions_and_excludes_deferred(self):
        from src.parsing.continuation import build_queue
        p=make_publication_input()
        publications=[replace(p,arxiv_id=str(i)) for i in range(4)]
        signatures={str(i):str(i)*64 for i in range(4)}
        history={('1',signatures['1']):{'attempts':1,'status':'pending'},
                 ('2',signatures['2']):{'attempts':4,'status':'deferred'},
                 ('3',signatures['3']):{'attempts':1,'status':'done'}}
        selected,queue=build_queue(publications,signatures,history,1)
        self.assertEqual([p.arxiv_id for p in selected],['1'])
        self.assertEqual([v.version for v in selected[0].versions],[1,2])
        self.assertEqual(queue['remaining_eligible'],2)
        for limit in (0,-1,True,1.5):
            with self.assertRaises(ValueError):build_queue(publications,signatures,history,limit)


if __name__=='__main__':unittest.main()
