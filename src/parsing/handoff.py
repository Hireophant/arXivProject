"""Publish verified Parquet tables from a finished M2 run without parsing again."""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .contracts import RunManifest, TABLE_COLUMNS
from .pipeline import _atomic_json, _hash, _relative_file
from .serialization import _hydrate, _loads, _owned_destination

try:
    from src.crawling.failures import classify_failure
except ModuleNotFoundError:
    from crawling.failures import classify_failure

_KIND = 'm2-handoff-tables-1.0'
_PUBLICATIONS_PER_SHARD = 50


def _schemas(pa):
    string, strings, integer = pa.string(), pa.list_(pa.string()), pa.int64()
    arxiv_id = pa.field('arxiv_id', string, nullable=False)
    element_id = pa.field('element_id', string, nullable=False)
    return {
        'papers': pa.schema([arxiv_id, ('title', string), ('authors', strings), ('submission_date', string),
                             ('revised_dates', strings), ('venue', string)]),
        'references': pa.schema([arxiv_id, pa.field('ref_arxiv_id', string, nullable=False),
                                  ('ref_title', string), ('ref_authors', strings),
                                  ('ref_submission_date', string), ('ref_s2_id', string)]),
        'elements': pa.schema([element_id, arxiv_id, ('kind', string), ('content', string)]),
        'hierarchy': pa.schema([arxiv_id, ('version', integer), element_id,
                                 pa.field('parent_id', string, nullable=False)]),
        'bibtex': pa.schema([arxiv_id, pa.field('citation_key', string, nullable=False),
                            ('entry_type', string), ('title', string), ('authors', strings),
                            ('year', integer), ('doi', string), ('journal', string), ('url', string)]),
    }


def _reference_rows(raw_root: Path, identifier: str, paper: dict) -> list[dict]:
    references = paper['references']
    if references is None:
        return []
    result = _loads(_relative_file(raw_root, references['path']).read_text('utf-8'))
    if result['arxiv_id'] != identifier or result['status'] != references['status']:
        raise ValueError(f'M1 reference receipt disagrees with prepared manifest for {identifier}')
    return [
        dict(arxiv_id=identifier, ref_arxiv_id=key if '/' in key else key.replace('-', '.'),
             ref_title=item['title'], ref_authors=item['authors'],
             ref_submission_date=item['submission_date'], ref_s2_id=item['semantic_scholar_id'])
        for key, item in sorted(result['references'].items())
    ]


def _verify_tables(root: Path, manifest: dict) -> None:
    files = manifest['files']
    expected = {file['path'] for file in files}
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*.parquet')}
    if expected != actual or len(expected) != len(files):
        raise ValueError(f'Handoff file inventory mismatch: {root}')
    for file in files:
        path = _relative_file(root, file['path'])
        if path.stat().st_size != file['bytes'] or _hash(path) != file['sha256']:
            raise ValueError(f'Handoff checksum mismatch: {path}')


def _publish_tables(local: Path, destination: Path, manifest: dict) -> None:
    if destination.exists():
        saved = _loads((destination/'manifest.json').read_text('utf-8'))
        if saved != manifest:
            raise FileExistsError(f'Different handoff already exists: {destination}')
        _verify_tables(destination, manifest)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.tables-upload-', dir=destination.parent) as temporary:
        staging = Path(temporary)/'tables'
        for file in manifest['files']:
            relative = file['path']
            target = _relative_file(staging, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with (local/relative).open('rb') as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, length=1024*1024)
                output.flush()
                os.fsync(output.fileno())
        _verify_tables(staging, manifest)
        _atomic_json(staging/'manifest.json', manifest)
        if destination.exists():
            raise FileExistsError(f'Handoff destination appeared during upload: {destination}')
        staging.rename(destination)


