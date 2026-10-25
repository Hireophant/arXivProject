"""Offline HTTP, durable retry migration and bounded notebook presentation checks."""
from copy import deepcopy
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import requests
from crawling.backup import backup_run
from crawling.discover import OaiClient
from crawling.failures import classify_failure, failure_rows, quarantined_ids
from crawling.metrics import export_report_data
from crawling.pipeline import run_pipeline, load_manifest, initialize_manifest, save_manifest
from crawling.presentation import (format_bytes, format_duration, preview_table,
                                   summary_dashboard, verified_drive_bytes)
from crawling.references import _request_s2
from crawling.sessions import (prepare_session, finish_session, progress, plan_session,
                               migrate_permanent_failures, seed_pending)
from test_reference_dates import raw, Response, POLICY, PAPER, SCOPE


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / 'corpus'
        self.drive = self.root / 'drive'
        self.state = self.drive / 'retry-state/member-1.json'
        self.calls = []
        self.source_status = 200
        self.source_body = gzip.compress(b'\\documentclass{article}\n\\begin{document}x\\end{document}')
        self.s2_status = 200

    def network(self, url, **kwargs):
        self.calls.append(url)
        if 'oaipmh' in url:
            return Response(raw(PAPER, versions=2))
        if 'export.arxiv' in url:
            r = Response(self.source_body)
            r.status_code = self.source_status
            return r
        if 'semanticscholar' in url:
            r = Response(payload={'offset': 0, 'data': []})
            r.status_code = self.s2_status
            def check():
                if r.status_code != 200:
                    raise requests.HTTPError(f'{r.status_code} URL https://api.semanticscholar.org/long', response=r)
            r.raise_for_status = check
            return r
        raise AssertionError(url)

    def collect(self, root=None, **kwargs):
        with patch('requests.get', side_effect=self.network), patch('time.sleep'):
            result = run_pipeline(deepcopy(SCOPE), root or self.corpus, policy=POLICY, **kwargs)
        return result, load_manifest((root or self.corpus) / 'manifest.json')

    def backup(self, result, manifest):
        report = self.root / ('report-' + manifest['run_id'])
        export_report_data(manifest, result['benchmark'], report)
        (report / 'manifest.json').write_text(json.dumps(manifest))
        (report / 'run_summary.json').write_text(json.dumps(result))
        (report / 'integrity_audit.csv').write_text('arxiv_id,artifact,valid,detail\n' + PAPER + ',test,True,checked\n')
        return backup_run(self.corpus, report, self.drive, run_id=manifest['run_id'], work_dir=self.root / 'staging')

    def test_source_404_and_s2_429_only_retries_s2_then_quarantines(self):
        plan = prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        self.source_status, self.s2_status = 404, 429
        result, manifest = self.collect()
        self.assertEqual(quarantined_ids(manifest), set())
        saved = finish_session(self.state, plan, manifest, self.backup(result, manifest))
        self.assertEqual(saved['pending_ids'], [PAPER])
        plan = plan_session(self.state, member='Danh', assignment_scope=SCOPE, new_limit=1)
        next_root = self.root / 'next'
        self.assertGreater(seed_pending(plan, next_root), 0)
        save_manifest(initialize_manifest(SCOPE, run_id='restored'), next_root / 'manifest.json')
        self.calls.clear()
        self.s2_status = 200
        result, manifest = self.collect(next_root)
        self.assertEqual(sum('export.arxiv' in u for u in self.calls), 0)
        self.assertEqual(sum('semanticscholar' in u for u in self.calls), 1)
        self.assertEqual(quarantined_ids(manifest), {PAPER})
        # Back up the actual new root for queue evidence.
        self.corpus = next_root
        saved = finish_session(self.state, plan, manifest, self.backup(result, manifest))
        self.assertEqual(saved['pending_ids'], [])
        self.assertIn(PAPER, saved['permanent_failures'])
        info = progress(self.state, member='Danh', assignment_scope=SCOPE)
        self.assertEqual((info['completed'], info['quarantined'], info['pending'], info['unseen']), (0, 1, 0, 0))
        self.assertIsNone(plan_session(self.state, member='Danh', assignment_scope=SCOPE, new_limit=1)['scope'])

    def test_resume_404_reuses_decision_and_explicit_override_rechecks(self):
        self.s2_status = 404
        _, manifest = self.collect()
        self.assertIn(PAPER, quarantined_ids(manifest))
        for iteration in range(2):
            self.calls.clear()
            result, manifest = self.collect()
            self.assertFalse(any('semanticscholar' in u for u in self.calls))
            self.assertEqual(manifest['papers'][PAPER]['references']['attempts'], 0)
            self.assertNotEqual(result['status'], 'success')
        self.s2_status = 200
        self.calls.clear()
        result, manifest = self.collect(retry_permanent=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(sum('semanticscholar' in u for u in self.calls), 1)

    def test_interrupted_resume_keeps_permanent_decisions(self):
        self.s2_status = 404
        self.collect()
        with patch.object(OaiClient, 'discover', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                self.collect()
        self.calls.clear()
        self.collect()
        self.assertFalse(any('semanticscholar' in u for u in self.calls))

    def test_old_discovery_record_does_not_inflate_new_discovery_count(self):
        self.collect()
        missing = dict(status='partial', scope=deepcopy(SCOPE), requested_count=1, scope_complete=True,
                       papers=[], issues=[dict(arxiv_id=PAPER, status='not_found', error='OAI id does not exist')],
                       elapsed_seconds=0., metadata_source='oai-pmh/arXivRaw')
        with patch.object(OaiClient, 'discover', return_value=missing):
            result, manifest = self.collect()
        self.assertEqual(result['summary']['papers_discovered'], 0)
        self.assertEqual(quarantined_ids(manifest), {PAPER})

    def test_verified_no_tex_is_reused_while_s2_is_retried(self):
        self.source_body = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nstartxref\n0\n%%EOF\n'
        self.s2_status = 429
        _, manifest = self.collect()
        self.assertEqual({d['status'] for d in manifest['papers'][PAPER]['downloads'].values()}, {'no_tex'})
        self.calls.clear()
        self.s2_status = 200
        result, manifest = self.collect()
        self.assertFalse(any('export.arxiv' in u for u in self.calls))
        self.assertEqual(result['summary']['versions_no_tex'], 2)
        self.assertEqual(result['summary']['full_source_papers'], 0)
        self.assertEqual(result['status'], 'success')

    def test_invalid_scope_stops_before_network(self):
        with patch('requests.get') as network:
            with self.assertRaises(ValueError):
                run_pipeline(dict(SCOPE, ids=['../../bad']), self.corpus, policy=POLICY)
        network.assert_not_called()

    def test_discovery_not_found_is_not_requested_again(self):
        with patch.object(OaiClient, '_request', side_effect=LookupError('OAI id does not exist')) as request:
            self.collect()
            result, manifest = self.collect()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(manifest['discovery']['requested_count'], 1)
        self.assertEqual(quarantined_ids(manifest), {PAPER})
        self.assertEqual(result['status'], 'partial')

    def test_oai_endpoint_404_does_not_quarantine_paper_absence(self):
        with patch.object(OaiClient, '_request', side_effect=RuntimeError('OAI endpoint HTTP 404; paper absence is unverified.')) as request:
            self.collect()
            _, manifest = self.collect()
        self.assertEqual(request.call_count, 2)
        self.assertEqual(quarantined_ids(manifest), set())

    def test_s2_http_408_retries_within_request_policy(self):
        self.s2_status = 408
        def network(*args, **kwargs):
            response = self.network(*args, **kwargs)
            self.s2_status = 200
            return response
        with patch('requests.get', side_effect=network), patch('time.sleep'):
            _, attempts = _request_s2(PAPER, offset=0, policy=dict(POLICY, max_attempts=3), _with_attempts=True)
        self.assertEqual(attempts, 2)

    def test_old_queue_migrates_from_verified_backup_without_relabeling_success(self):
        plan = prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        self.s2_status = 404
        result, manifest = self.collect()
        backup = self.backup(result, manifest)
        # Recreate the pre-quarantine queue format.
        old = json.loads(self.state.read_text())
        old.pop('permanent_failures', None)
        old['sources'] = {PAPER: backup['receipt_path']}
        old['backups'] = [dict(run_id=manifest['run_id'], requested_ids=[PAPER], completed_ids=[],
                              receipt_path=backup['receipt_path'])]
        self.state.write_text(json.dumps(old))
        self.assertEqual(migrate_permanent_failures(self.state, member='Danh'), 1)
        self.assertEqual(migrate_permanent_failures(self.state, member='Danh'), 0)
        info = progress(self.state, member='Danh', assignment_scope=SCOPE)
        self.assertEqual(info['completed'], 0)
        self.assertEqual(info['quarantined'], 1)

    def test_corrupt_legacy_backup_does_not_drop_pending(self):
        prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        self.s2_status = 404
        result, manifest = self.collect()
        backup = self.backup(result, manifest)
        old = json.loads(self.state.read_text())
        old['sources'] = {PAPER: backup['receipt_path']}
        self.state.write_text(json.dumps(old))
        (Path(backup['receipt_path']).parent / 'report.zip').write_bytes(b'broken')
        before = self.state.read_bytes()
        with self.assertRaises(OSError):
            migrate_permanent_failures(self.state, member='Danh')
        self.assertEqual(self.state.read_bytes(), before)

    def test_integrity_failure_stays_pending_despite_upstream_404(self):
        plan = prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        self.s2_status = 404
        result, manifest = self.collect()
        saved = finish_session(self.state, plan, manifest, self.backup(result, manifest), invalid_ids={PAPER})
        self.assertEqual(saved['pending_ids'], [PAPER])
        self.assertEqual(saved['permanent_failures'], {})

    def test_drive_dashboard_measures_committed_files(self):
        plan = prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        result, manifest = self.collect()
        backup = self.backup(result, manifest)
        finish_session(self.state, plan, manifest, backup)
        size = verified_drive_bytes(self.state, 'Danh', result['run_id'])
        folder = Path(backup['receipt_path']).parent
        self.assertEqual(size, sum(p.stat().st_size for p in folder.iterdir() if p.is_file()))
        html = summary_dashboard(manifest, result, drive_bytes=size)
        self.assertIn('1/1 (100.0%)', html)
        self.assertIn(format_bytes(size), html)
        self.assertIn('2', html)
        self.assertIsNone(verified_drive_bytes(self.state, 'Danh', 'unrelated'))

    def test_no_tex_is_resolved_and_never_counts_as_tex_success(self):
        result, manifest = self.collect()
        for d in manifest['papers'][PAPER]['downloads'].values():
            d.update(status='no_tex', source_bytes_after=0, file_count=0, error='Verified pdf source without TeX.')
        self.assertEqual(quarantined_ids(manifest), set())
        rows = failure_rows(manifest)
        self.assertTrue(all(r['code'] == 'no_tex' for r in rows))
        self.assertIn('1/1 (100.0%)', summary_dashboard(manifest, result))
        manifest['papers'][PAPER]['references'].update(status='failed', error='Semantic Scholar HTTP 429.')
        self.assertEqual(quarantined_ids(manifest), set())

    def test_drive_source_count_deduplicates_backups_and_rejects_tampering(self):
        from crawling.presentation import verified_drive_source_files
        plan = prepare_session(self.state, member='Danh', scope=deepcopy(SCOPE))
        result, manifest = self.collect()
        first = self.backup(result, manifest)
        finish_session(self.state, plan, manifest, first)
        second = self.backup(result, manifest)
        self.assertEqual(verified_drive_source_files(self.state, 'Danh', result['run_id'],
                         extra_receipt=second['receipt_path']), 2)
        self.assertIsNone(verified_drive_source_files(self.state, 'Danh', 'unrelated'))
        archive = Path(second['receipt_path']).parent / 'corpus.zip'
        body = archive.read_bytes()
        archive.write_bytes(bytes([body[0] ^ 1]) + body[1:])
        with self.assertRaises(OSError):
            verified_drive_source_files(None, 'Danh', result['run_id'], second['receipt_path'])

    def test_dashboard_separates_full_session_time_and_verified_drive_count(self):
        result, manifest = self.collect()
        html = summary_dashboard(manifest, result, session_seconds=125,
                                 session_finished=True, drive_source_files=2)
        self.assertIn('02:05', html)
        self.assertIn('Tổng thời gian phiên đến backup Drive', html)
        self.assertIn('File .tex / .bib đã xác minh trên Drive', html)
        unknown = summary_dashboard(manifest, result)
        self.assertIn('Chưa xác minh', unknown)

    def test_verified_no_tex_backup_reports_zero_drive_source_files(self):
        from crawling.presentation import verified_drive_source_files
        self.source_body = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nstartxref\n0\n%%EOF\n'
        result, manifest = self.collect()
        backup = self.backup(result, manifest)
        self.assertEqual(verified_drive_source_files(None, 'Danh', result['run_id'],
                                                    backup['receipt_path']), 0)


class PresentationTests(unittest.TestCase):
    def test_grouped_errors_show_and_export_all_groups_despite_pandas_limit(self):
        import pandas as pd
        from crawling.presentation import export_issue_groups, preview_style
        rows = pd.DataFrame([dict(category='review', reason=f'group-{i:02d}',
                                  arxiv_id=PAPER, task=f'source v{i}') for i in range(16)])
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'issue_groups.csv'
            groups = export_issue_groups(rows, target)
            self.assertEqual(len(pd.read_csv(target)), 16)
            with pd.option_context('display.max_rows', 5):
                html = preview_style(groups, limit=len(groups)).to_html()
            for i in range(16):
                self.assertIn(f'group-{i:02d}', html)

    def test_classification_legacy_urls_and_unknown_errors(self):
        for status, error, category in [('failed', 'Source HTTP 404.', 'permanent'),
                ('not_found', '404 https://api.semanticscholar.org/long', 'permanent'),
                ('failed', 'Semantic Scholar HTTP 429: URL', 'transient'),
                ('failed', 'Source HTTP 503.', 'transient'),
                ('failed', 'ReadTimeout', 'transient'),
                ('failed', 'Unsafe archive path.', 'review'),
                ('failed', 'Semantic Scholar HTTP 403.', 'review')]:
            with self.subTest(error=error):
                self.assertEqual(classify_failure('source', status, error)[0], category)
        self.assertNotIn('PDF', classify_failure('source', 'failed', 'Source HTTP 404.')[2])

    def test_units_and_preview_bound_preserve_numeric_data(self):
        import pandas as pd
        self.assertEqual(format_bytes(541335552), '516.3 MiB')
        self.assertEqual(format_bytes(1024**3), '1.0 GiB')
        self.assertEqual(format_bytes(None), '—')
        self.assertEqual(format_duration(125), '02:05')
        self.assertEqual(format_duration(.25), '0.25 s')
        frame = pd.DataFrame({'source_bytes_after': [541335552] * 200,
                              'elapsed_seconds': [125] * 200,
                              'error': ['HTTP 429 https://api.semanticscholar.org/' + 'x' * 200] * 200})
        preview = preview_table(frame)
        self.assertEqual(len(preview), 5)
        self.assertEqual(frame.iloc[0, 0], 541335552)
        self.assertEqual(preview.iloc[0, 0], '516.3 MiB')
        self.assertNotIn('https://', preview.to_html())

    def test_notebook_is_clean_and_every_code_cell_compiles(self):
        import nbformat
        path = Path(__file__).resolve().parents[1] / 'src/notebooks/milestone1.ipynb'
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type == 'code':
                compile(cell.source, f'cell-{cell.id}', 'exec')
                self.assertEqual(cell.outputs, [])
                self.assertIsNone(cell.execution_count)


if __name__ == '__main__':
    unittest.main()
