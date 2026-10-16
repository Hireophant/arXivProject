"""Sequential orchestration; file owners validate receipts on every resume."""

import json
import math
import os
import platform
import sys
import re
import shutil
import subprocess
import tempfile
import time
import types
import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from functools import partial
from pathlib import Path
from threading import Event, Thread
from typing import get_args, get_origin, get_type_hints, is_typeddict, Literal, Union

from . import (
    DatesCallable, DiscoverCallable, DownloadCallable, HttpPolicy, Manifest,
    PaperRecord, ReferencesCallable, RunResult, Scope, DownloadResult, ReferenceResult,
    DiscoveryResult,
)
from .discover import discover_papers, fetch_submission_dates
from .download import download_version
from .references import collect_references
from .metrics import collect_resource_samples, summarize_corpus, summarize_benchmark, _disk_bytes

_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})\Z')


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _typed(value, annotation):
    """Validate JSON primitives against the unchanged shared TypedDict schemas."""
    origin, args = get_origin(annotation), get_args(annotation)
    if is_typeddict(annotation):
        fields = get_type_hints(annotation)
        return isinstance(value, dict) and value.keys() == fields.keys() and all(_typed(value[k], t) for k, t in fields.items())
    if origin in (Union, types.UnionType):
        return any(_typed(value, t) for t in args)
    if origin is Literal:
        return any(type(value) is type(v) and value == v for v in args)
    if origin is list:
        return isinstance(value, list) and all(_typed(v, args[0]) for v in value)
    if origin is dict:
        return isinstance(value, dict) and all(_typed(k, args[0]) and _typed(v, args[1]) for k, v in value.items())
    if annotation is float:
        return type(value) in (float, int) and math.isfinite(value) and value >= 0
    if annotation is int:
        return type(value) is int and value >= 0
    return type(value) is annotation


def _require(value, schema):
    if not _typed(value, schema):
        raise ValueError(f'Invalid {schema.__name__} schema')


def _scope(scope):
    _require(scope, Scope)
    if scope['mode'] == 'ids':
        if not scope['ids'] or scope['start_id'] is not None or scope['end_id'] is not None:
            raise ValueError('Invalid IDs scope')
        for identifier in scope['ids']:
            paper_directory(identifier, Path('.'))
    else:
        a, b = scope['start_id'], scope['end_id']
        if (scope['ids'] or not a or not b or not re.fullmatch(r'\d{4}\.\d{4,5}', a)
                or not re.fullmatch(r'\d{4}\.\d{4,5}', b) or a[:4] != b[:4]
                or len(a) != len(b) or a > b):
            raise ValueError('Invalid range scope')
        paper_directory(a, Path('.'))
        paper_directory(b, Path('.'))


def _assignment_scope(assignment, month_end_ids=None):
    """Convert a teacher row to the existing Scope; never guess month boundaries."""
    month_end_ids = {} if month_end_ids is None else month_end_ids

    def parse_month(value):
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}', value):
            raise ValueError('Months must use YYYY-MM.')
        try:
            parsed = date.fromisoformat(value + '-01')
        except ValueError as exc:
            raise ValueError('Invalid assignment month.') from exc
        if parsed.year < 2007 or (parsed.year == 2007 and parsed.month < 4):
            raise ValueError('Monthly numeric IDs require April 2007 or later.')
        return parsed.year * 12 + parsed.month - 1

    def sequence(value, month_index):
        year, offset = divmod(month_index, 12)
        width = 4 if (year, offset + 1) < (2015, 1) else 5
        if type(value) is int:
            number = value
        elif isinstance(value, str) and re.fullmatch(r'\d+', value):
            number = int(value)
        else:
            raise ValueError('ID suffixes must be positive integers.')
        if not 1 <= number < 10 ** width:
            raise ValueError('ID suffix is outside the supported monthly format.')
        return number

    def identifier(month_index, number):
        year, offset = divmod(month_index, 12)
        width = 4 if (year, offset + 1) < (2015, 1) else 5
        return f'{year % 100:02d}{offset + 1:02d}.{number:0{width}d}'

    start_month = parse_month(assignment['start_month'])
    end_month = parse_month(assignment['end_month'])
    start = sequence(assignment['start_id'], start_month)
    end = sequence(assignment['end_id'], end_month)
    if start_month > end_month or (start_month == end_month and start > end):
        raise ValueError('Assignment start must not exceed its end.')
    if start_month == end_month:
        scope = dict(mode='range', ids=[], start_id=identifier(start_month, start),
                     end_id=identifier(end_month, end))
    else:
        ids = []
        for month_index in range(start_month, end_month + 1):
            year, offset = divmod(month_index, 12)
            month_key = f'{year:04d}-{offset + 1:02d}'
            lower = start if month_index == start_month else 1
            if month_index == end_month:
                upper = end
            else:
                if month_key not in month_end_ids:
                    raise ValueError(f'Provide the verified last ID for {month_key} in MONTH_END_IDS; it cannot be guessed.')
                upper = sequence(month_end_ids[month_key], month_index)
            if lower > upper:
                raise ValueError(f'Invalid lower/upper ID for {month_key}.')
            ids.extend(identifier(month_index, number) for number in range(lower, upper + 1))
        scope = dict(mode='ids', ids=ids, start_id=None, end_id=None)
    _scope(scope)
    return scope



