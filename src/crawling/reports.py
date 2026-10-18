"""Label session roles and aggregate durable receipts without double counting.

The Book should call aggregation at build time; final measurement and partial
prefix measurements stay distinct. Uses csv/json/zipfile/hashlib stdlib APIs.
Full attribution and accounting policy: KE_HOACH_MILESTONE_1.md sections 10/13.
"""
import csv
import io
import json
from pathlib import Path
import zipfile

from .backup import _sha256
from .sessions import _read, _receipt, completed_sources, scope_ids, successful_ids, locate_receipt


def _csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def session_rows(manifest, plan, invalid_ids=()):
    complete = successful_ids(manifest, invalid_ids)
    new, retry = set(plan.get('new_ids', [])), set(plan.get('retry_ids', []))
    return [dict(run_id=manifest['run_id'], arxiv_id=i,
                 role='retry' if i in retry else 'new' if i in new else 'unclassified',
                 complete=i in complete) for i in scope_ids(manifest['scope'])]


def write_session_breakdown(report_dir: Path, plan: dict, manifest: dict, invalid_ids=()) -> dict:
    rows = session_rows(manifest, plan, invalid_ids)
    _csv(report_dir/'attempts.csv', rows, ['run_id','arxiv_id','role','complete'])
    counts = {f'{role}_{key}': sum(r['role']==role and (key=='requested' or r['complete']) for r in rows)
              for role in ('new','retry','unclassified') for key in ('requested','complete')}
    (report_dir/'session_counts.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')
    (report_dir/'session_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return counts


def aggregate_reports(state_paths: list[Path], output_dir: Path) -> dict:
    """Build one row per completed base ID and one per run/ID attempt.

    Accept state paths copied with their backup folder trees, or mounted Drives.
    A state belongs to one member. Missing/moved archives fail rather than lower
    totals silently. Checkpoints and final snapshots from one run are deduped;
    retry time is retained, and interrupted prefixes are explicitly incomplete.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    attempts, runs, papers, pending, registered_new = {}, {}, {}, set(), set()
    receipts, verified_corpora = {}, set()
    owners = {}
    for state_path in state_paths:
        state_path = Path(state_path)
        raw = json.loads(state_path.read_text(encoding='utf-8'))
        state = _read(state_path, raw['member'])
        chosen = completed_sources(state)
        for plan in state.get('plans', []):
            registered_new.update(plan['new_ids'])
        pending.update(set(state['pending_ids']) - chosen.keys())
        for entry in state['backups']:
            receipt_path = entry['receipt_path']
            receipt_file = locate_receipt(receipt_path,state_path.resolve().parent.parent)
            if receipt_path not in receipts:
                receipt = _receipt(receipt_file, state_path.resolve().parent.parent)
                archive = receipt_file.parent/'report.zip'
                expected = receipt['archives']['report']
                if archive.stat().st_size != expected['bytes'] or _sha256(archive) != expected['sha256']:
                    raise OSError('Aggregate input report failed its backup hash.')
                with zipfile.ZipFile(archive) as z:
                    manifest = json.loads(z.read('manifest.json'))
                    plan = json.loads(z.read('session_plan.json')) if 'session_plan.json' in z.namelist() else {}
                    summary = json.loads(z.read('run_summary.json'))
                    invalid = set()
                    if 'integrity_audit.csv' in z.namelist():
                        invalid = {r['arxiv_id'] for r in csv.DictReader(io.StringIO(z.read('integrity_audit.csv').decode('utf-8')))
                                   if r['valid'].lower() not in ('true','1')}
                receipts[receipt_path] = manifest, plan, summary, invalid
            manifest, plan, summary, invalid = receipts[receipt_path]
            priority = {'checkpoint':1,'final_report':2,'final':3}.get(entry.get('kind','final'),3)
            for row in session_rows(manifest, plan, invalid):
                key = state['member'], row['run_id'], row['arxiv_id']
                if key not in attempts or priority > attempts[key][0]:
                    attempts[key] = priority, dict(member=state['member'], **row)
            if 'benchmark' in summary:
                b = summary['benchmark']
                key = state['member'], manifest['run_id']
                old = runs.get(key)
                if old is None or priority > old[0] or (priority==old[0] and b['wall_seconds']>old[1]['wall_seconds']):
                    runs[key] = priority, dict(member=state['member'], run_id=manifest['run_id'],
                        wall_seconds=b['wall_seconds'], ram_peak_bytes=b.get('ram_peak_bytes'),
                        disk_peak_bytes=b.get('disk_peak_bytes'),
                        complete_measurement=entry.get('kind','final')!='checkpoint',
                        cache_mode=b.get('cache_mode'), environment=b.get('environment'))
            for identifier in entry['completed_ids']:
                if chosen.get(identifier) != receipt_path:
                    continue
                if identifier in owners and owners[identifier] != state['member']:
                    raise ValueError('Assignments overlap between members; cannot count this ID twice.')
                if receipt_path not in verified_corpora:
                    receipt = _receipt(receipt_file, state_path.resolve().parent.parent)
                    archive = receipt_file.parent/'corpus.zip'
                    expected = receipt['archives']['corpus']
                    if archive.stat().st_size != expected['bytes'] or _sha256(archive) != expected['sha256']:
                        raise OSError('Chosen corpus ZIP failed its backup hash.')
                    verified_corpora.add(receipt_path)
                owners[identifier] = state['member']
                metadata = manifest['papers'][identifier]['record']['metadata']
                papers[identifier] = dict(member=state['member'], arxiv_id=identifier,
                    title=metadata['title'], submission_date=metadata['submission_date'],
                    corpus_zip=str(receipt_file.parent/'corpus.zip'), receipt_path=str(receipt_file))
    rows = [v[1] for v in attempts.values()]
    result = dict(unique_complete_papers=len(papers), unique_new_ids=len(registered_new | {r['arxiv_id'] for r in rows if r['role']=='new'}),
                  retry_attempts=sum(r['role']=='retry' for r in rows), distinct_runs=len(runs), pending_ids=sorted(pending))
    _csv(output/'papers_unique.csv', list(papers.values()), ['member','arxiv_id','title','submission_date','corpus_zip','receipt_path'])
    _csv(output/'attempts.csv', rows, ['member','run_id','arxiv_id','role','complete'])
    _csv(output/'benchmark_runs.csv', [v[1] for v in runs.values()],
         ['member','run_id','wall_seconds','ram_peak_bytes','disk_peak_bytes','complete_measurement','cache_mode','environment'])
    (output/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
