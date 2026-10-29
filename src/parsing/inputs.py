"""PROTOTYPE — Khánh / KH1.

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
Kiểm corpus đúng một lần mỗi run trong load_publications; private loader dùng manifest/context đã đọc. Không cache validation qua run hoặc rehash toàn corpus từng version.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import PublicationInput, VersionInput


def load_publications(corpus_root: Path) -> list[PublicationInput]:
    """API chính. Đọc raw m2-input-1.0 do notebook prepare tạo, không restore ZIP.
    1. Gọi preparation.validate_prepared_corpus, đòi valid=True; complete=False vẫn nạp nhưng giữ blocked.
    2. Đối chiếu preparation/input_validation/manifest cùng run và snapshot hiện tại.
    3. Duyệt manifest.papers theo arxiv_id, record.versions tăng dần; không glob folders để suy versions.
    4. Gọi load_version_input cho TẤT CẢ versions. Giữ corpus_root, snapshot_id và preparation_run_id.
    5. Path tuyệt đối chỉ tồn tại trong input runtime; JSON xuất ra dùng relative POSIX paths.
    Không import crawler, không gọi mạng, không loại bài vì references M1 rỗng.
    Raw schema khác hoặc contract hỏng -> ValueError rõ; source blocked đã biết -> VersionInput, không raise bỏ bài.
    Kiểm tay: đối chiếu một bài nhiều versions và một blocked/no_tex với inventory.csv.
    Kiểm độc lập: dựng raw fixture bằng tests/test_m2_preparation.py hoặc helper backup; không chờ gather.
    """
    raise NotImplementedError("M2 prototype: inputs.load_publications — Khánh / KH1")


def load_version_input(corpus_root: Path, arxiv_id: str, version: int) -> VersionInput:
    """Đọc đúng version_states/inventory của một version đã kiểm, map ready_tex->tex,
    empty_no_tex->no_tex, blocked_input->blocked. Có thể dùng private loader để tránh đọc/hash toàn corpus mỗi version.
    source_dir là thư mục tuyệt đối đã xác minh; blocked luôn None. no_tex có thể giữ thư mục rỗng có receipt.
    source_fingerprint lấy receipt/inventory đã đối chiếu, không tự dùng mtime.
    Giữ reason/m1_error trong diagnostics với arxiv_id/version; không tin downloads.status một mình.
    Không sửa source. Version không thuộc record.versions -> ValueError, không tự thêm version.
    """
    raise NotImplementedError("M2 prototype: inputs.load_version_input — Khánh / KH1")