def paper_directory(arxiv_id: str, data_root: Path) -> Path:
    if not isinstance(arxiv_id, str) or not _ID.fullmatch(arxiv_id):
        raise ValueError('Invalid base arXiv ID')
    digits = arxiv_id.split('/')[-1] if '/' in arxiv_id else arxiv_id.split('.')[0]
    if not 1 <= int(digits[2:4]) <= 12:
        raise ValueError('Invalid arXiv month')
    root = data_root.resolve()
    target = (root / arxiv_id.replace('.', '-').replace('/', '-')).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError('Paper directory escapes data root')
    return target


def _record(record):
    _require(record, PaperRecord)
    paper_directory(record['arxiv_id'], Path('.'))
    versions, metadata = record['versions'], record['metadata']
    if (not versions or versions != list(range(1, max(versions) + 1))
            or metadata['arxiv_id'] != record['arxiv_id'] or not metadata['title'].strip()
            or not metadata['authors'] or any(not a.strip() for a in metadata['authors'])
            or len(metadata['revised_dates']) != len(versions) - 1):
        raise ValueError('Invalid paper metadata/version history')
    dates = [metadata['submission_date'], *metadata['revised_dates']]
    try:
        if any(date.fromisoformat(d).isoformat() != d for d in dates) or dates != sorted(dates):
            raise ValueError('Invalid dates')
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid metadata dates') from exc


def initialize_manifest(scope: Scope, *, run_id: str) -> Manifest:
    _scope(scope)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('run_id must be nonempty')
    return dict(schema_version='1.0', run_id=run_id, scope=deepcopy(scope),
                discovery=None, papers={}, updated_at=_utc())


def _manifest(manifest):
    _require(manifest, Manifest)
    _scope(manifest['scope'])
    if not manifest['run_id'].strip():
        raise ValueError('Empty run_id')
    try:
        if datetime.fromisoformat(manifest['updated_at'].replace('Z', '+00:00')).utcoffset() is None:
            raise ValueError('Naive timestamp')
    except ValueError as exc:
        raise ValueError('Invalid manifest timestamp') from exc
    if manifest['discovery'] is not None:
        _discovery(manifest['discovery'], manifest['scope'])
    for identifier, state in manifest['papers'].items():
        _record(state['record'])
        expected_path = paper_directory(identifier, Path('/')).name + '/metadata.json'
        if (identifier != state['record']['arxiv_id'] or state['metadata_path'] != expected_path
                or set(state['downloads']) != {str(v) for v in state['record']['versions']}):
            raise ValueError('Inconsistent paper state')
        for version, result in state['downloads'].items():
            if result is not None:
                _download(result, identifier, int(version))
        if state['references'] is not None:
            _references(state['references'], identifier)


def _discovery(result, scope):
    _require(result, DiscoveryResult)
    identifiers = [p['arxiv_id'] for p in result['papers']] + [i['arxiv_id'] for i in result['issues']]
    if (result['scope'] != scope or len(set(identifiers)) != len(identifiers)
            or result['requested_count'] != len(identifiers)):
        raise ValueError('Inconsistent discovery scope/count/IDs')
    if scope['mode'] == 'ids':
        expected = set(scope['ids'])
        if set(identifiers) != expected:
            raise ValueError('Discovery omitted requested IDs')
    else:
        a, b = scope['start_id'], scope['end_id']
        expected_count = int(b[5:]) - int(a[5:]) + 1
        if len(identifiers) != expected_count or any(len(i) != len(a) or not a <= i <= b for i in identifiers):
            raise ValueError('Discovery omitted range IDs')
    for record in result['papers']:
        _record(record)
    for issue in result['issues']:
        paper_directory(issue['arxiv_id'], Path('.'))
    if result['status'] == 'success' and (not result['scope_complete'] or result['issues']):
        raise ValueError('Inconsistent discovery success')


