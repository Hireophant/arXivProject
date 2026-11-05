"""Replay verified M2 backups into a per-signature visit queue (Danh).

Queue JSON is a report, never the authority for skipping input. Attempts require
durable audit/output evidence; metadata-only snapshots do not add attempts.
"""
from __future__ import annotations

import csv
import hashlib
import zipfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

from . import contracts as c
from .serialization import _hydrate, _loads

MAX_ATTEMPTS = 4


def read_history(backup_root: Path, snapshot_id: str) -> dict:
    """Verify immutable receipts/ZIPs once per visit; fail closed on corruption."""
    from .pipeline import _hash, _relative_file
    files, events = {}, {}
    for path in sorted(Path(backup_root).glob('*/batch-*.zip.receipt.json')):
        receipt = _loads(path.read_text('utf-8'))
        if receipt.get('kind') != 'm2-parsed-batch-1.0':
            raise ValueError(f'Unexpected M2 backup receipt: {path}')
        if receipt.get('snapshot_id') != snapshot_id:
            continue
        archive_name = receipt['archive']
        if Path(archive_name).name != archive_name or path.name != archive_name+'.receipt.json':
            raise ValueError('Invalid backup archive name')
        archive = _relative_file(path.parent, archive_name)
        if _hash(archive) != receipt['sha256']:
            raise ValueError(f'Backup checksum mismatch: {archive}')
        run_id = receipt['run_id']
        if run_id != path.parent.name:
            raise ValueError('Backup run directory mismatch')
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate backup ZIP members')
            for relative, expected in receipt['files'].items():
                with bundle.open(relative) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual != expected:
                    raise ValueError(f'Backup member checksum mismatch: {relative}')
                files.setdefault(run_id, set()).add((relative, actual))
            name = 'run_manifest.json' if 'run_manifest.json' in receipt['files'] else 'manifest.json'
            manifest = _hydrate(c.RunManifest, _loads(bundle.read(name).decode('utf-8')))
            if (manifest.run_id != run_id or manifest.snapshot_id != snapshot_id or
                    manifest.contract_version != c.CONTRACT_VERSION or manifest.schema_version != c.OUTPUT_SCHEMA_VERSION):
                raise ValueError('Backup manifest identity/schema mismatch')
            for record in manifest.publications:
                audit_sha = record.output_sha256.get(record.audit_path) or receipt.get('metadata_files', {}).get(record.audit_path)
                if audit_sha is None:
                    continue  # Older failed-only backups did not preserve audit evidence.
                key = (run_id, record.arxiv_id, record.checkpoint_signature)
                event = (record, audit_sha)
                if key in events and events[key] != event:
                    raise ValueError('Conflicting publication attempts in one run')
                events[key] = event
    history = {}
    for (run_id, arxiv_id, signature), (record, audit_sha) in events.items():
        required = {(record.audit_path, audit_sha)} | set(record.output_sha256.items())
        if not required <= files.get(run_id, set()):
            continue  # An uncommitted or incomplete attempt remains eligible.
        row = history.setdefault((arxiv_id, signature), {'attempts': 0, 'status': 'pending', 'evidence': []})
        row['attempts'] += 1
        row['evidence'].append({'run_id': run_id, 'audit_path': record.audit_path,
                                'audit_sha256': audit_sha, 'export_ready': record.export_ready})
        if record.export_ready and record.working_path:
            row['status'] = 'done'
    for row in history.values():
        if row['status'] != 'done' and row['attempts'] >= MAX_ATTEMPTS:
            row['status'] = 'deferred'
    return history


def build_queue(publications: list, signatures: dict, history: dict, limit: int) -> tuple[list, dict]:
    """Pending first, then unseen; one attempt per publication per visit."""
    if type(limit) is not int or limit < 1:
        raise ValueError('max_publications must be a positive integer')
    rows = []
    for publication in sorted(publications, key=lambda p: p.arxiv_id):
        row = deepcopy(history.get((publication.arxiv_id, signatures[publication.arxiv_id]),
                                   {'attempts': 0, 'status': 'unseen', 'evidence': []}))
        row.update(arxiv_id=publication.arxiv_id, signature=signatures[publication.arxiv_id],
                   expected_versions=[v.version for v in publication.versions])
        rows.append(row)
    eligible = sorted((r for r in rows if r['status'] in ('pending', 'unseen')),
                      key=lambda r: (r['status'] != 'pending', r['arxiv_id']))
    selected_ids = [r['arxiv_id'] for r in eligible[:limit]]
    by_id = {p.arxiv_id: p for p in publications}
    return [by_id[k] for k in selected_ids], {
        'kind': 'm2-visit-queue-1.0', 'max_attempts': MAX_ATTEMPTS, 'requested': limit,
        'total_publications': len(rows), 'selected_ids': selected_ids,
        'remaining_eligible': len(eligible), 'publications': rows,
        'note': 'Selected visit only; queue exhaustion is not M2 acceptance. Progress counts only verified Drive evidence.'}


def write_queue(root: Path, queue: dict) -> None:
    from .pipeline import _atomic_json
    queue['status_counts'] = dict(Counter(row['status'] for row in queue['publications']))
    queue['remaining_eligible'] = sum(row['status'] in ('pending', 'unseen') for row in queue['publications'])
    _atomic_json(root/'queue.json', queue)
    # Paths link to the immutable run/manifest rather than moving user artifacts.
    with (root/'review_later.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['arxiv_id', 'attempts', 'signature', 'run_id', 'audit_path'])
        writer.writeheader()
        for row in queue['publications']:
            if row['status'] == 'deferred':
                for evidence in row.get('evidence', []):
                    writer.writerow({k: row[k] if k in row else evidence[k] for k in writer.fieldnames})
