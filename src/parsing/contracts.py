"""Hợp đồng M2 v1 — Danh quản lý; mọi owner phải dùng nguyên schema này.

Chỉ types/constants, không đọc file, không chạy parser, không import owner modules.
Đọc docstring của từng type bên dưới và của prototype đang triển khai.
Quy ước chung: Python >=3.11; dataclass keyword-only tại mọi ranh giới owner.
Tests import src.parsing; notebook thêm <repo>/src và import parsing. Không trộn
hai kiểu import trong một process. Nội bộ không thay typed objects bằng dict/pandas.
Raw nhận m2-input-1.0 từ notebook prepare; working output m2-working-1.0.
Khánh: inputs/gather/metrics; Khang: hierarchy/sentences; Nguyên: bibliography/
reference_dedup; Danh: normalize/content_dedup/validation/serialization/pipeline/
benchmark. Owner chỉ sửa module/tests của mình. contracts và fixtures do Danh quản lý.
JSON/hash canonical: UTF-8, ensure_ascii=False, sort_keys=True, allow_nan=False,
separators=(',', ':'); None -> JSON null. Scratch/output thật dưới data/ ngoài Git.
Chưa chọn thư viện LaTeX/BibTeX; owner thử private implementation và báo dependencies
cho Danh ghép requirements một lần. Không tự thay public signatures/schema.
Dataclasses không tự validate; validation.py phải kiểm invariant trước export.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CONTRACT_VERSION = "m2-contract-1.0"
OUTPUT_SCHEMA_VERSION = "m2-working-1.0"
NORMALIZATION_VERSION = "cleanup_v1+math_v1+component_content_v1+identity_v1"
NodeKind = Literal["document", "heading", "paragraph", "itemize", "item", "sentence", "block_formula", "figure"]
SourceStatus = Literal["tex", "no_tex", "blocked"]
VersionStatus = Literal["parsed", "empty_no_tex", "partial", "failed", "blocked_input"]
GatherStatus = Literal["ready", "partial", "failed", "empty_no_tex", "blocked_input"]
NODE_KINDS: tuple[str, ...] = ("document", "heading", "paragraph", "itemize", "item", "sentence", "block_formula", "figure")
VERSION_STATUSES: tuple[str, ...] = ("parsed", "empty_no_tex", "partial", "failed", "blocked_input")
TABLE_COLUMNS = {
    "elements": ("element_id", "arxiv_id", "kind", "content"),
    "hierarchy": ("arxiv_id", "version", "element_id", "parent_id"),
    "bibtex": ("arxiv_id", "citation_key", "entry_type", "title", "authors", "year", "doi", "journal", "url"),
}


@dataclass(frozen=True, kw_only=True)
class ParseConfig:
    """Cấu hình immutable do Danh truyền toàn pipeline. strict chỉ điều khiển publish,
    không đổi cách tính status. normalization_version gồm cleanup/math/component/identity.
    Run thật phải ghi code_revision thực tế, không dùng unrecorded. review path ngoài Git;
    None nghĩa chưa có quyết định review ngoài. RAM interval tính bằng giây, phải >0.
    """
    normalization_version: str = NORMALIZATION_VERSION
    strict: bool = True
    reference_review_path: Path | None = None
    # Danh truyền revision thực tế; không dùng placeholder khi xuất run thật.
    code_revision: str = "unrecorded"
    ram_sample_interval_seconds: float = 0.1


@dataclass(kw_only=True)
class SourceSpan:
    """Vị trí nguồn [start,end) zero-based theo Unicode characters sau decode, KHÔNG bytes.
    path là POSIX relative tới source_dir của version, không tới file include đang gọi.
    Decode bytes UTF-8-SIG strict trước, Latin-1 strict fallback; không normalize newlines.
    flat_start/end cùng quy ước trong GatherResult.latex; cả hai None với .bib ngoài luồng.
    Mỗi lần include lặp có flat range riêng. Newline tổng hợp không giả thành source span.
    Sau normalize vẫn trỏ raw gốc, không đổi offsets theo chuỗi đã cleanup.
    """
    path: str
    start: int
    end: int
    flat_start: int | None = None
    flat_end: int | None = None


@dataclass(kw_only=True)
class SourceFile:
    """Một file đã đọc: path relative source root, encoding thực dùng, sha256 bytes gốc.
    UTF-8 BOM có thể bỏ khi decode nhưng hash vẫn gồm BOM. Không errors=ignore/replace.
    """
    path: str
    encoding: str
    sha256: str  # Hash bytes gốc, không phải hash chuỗi decode.


@dataclass(kw_only=True)
class Diagnostic:
    """Lỗi xuyên owner; ValidationIssue là alias của cùng type này.
    version cụ thể hoặc affected_versions xác định versions bị tác động. version=None và
    list rỗng nghĩa toàn publication. path/offset không biết để None, không bịa vị trí.
    Codes chung: SOURCE_MISSING/SOURCE_INTEGRITY/ROOT_UNRESOLVED/INCLUDE_MISSING/
    INCLUDE_CYCLE/INCLUDE_PATH_FALLBACK/UNSUPPORTED_CONTENT/PARSE_FATAL/INVALID_STRUCTURE/
    BIBLIOGRAPHY_MISSING/BIB_ENTRY_UNPARSED/CITATION_UNRESOLVED/KEY_CONFLICT/
    REFERENCE_IDENTITY_REVIEW/FIELD_CONFLICT/OUTPUT_WRITE_FAILED.
    Mất nội dung/citation/identity pending là error; field vốn thiếu có thể warning.
    """
    code: str
    severity: Literal["error", "warning"]
    message: str
    arxiv_id: str
    version: int | None = None
    path: str | None = None
    offset: int | None = None
    affected_versions: list[int] = field(default_factory=list)


# Một kiểu diagnostic duy nhất giữa các owner; tên cũ vẫn import được.
ValidationIssue = Diagnostic


@dataclass(kw_only=True)
class VersionInput:
    """Khánh bàn giao một expected version, không bỏ version thiếu source.
    arxiv_id base ID nguyên gốc (legacy slash giữ nguyên), version int>=1, không bool.
    tex -> source_dir tuyệt đối đã kiểm; no_tex -> có receipt xác minh, có thể giữ empty dir;
    blocked -> source_dir=None + reason/error trong diagnostics. Fingerprint từ prepare,
    không dùng mtime hoặc tự tính lại trên text đã decode. Không sửa raw.
    """
    arxiv_id: str
    version: int
    source_dir: Path | None
    source_status: SourceStatus
    source_fingerprint: str | None
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(kw_only=True)
class PublicationInput:
    """Một publication với TẤT CẢ versions expected, tăng dần và không trùng.
    Snapshot/preparation run phải khớp raw validation hiện tại; corpus_root Path runtime.
    Không chia versions cùng bài qua shards khác nhau. Tên dataset không chứng minh đủ assignment.
    """
    arxiv_id: str
    versions: list[VersionInput]
    snapshot_id: str
    preparation_run_id: str
    corpus_root: Path


@dataclass(kw_only=True)
class BibliographyLocation:
    """Khai báo bibliography trong compilation path, kể cả .bbl/.bib không tồn tại.
    path relative source root; declared_at trỏ lệnh gọi; exists chỉ cho biết file hiện có.
    Không nhập mọi .bib trong folder; missing cần truyền Nguyên xét nguồn thay thế/diagnostic.
    """
    path: str
    kind: Literal["bib", "bbl"]
    declared_at: SourceSpan
    exists: bool


@dataclass(kw_only=True)
class GatherResult:
    """Khánh -> Khang/Nguyên, không cần gọi module consumer để tạo object.
    latex flatten theo thứ tự compile; source_map có mọi occurrence, source_files unique path.
    bib_paths có khai báo typed (không list[str]); .bib/.bbl không flatten thành prose.
    ready là gather xong, không phải pipeline parsed. no_tex/blocked có root None/latex rỗng.
    Root ambiguity/fatal giữ failed; lỗi include còn body tin cậy giữ partial + diagnostics.
    """
    version_input: VersionInput
    root_path: str | None
    latex: str
    source_map: list[SourceSpan]
    bib_paths: list[BibliographyLocation]
    source_files: list[SourceFile]
    status: GatherStatus
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(kw_only=True)
class BibliographyBlock:
    """Khang giữ raw bibliography nguyên văn và spans theo nguồn để Nguyên đọc bibitem.
    Block có thể trải nhiều file. Không nằm trong body nodes; không cắt appendix phía sau.
    """
    raw: str
    source_spans: list[SourceSpan]


@dataclass(kw_only=True)
class RawNode:
    """Một OCCURRENCE trong version, không phải shared element đã dedup.
    Production local_id: root r, còn lại n000001,n000002,... theo preorder ổn định.
    position 0-based unique giữa mọi siblings, root=0; parent_local_id=None chỉ root.
    Heading content chỉ title, heading_level chapter=0/section=1/subsection=2,... kể cả section*.
    Leaf giữ raw text/math/caption/table semantics. paragraph/item/itemize giữ raw component
    đầy đủ và children theo thứ tự; không placeholder rỗng làm mất body. Document Version N root.
    Table kind=figure/subtype=table; inline math trong sentence; display=block_formula.
    Danh cleanup copies, rebuild component bottom-up; source spans vẫn giữ raw gốc.
    """
    local_id: str
    parent_local_id: str | None
    kind: NodeKind
    content: str
    position: int  # 0-based trong siblings; root=0; không phải offset source.
    source_spans: list[SourceSpan] = field(default_factory=list)
    heading_level: int | None = None  # chapter=0, section=1, subsection=2,...
    subtype: str | None = None  # table, align,...; không thêm vào bảng cuối.


@dataclass(kw_only=True)
class VersionTree:
    """Khang -> Danh/Nguyên: occurrence tree riêng version, bibliography tách riêng.
    normalized_with=None trước cleanup, Danh set config version sau normalize thành công.
    no_tex/blocked/failed không có body tin cậy: root None, nodes rỗng, vẫn giữ status/version.
    parsed ở bước hierarchy chỉ tạm; bibliography/cites/validation có thể hạ xuống partial/failed.
    """
    arxiv_id: str
    version: int
    root_local_id: str | None
    nodes: list[RawNode]
    bibliography_blocks: list[BibliographyBlock]
    status: VersionStatus
    source_fingerprint: str | None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    # Khang trả None; Danh set config.normalization_version sau normalize.
    normalized_with: str | None = None


@dataclass(kw_only=True)
class BibEntry:
    """Đúng 9 cột bibtex, không thêm raw/status/provenance vào đây.
    arxiv_id/citation_key nonempty; fields string không biết -> None, authors không biết ->[].
    Authors giữ thứ tự/tên có evidence, không stringify list hay mở rộng initials; year int/None,
    không năm 0. Giữ cả references non-arXiv. Entry hỏng dùng BibOccurrence.entry=None,
    không xuất hàng fake. M3 xuất entry_type dictionary string và authors Arrow list<string>.
    """
    arxiv_id: str
    citation_key: str
    entry_type: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    journal: str | None = None
    url: str | None = None


@dataclass(kw_only=True)
class BibOccurrence:
    """Một lần xuất hiện entry qua version/path, giữ raw kể cả parse hỏng.
    Production ID: <paper-prefix>#bib-vN-<SHA256 canonical JSON object gồm arxiv_id,
    version,source_fingerprint,source_spans(list {path,start,end}),raw_sha256(hash UTF-8 raw)>.
    Không đưa flat ranges vào ID. original_key None nếu chưa đọc được key; entry None khi hỏng.
    authors_complete False cho initials/et al./others/unknown; identity C3 không đoán tên đầy đủ.
    Fixtures có IDs minh họa dựng tay, không phải kết quả algorithm production.
    """
    occurrence_id: str
    arxiv_id: str
    version: int
    entry: BibEntry | None  # None khi entry hỏng, vẫn giữ raw + error.
    original_key: str | None
    source_spans: list[SourceSpan]
    source_fingerprint: str
    raw: str
    authors_complete: bool  # False cho initials/et al./others/unknown.
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(kw_only=True)
class BibliographyExtraction:
    """Nguyên trả wrapper luôn có publication/version, occurrences và diagnostics.
    Rỗng nhưng missing bibliography vẫn có error: không trả list trần làm mất lỗi.
    Unify nhận list wrappers của mọi versions; entries hỏng vẫn giữ raw occurrence.
    """
    arxiv_id: str
    version: int
    occurrences: list[BibOccurrence]
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(kw_only=True)
class IdentityDecision:
    """Bằng chứng merge/keep_separate/pending, dùng cả auto rule và người review.
    Occurrence IDs/fingerprints phải khớp input. Review người cần reviewer/evidence/snapshot
    khớp ReviewFile envelope; auto có reviewer/snapshot None. pending không phải approval.
    Source đổi thì review hết hiệu lực; pipeline hash review file vào checkpoint signature.
    """
    decision_id: str
    arxiv_id: str
    occurrence_ids: list[str]
    # Keys occurrence ID, values fingerprint; phải khớp input trước khi áp dụng.
    source_fingerprints: dict[str, str]
    outcome: Literal["merge", "keep_separate", "pending"]
    rule: str
    evidence: str
    reviewer: str | None  # null cho rule tự động; bắt buộc cho review người.
    input_snapshot_id: str | None
    code_revision: str


@dataclass(kw_only=True)
class FieldConflict:
    """Field values mâu thuẫn của occurrences đã xác định identity.
    values/selected_value là JSON representations để giữ kiểu gốc; resolution ghi policy/evidence.
    Không dùng ưu tiên field để biện minh merge identity mơ hồ/DOI đối nghịch.
    """
    arxiv_id: str
    occurrence_ids: list[str]
    field_name: str
    values: list[str]  # JSON representations của giá trị gốc.
    selected_value: str | None
    resolution: str


@dataclass(kw_only=True)
class UnifiedBibliography:
    """Nguyên -> Danh: unified entries, tuple key map theo VERSION, giữ mọi raw occurrences.
    Runtime map (int version,str old_key)->canonical str; JSON phải đổi thành rows, không str(tuple).
    Key conflict trong cùng version chưa giải không được có map đoán một đích; phát error.
    Canonical/identity details nằm trong reference_dedup.unify_entries docstring.
    """
    arxiv_id: str
    entries: list[BibEntry]
    key_map: dict[tuple[int, str], str]
    occurrences: list[BibOccurrence]
    conflicts: list[FieldConflict] = field(default_factory=list)
    identity_decisions: list[IdentityDecision] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(kw_only=True)
class ElementRow:
    """Bảng elements cuối: chỉ 4 cột này, ID unique trong publication.
    Exact (kind,cleaned content) dùng chung giữa versions; root giữ ID riêng từng version.
    Production IDs quy định trong content_dedup.assemble_publication; không thêm position/status.
    """
    element_id: str
    arxiv_id: str
    kind: NodeKind
    content: str


@dataclass(kw_only=True)
class HierarchyRow:
    """Bảng edges cuối: một row unique (arxiv_id,version,element_id,parent_id).
    parent_id non-null, root không có parent row. IDs cùng publication và tồn tại trong elements.
    Dedup projection có thể nhiều parents/self-edge/cycle; occurrence tree sidecar mới là cây.
    Không thêm order hoặc ép projected graph thành cây để xóa lần lặp hợp lệ.
    """
    arxiv_id: str
    version: int
    element_id: str
    parent_id: str


@dataclass(kw_only=True)
class ElementOccurrence:
    """Sidecar giữ đủ từng lần xuất hiện/order/raw spans, kể cả nhiều lần cùng shared ID.
    Unique (arxiv_id,version,local_id), parent_local_id cùng version; root parent None.
    Dựng lại occurrence tree bằng fields này, không từ hierarchy đã mất multiplicity.
    """
    arxiv_id: str
    version: int
    local_id: str
    parent_local_id: str | None
    element_id: str
    position: int
    source_spans: list[SourceSpan]
    heading_level: int | None = None
    subtype: str | None = None


@dataclass(kw_only=True)
class DedupCount:
    """before total occurrences, after distinct rows trong CÙNG phạm vi kind/publication.
    Root document thống kê riêng, không trộn với body dedup. bibtex before gồm attempted
    occurrences hỏng; báo parse lỗi riêng, không gọi mọi rows giảm là dedup thành công.
    """
    # before/after cùng phạm vi; root tách riêng, không trộn với content dedup.
    kind: str  # NodeKind hoặc "bibtex"
    before: int
    after: int


@dataclass(kw_only=True)
class ParsedPublication:
    """Đầu ra assemble đầy đủ versions + tables + sidecars, chưa được tự coi nghiệm thu.
    Danh finalize_publication set export_ready sau schema/occurrence/citation/diagnostics.
    All-no_tex: ba bảng rỗng, version_states empty_no_tex/root_ids None vẫn có thể export-ready.
    States/root IDs runtime int keys; khi JSON ghi string số, đọc lại phải hydrate về int.
    """
    arxiv_id: str
    elements: list[ElementRow]
    hierarchy: list[HierarchyRow]
    bibtex: list[BibEntry]
    version_states: dict[int, VersionStatus]
    occurrences: list[ElementOccurrence]
    root_ids: dict[int, str | None]
    key_map: dict[tuple[int, str], str]
    bib_occurrences: list[BibOccurrence]
    identity_decisions: list[IdentityDecision]
    conflicts: list[FieldConflict]
    diagnostics: list[Diagnostic]
    counts_before_after: list[DedupCount]
    export_ready: bool = False  # Chỉ finalize_publication mới được set True.


@dataclass(kw_only=True)
class PublicationMeasurement:
    """Số đo một bài của đúng run; wall_seconds=None khi chưa đo, không điền 0.
    used_cache phải tách khi benchmark fresh; versions_expected không phải mẫu số mean/bài.
    Ghi ra CSV kèm run_id/snapshot_id để không trộn measurements các run.
    """
    arxiv_id: str
    versions_expected: int
    wall_seconds: float | None  # Chưa đo -> None, không ghi 0.
    used_cache: bool
    status: Literal["success", "partial", "failed", "blocked"]


@dataclass(kw_only=True)
class ResourceSample:
    """Một sample RSS process tree theo perf_counter elapsed_seconds, bytes chứ không MB.
    Không đọc được -> rss_bytes=None + error, không zero. CSV kèm run_id.
    """
    elapsed_seconds: float
    rss_bytes: int | None
    error: str | None = None


@dataclass(kw_only=True)
class BenchmarkResult:
    """Receipt JSON bằng asdict, publication/sample CSV cùng run_id/snapshot.
    Peak là observed theo interval, không khẳng định peak tuyệt đối. cpu_only_colab cần
    bằng chứng runtime thật; fixture/local smoke không được gắn nhãn Colab benchmark.
    Wall/mean/RSS/final-output boundary nằm trong prototype benchmark_run/measure_output_bytes.
    """
    run_id: str
    snapshot_id: str
    code_revision: str
    environment: dict[str, str]
    wall_seconds: float
    mean_seconds_per_publication: float | None
    observed_peak_rss_bytes: int | None
    final_output_bytes: int
    sample_interval_seconds: float
    publications: list[PublicationMeasurement]
    samples: list[ResourceSample]
    cpu_only_colab: bool


@dataclass(kw_only=True)
class VersionMetric:
    """Một row cho TẤT CẢ expected versions, kể cả empty/blocked/failed.
    error_codes list codes unique liên quan version, export_ready của publication chứa nó.
    CSV kèm run/snapshot, error_codes JSON list trong một cell.
    """
    arxiv_id: str
    version: int
    status: VersionStatus
    error_codes: list[str]
    export_ready: bool


@dataclass(kw_only=True)
class MetricsSummary:
    """Counts/rates sau finalize, đủ 5 status kể cả 0. Mẫu số 0 -> None.
    Không trung bình tỷ lệ shards, không đưa retry cùng publication vào hai lần.
    Công thức cụ thể ở metrics.summarize, output filenames/columns ở write_metrics.
    """
    versions: list[VersionMetric]
    status_counts: dict[str, int]
    publication_count: int
    export_ready_publication_count: int
    parse_success_rate: float | None
    resolved_version_coverage: float | None
    attempt_coverage: float | None
    dedup: list[DedupCount]


@dataclass(kw_only=True)
class ParseRunResult:
    """Kết quả điều phối, không trả tables toàn corpus qua notebook.
    Chỉ success khi mọi expected publication export-ready và output/audit ghi thành công.
    Manifest/metrics paths Path runtime; status partial/failed phải giữ diagnostics thực.
    """
    run_id: str
    snapshot_id: str
    status: Literal["success", "partial", "failed"]
    manifest_path: Path
    metrics_path: Path
    processed_publications: int
    diagnostics: list[Diagnostic]


@dataclass(kw_only=True)
class PublicationRecord:
    """publication.json = asdict của đúng type này, không nhét duplicate tables/raw vào đây.
    version_states/root_ids runtime int keys -> JSON string số; read hydrate lại int.
    Sidecar tables/occurrences/key map/decisions/conflicts/diagnostics ghi file riêng trong
    serialization.write_publication; đây là working schema, không đổi schema bảng đề.
    """
    arxiv_id: str
    version_states: dict[int, VersionStatus]
    root_ids: dict[int, str | None]
    counts_before_after: list[DedupCount]
    export_ready: bool
    contract_version: str = CONTRACT_VERSION
    schema_version: str = OUTPUT_SCHEMA_VERSION


@dataclass(kw_only=True)
class RunPublicationRecord:
    """Một record trong RunManifest cho mọi expected publication, kể cả không publish.
    Paths/hashes relative RUN ROOT, không absolute. working_path/published_path None khi
    chưa có tables hợp lệ; audit_path luôn phải cố ghi. used_cache không được tăng fresh coverage.
    Hash bytes từng artifact dùng kiểm resume/read-back, không chỉ kiểm marker tồn tại.
    """
    arxiv_id: str
    expected_versions: list[int]
    checkpoint_signature: str
    export_ready: bool
    # Relative tới thư mục run; None nếu không ghi được tables, vẫn có audit.
    working_path: str | None
    published_path: str | None
    audit_path: str
    wall_seconds: float | None
    used_cache: bool
    output_sha256: dict[str, str]  # Relative artifact path -> SHA256 bytes.


@dataclass(kw_only=True)
class RunManifest:
    """manifest.json = asdict của đúng type này; một run namespace riêng dưới OUTPUT_ROOT.
    Run bắt đầu in_progress, sau ghi tables/audit/checkpoints/metrics mới chốt status.
    Không đếm output tốt run cũ thành success của input mới. Publications đủ mọi bài expected.
    """
    run_id: str
    snapshot_id: str
    preparation_run_id: str
    code_revision: str
    normalization_version: str
    strict: bool
    review_sha256: str | None
    status: Literal["in_progress", "success", "partial", "failed"]
    publications: list[RunPublicationRecord]
    contract_version: str = CONTRACT_VERSION
    schema_version: str = OUTPUT_SCHEMA_VERSION


@dataclass(kw_only=True)
class CheckpointRecord:
    """Checkpoint chỉ publish sau output/audit/read-back thành công; artifact_path/hash
    relative run root. Signature gồm snapshot/source/config/code/review/contract/schema.
    Resume phải kiểm hashes và hydrate/validate outputs, không chỉ đọc signature marker.
    """
    arxiv_id: str
    run_id: str
    signature: str
    artifact_path: str
    output_sha256: dict[str, str]
    contract_version: str = CONTRACT_VERSION
    schema_version: str = OUTPUT_SCHEMA_VERSION


@dataclass(kw_only=True)
class ReviewFile:
    """JSON review ngoài Git: {schema_version:m2-reference-review-1.0,snapshot_id,decisions:[...]}.
    Mỗi decision đúng IdentityDecision, người review có reviewer/evidence, input_snapshot_id
    trùng envelope. None path -> không có decisions; stale fingerprint/snapshot không được áp dụng.
    """
    snapshot_id: str
    decisions: list[IdentityDecision]
    schema_version: str = "m2-reference-review-1.0"