def _download(result, identifier, version):
    _require(result, DownloadResult)
    if result['arxiv_id'] != identifier or result['version'] != version:
        raise ValueError('Download identity mismatch')
    before, after = result['source_bytes_before'], result['source_bytes_after']
    if before is not None and after is not None and after > before:
        raise ValueError('Inconsistent source sizes')
    if result['status'] == 'success' and (result['error'] is not None or result['file_count'] == 0):
        raise ValueError('Inconsistent successful source result')
    if result['status'] == 'no_tex' and (result['file_count'] != 0 or result['source_bytes_after'] != 0):
        raise ValueError('Inconsistent verified no_tex result')
    if result['used_cache'] and (result['attempts'] or result['status'] == 'failed'):
        raise ValueError('Invalid download cache result')


def _references(result, identifier):
    _require(result, ReferenceResult)
    if (result['arxiv_id'] != identifier or result['kept_references'] != len(result['references'])
            or not 0 <= result['missing_submission_dates'] <= result['incomplete_references'] <= result['kept_references']):
        raise ValueError('Inconsistent reference counts/identity')
    if result['total_references'] is not None and result['total_references'] < result['kept_references']:
        raise ValueError('Reference total smaller than kept count')
    if result['used_cache'] and (result['attempts'] or result['status'] != 'success'):
        raise ValueError('Invalid reference cache result')
    if result['status'] == 'success' and (not result['pagination_complete'] or result['incomplete_references'] or result['error'] is not None):
        raise ValueError('Inconsistent reference success')


def load_manifest(path: Path) -> Manifest:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        _manifest(value)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError('Invalid manifest JSON/schema/invariants') from exc
    return value