def _exclusions(raw_root: Path, papers: dict, run_root: Path, run: RunManifest, records: dict) -> list[dict]:
    with _relative_file(raw_root, 'inventory.csv').open(encoding='utf-8', newline='') as stream:
        inputs = {(row['arxiv_id'], int(row['version'])): row for row in csv.DictReader(stream)}
    with _relative_file(run_root, 'metrics/versions.csv').open(encoding='utf-8', newline='') as stream:
        outcomes = {}
        for row in csv.DictReader(stream):
            if (row['run_id'], row['snapshot_id']) != (run.run_id, run.snapshot_id):
                raise ValueError('M2 version metrics do not match the handoff run')
            outcomes[(row['arxiv_id'], int(row['version']))] = row['status']
    excluded = []
    for identifier, paper in sorted(papers.items()):
        record = records.get(identifier)
        if record is not None and record.export_ready:
            continue
        diagnostics = []
        if record is not None:
            with _relative_file(run_root, record.audit_path).open(encoding='utf-8') as stream:
                diagnostics = [_loads(line) for line in stream if line.strip()]
        versions = []
        for version in paper['record']['versions']:
            key = (identifier, version)
            source = inputs[key]
            status = outcomes.get(key)
            if record is not None and status is None:
                raise ValueError(f'Missing M2 version metrics for {identifier} v{version}')
            m1_status, m1_error = source['m1_source_status'] or None, source['m1_error'] or None
            m1_category, m1_code = None, None
            errors = sorted({d['code'] for d in diagnostics if d['severity'] == 'error'
                             and (d['version'] == version or version in d['affected_versions']
                                  or (d['version'] is None and not d['affected_versions']))})
            if source['reason'] == 'PENDING_BATCH':
                cause = 'preparation_pending'
            elif source['status'] == 'blocked_input':
                cause = 'prepared_input_blocked'
                if source['reason'] == 'SOURCE_MISSING_OR_INVALID' and m1_status == 'failed':
                    m1_category, m1_code, _ = classify_failure('source', m1_status, m1_error)
                    cause = 'm1_permanent_source_failure' if m1_category == 'permanent' else 'm1_crawl_failed'
            elif record is None:
                cause = 'not_attempted'
            elif 'OUTPUT_WRITE_FAILED' in errors:
                cause = 'm2_output_failed'
            elif status in ('partial', 'failed'):
                cause = 'm2_parse_or_validation'
            else:
                cause = status
            versions.append(dict(version=version, cause=cause, input_status=source['status'],
                                 input_reason=source['reason'] or None, m1_source_status=m1_status,
                                 m1_error=m1_error, m1_failure_category=m1_category, m1_failure_code=m1_code,
                                 m2_status=status, m2_error_codes=errors))
        excluded.append(dict(arxiv_id=identifier, reason=('not_attempted' if record is None
                             else 'not_export_ready' if record.working_path else 'no_working_output'),
                             audit_path=record.audit_path if record is not None else None, versions=versions))
    return excluded


def export_handoff_tables(raw_root: Path, run_root: Path, *, backup_root: Path | None = None) -> Path:
    """Build one reusable handoff for the export-ready publications of this run."""
    raw_root, run_root = Path(raw_root).resolve(), Path(run_root).resolve()
    local = _owned_destination(run_root/'tables')
    if raw_root.is_relative_to(local) or local.is_relative_to(raw_root):
        raise ValueError('Handoff output must be separate from raw input')
    manifest_bytes = _relative_file(run_root, 'manifest.json').read_bytes()
    run = _hydrate(RunManifest, _loads(manifest_bytes.decode('utf-8')))
    if run.status not in ('success', 'partial') or run.run_id != run_root.name:
        raise ValueError('Handoff requires a finished M2 run in its original run directory')
    raw = _loads(_relative_file(raw_root, 'manifest.json').read_text('utf-8'))
    preparation = _loads(_relative_file(raw_root, 'preparation.json').read_text('utf-8'))
    if (preparation['run_id'] != run.preparation_run_id or raw['run_id'] != run.preparation_run_id
            or preparation['snapshot_id'] != run.snapshot_id):
        raise ValueError('Prepared input does not match the finished M2 run')
    identity = dict(kind=_KIND, run_id=run.run_id, snapshot_id=run.snapshot_id,
                    code_revision=run.code_revision, run_status=run.status,
                    run_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest())

    if local.exists():
        handoff = _loads((local/'manifest.json').read_text('utf-8'))
        if any(handoff.get(key) != value for key, value in identity.items()):
            raise ValueError(f'Local handoff does not match this run: {local}')
        _verify_tables(local, handoff)
    else:
        handoff = _build_tables(raw_root, raw['papers'], run_root, run, identity, local)

    if backup_root is None:
        return local
    destination = _owned_destination(Path(backup_root)/run.run_id/'tables')
    if destination != local:
        if destination.is_relative_to(raw_root) or raw_root.is_relative_to(destination):
            raise ValueError('Drive handoff must be separate from raw input')
        _publish_tables(local, destination, handoff)
    return destination


