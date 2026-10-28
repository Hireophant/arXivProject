"""PROTOTYPE — Nguyên / NG1.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from .contracts import BibliographyExtraction, BibOccurrence, GatherResult, SourceSpan, VersionTree


def parse_bibtex(text: str, *, arxiv_id: str, version: int, path: str, source_fingerprint: str) -> BibliographyExtraction:
    """Đọc .bib multiline/nested braces/quoted strings, @string/concatenation/crossref theo phạm vi có test.
    Dùng parser đã thử hoặc scanner trạng thái; không split dòng/dấu phẩy để chia fields.
    Map author->authors theo tên người/tổ chức, year->int hoặc None; giữ raw + SourceSpan source-only.
    Entry parse hỏng -> BibOccurrence(entry=None) + BIB_ENTRY_UNPARSED, không drop.
    Fields vốn thiếu -> None/[] và warning nếu cần; không tự bịa title/year/type.
    Occurrence ID chứa publication/version/path/span và hash raw ổn định; fingerprint từ input.
    authors_complete=False cho initials/et al./others hoặc chưa chắc; không mở rộng tên.
    Các field ngoài 9 cột có thể giữ trong raw; lỗi unsupported ảnh hưởng trích fields phải nêu rõ.

    Xem công thức occurrence_id chính xác ngay trong contracts.BibOccurrence.
    Test trực tiếp text input không cần gather/hierarchy; source-only span có flat_start/end=None.
    """
    raise NotImplementedError("M2 prototype: bibliography.parse_bibtex — Nguyên / NG1")


def parse_bibitems(raw: str, *, arxiv_id: str, version: int, source_spans: list[SourceSpan], source_fingerprint: str) -> BibliographyExtraction:
    """Chuyển bibitem[optional]{key} trong raw block thành BibOccurrence + BibEntry.
    Tách bằng command có braces cân bằng, trích author/title/year/DOI/journal/URL có evidence.
    Không dùng references.json M1 để bịa nội dung bibitem; giữ raw để người kiểm so lại.
    Span của occurrence phải map về file gốc từ block spans, kể cả block trải nhiều file.
    Key không đọc được giữ original_key=None, entry=None/error. Không tạo key giả rồi báo thành công.
    Câu prose trong bibitem không phải body sentences. Không tự gọi hierarchy hoặc gather để phát triển độc lập.
    """
    raise NotImplementedError("M2 prototype: bibliography.parse_bibitems — Nguyên / NG1")


def extract_entries(gathered: GatherResult, tree: VersionTree) -> BibliographyExtraction:
    """API chính, trả wrapper để giữ lỗi khi không có entry nào.
    Đối chiếu cùng arxiv_id/version; đọc chỉ các bib_paths kind=bib có khai báo, theo cùng decode policy của gather.
    Không import gather.read_source: viết helper private cùng policy hoặc đề nghị Danh tách helper sau tích hợp.
    Gọi parse_bibtex cho .bib và parse_bibitems cho tree.bibliography_blocks; giữ occurrence riêng từng version.
    .bbl thiếu và không có .bib/bibitem thay thế -> BIBLIOGRAPHY_MISSING; không mở toàn folder lấy file thừa.
    No_tex/blocked/failed -> result rỗng có diagnostics đầu vào. Không tạo empty success che bibliography lỗi.
    Nếu không có bibliography/citation thật thì rỗng hợp lệ. Dedup lặp khai báo cùng file trong một version
    chỉ khi cùng source occurrence, không gộp các entries nội dung trùng trước bước unify.
    Kiểm tay 1 .bib, 1 bibitem, nested braces, tên tổ chức, fields thiếu và source gọi .bbl không có.

    Khi test có đọc file, dùng TemporaryDirectory ghi .bib rồi set gathered.version_input.source_dir;
    sentinel /SYNTHETIC-NOT-A-REAL-CORPUS của fixture không phải thư mục để tạo trên máy.
    Trả BibliographyExtraction cả khi [] để downstream vẫn biết missing/error; không sửa tree input.
    """
    raise NotImplementedError("M2 prototype: bibliography.extract_entries — Nguyên / NG1")

