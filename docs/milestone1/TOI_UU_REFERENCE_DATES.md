# Tối ưu ngày v1 của references — 20/10/2026

## Luồng và giới hạn Milestone 1

Discovery của bài được giao vẫn dùng OAI-PMH `GetRecord/arXivRaw` hiện tại: metadata, mọi version, ngày v1 và tất cả revised dates. Tải source riêng từng version, giữ nguyên `.tex`/`.bib`, giữ record `no_tex`. References vẫn phải lấy qua Semantic Scholar và đủ mọi trang; giữ mọi row local, chỉ pool arXiv vào bảng matching. Không lấy snapshot Kaggle làm bằng chứng rằng đã có đủ versions mới nhất của bài được giao.

Riêng ngày v1 references: ưu tiên OAI discovery đã có trong phiên → memory/persistent cache đã xác minh → index Cornell Kaggle local → OAI cho ID thiếu/lỗi. Không thay ngày v1 bằng `update_date`, năm hay Semantic Scholar `publicationDate`. Chọn version có **nhãn v1**, chuẩn hóa múi giờ UTC, giữ ID dạng chuỗi và ID legacy.

`dates.py` đọc JSONL từng dòng hoặc đọc đúng metadata member bên trong ZIP, xây SQLite chỉ gồm ID/created-v1. ID duplicate hoặc có record sai bị loại để fallback OAI; thống kê rejected rows được lưu. Không nạp toàn bộ JSON vào pandas. Snapshot chỉ chứa metadata; không thay source hay references S2.

## Chuyển từ phiên bản cũ

1. Để phiên đang chạy hoàn tất và xác nhận backup; không thay module giữa phiên.
2. Khi source mới đã có trên GitHub, mở notebook mới và runtime Colab CPU mới. Notebook bản sao/checkout đang mở không tự cập nhật. Nếu dùng source local, upload cả thư mục `src`, không chỉ notebook.
3. Giữ nguyên `DRIVE_BACKUP_DIR`, `SELECTED_MEMBER`, assignment và `retry-state/member-N.json`. Giữ mọi ZIP/receipt cũ. Không reset queue hoặc chuyển corpus cũ sang root mới bằng tay.
4. Lần đầu đặt `NEW_PAPERS_PER_SESSION=1`. Giữ hybrid/Kaggle bật, cấp quyền Drive trước crawl rồi Run All.
5. Kiểm `Completed`, audit, checkpoint/backup VERIFIED và pending. Lượt sau tăng số ID mới. Completed cũ vẫn được planner bỏ qua; pending được khôi phục từ backup đã xác minh.

Không sửa Drive thật hoặc ZIP gốc khi kiểm thử nâng cấp. Code đọc manifest/source/reference schema 3.0 cũ; reference source mới `kaggle-cache/oai-v1` được mở rộng trong hợp đồng, không đổi cột dữ liệu xuất. Code cũ chỉ hiểu OAI **không đọc được receipt hybrid mới**: sau chuyển đổi phải dùng trọn bộ source mới cho crawl/analyze/restore/report.

## Cấu hình notebook

```python
USE_HYBRID_REFERENCE_DATES = True
USE_KAGGLE_REFERENCE_DATES = True
AUTO_DOWNLOAD_KAGGLE = IN_COLAB
KAGGLE_SNAPSHOT_PATH = None
REFRESH_KAGGLE_INDEX = False
V1_CACHE_MAX_AGE_DAYS = 365
V1_CACHE_DIR = None  # Chỉ override bằng đường dẫn mới/rỗng cho cold benchmark.
```

Lần đầu: Colab tự tải public metadata ZIP Cornell, xây index trên ổ local, copy/hash-verify lên Drive và publish `current.json` cuối cùng. Bước chuẩn bị có thể lâu và cần dung lượng cho ZIP + index; ZIP tải tự động được xóa sau build. Lần sau chỉ copy/hash-verify index về local. Không mở SQLite trực tiếp trên mounted Drive. Index cũ không bị ghi đè: mỗi build có tên riêng, pointer được thay sau khi copy thành công.

Nếu Kaggle yêu cầu đăng nhập hoặc lỗi mạng, bước chuẩn bị dừng, không âm thầm chuyển sang crawl OAI chậm. Có thể tải snapshot từ trang Cornell bằng trình duyệt rồi đặt `KAGGLE_SNAPSHOT_PATH` tới JSONL/ZIP local. Sau build đặt lại `None` để dùng index đã lưu. Đổi `REFRESH_KAGGLE_INDEX=True` khi chủ động lấy snapshot mới; phiên sau đặt lại `False`. Không cần refresh mỗi ngày chỉ để lấy ngày v1 của references cũ; ID quá mới sẽ fallback OAI.

Nếu cần tiếp tục ngay khi chưa có Kaggle: `USE_KAGGLE_REFERENCE_DATES=False` dùng cache ngày v1 + OAI. `USE_HYBRID_REFERENCE_DATES=False` dùng luồng OAI cũ; reader vẫn hiểu cả receipt cũ/mới.

## Cây Drive và bằng chứng

```text
Milestone1/
  retry-state/member-N.json                 # giữ nguyên
  checkpoints/<run>/<attempt>/...           # giữ nguyên
  session-reports/<run>/<attempt>/...       # giữ nguyên
  <run>/<attempt>/corpus.zip, report.zip, backup_receipt.json
  metadata-index/
    current.json
    <snapshot-hash>-<unique>.sqlite
    <snapshot-hash>-<unique>.sqlite.receipt.json
  v1-cache/member-N/<unique>.bundle.json
```

