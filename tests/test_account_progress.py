"""Existing Drive queues must survive splitting a person's assignment."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from crawling.sessions import plan_session, progress, scope_ids


class AccountProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'retry-state/member-1.json'
        self.path.parent.mkdir()
        self.full = dict(mode='range', ids=[], start_id='2606.15734', end_id='2606.20733')
        self.part = dict(self.full, end_id='2606.17400')
        ids = scope_ids(self.full)
        self.state = dict(schema_version='1.0', member='Danh', assignment_ids=ids,
                          pending_ids=[ids[500], ids[2000]], sources={},
                          active_session=None, last_completed_session=None,
                          backups=[dict(requested_ids=ids[:500] + [ids[3000]],
                                        completed_ids=ids[:500] + [ids[3000]],
                                        receipt_path='old-backup/backup_receipt.json')])
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.state), encoding='utf-8')

    def options(self):
        return dict(member='Danh', assignment_scope=self.part, previous_assignment_scope=self.full)

    def test_keep_500_completions_and_pending_across_repeated_visits(self):
        before = self.path.read_bytes()
        info = progress(self.path, **self.options())
        self.assertEqual((info['total'], info['completed'], info['pending']), (1667, 500, 1))
        self.assertEqual(info['next_new_id'], '2606.16235')
        self.assertEqual(info['last_saved_id'], '2606.16233')
        self.assertEqual(self.path.read_bytes(), before)
        plan = plan_session(self.path, **self.options(), new_limit=5)
        self.assertEqual(plan['new_ids'], [f'2606.{n:05}' for n in range(16235, 16240)])
        self.assertEqual(plan['retry_ids'], ['2606.16234'])
        self.assertIn('2606.17734', plan['deferred_ids'])
        after = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(after['backups'], self.state['backups'])
        self.assertEqual(after['assignment_ids'], self.state['assignment_ids'])
        self.assertEqual(progress(self.path, **self.options())['completed'], 500)

    def test_v1_ledger_without_assignment_ids(self):
        self.state.pop('assignment_ids')
        self.save()
        plan_session(self.path, **self.options(), new_limit=5)
        self.assertEqual(progress(self.path, **self.options())['completed'], 500)

    def test_500_completed_without_pending_continues_at_501(self):
        self.state['pending_ids'] = []
        self.save()
        plan = plan_session(self.path, **self.options(), new_limit=5)
        self.assertEqual(plan['progress_before']['completed'], 500)
        self.assertEqual(plan['new_ids'][0], '2606.16234')

    def test_finished_segment_does_not_crawl_old_pending_outside_it(self):
        self.state['backups'][0]['requested_ids'] = scope_ids(self.part)
        self.state['backups'][0]['completed_ids'] = scope_ids(self.part)
        self.state['pending_ids'] = ['2606.17734']
        self.save()
        before = self.path.read_bytes()
        plan = plan_session(self.path, **self.options(), new_limit=5)
        self.assertIsNone(plan['scope'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_other_assignment_still_fails(self):
        with self.assertRaises(ValueError):
            progress(self.path, member='Danh', assignment_scope=self.part)
        self.state['assignment_ids'] = ['2606.00001']
        self.save()
        with self.assertRaises(ValueError):
            progress(self.path, **self.options())

    def test_wrong_member_and_outside_legacy_ids_still_fail(self):
        with self.assertRaises(ValueError):
            progress(self.path, member='Danh1', assignment_scope=self.part,
                     previous_assignment_scope=self.full)
        self.state['pending_ids'].append('2606.00001')
        self.save()
        with self.assertRaises(ValueError):
            progress(self.path, **self.options())

    def test_new_account_has_independent_queue(self):
        path = self.path.with_name('member-5.json')
        scope = dict(self.full, start_id='2606.17401', end_id='2606.19067')
        plan = plan_session(path, member='Danh1', assignment_scope=scope, new_limit=5)
        self.assertEqual(plan['new_ids'][0], '2606.17401')
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), self.state)


if __name__ == '__main__':
    unittest.main()
