"""PROTOTYPE — Danh / DA2.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from .contracts import ParsedPublication, ValidationIssue


def validate_publication(publication: ParsedPublication) -> list[ValidationIssue]:
    """API chỉ đọc: kiểm schema đúng cột/types/nullability, unique IDs/keys và foreign keys cùng publication.
    Kiểm root_ids/version_states phủ cùng tập; occurrence tree mỗi version có một root, parent hợp lệ,
    không cycle, position siblings unique; every node reachable và kind leaf đúng sentence/formula/figure.
    Không cấm projected hierarchy nhiều parent/self-edge/cycle nếu occurrence tree đúng sau dedup.
    Đối chiếu projection edges với occurrences/root; không đòi root có parent row.
    Cite sau normalize map được vào bibtex; key collision/entry chưa parse/missing bibliography phải là error.
    Kiểm normalized semantics/counts khi có evidence; không giả vờ đảm bảo accuracy chỉ bằng schema.
    Bổ sung diagnostics mới, không lặp lại toàn bộ errors sẵn có để counts nhân đôi.
    Không tự sửa row hỏng, không set parsed/export_ready ở hàm này.
    """
    raise NotImplementedError("M2 prototype: validation.validate_publication — Danh / DA2")


def finalize_publication(publication: ParsedPublication) -> ParsedPublication:
    """Trả COPY sau validate_publication, merge/dedup diagnostics và tính status cuối theo kế hoạch 9.3.
    Giữ empty_no_tex/blocked_input. Version có body tin cậy + lỗi include/bib/cite/identity -> partial;
    root/body/schema/occurrence integrity hỏng -> failed. Error không định vị version chặn cả publication có TeX.
    Field vốn thiếu hoặc field conflict đã giải có evidence -> warning; không hạ error để tăng success.
    export_ready=True chỉ khi mọi expected version parsed/empty_no_tex và không error publication/schema.
    All-no_tex hợp lệ có ba bảng rỗng và export_ready=True. Strict không ảnh hưởng status; pipeline chọn publish.
    Test S13 với cùng input strict True/False phải có cùng status.
    """
    raise NotImplementedError("M2 prototype: validation.finalize_publication — Danh / DA2")

