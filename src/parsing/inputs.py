"""PROTOTYPE — Khánh / KH1.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
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

