"""PROTOTYPE — Khánh / KH2.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import BibliographyLocation, GatherResult, SourceFile, SourceSpan, VersionInput


def find_root(source_dir: Path) -> str:
    """Trả root path relative POSIX có documentclass đang có hiệu lực.
    Đọc .tex, bỏ qua commands trong comment/verbatim đúng ngữ cảnh; không strip phần sau escaped percent.
    Không lấy file đầu tiên khi nhiều candidate. Nếu không thể chọn có bằng chứng -> ValueError;
    gather_version bắt và chuyển ROOT_UNRESOLVED/failed. Giữ ambiguity trong diagnostic, không đoán tên main.tex.
    Kiểm: không root, nhiều root, documentclass trong comment, root ở thư mục con.
    """
    raise NotImplementedError("M2 prototype: gather.find_root — Khánh / KH2")


def read_source(source_dir: Path, relative_path: str) -> tuple[str, SourceFile]:
    """Đọc bytes chỉ dưới source root, không theo symlink/đường dẫn thoát root.
    Chốt decode UTF-8-SIG trước, fallback Latin-1 strict để không mất bytes; ghi encoding + hash bytes gốc.
    Không errors=ignore/replace. SourceSpan offsets tính theo chuỗi decode này (BOM đã bỏ), không bytes.
    Chỉ phục vụ .tex/.bib theo contract; file .bbl thiếu phải đi đường diagnostic bibliography.
    Không đổi source; trả cả text và SourceFile để Nguyên áp dụng đúng decoding độc lập.
    """
    raise NotImplementedError("M2 prototype: gather.read_source — Khánh / KH2")


def expand_includes(version: VersionInput, root_path: str) -> GatherResult:
    """Theo input/include bắc cầu theo thứ tự; include lặp hợp lệ phải xuất hiện lại.
    Dùng recursion stack để chặn cycle, không dùng visited-set toàn cục làm mất lần include sau.
    Resolve path theo thư mục source root như TeX; hỗ trợ relative-to-includer chỉ như fallback có diagnostic nếu root path không có.
    Nếu cả hai khác nhau có thể tồn tại, root-relative ưu tiên; ghi ca này trong tests và báo cáo.
    Không theo commented commands, xử lý balanced braces; macro path không giải được -> diagnostic.
    Flatten bằng cách thay command include bằng nội dung file; giữ newline phân cách chống dính token.
    Mỗi đoạn copied có SourceSpan [start,end)/[flat_start,flat_end); đoạn newline tổng hợp không cần fake span.
    Ghi source_files duy nhất theo path; source_map giữ mọi lần xuất hiện.
    Giữ khai báo bibliography trong latex và bib_paths; KHÔNG flatten .bib/.bbl vào body.
    Thiếu include/cycle -> partial nếu còn body tin cậy; không đủ body -> failed. Không catch tất cả rồi ready.
    Root/includes chỉ là bước gather, ready chưa có nghĩa pipeline parsed.
    """
    raise NotImplementedError("M2 prototype: gather.expand_includes — Khánh / KH2")


def gather_version(version: VersionInput) -> GatherResult:
    """API chính. no_tex -> latex rỗng/root None/empty_no_tex; blocked -> blocked_input.
    tex -> find_root rồi expand_includes; aggregate diagnostics đầu vào, không làm mất version.
    Phát hiện bibliography/bbl declarations kể cả file không tồn tại; BibliographyLocation.exists=False.
    Không cleanup, split sentence hoặc convert bibitem ở đây. Không import hierarchy/bibliography.
    Kiểm tay source_map: chọn đoạn sau include và lần include lặp, mở file/path/range tương ứng.
    Test S1/S8/S9, so flattened order với TeX gốc trước khi bàn giao Khang/Nguyên.
    """
    raise NotImplementedError("M2 prototype: gather.gather_version — Khánh / KH2")