Cache ngày v1 được dùng trên ổ local và ghi **theo lô**, mỗi 40 bài (hoặc nhịp checkpoint) và cuối collection; không ghi một file nhỏ lên Drive cho mỗi reference. Batches bất biến, có hash và per-ID evidence, tách theo member. Cache lỗi/hết hạn không được tin; lookup lại. Không có negative cache làm che lỗi upstream. Cache mất chỉ ảnh hưởng tốc độ, không làm mất corpus/progress. Không sửa các bundle cũ; xóa bundle lỗi hoặc dùng thư mục cache mới nếu chủ động kiểm tra lại ngày.

Mỗi `.references_receipt.json` hybrid chứa bằng chứng đủ để audit offline:

- Kaggle: projection `{id, versions:[v1]}`, timestamp gốc, ngày UTC, nguồn snapshot, hash JSONL/index và hash evidence.
- OAI: raw XML, ID, ngày v1, retrieval timestamp và hash evidence.
- Hash của cả hai reference stores và toàn bộ tập evidence.

Bằng chứng nằm trong thư mục bài, tự đi cùng corpus ZIP, immutable checkpoint và selective restore. Không đóng gói toàn bộ index Kaggle trong từng corpus ZIP. Không cần giữ shared index để kiểm một backup cũ. Hash kiểm toàn vẹn và sự nhất quán nguồn; không chứng minh snapshot chính xác độc lập, nên vẫn cần kiểm mẫu với arXiv.

Audit dữ liệu lịch sử không áp TTL 24 giờ; nó kiểm bytes/identity/provenance. Reuse live OAI metadata/S2 vẫn áp TTL 24 giờ. Partial retry không ghi đè complete reference store, kể cả store đã quá TTL.

## Benchmark và điều phối

`reference_date_stats.json` đi cùng metrics/report, ghi Kaggle/cache/OAI hits, failures, rejected rows, snapshot hash, preparation time và index reuse. Benchmark bắt đầu **trước** prepare/download/copy/verify index, đo process-tree RSS và disk của corpus + local index/download + cache. Cold và warm/mixed được phân biệt; không lấy tốc độ sau khi đã xây index làm cold end-to-end. ZIP cuối notebook nằm ngoài benchmark; background checkpoint vẫn nằm trong benchmark.

Benchmark cuối: Colab CPU, corpus mới, index mới (`REFRESH_KAGGLE_INDEX=True`) và đặt `V1_CACHE_DIR` tới cache ngày v1 riêng còn trống. Không xóa cache/progress đang dùng để tạo cold benchmark. Giữ nguyên thứ tự dữ liệu/versions/reference pages khi so baseline và hybrid; báo tỷ lệ fallback và lỗi, không cam kết phần trăm tăng tốc từ vài bài.

Một runtime/member để bảo vệ queue. Giới hạn arXiv áp dụng tổng các máy dưới quyền điều khiển: không dùng ba tài khoản để nhân quota, lên lịch các luồng arXiv tuần tự. Module không cung cấp distributed rate limiter giữa các Colab; notebook không tự điều phối những runtime khác đang chạy. Index build/cache local có thể thực hiện độc lập; network arXiv giữ pacing ít nhất 3 giây/request và Retry-After như trước.

## Kiểm chứng trong lần nâng cấp

- 20 regression tests: queue cũ, ngày UTC/ID legacy, snapshot thiếu/duplicate, cache lỗi/hết hạn, ưu tiên OAI mới, index immutable/hash, pagination thiếu, evidence bị sửa, mọi versions, checkpoint/backup/restore.
- Mở bản sao ZIP nhóm gửi (18/10): 100 bài đọc được, 100 artifact audits đạt; notebook analyze kiểm 433 mục và tạo report ZIP. Audit toàn vẹn không khẳng định mọi bài đều crawl hoàn tất.
- Bộ tổng hợp Book đọc nguyên cây ZIP cũ: 98 bài hoàn tất duy nhất, 100 ID mới đã đăng ký, 2 ID pending được giữ nguyên.
- Endpoint Kaggle thật trả ZIP; lấy 10 records đầu để kiểm parser, không tải toàn snapshot. Ngày v1 bài `0704.0001` từ Kaggle và OAI cùng là `2007-04-02`.
- Luồng notebook hybrid được chạy với HTTP giả lập để kiểm pipeline/cells/report; chưa đo tốc độ trên toàn snapshot hoặc benchmark Google Colab thật.

Chạy kiểm thử trong môi trường đã cài `src/requirements.txt`:

```bash
python -m unittest discover -s tests -v
```

## Nguồn

- [Đề M1](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/): yêu cầu mọi versions, sources và S2 references.
- [Cornell arXiv metadata](https://www.kaggle.com/datasets/Cornell-University/arxiv): nguồn snapshot, ID và `versions[].created`.
- [arXiv OAI](https://info.arxiv.org/help/oa/index.html): arXivRaw history và ý nghĩa datestamp.
- [arXiv API Terms](https://info.arxiv.org/help/api/tou.html): pacing và giới hạn trên tổng các máy.
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/): references endpoint/pagination, không đổi phương pháp S2.
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html), [zipfile](https://docs.python.org/3/library/zipfile.html), [hashlib](https://docs.python.org/3/library/hashlib.html): index, đọc ZIP và hashes. `dates.py` là implementation của nhóm theo thiết kế này, không copy code từ dataset.
