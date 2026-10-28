"""PROTOTYPE — Nguyên / NG2, NG3.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from .contracts import BibliographyExtraction, BibOccurrence, IdentityDecision, UnifiedBibliography


def unify_entries(arxiv_id: str, extractions: list[BibliographyExtraction], *, review_decisions: list[IdentityDecision] | None = None) -> UnifiedBibliography:
    """API chính. Nhận TẤT CẢ extractions của mọi versions, giữ diagnostics kể cả extraction rỗng lỗi.
    Giữ mọi BibOccurrence (entry=None cũng giữ); entries output chỉ chứa entry có cấu trúc hợp lệ.
    Áp dụng C3 kế hoạch: DOI chung mạnh; thiếu DOI chỉ auto-merge title chuẩn + full ordered authors + year bằng.
    Không merge theo key/title gần nghĩa; kiểm toàn cluster tránh B thiếu DOI nối DOI X và Y khác nhau.
    Candidate thực sự mơ hồ -> REFERENCE_IDENTITY_REVIEW error + pending decision; không coi mọi entry thiếu DOI là lỗi.
    Đọc/kiểm review source fingerprints, occurrence IDs, arxiv_id; review pending hoặc cũ không được auto áp dụng.
    Pipeline kiểm snapshot; hàm này vẫn kiểm fingerprint/occurrences với input nhận được.
    Chọn canonical key ổn định: key nhỏ nhất theo Unicode lexical trong cluster; collision giữa clusters thì suffix
    '__' + full SHA256 canonical JSON [arxiv_id, sorted(occurrence_ids)] của cluster; nếu collision hash kiểm nội dung và mở rộng suffix, không dùng Python hash().
    Union nonmissing fields; conflict chọn DOI-consistent rồi nhiều fields hơn rồi version sớm hơn, tie occurrence_id.
    Giữ FieldConflict/IdentityDecision với raw evidence; metadata thiếu -> warning, không đổi null thành năm 0.
    Map (version, original_key)->canonical_key; key collision trong một version mơ hồ thì KHÔNG thêm map cho key đó,
    phát KEY_CONFLICT error gắn mọi versions affected. Entries non-arXiv vẫn giữ.
    Output không rewrite tree; Danh dùng key_map. Test S6/S9/S12 và input đảo thứ tự cho cùng kết quả.
    """
    raise NotImplementedError("M2 prototype: reference_dedup.unify_entries — Nguyên / NG2, NG3")

