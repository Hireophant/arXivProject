"""Fresh-run measurement and raw evidence receipts (Danh / DA4).

Measures wall/per-publication time, sampled process-tree RSS and manifest-bounded output
bytes. Setup/stage/backup are separate. Unknown measurements retain null/error, never
zero placeholders. cpu_only_colab requires runtime signals plus operator CPU-settings evidence;
local fixture smoke cannot substitute for the required actual Colab CPU benchmark.
"""
from __future__ import annotations

import csv
import importlib.metadata
import math
import os
import platform
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from .contracts import BenchmarkResult, ParseConfig, ResourceSample
from . import contracts as c


def _output_inventory(output_root: Path) -> list[dict]:
    from .pipeline import _hash,_relative_file
    from .serialization import _hydrate,_loads
    root = Path(output_root).resolve()
    manifest = _hydrate(c.RunManifest,_loads((root/'manifest.json').read_text('utf-8')))
    if manifest.status == 'in_progress': raise ValueError('Cannot measure incomplete run')
    references = {}
    for record in manifest.publications:
        for artifact in {record.working_path,record.published_path}-{None}:
            folder = _relative_file(root,artifact)
            if not folder.is_dir(): raise ValueError('Missing output folder')
            for path in folder.iterdir():
                if path.is_symlink() or not path.is_file(): raise ValueError('Unexpected output member')
                relative = path.relative_to(root).as_posix()
                expected = record.output_sha256.get(relative)
                digest = _hash(path)
                if expected is None or expected != digest: raise ValueError('Output inventory checksum mismatch')
                references[relative] = {'path':relative,'bytes':path.stat().st_size,'sha256':digest}
    return [references[key] for key in sorted(references)]


def _environment() -> tuple[dict[str,str],bool]:
    environment = {'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
        'processor':platform.processor(),'cpu_count':str(os.cpu_count()),
        'output_boundary':'Unique files in manifest working/published publication artifacts; excludes audit/checkpoint/metrics/benchmark/raw/backup',
        'wall_boundary':'perf_counter immediately before pipeline.run validation through return after outputs/readback/checkpoints/metrics; excludes setup/stage/backup'}
    for package in ('psutil','requests','pandas'):
        try: environment['package.'+package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: environment['package.'+package] = 'unavailable'
    try:
        import psutil
        environment['total_ram_bytes'] = str(psutil.virtual_memory().total)
    except (ImportError,OSError): environment['total_ram_bytes'] = 'unavailable'
    for name in ('COLAB_RELEASE_TAG','COLAB_BACKEND_VERSION','COLAB_GPU','TPU_NAME','M2_COLAB_ACCELERATOR'):
        environment[name] = os.environ.get(name,'unrecorded')
    colab = bool(os.environ.get('COLAB_RELEASE_TAG')) and 'google.colab' in sys.modules
    cpu_only = colab and os.environ.get('M2_COLAB_ACCELERATOR') == 'None' and os.environ.get('COLAB_GPU') == '0' and not os.environ.get('TPU_NAME')
    environment['testbed'] = 'Colab CPU (settings recorded by operator)' if cpu_only else 'local or unverified Colab; not official CPU benchmark'
    return environment,cpu_only


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:('true' if v is True else 'false' if v is False else v) for k,v in row.items()})
        stream.flush(); os.fsync(stream.fileno())


def sample_process_tree(elapsed_seconds: float) -> ResourceSample:
    """psutil Process(os.getpid()) và children(recursive=True), sum RSS các PID còn sống.
    Không cộng PID trùng; NoSuchProcess do process kết thúc xử lý rõ; không đọc được -> rss_bytes=None/error,
    không thay bằng zero. Ghi elapsed từ perf_counter, sampling interval được công bố.
    Owner triển khai sampler loop/thread nội bộ, đảm bảo stop/join trong finally; không import psutil lúc package import.
    """
    try:
        import psutil
        parent = psutil.Process(os.getpid())
        processes = [parent]+parent.children(recursive=True)
        seen,total = set(),0
        for process in processes:
            if process.pid in seen: continue
            seen.add(process.pid)
            try: total += process.memory_info().rss
            except psutil.NoSuchProcess:
                if process.pid == parent.pid: raise
                continue
        return ResourceSample(elapsed_seconds=elapsed_seconds,rss_bytes=total)
    except Exception as exc:
        return ResourceSample(elapsed_seconds=elapsed_seconds,rss_bytes=None,error=f'{type(exc).__name__}: {exc}')


def measure_output_bytes(output_root: Path) -> int:
    """Đếm bytes final working/published artifacts được manifest run hiện tại tham chiếu, không đếm duplicate
    published/working cùng nội dung hai lần nếu policy chỉ canonical artifact; công bố boundary chính xác.
    Loại raw M1, backups, temp, samples benchmark, output run cũ; không theo symlink.
    Đối chiếu danh sách files + bytes trong receipt để người khác kiểm lại được, không dùng dung lượng ZIP làm output size.
    """
    return sum(row['bytes'] for row in _output_inventory(output_root))


