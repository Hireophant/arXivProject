"""Corpus statistics and observed resource measurements; no network access.

Process-tree RSS uses psutil's Process.children and Process.memory_info APIs:
https://psutil.io/ . Full citations and denominator/measurement decisions are
documented in docs/milestone1/KE_HOACH_MILESTONE_1.md.
"""

import csv
import json
import os
import time
from pathlib import Path
from threading import Event
from statistics import mean

from . import BenchmarkResult, CorpusSummary, Manifest, ResourceSample
from .failures import failure_rows


def _disk_bytes(root: Path) -> int:
    total = 0
    def fail(exc):
        if not isinstance(exc, FileNotFoundError):
            raise exc
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                try:
                    total += path.stat().st_size
                except FileNotFoundError:
                    # Background uploads delete verified staging directories.
                    # Sampling is a live observation, not an archive inventory.
                    pass
    return total


def disk_bytes_with_extras(data_root: Path, extra_roots=()) -> int:
    """Count corpus plus local index/download/cache work without double counting."""
    roots = sorted({Path(p).resolve() for p in (data_root, *extra_roots)}, key=lambda p: len(p.parts))
    selected = []
    for root in roots:
        if not any(root.is_relative_to(parent) for parent in selected):
            selected.append(root)
    return sum(root.stat().st_size if root.is_file() else _disk_bytes(root) for root in selected)


def sample_resources(pid: int, data_root: Path, *, elapsed_seconds: float, extra_roots=()) -> ResourceSample:
    """Measure RSS of unique live processes and regular file bytes under root."""
    import psutil
    process = psutil.Process(pid)
    processes = {p.pid: p for p in [process, *process.children(recursive=True)]}
    ram = sum(p.memory_info().rss for p in processes.values())
    return dict(elapsed_seconds=elapsed_seconds, ram_bytes=ram,
                disk_bytes=disk_bytes_with_extras(data_root, extra_roots))


def collect_resource_samples(
    pid: int, data_root: Path, stop_event: Event, *,
    interval_seconds: float, samples: list[ResourceSample], errors: list[str],
    extra_roots=(),
) -> None:
    """Sample immediately, periodically, and at stop; retain measurement failures."""
    if interval_seconds <= 0:
        raise ValueError('interval_seconds must be positive')
    start = time.perf_counter()
    def capture():
        try:
            samples.append(sample_resources(pid, data_root, elapsed_seconds=time.perf_counter() - start, extra_roots=extra_roots))
        except Exception as exc:
            # Do not persist exception contents (may contain sensitive paths/data).
            errors.append(f'Resource sample failed: {type(exc).__name__}')
    capture()
    while not stop_event.wait(interval_seconds):
        capture()
    capture()


def summarize_corpus(manifest: Manifest) -> CorpusSummary:
    """Compute rates with explicit denominators; unknown measurements stay None.

    Source coverage includes validated no_tex records, while paper_success_rate
    counts papers with TeX in every version. Reference completeness describes
    the arXiv matching pool; non-arXiv quality counts are reported separately.
    """
    states = list(manifest['papers'].values())
    result = dict(papers_discovered=len(states), full_source_papers=0, versions_expected=0)
    for status in ('success', 'no_tex', 'failed', 'pending'):
        result[f'versions_{status}'] = 0
    for status in ('success', 'partial', 'failed', 'not_found', 'pending'):
        result[f'reference_jobs_{status}'] = 0
    sizes, paper_sizes, counts, completeness, times = [], [], [], [], []
    result.update(crawled_reference_rows=0, arxiv_reference_rows=0, non_arxiv_reference_rows=0)
    for state in states:
        downloads = [state['downloads'].get(str(v)) for v in state['record']['versions']]
        result['versions_expected'] += len(downloads)
        for item in downloads:
            result['versions_' + (item['status'] if item else 'pending')] += 1
        full = bool(downloads) and all(d is not None and d['status'] == 'success' for d in downloads)
        result['full_source_papers'] += int(full)
        paired = [(d['source_bytes_before'], d['source_bytes_after']) for d in downloads
                  if d is not None
                  and d['source_bytes_before'] is not None and d['source_bytes_after'] is not None]
        sizes.extend(paired)
        if full and len(paired) == len(downloads):
            paper_sizes.append(tuple(map(sum, zip(*paired))))
        refs = state['references']
        if refs:
            result['crawled_reference_rows'] += len(refs['all_references'])
            result['arxiv_reference_rows'] += sum(r['arxiv_id'] is not None for r in refs['all_references'])
            result['non_arxiv_reference_rows'] += sum(r['arxiv_id'] is None for r in refs['all_references'])
        result['reference_jobs_' + (refs['status'] if refs else 'pending')] += 1
        if refs and refs['pagination_complete']:
            if refs['total_references'] is not None:
                counts.append(refs['total_references'])
            if refs['kept_references'] > 0:
                completeness.append((refs['kept_references'] - refs['incomplete_references']) / refs['kept_references'])
        if state['elapsed_seconds'] is not None:
            times.append(state['elapsed_seconds'])
    def ratio(a, b):
        return a / b if b else None
    result.update(paper_success_rate=ratio(result['full_source_papers'], len(states)),
                  source_coverage_rate=ratio(result['versions_success'] + result['versions_no_tex'], result['versions_expected']),
                  reference_success_rate=ratio(result['reference_jobs_success'], len(states)))
    for values, average, denominator in (
        (counts, 'average_reference_count', 'reference_count_denominator'),
        (completeness, 'average_reference_completeness_rate', 'reference_completeness_denominator'),
        (times, 'average_paper_processing_seconds', 'paper_time_denominator')):
        result[average] = float(mean(values)) if values else None
        result[denominator] = len(values)
    for pairs, prefix, denominator in ((sizes, 'average_source_bytes_', 'source_size_denominator'),
                                       (paper_sizes, 'average_paper_source_bytes_', 'paper_size_denominator')):
        result[denominator] = len(pairs)
        for index, suffix in enumerate(('before', 'after')):
            result[prefix + suffix] = float(mean(p[index] for p in pairs)) if pairs else None
    return result


