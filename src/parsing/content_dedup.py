"""PROTOTYPE — Danh / DA2.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from .contracts import ParsedPublication, UnifiedBibliography, VersionTree


def assemble_publication(trees: list[VersionTree], bibliography: UnifiedBibliography) -> ParsedPublication:
    """API chính, cần >=1 VersionTree cùng publication, version unique; giữ mọi expected version.
    Đòi normalized_with giống nhau và khác None cho trees có nodes; không dedup raw content.
    Sinh IDs publication prefix (dot/slash -> hyphen) + kind + SHA256 canonical JSON [kind,content].
    Root ID riêng '#root-vN'; root không dedup; hash collisions so nội dung thật và xử lý deterministic.
    Exact match theo (kind,content), không fuzzy/cross-paper. Giữ mọi occurrence/position/source spans.
    Projection hierarchy unique theo (arxiv_id,version,element_id,parent_id), không thêm position cột cuối.
    Các occurrences trùng edge giữ trong occurrences sidecar; shared element có thể có nhiều parents.
    Không ép projected graph thành occurrence tree (có thể self-edge/cycle sau dedup); validate tree gốc qua sidecar.
    Root mapping version->ID, empty/blocked root None. Counts before là occurrences, after distinct theo kind;
    bibtex before gồm mọi attempted BibOccurrence kể cả entry hỏng, ghi lỗi riêng; không gọi drop là dedup success.
    Tập hợp bib_occurrences, key_map, decisions/conflicts/diagnostics, export_ready=False cho đến finalize.
    Kiểm S7/S10/S11: cùng câu đổi parent, paragraph đổi body, item đảo thứ tự, repeated sentence trong một version.

    Quy tắc ID chính xác: prefix = arxiv_id.replace('.', '-').replace('/', '-');
    root prefix+'#root-vN'; node khác prefix+'#'+kind+'-'+SHA256(canonical JSON [kind,content]).
    Canonical JSON: ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':').
    Mẫu kiểm tay: v1/v2 câu không đổi chỉ một elements row, vẫn đủ edges/occurrences.
    Dùng make_normalized_tree/make_unified_bibliography trong tests/m2_support/fixtures.py
    để làm độc lập; fixtures IDs là expected minh họa, không ép production theo IDs fixture.
    """
    raise NotImplementedError("M2 prototype: content_dedup.assemble_publication — Danh / DA2")

