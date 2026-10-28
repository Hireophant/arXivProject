"""PROTOTYPE — Danh / DA4.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import BenchmarkResult, ParseConfig, ResourceSample


def sample_process_tree(elapsed_seconds: float) -> ResourceSample:
    """psutil Process(os.getpid()) và children(recursive=True), sum RSS các PID còn sống.
    Không cộng PID trùng; NoSuchProcess do process kết thúc xử lý rõ; không đọc được -> rss_bytes=None/error,
    không thay bằng zero. Ghi elapsed từ perf_counter, sampling interval được công bố.
    Owner triển khai sampler loop/thread nội bộ, đảm bảo stop/join trong finally; không import psutil lúc package import.
    """
    raise NotImplementedError("M2 prototype: benchmark.sample_process_tree — Danh / DA4")


def measure_output_bytes(output_root: Path) -> int:
    """Đếm bytes final working/published artifacts được manifest run hiện tại tham chiếu, không đếm duplicate
    published/working cùng nội dung hai lần nếu policy chỉ canonical artifact; công bố boundary chính xác.
    Loại raw M1, backups, temp, samples benchmark, output run cũ; không theo symlink.
    Đối chiếu danh sách files + bytes trong receipt để người khác kiểm lại được, không dùng dung lượng ZIP làm output size.
    """
    raise NotImplementedError("M2 prototype: benchmark.measure_output_bytes — Danh / DA4")


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
    raise NotImplementedError("M2 prototype: benchmark.benchmark_run — Danh / DA4")