def _atomic_json(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.danh-', delete=False) as stream:
            name = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def save_manifest(manifest: Manifest, path: Path) -> None:
    _manifest(manifest)
    updated = dict(manifest, updated_at=_utc())
    _atomic_json(path, updated)
    manifest['updated_at'] = updated['updated_at']


def save_paper_metadata(record: PaperRecord, paper_dir: Path) -> None:
    _record(record)
    _atomic_json(paper_dir / 'metadata.json', record['metadata'])


def _cpu_only_environment():
    if os.environ.get('COLAB_TPU_ADDR') or os.environ.get('TPU_NAME'):
        return False
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            result = subprocess.run([executable, '-L'], capture_output=True, text=True, timeout=5, check=False)
            # Conservatively avoid claiming CPU-only when accelerator detection fails.
            return result.returncode == 0 and not result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return False
    return True


def run_pipeline(
    scope: Scope, data_root: Path, *, policy: HttpPolicy, resume: bool = True,
    discover_fn: DiscoverCallable = discover_papers,
    download_fn: DownloadCallable = download_version,
    reference_fn: ReferencesCallable = collect_references,
    dates_fn: DatesCallable = fetch_submission_dates,
) -> RunResult:
    _scope(scope)
    _require(policy, HttpPolicy)
    if (type(resume) is not bool or policy['timeout_seconds'] <= 0 or policy['max_attempts'] < 1
            or not policy['user_agent'].strip()):
        raise ValueError('Invalid pipeline configuration')
    root = data_root.resolve()
    path = root / 'manifest.json'
    if not resume and root.exists() and any(root.iterdir()):
        raise ValueError('Cold run requires a new empty root')
    manifest = load_manifest(path) if path.exists() else initialize_manifest(scope, run_id=str(uuid.uuid4()))
    if manifest['scope'] != scope:
        raise ValueError('Resume scope differs from manifest')
    if not path.exists() and root.exists() and any(root.iterdir()):
        raise ValueError('Nonempty root has no manifest; choose a new root')
    had_manifest = path.exists()
    manifest['run_id'] = str(uuid.uuid4())
    for state in manifest['papers'].values():
        state['elapsed_seconds'] = None
        # Old outputs remain on disk, but are not successes of this run until verified.
        state['downloads'] = {str(v): None for v in state['record']['versions']}
        state['references'] = None
    if not (root / 'metrics').resolve().is_relative_to(root):
        raise ValueError('Metrics directory escapes root')
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    samples, errors = [], []
    interval = 0.25
    stop = Event()
    worker = Thread(target=collect_resource_samples, args=(os.getpid(), root, stop),
                    kwargs=dict(interval_seconds=interval, samples=samples, errors=errors),
                    name='arxiv-resource-sampler', daemon=True)
    worker.start()
    try:
        save_manifest(manifest, path)
        discovery = discover_fn(deepcopy(scope), policy=policy)
        _discovery(discovery, scope)
        manifest['discovery'] = deepcopy(discovery)
        save_manifest(manifest, path)
        for record in discovery['papers']:
            identifier = record['arxiv_id']
            directory = paper_directory(identifier, root)
            state = dict(record=deepcopy(record), metadata_path=(directory / 'metadata.json').relative_to(root).as_posix(),
                         downloads={str(v): None for v in record['versions']}, references=None, elapsed_seconds=None)
            manifest['papers'][identifier] = state
            paper_started = time.perf_counter()
            save_paper_metadata(record, directory)
            save_manifest(manifest, path)
            for version in record['versions']:
                version_dir = directory / 'sources' / f'v{version}'
                if not version_dir.resolve().is_relative_to(root):
                    raise ValueError('Source directory escapes root')
                task_started = time.perf_counter()
                try:
                    result = download_fn(identifier, version, version_dir,
                                         policy=policy, use_cache=resume)
                except (ValueError, NotImplementedError):
                    raise
                except Exception as exc:
                    result = dict(arxiv_id=identifier, version=version, status='failed', source_bytes_before=None,
                                  source_bytes_after=None, archive_bytes=None, file_count=None, elapsed_seconds=time.perf_counter() - task_started,
                                  attempts=0, used_cache=False, error=f'Download dependency raised {type(exc).__name__}')
                _download(result, identifier, version)
                state['downloads'][str(version)] = deepcopy(result)
                state['elapsed_seconds'] = time.perf_counter() - paper_started
                save_manifest(manifest, path)
            task_started = time.perf_counter()
            try:
                refs = reference_fn(identifier, directory, partial(dates_fn, policy=policy), policy=policy, use_cache=resume)
            except (ValueError, NotImplementedError):
                raise
            except Exception as exc:
                refs = dict(arxiv_id=identifier, status='failed', references={}, total_references=None, kept_references=0,
                            missing_submission_dates=0, incomplete_references=0, pagination_complete=False,
                            retrieved_at=_utc(), elapsed_seconds=time.perf_counter() - task_started, attempts=0, used_cache=False,
                            error=f'Reference dependency raised {type(exc).__name__}')
            _references(refs, identifier)
            state['references'] = deepcopy(refs)
            state['elapsed_seconds'] = time.perf_counter() - paper_started
            save_manifest(manifest, path)
        summary = summarize_corpus(manifest)
        complete = (discovery['status'] == 'success' and discovery['scope_complete'] and not discovery['issues']
                    and not any(summary[k] for k in ('versions_failed', 'versions_pending', 'reference_jobs_partial',
                                                     'reference_jobs_failed', 'reference_jobs_not_found', 'reference_jobs_pending')))
        progressed = summary['versions_success'] + summary['versions_no_tex'] + summary['reference_jobs_success']
        operational_failure = summary['versions_failed'] + summary['reference_jobs_failed']
        status = 'success' if complete else ('failed' if not progressed and (operational_failure or discovery['status'] == 'failed') else 'partial')
        cache_results = [d for s in manifest['papers'].values() for d in [*s['downloads'].values(), s['references']] if d]
        cache_mode = 'mixed' if any(d['used_cache'] for d in cache_results) and any(not d['used_cache'] for d in cache_results) else ('resume' if had_manifest or any(d['used_cache'] for d in cache_results) else 'cold')
        cpu_only = _cpu_only_environment()
        benchmark = summarize_benchmark(samples, wall_seconds=time.perf_counter() - started, final_disk_bytes=_disk_bytes(root),
                                        environment=f'{platform.system()} {platform.machine()}; Python {platform.python_version()}; ' + ('Colab' if 'COLAB_RELEASE_TAG' in os.environ or 'google.colab' in sys.modules else 'local development'),
                                        cpu_only=cpu_only, cache_mode=cache_mode, sampling_interval_seconds=interval)
        output = dict(status=status, run_id=manifest['run_id'], manifest_path='manifest.json', metrics_path='metrics/run_summary.json',
                      summary=summary, benchmark=benchmark)
        _atomic_json(root / 'metrics' / 'run_summary.json', output)
    finally:
        stop.set()
        worker.join()
        _atomic_json(root / 'metrics' / 'resource_errors.json', errors)
        _atomic_json(root / 'metrics' / 'resource_samples.json', samples)
    # Fold the final sample into the result after the worker has joined. The
    # initial summary was persisted with the sampler still running. Wall time
    # includes that write and worker shutdown; final rewrite is bookkeeping.
    benchmark.update(summarize_benchmark(samples, wall_seconds=time.perf_counter() - started,
        final_disk_bytes=_disk_bytes(root), environment=benchmark['environment'], cpu_only=cpu_only,
        cache_mode=cache_mode, sampling_interval_seconds=interval))
    for _ in range(8):
        _atomic_json(root / 'metrics' / 'run_summary.json', output)
        size = _disk_bytes(root)
        if size == benchmark['final_disk_bytes']:
            break
        benchmark['final_disk_bytes'] = size
    else:
        raise OSError('Run summary disk footprint did not stabilize')
    return output