def benchmark_run(corpus_root: Path, output_root: Path, config: ParseConfig) -> BenchmarkResult:
    """Fresh pipeline run trên output mới, resume=False; nguồn input đã prepare trước timer.
    Dùng perf_counter + sampler process-tree, ghi peak observed, wall, mean/publication, final output bytes.
    Ghi environment CPU/RAM/packages/Colab accelerator và commit/input snapshot/config cùng raw samples.
    Không gắn local run là Colab; cpu_only_colab chỉ True khi có evidence runtime Colab CPU accelerator None.
    Mean denominator là publications thực xử lý; công bố blocked/cache riêng, không chia tổng versions.
    Không gọi run nhiều lần để lấy số đẹp; sampler có exception phải giữ measurement error, không số giả.
    BenchmarkResult.run_id phải khớp pipeline manifest và per-publication measurements cùng run.
    Sau return có receipt/files raw để viết Book; notebook scaffold chưa được xem benchmark thật.

    Receipt benchmark/receipt.json = asdict(BenchmarkResult); publications.csv đúng fields
    PublicationMeasurement + run_id/snapshot_id, resource_samples.csv đúng ResourceSample + run_id.
    Tự mở CPU settings Colab và đối chiếu một measurement với raw samples; không AI ký thay người kiểm.
    """
    from .pipeline import run,_atomic_json
    from .serialization import _hydrate,_loads
    interval = config.ram_sample_interval_seconds
    if not isinstance(interval,(int,float)) or isinstance(interval,bool) or not math.isfinite(interval) or interval <= 0:
        raise ValueError('Sampling interval must be finite and positive')
    output_root = Path(output_root)
    if output_root.exists(): raise ValueError('Fresh benchmark requires a new output root')
    environment,cpu_only = _environment()
    stop,samples = threading.Event(),[]
    started = time.perf_counter()
    def sample() -> None:
        while not stop.is_set():
            samples.append(sample_process_tree(time.perf_counter()-started))
            stop.wait(interval)
    sampler = threading.Thread(target=sample,name='m2-rss-sampler',daemon=True)
    sampler.start()
    try:
        result = run(corpus_root,output_root,config,resume=False)
        wall = time.perf_counter()-started
    finally:
        stop.set();sampler.join()
        samples.append(sample_process_tree(time.perf_counter()-started))
    root = result.manifest_path.parent
    manifest = _hydrate(c.RunManifest,_loads(result.manifest_path.read_text('utf-8')))
    if manifest.run_id != result.run_id or manifest.snapshot_id != result.snapshot_id: raise ValueError('Benchmark run mismatch')
    if any(record.used_cache for record in manifest.publications): raise ValueError('Fresh benchmark used parsed cache')
    measurements = []
    for record in manifest.publications:
        if record.working_path is not None:
            from .serialization import read_publication
            states = set(read_publication(root/record.working_path).version_states.values())
        else: states = {'failed'}
        status = 'success' if record.export_ready else 'blocked' if states <= {'blocked_input','empty_no_tex'} and 'blocked_input' in states else 'failed' if states <= {'failed','empty_no_tex'} and 'failed' in states else 'partial'
        measurements.append(c.PublicationMeasurement(arxiv_id=record.arxiv_id,versions_expected=len(record.expected_versions),
            wall_seconds=record.wall_seconds,used_cache=record.used_cache,status=status))
    observed = [sample.rss_bytes for sample in samples if sample.rss_bytes is not None]
    environment['run_status'] = result.status
    environment['sampling_errors'] = str(sum(sample.error is not None for sample in samples))
    inventory = _output_inventory(root)
    receipt = BenchmarkResult(run_id=result.run_id,snapshot_id=result.snapshot_id,code_revision=config.code_revision,
        environment=environment,wall_seconds=wall,mean_seconds_per_publication=wall/len(measurements) if measurements else None,
        observed_peak_rss_bytes=max(observed) if observed else None,final_output_bytes=sum(row['bytes'] for row in inventory),
        sample_interval_seconds=interval,publications=measurements,samples=samples,cpu_only_colab=cpu_only)
    destination = root/'benchmark'
    destination.mkdir()
    _write_csv(destination/'resource_samples.csv',['run_id','elapsed_seconds','rss_bytes','error'],
        [dict(run_id=result.run_id,**asdict(sample)) for sample in samples])
    _write_csv(destination/'publications.csv',['run_id','snapshot_id','arxiv_id','versions_expected','wall_seconds','used_cache','status'],
        [dict(run_id=result.run_id,snapshot_id=result.snapshot_id,**asdict(row)) for row in measurements])
    _atomic_json(destination/'output_inventory.json',{'run_id':result.run_id,'boundary':environment['output_boundary'],'files':inventory})
    _atomic_json(destination/'receipt.json',asdict(receipt))
    return receipt

