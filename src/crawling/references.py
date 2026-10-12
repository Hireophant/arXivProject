"""Nguyên: lấy references.json từ Semantic Scholar cho từng bài chính.

Chỉ prototype. Không cần input nguồn LaTeX; không tải nguồn của bài được dẫn.
Ngày gửi bổ sung qua DateLookup của Khánh; dùng fixture cùng kiểu để thử.
"""

from pathlib import Path

from . import DateLookup, HttpPolicy, ReferenceResult


def collect_references(
    arxiv_id: str, paper_dir: Path, date_lookup: DateLookup, *,
    policy: HttpPolicy, use_cache: bool = True,
) -> ReferenceResult:
    """Input: mã bài chính, thư mục bài, hàm tra ngày, HTTP policy/cache.

    Output: ReferenceResult; ghi references.json bằng result['references']
    khi có phản hồi hợp lệ, ghi nguyên tử và không đè dữ liệu tốt bằng lỗi.
    Cách làm: gọi S2 paper/references hoặc batch theo docs hiện hành; lấy hết
    trang, title/authors/paperId/externalIds/publicationDate. Giữ mục có arXiv;
    khóa mã mới đổi '.' thành '-', mã cũ giữ nguyên. Gộp mục API trùng theo ID,
    ghi xung đột; không làm dedup BibTeX của Milestone 2. Bổ sung ngày qua
    date_lookup(ids); thiếu trường -> partial và đếm incomplete_references.
    API key tùy chọn đọc S2_API_KEY; không đưa vào notebook/log/output.
    429: Retry-After/backoff có giới hạn; không biến lỗi thành danh sách rỗng.
    not_found tách biệt failed; total=None khi chưa biết. Danh sách thật rỗng
    có thể success. Không mặc định S2 phân biệt từng phiên bản bài chính.
    retrieved_at là timestamp UTC. Raises ValueError nếu ID/config sai.
    Cache theo ReferenceReceipt trong __init__.py: .references_receipt.json.
    Thiếu/sai hash/schema/ID hoặc status partial -> truy vấn lại; cache hợp lệ
    trả attempts=0, used_cache=True, elapsed của lần gọi này, retrieved_at giữ gốc.
    Thiếu publication_date không tính incomplete; bốn trường bắt buộc thì có.
    total_references đếm số mục API trước lọc/gộp khi đủ trang; chưa đủ trang
    và chưa có total đáng tin -> None. incomplete đếm số reference thiếu >=1
    trường bắt buộc (không cộng số trường thiếu); missing_dates là tập con.
    """
    raise NotImplementedError("Nguyên triển khai collect_references.")