def _build_tables(raw_root: Path, papers: dict, run_root: Path, run: RunManifest,
                  identity: dict, destination: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    records = {record.arxiv_id: record for record in run.publications}
    if len(records) != len(run.publications) or records.keys() - papers.keys():
        raise ValueError('Run manifest has duplicate publications or IDs outside the raw snapshot')
    accepted = [record for record in run.publications if record.export_ready]
    excluded = _exclusions(raw_root, papers, run_root, run, records)
    schemas = _schemas(pa)
    counts = dict.fromkeys(schemas, 0)
    files = []
    with TemporaryDirectory(prefix='.tables-build-', dir=run_root) as temporary:
        staging = Path(temporary)/'tables'
        for shard, start in enumerate(range(0, max(1, len(accepted)), _PUBLICATIONS_PER_SHARD)):
            rows = {name: [] for name in schemas}
            for record in accepted[start:start+_PUBLICATIONS_PER_SHARD]:
                identifier = record.arxiv_id
                paper = papers[identifier]
                metadata = paper['record']['metadata']
                if metadata['arxiv_id'] != identifier or paper['record']['versions'] != record.expected_versions:
                    raise ValueError(f'Prepared metadata disagrees with M2 record for {identifier}')
                rows['papers'].append(metadata)
                rows['references'].extend(_reference_rows(raw_root, identifier, paper))
                if not record.working_path:
                    raise ValueError(f'Export-ready publication is missing tables: {identifier}')
                for name, columns in TABLE_COLUMNS.items():
                    relative = f'{record.working_path}/{name}.jsonl'
                    digest = hashlib.sha256()
                    expected_columns = set(columns)
                    with _relative_file(run_root, relative).open('rb') as stream:
                        for line in stream:
                            digest.update(line)
                            if not line.strip():
                                continue
                            row = _loads(line.decode('utf-8'))
                            if row.keys() != expected_columns or row['arxiv_id'] != identifier:
                                raise ValueError(f'M2 table schema or publication mismatch: {relative}')
                            rows[name].append(row)
                    if digest.hexdigest() != record.output_sha256.get(relative):
                        raise ValueError(f'M2 table checksum mismatch: {relative}')
            for name, schema in schemas.items():
                path = staging/name/f'part-{shard:05}.parquet'
                path.parent.mkdir(parents=True, exist_ok=True)
                table = pa.Table.from_pylist(rows[name], schema=schema)
                pq.write_table(table, path, compression='zstd',
                               use_dictionary={'elements': ['kind'], 'bibtex': ['entry_type']}.get(name, False))
                if pq.ParquetFile(path).metadata.num_rows != table.num_rows:
                    raise ValueError(f'Parquet row count mismatch: {path}')
                counts[name] += table.num_rows
                files.append(dict(path=path.relative_to(staging).as_posix(), rows=table.num_rows,
                                  bytes=path.stat().st_size, sha256=_hash(path)))
        handoff = dict(identity, publications_expected=len(papers), publications_processed=len(records),
                       publications_included=len(accepted), publications_excluded=len(excluded),
                       excluded_version_counts=dict(Counter(version['cause'] for paper in excluded
                                                            for version in paper['versions'])),
                       excluded=excluded, rows=counts, files=files)
        _atomic_json(staging/'manifest.json', handoff)
        staging.rename(destination)
    return handoff
