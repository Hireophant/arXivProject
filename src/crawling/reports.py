"""Export per-session new/retry roles and counts for crawler backups.

Cross-session and group aggregation belongs to the separate report repository.
Full attribution and accounting policy: KE_HOACH_MILESTONE_1.md sections 10/13.
"""
import csv
import json
from pathlib import Path

from .sessions import scope_ids, successful_ids
from .failures import quarantined_ids


def _csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def session_rows(manifest, plan, invalid_ids=()):
    complete = successful_ids(manifest, invalid_ids)
    quarantine = quarantined_ids(manifest, invalid_ids)
    new, retry = set(plan.get('new_ids', [])), set(plan.get('retry_ids', []))
    return [dict(run_id=manifest['run_id'], arxiv_id=i,
                 role='retry' if i in retry else 'new' if i in new else 'unclassified',
                 complete=i in complete, quarantined=i in quarantine) for i in scope_ids(manifest['scope'])]


def write_session_breakdown(report_dir: Path, plan: dict, manifest: dict, invalid_ids=()) -> dict:
    rows = session_rows(manifest, plan, invalid_ids)
    _csv(report_dir/'attempts.csv', rows, ['run_id','arxiv_id','role','complete','quarantined'])
    counts = {f'{role}_{key}': sum(r['role']==role and (key=='requested' or r['complete']) for r in rows)
              for role in ('new','retry','unclassified') for key in ('requested','complete')}
    (report_dir/'session_counts.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')
    (report_dir/'session_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return counts