def summarize_benchmark(
    samples: list[ResourceSample], *, wall_seconds: float,
    final_disk_bytes: int, environment: str, cpu_only: bool,
    cache_mode: str, sampling_interval_seconds: float,
) -> BenchmarkResult:
    """Report observed sample peaks/mean RSS and separately measured final disk.

    Sampling can miss brief peaks. Missing samples remain None, not zero; wall
    time is measured by the pipeline rather than summed from individual tasks.
    """
    if cache_mode not in ('cold', 'resume', 'mixed'):
        raise ValueError('Invalid cache_mode')
    if sampling_interval_seconds <= 0 or wall_seconds < 0 or final_disk_bytes < 0:
        raise ValueError('Invalid benchmark measurement')
    return dict(environment=environment, cpu_only=cpu_only, cache_mode=cache_mode,
                sampling_interval_seconds=sampling_interval_seconds, wall_seconds=wall_seconds,
                ram_peak_bytes=max(s['ram_bytes'] for s in samples) if samples else None,
                ram_mean_bytes=float(mean(s['ram_bytes'] for s in samples)) if samples else None,
                disk_peak_bytes=max(s['disk_bytes'] for s in samples) if samples else None,
                final_disk_bytes=final_disk_bytes)


def export_report_data(manifest: Manifest, benchmark: BenchmarkResult, output_dir: Path) -> None:
    """Export collected values only; blank CSV cells represent unknown values."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in [('summary', summarize_corpus(manifest)), ('benchmark', benchmark)]:
        (output_dir / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (output_dir / 'run_id.txt').write_text(manifest['run_id'] + '\n', encoding='utf-8')
    papers, versions, references, all_references = [], [], [], []
    for arxiv_id, state in manifest['papers'].items():
        base = dict(run_id=manifest['run_id'], arxiv_id=arxiv_id)
        refs = state['references']
        statuses = [(d['status'] if d else 'pending') for d in state['downloads'].values()]
        paper = dict(base, metadata_source=manifest['metadata_source'], metadata_path=state['metadata_path'], elapsed_seconds=state['elapsed_seconds'],
                     source_status='success' if statuses and all(s == 'success' for s in statuses) else 'incomplete',
                     reference_status=refs['status'] if refs else 'pending', versions_expected=len(statuses))
        for status in ('success', 'no_tex', 'failed', 'pending'):
            paper['versions_' + status] = statuses.count(status)
        for key in ('total_references', 'kept_references', 'incomplete_references', 'incomplete_non_arxiv_references', 'missing_submission_dates'):
            paper[key] = refs[key] if refs else None
        papers.append(paper)
        for version in state['record']['versions']:
            item = state['downloads'].get(str(version))
            versions.append(dict(base, **{k: v for k, v in (item or {}).items() if k != 'arxiv_id'},
                                 **({} if item else {'version': version, 'status': 'pending'})))
        if refs:
            for key, metadata in refs['references'].items():
                reference_id = key if '/' in key else key.replace('-', '.')
                references.append(dict(base, reference_arxiv_id=reference_id, **metadata))
            for metadata in refs['all_references']:
                all_references.append(dict(base, reference_arxiv_id=metadata['arxiv_id'],
                                           **{k: v for k, v in metadata.items() if k != 'arxiv_id'}))
    from . import CrawledReference, DownloadResult, ReferenceMetadata
    headers = {
        'papers': ['run_id', 'arxiv_id', 'metadata_source', 'metadata_path', 'elapsed_seconds', 'source_status', 'reference_status',
                   'versions_expected', 'versions_success', 'versions_no_tex', 'versions_failed', 'versions_pending',
                   'total_references', 'kept_references', 'incomplete_references', 'incomplete_non_arxiv_references', 'missing_submission_dates'],
        'versions': ['run_id', *DownloadResult.__annotations__],
        'references': ['run_id', 'arxiv_id', 'reference_arxiv_id', *ReferenceMetadata.__annotations__],
        'references_all': ['run_id', 'arxiv_id', 'reference_arxiv_id', *[k for k in CrawledReference.__annotations__ if k != 'arxiv_id']],
    }
    for name, rows in [('papers', papers), ('versions', versions), ('references', references), ('references_all', all_references)]:
        with (output_dir / f'{name}.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=headers[name])
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    issues = failure_rows(manifest)
    fields = ['arxiv_id', 'task', 'status', 'category', 'code', 'reason', 'error']
    for name, rows in [('outstanding_tasks', [r for r in issues if r['status'] != 'no_tex']),
                       ('permanent_failures', [r for r in issues if r['category'] == 'permanent'])]:
        with (output_dir / f'{name}.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
