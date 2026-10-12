"""Hợp đồng dữ liệu Milestone 1 — đọc trước khi triển khai bất kỳ module nào.

Chỉ khai báo kiểu, không thực hiện crawler. Python >= 3.11.
TypedDict mô tả dictionary trao đổi, KHÔNG tự kiểm tra dữ liệu lúc chạy.
Khánh: discover; Khang: download; Nguyên: references;
Danh: pipeline, metrics và báo cáo. Hàm nghiệp vụ đều chưa triển khai.

Quy ước: arxiv_id giữ mã gốc, không hậu tố v; version là int >= 1.
Ngày dữ liệu YYYY-MM-DD (UTC), thời điểm log ISO có múi giờ; byte/int,
giây/float. None là chưa biết, không phải 0. Path chỉ dùng ở input;
output JSON chỉ chứa kiểu primitive, đường dẫn tương đối với data_root.
Chuỗi lỗi không được chứa API key. Fixture chỉ để phát triển, không nộp.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, TypedDict


class Scope(TypedDict):
    """mode=ids: ids khác rỗng, start_id/end_id=None.

    mode=range: ids=[], start_id/end_id là mã hiện đại cùng YYMM,
    lấy cả hai đầu. Phạm vi khác phải chuyển thành ids đã xác minh,
    không tự suy diễn. Chưa có phạm vi chính thức của nhóm.
    """

    mode: Literal["ids", "range"]
    ids: list[str]
    start_id: str | None
    end_id: str | None


class HttpPolicy(TypedDict):
    """Cấu hình chung: attempts tính cả lần đầu, timeout > 0.

    Nhịp theo từng dịch vụ; Retry-After có ưu tiên, backoff có trần.
    S2 cần xét cả giới hạn cửa sổ; tốc độ thực tế kiểm tra docs hiện hành.
    Không chứa khóa API; module tự đọc biến môi trường.
    Triển khai đơn giản tuần tự: chờ service delay TRƯỚC mỗi request, kể cả
    request đầu/retry, để không gọi dồn khi chuyển discover -> download -> dates.
    Backoff/Retry-After không được làm thời gian chờ ngắn hơn service delay.
    """

    timeout_seconds: float
    max_attempts: int
    arxiv_delay_seconds: float
    s2_delay_seconds: float
    backoff_cap_seconds: float
    user_agent: str


class PaperMetadata(TypedDict):
    """Nội dung metadata.json: tác giả đầy đủ theo nguồn, không tự đoán venue."""

    arxiv_id: str
    title: str
    authors: list[str]
    submission_date: str
    revised_dates: list[str]
    venue: str | None


class PaperRecord(TypedDict):
    """Một bài đã xác minh: versions tăng dần, duy nhất, bao gồm v1."""

    arxiv_id: str
    versions: list[int]
    metadata: PaperMetadata


class DiscoveryIssue(TypedDict):
    """Mã không tồn tại hoặc chưa xử lý được; không âm thầm bỏ khỏi phạm vi."""

    arxiv_id: str
    status: Literal["not_found", "failed"]
    error: str


class DiscoveryResult(TypedDict):
    """partial nếu còn lỗi; success chỉ khi đã xét hết phạm vi cấu hình.

    papers chỉ chứa bài có metadata và lịch sử phiên bản đã xác minh.
    requested_count đếm mã cần kiểm tra, không phải số bài thực tồn tại.
    not_found đã xác minh không nhất thiết làm scope_complete=False;
    lỗi mạng/chưa xác minh phiên bản bắt buộc scope_complete=False.
    requested_count đếm ID duy nhất; mỗi ID thuộc papers hoặc issues, không cả hai.
    success: complete và không issues. partial: có papers hoặc ít nhất một
    not_found đã xác minh nhưng còn issues. failed: mọi ID thất bại do lỗi
    vận hành, không có kết quả xác minh. All-not-found là partial/complete.
    """

    status: Literal["success", "partial", "failed"]
    scope: Scope
    requested_count: int
    scope_complete: bool
    papers: list[PaperRecord]
    issues: list[DiscoveryIssue]
    elapsed_seconds: float


class DateLookupResult(TypedDict):
    """Mọi ID input có khóa dates; thiếu ngày=None và có lỗi tương ứng."""

    dates: dict[str, str | None]
    errors: dict[str, str]


DateLookup = Callable[[list[str]], DateLookupResult]


class DownloadResult(TypedDict):
    """Một phiên bản: success cần có nguồn TeX đã kiểm tra; no_tex không là lỗi mạng.

    Trước/sau lọc đều chưa nén; archive_bytes là số riêng. used_cache=True
    không được trộn với benchmark tải mới. failed không đè nguồn hợp lệ cũ.
    Các byte/file chưa xác định là None, không phải 0.
    """

    arxiv_id: str
    version: int
    status: Literal["success", "no_tex", "failed"]
    source_bytes_before: int | None
    source_bytes_after: int | None
    archive_bytes: int | None
    file_count: int | None
    elapsed_seconds: float
    attempts: int
    used_cache: bool
    error: str | None


class ReferenceMetadata(TypedDict):
    """Giá trị references.json. Thiếu title/authors/submission_date/S2 ID -> partial.

    publication_date tùy chọn về mặt nội dung nhưng khóa luôn có, có thể None.
    publication_date=None KHÔNG làm tăng incomplete_references.
    Ngày xuất bản không thay ngày gửi. Không tự mở rộng tên tác giả viết tắt.
    """

    title: str | None
    authors: list[str]
    submission_date: str | None
    semantic_scholar_id: str | None
    publication_date: str | None


class ReferenceResult(TypedDict):
    """total_references trước lọc; kept_references=len(references).

    API lỗi/not_found: total=None, references={}, kept=0, KHÔNG ghi đè file cũ.
    success với {} chỉ khi xác minh danh sách hợp lệ (có thể không có arXiv).
    partial nếu thiếu trang, thiếu trường, hoặc xung đột metadata chưa giải quyết.
    """

    arxiv_id: str
    status: Literal["success", "partial", "not_found", "failed"]
    references: dict[str, ReferenceMetadata]
    total_references: int | None
    kept_references: int
    missing_submission_dates: int
    incomplete_references: int
    pagination_complete: bool
    retrieved_at: str
    elapsed_seconds: float
    attempts: int
    used_cache: bool
    error: str | None


class SourceReceipt(TypedDict):
    """Khang ghi sources/.vN.receipt.json sau commit nguồn, ngoài thư mục vN.

    files_sha256: đường dẫn tương đối trong vN -> SHA-256 mọi file đã giữ.
    Cache cần đúng ID/version/schema, danh sách file và hash; không chỉ exists.
    no_tex cần xác minh loại nguồn và result tương ứng, không suy từ dir rỗng.
    Receipt không tính vào số byte/file nguồn, nhưng tính vào dung lượng đĩa.
    """

    schema_version: Literal["1.0"]
    arxiv_id: str
    version: int
    source_url: str
    source_kind: str
    result: DownloadResult
    files_sha256: dict[str, str]


class ReferenceReceipt(TypedDict):
    """Nguyên ghi .references_receipt.json cạnh references.json, sau file dữ liệu.

    references_sha256 là hash byte file UTF-8 đã lưu; cache chỉ success, đúng
    ID/schema/hash và schema nội dung. Giữ retrieved_at gốc khi dùng cache.
    """

    schema_version: Literal["1.0"]
    arxiv_id: str
    result: ReferenceResult
    references_sha256: str


class PaperState(TypedDict):
    """Khóa downloads là str(version) để round-trip JSON không đổi kiểu khóa.

    None = chưa chạy. Nếu chương trình ngắt giữa chừng, output đã ghi phải được
    xác minh lại trước khi tái sử dụng, không chỉ dựa vào manifest cũ.
    """

    record: PaperRecord
    metadata_path: str
    downloads: dict[str, DownloadResult | None]
    references: ReferenceResult | None
    elapsed_seconds: float | None


class Manifest(TypedDict):
    """Chỉ pipeline ghi manifest; keys papers giữ ID gốc, path nằm trong data_root."""

    schema_version: Literal["1.0"]
    run_id: str
    scope: Scope
    discovery: DiscoveryResult | None
    papers: dict[str, PaperState]
    updated_at: str


class ResourceSample(TypedDict):
    """Một mẫu: RSS tổng process tree (tránh đếm PID trùng), dung lượng data_root.

    Dùng lấy mẫu trong lúc chạy; đỉnh đo là đỉnh quan sát được, báo tần suất.
    """

    elapsed_seconds: float
    ram_bytes: int
    disk_bytes: int


class BenchmarkResult(TypedDict):
    """Benchmark toàn hệ thống. samples=[] -> RAM/đỉnh đĩa=None, không tự điền 0."""

    environment: str
    cpu_only: bool
    cache_mode: Literal["cold", "resume", "mixed"]
    sampling_interval_seconds: float
    wall_seconds: float
    ram_peak_bytes: int | None
    ram_mean_bytes: float | None
    disk_peak_bytes: int | None
    final_disk_bytes: int


class CorpusSummary(TypedDict):
    """Mẫu số: paper_success_rate=full_source_papers/papers_discovered.

    full_source_papers cần mọi phiên bản success, no_tex đếm riêng, không giấu.
    source_coverage_rate=(success+no_tex)/versions_expected, chỉ độ phủ xử lý.
    reference_success_rate=reference_jobs_success/papers_discovered.
    Trung bình tham khảo dùng job pagination_complete có total đã biết.
    average_reference_completeness_rate: trung bình (kept-incomplete)/kept
    trên các job đủ trang và kept>0. Đếm đầy đủ metadata bắt buộc, không phải
    độ chính xác của trích dẫn hay tỷ lệ tham khảo có mặt trên Semantic Scholar.
    Trung bình byte trước/sau dùng cùng tập version có đủ cả hai số đo.
    Mẫu số 0 -> None. Statistics không đồng nghĩa quét đủ phạm vi.
    """

    papers_discovered: int
    full_source_papers: int
    versions_expected: int
    versions_success: int
    versions_no_tex: int
    versions_failed: int
    versions_pending: int
    reference_jobs_success: int
    reference_jobs_partial: int
    reference_jobs_failed: int
    reference_jobs_not_found: int
    reference_jobs_pending: int
    paper_success_rate: float | None
    source_coverage_rate: float | None
    reference_success_rate: float | None
    average_reference_count: float | None
    reference_count_denominator: int
    average_reference_completeness_rate: float | None
    reference_completeness_denominator: int
    average_source_bytes_before: float | None
    average_source_bytes_after: float | None
    source_size_denominator: int
    average_paper_source_bytes_before: float | None
    average_paper_source_bytes_after: float | None
    paper_size_denominator: int
    average_paper_processing_seconds: float | None
    paper_time_denominator: int


class RunResult(TypedDict):
    """Trạng thái toàn run không dùng để suy ra đủ dữ liệu khi scope còn lỗi."""

    status: Literal["success", "partial", "failed"]
    run_id: str
    manifest_path: str
    metrics_path: str
    summary: CorpusSummary
    benchmark: BenchmarkResult


class DiscoverCallable(Protocol):
    """Khuôn KIỂU HÀM discovery, không phải hàm mock hay crawler.

    Hàm được truyền vào pipeline phải nhận scope và keyword policy, trả
    DiscoveryResult. Thường dùng discover_papers thật; nếu nhóm viết hàm giả
    để kiểm tra, hàm giả cũng phải có chữ ký này. Không tạo instance lớp này.
    """

    def __call__(self, scope: Scope, *, policy: HttpPolicy) -> DiscoveryResult:
        """Chỉ prototype chữ ký dependency, không xử lý."""
        raise NotImplementedError


class DatesCallable(Protocol):
    """Khuôn kiểu hàm tra ngày: ids + keyword policy -> DateLookupResult.

    Không gọi API, không cung cấp dữ liệu giả. partial gắn policy vào hàm thật
    để người 3 chỉ cần gọi date_lookup(ids), phù hợp kiểu DateLookup.
    """

    def __call__(self, ids: list[str], *, policy: HttpPolicy) -> DateLookupResult:
        """Chỉ prototype chữ ký dependency, không xử lý."""
        raise NotImplementedError


class DownloadCallable(Protocol):
    """Khuôn kiểu hàm tải nguồn, không thực hiện tải hay giả lập kết quả.

    Quy định ID, version, Path và các keyword policy/use_cache -> DownloadResult.
    Pipeline nhận download_version thật hoặc hàm giả cùng khuôn khi kiểm tra.
    """

    def __call__(
        self, arxiv_id: str, version: int, version_dir: Path, *,
        policy: HttpPolicy, use_cache: bool = True,
    ) -> DownloadResult:
        """Chỉ prototype chữ ký dependency, không xử lý."""
        raise NotImplementedError


class ReferencesCallable(Protocol):
    """Khuôn kiểu hàm lấy tham khảo, không phải mock Semantic Scholar.

    Quy định ID, Path, DateLookup và policy/use_cache -> ReferenceResult.
    Hàm thật hay hàm giả dùng để kiểm tra đều phải tuân theo chữ ký này.
    """

    def __call__(
        self, arxiv_id: str, paper_dir: Path, date_lookup: DateLookup, *,
        policy: HttpPolicy, use_cache: bool = True,
    ) -> ReferenceResult:
        """Chỉ prototype chữ ký dependency, không xử lý."""
        raise NotImplementedError
