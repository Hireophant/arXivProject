"""PROTOTYPE — Danh / DA3 — định dạng chung, owner khác không tự viết format riêng.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import IdentityDecision, ParsedPublication


def write_publication(publication: ParsedPublication, destination: Path) -> list[Path]:
    """Ghi working format mô tả trực tiếp bên dưới bằng staging sibling + atomic publish.
    Elements/hierarchy/bibtex JSONL chỉ đúng cột TABLE_COLUMNS; Path/tuple keys không lọt vào JSON.
    Sidecars: publication.json, occurrences.jsonl, bib_occurrences.jsonl, citation_key_map.json,
    identity_decisions.json, conflicts.json, diagnostics.jsonl. Kèm contract/output schema + counts/root/status.
    Working partial hợp lệ được ghi; rows schema hỏng không được ghi. strict publish do pipeline quyết định.
    Không ghi raw source vào output tables; giữ spans/fingerprint. Không ghi vào preparationM2.
    Ghi lỗi không thay output tốt trước; chỉ replace sau đọc lại kiểm round-trip; destination phải owned.
    Test ngắt giữa write, duplicate rerun, read-back equality, Unicode/null/authors list.

    Định dạng cụ thể trong destination (đúng folder một publication, không tự thêm run):
    publication.json = asdict(PublicationRecord), các tables mỗi row asdict đúng TABLE_COLUMNS.
    occurrences.jsonl = ElementOccurrence; bib_occurrences.jsonl = BibOccurrence; diagnostics.jsonl = Diagnostic.
    identity_decisions.json/conflicts.json = lists typed objects. citation_key_map.json =
    {schema_version:'m2-working-1.0', arxiv_id, rows:[{version:1,old_key:'x',canonical_key:'y'}]}.
    Rows key-map sort (version,old_key); tuyệt đối không JSON stringify tuple làm key.
    JSON UTF-8 ensure_ascii=False/sort_keys=True/allow_nan=False; JSONL file rỗng hợp lệ.
    publication.json state/root keys ghi string số, đọc về int; None null, authors list không stringify.
    M3 chuyển kind/entry_type dictionary-encoded Parquet, authors list<string>, year nullable int;
    không bắt owner cài pyarrow lúc prototype. Không thêm field ngoài bảng đề.
    Kiểm tay mở JSON của một bài hai versions, so authors/year null/key-map/root/status rồi đọc lại.
    """
    raise NotImplementedError("M2 prototype: serialization.write_publication — Danh / DA3 — định dạng chung, owner khác không tự viết format riêng")


def read_publication(destination: Path) -> ParsedPublication:
    """Đọc đúng schema m2-working-1.0, hydrate nested dataclasses; không trả dict tùy ý.
    Đọc citation_key_map list rows về tuple keys, version_states/root_ids keys về int.
    Đối chiếu publication identity các file, không parse lại TeX. Contract/schema unknown -> ValueError.
    Caller kiểm input/config/code cache signature ngoài publication record trước khi dùng cache.
    """
    raise NotImplementedError("M2 prototype: serialization.read_publication — Danh / DA3 — định dạng chung, owner khác không tự viết format riêng")


def read_review_decisions(path: Path | None, *, snapshot_id: str) -> list[IdentityDecision]:
    """None -> []; file có schema m2-reference-review-1.0 và snapshot_id phải khớp run.
    Đọc decisions thành typed objects; reviewer/evidence bắt buộc cho quyết định người.
    Outcome pending không được dùng như approved; malformed/duplicate decision IDs -> ValueError.
    Source fingerprint/occurrence matching còn được Nguyên kiểm khi unify; không chấp nhận review stale.
    Hash bytes file review phải tham gia cache key trong pipeline, kể cả khi path đổi mà nội dung giống.

    Envelope đúng ReviewFile; từng IdentityDecision.input_snapshot_id trùng envelope cho review người.
    Chưa có reviewers thật không bịa tên/xác nhận; quyết định auto giữ reviewer=None.
    """
    raise NotImplementedError("M2 prototype: serialization.read_review_decisions — Danh / DA3 — định dạng chung, owner khác không tự viết format riêng")

