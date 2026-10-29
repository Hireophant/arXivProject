"""PROTOTYPE — Khánh / KH3.

Prototype và docstring thuật toán là hướng tham khảo, không giới hạn ở điền thân hàm.
Đọc contracts.py, phần việc owner và tiêu chí nghiệm thu; hoàn thiện đầy đủ task/đầu ra.
Nếu có phương án tốt hơn, so sánh lợi ích/đánh đổi, dependencies, ảnh hưởng API và cách kiểm chứng;
hỏi người phụ trách task chọn hướng trước khi làm phần phụ thuộc, tiếp tục việc độc lập trong lúc chờ.
Không hỏi lại lựa chọn đã chốt hoặc từng chi tiết nhỏ. Sau khi chốt có thể thêm/thay/tổ chức lại code.
Test độc lập dùng fixtures trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa phạm vi owner đang thống nhất; mở rộng phạm vi cần phối hợp owner bị ảnh hưởng.
Ưu tiên giữ nguyên schema, kiểu dữ liệu và API; không cần đổi mà vẫn hoàn thành tốt task thì càng tốt.
Không khuyến khích đổi; chỉ đổi khi thật sự cần thiết và hạn chế sửa phần chung để tránh conflict. Phối hợp Danh/owner bị ảnh hưởng và đồng bộ consumer, fixtures, tests, notebook, tài liệu.
Không giảm yêu cầu hay acceptance cases khi đổi thiết kế.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.

Hướng hiệu năng đã chọn (kế hoạch 10.0; chưa triển khai):
Pipeline gọi summarize([publication]), gộp counts/version rows tăng dần bằng helper rồi tính rates từ tổng; set ID chặn trùng. Giữ public API, không giữ tables toàn corpus chỉ để summarize.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import MetricsSummary, ParsedPublication


def summarize(publications: list[ParsedPublication]) -> MetricsSummary:
    """API thuần, nhận kết quả sau finalize (fixtures có sẵn), không gọi pipeline/validator.
    Publication IDs duplicate -> ValueError để tránh gộp retry hai lần. Tất cả version_states đều phải có row.
    status_counts đủ 5 statuses kể cả zero; error_codes lấy diagnostics version/affected_versions.
    parse_success=parsed/(parsed+partial+failed); resolved=(parsed+empty)/expected;
    attempt=(parsed+partial+failed)/(expected-empty); denominator 0 -> None.
    Counts dedup theo kind cộng before/after, không trung bình tỷ lệ; publication_count gồm all-empty/blocked.
    Đừng chỉ nhận successful export: pipeline phải truyền working publications cả lỗi để giữ mẫu số.
    Kiểm fixture tính tay mixed status và bản tổng hợp shard, không tính lại từ glob outputs tốt cũ.
    """
    raise NotImplementedError("M2 prototype: metrics.summarize — Khánh / KH3")


def write_metrics(summary: MetricsSummary, output_dir: Path, *, run_id: str, snapshot_id: str) -> list[Path]:
    """Ghi versions.csv, dedup.csv, run_summary.json với UTF-8/newline chuẩn và run/snapshot.
    JSON missing là null; CSV missing là cell rỗng; list error_codes encode JSON trong một cell.
    Dedup CSV kind,before,after,reduction; denominator 0 -> rỗng. Không thêm số đo benchmark chưa có.
    Atomic write; chỉ ghi vào output_dir chuyên metrics, không mutate corpus. Trả đường dẫn đã ghi.
    Đối chiếu CSV đọc lại với MetricsSummary; Book nhận snapshot này, không screenshot/hardcode.

    Cột versions.csv chính xác: run_id,snapshot_id,arxiv_id,version,status,error_codes,export_ready.
    Cột dedup.csv: run_id,snapshot_id,kind,before,after,reduction.
    run_summary.json: {schema_version,contract_version,run_id,snapshot_id,summary:asdict(summary)}.
    CSV bool true/false, None cell rỗng; rates missing JSON null, không số minh họa.
    Kiểm tay tính parsed/partial/failed/empty/blocked trên fixture, so numerator/denominator từng rate.
    """
    raise NotImplementedError("M2 prototype: metrics.write_metrics — Khánh / KH3")

