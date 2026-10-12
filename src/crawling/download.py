"""Khang: tải nguồn từng phiên bản và giữ nguồn văn bản cho Milestone 2.

Chỉ prototype; không gọi discovery, không ghi manifest/metadata/references.
API nhận ID/version trực tiếp nên dùng fixture làm độc lập được.
"""

from pathlib import Path

from . import DownloadResult, HttpPolicy


def download_version(
    arxiv_id: str, version: int, version_dir: Path, *, policy: HttpPolicy,
    use_cache: bool = True,
) -> DownloadResult:
    """Input: ID gốc, version>=1, thư mục riêng, policy và cờ dùng cache.

    Output: DownloadResult; ghi nguồn hợp lệ vào version_dir, giữ thư mục con.
    Cách làm: tải mã có v từ mirror trong đề; timeout/retry/pacing; kiểm tra
    nội dung thật thay vì đuôi file; dùng prepare_source trong thư mục tạm.
    Giữ tex/bib/bbl/sty/cls và văn bản liên quan, không đổi nội dung/lệnh hình.
    Chỉ thay output sau xác minh; cache cũng phải xác minh, attempts=0 khi dùng.
    Cache theo SourceReceipt trong __init__.py: sources/.vN.receipt.json.
    Thiếu/sai receipt/hash/danh sách file -> tải lại, không dùng tồn tại dir làm bằng chứng.
    download_version sở hữu receipt; prepare_source không ghi receipt mạng.
    use_cache=False buộc tải mới; cache trả thời gian hiện tại và used_cache=True.
    PDF/Word-only xác minh -> no_tex và bản ghi phiên bản rỗng; HTTP/mạng lỗi
    -> failed, không phải no_tex. Không ghi đè nguồn tốt cũ khi thất bại.
    Byte trước/sau đều chưa nén, elapsed gồm chờ; thông tin chưa đo được=None.
    Raises ValueError cho input sai; lỗi vận hành trả failed, error không chứa key.
    """
    raise NotImplementedError("Khang triển khai download_version.")


def prepare_source(
    source_path: Path, version_dir: Path, *, arxiv_id: str, version: int,
) -> DownloadResult:
    """Input: gói/văn bản tải sẵn, output dir và danh tính phiên bản.

    Output: cùng DownloadResult, attempts=0, used_cache=False (xử lý local,
    không phải benchmark tải mới); elapsed chỉ xử lý local. Caller tải mạng
    phải thay attempts/elapsed/used_cache đúng toàn tác vụ khi trả kết quả.
    Cách làm: nhận diện tar, gzip đơn, TeX đơn, PDF/khác; giải nén an toàn,
    chặn traversal, symlink/hardlink và giới hạn dung lượng bung nén; lọc ảnh
    nhị phân, giữ text kể cả các file không có đuôi quen thuộc khi phù hợp.
    Đo source_bytes_before trước lọc và source_bytes_after sau lọc; không dùng
    archive_bytes thay byte chưa nén. Đầu vào hỏng -> failed; xác minh không
    có TeX -> no_tex. Đầu vào không có/dir không hợp lệ -> ValueError.
    Không gọi mạng; nhóm có thể kiểm tra bằng gói giả lập độc lập Khánh.
    """
    raise NotImplementedError("Khang triển khai prepare_source.")
