# Chạy và kiểm tra Milestone 1 trên Windows/Colab

Cập nhật 18/10/2026: planner chọn đoạn tiếp theo, retry riêng và background checkpoint. Các phần code/chính sách/citations nằm trong [kế hoạch](./KE_HOACH_MILESTONE_1.md), mục 13. Giữ tài liệu này cùng docs phân công.

## 1. Môi trường Windows

Python >=3.11. Từ repository: `conda env create -f environment.yml`, `conda activate arxiv-project`, `python -m jupyterlab`; hoặc cài `python -m pip install -r src/requirements.txt`. Chọn đúng kernel. Không commit corpus, key hoặc notebook outputs. Không bật automatic planning trên local nếu chưa có Drive tiến độ; local kiểm offline/analyze hoặc cấu hình manual chủ động.

## 2. Cấu hình lượt Colab

Phạm vi TA đã điền đủ, không sửa endpoints mỗi lượt:

| Người | Bắt đầu | Kết thúc | ID |
|---|---|---|---:|
| Danh | 2606.15734 | 2606.20733 | 5.000 |
| Khánh | 2602.19870 | 2603.00579 | 5.000 |
| Khang | 2609.02834 | 2609.07833 | 5.000 |
| Nguyên | 2601.23156 | 2602.04869 | 5.000 |

Giữ thứ tự bốn thành viên. MONTH_END_IDS đã xác minh: 2026-01=23286, 2026-02=24290. Mỗi range đủ 5.000, không giao nhau.

```python
SELECTED_MEMBER = 'Danh'       # đổi đúng tên mình
NEW_PAPERS_PER_SESSION = 100   # có thể đổi thành 200 mỗi lượt
RUN_MODE = 'cold'
EXISTING_ROOT = None
SCOPE_PURPOSE = 'assigned'
AUTO_PLAN_SESSIONS = True
AUTO_RETRY_FROM_DRIVE = True
MAX_RETRY_PAPERS = 40
RETRY_ONLY = False
BACKGROUND_CHECKPOINTS = True
CHECKPOINT_EVERY_PAPERS = 40
DOWNLOAD_REPORT_ZIP = False
```

100 là số ID mới, chưa gồm retry (tối đa 40). Muốn chạy thử một bài: đặt new count=1, không thu hẹp full assignment vì queue gắn với assignment đầy đủ. API chậm/retry/source size làm thời gian biến động. Không giảm delay 3,1 giây để chạy nhanh hơn.

## 3. Bảng đầu phiên và lúc đang chạy

Sau cấu hình: cấp quyền Drive của mình ở **Connect Drive before collection**. Mount/write check lỗi thì dừng trước crawl. Preview hiển thị total=5000, completed (đã đủ dữ liệu/audit và backup), pending, unseen, next_new_id và last_saved_id. Planner chọn ID mới tiếp theo cộng retry; không chọn completed thành new. IDs mới được đăng ký trước crawl, nên ngắt runtime không làm mất danh sách việc.

Ví dụ 100 mới + 8 retry =108 ID thực tế. Xem `session_plan.json`, `session_counts.json`, `attempts.csv`; không coi 108 là 108 bài mới. no_tex đã xác minh là trạng thái xử lý hợp lệ, khác lỗi mạng; metadata/ref upstream thiếu vẫn pending. Retry lỗi quay xuống cuối queue để không chặn ID khác.

Trong pipeline: mỗi 40 bài đã xử lý (kể cả còn lỗi), main chốt snapshot và worker nén/upload/hash/ack, crawl tiếp. Log **Checkpoint queued** chưa phải đã lưu. **Checkpoint VERIFIED** chỉ xuất sau commit. Tối đa 2 snapshot chờ; Drive chậm thì crawl có thể phải đợi. Nhóm cuối ít hơn 40 được lưu khi kết thúc bình thường. Resource sampling bao gồm worker/staging/upload wait; file staging đã verified được dọn.

## 4. Phiên sau, resume và analyze

Nếu đang cùng runtime: đợi lượt hiện tại kết thúc/backup xong, đổi số bài mới nếu muốn rồi Run All (hoặc configuration và tất cả cells dưới). Không cần reset mỗi lượt. Nếu runtime đã mất: Connect lại, dùng notebook mới, cùng member và Drive root rồi Run All; planner đọc tiến độ Drive và nhận lại pending. Không chạy song song hai phiên cùng member.

Muốn chỉ sửa phần còn lỗi: đặt RETRY_ONLY=True; không chọn thêm ID mới. Khi không còn pending, notebook báo không có việc và không crawl. Muốn quay lại ID mới thì đặt False. Khi assignment hoàn tất, chạy lại không tự crawl lại 5.000 ID.

`resume`: khôi phục **full session corpus ZIP** hoặc cùng root local cũ; đặt RUN_MODE='resume', EXISTING_ROOT đúng root, giữ member. Scope lấy chính xác từ manifest và phải nằm trong full assignment. Không dùng manifest-only ZIP trong session-reports để resume. Checkpoint group scope nhỏ cũng có thể restore/resume riêng khi cần; auto planner bình thường tự restore pending.

`analyze`: RUN_MODE='analyze', EXISTING_ROOT đúng corpus root có metrics/run_summary.json; ALLOW_NETWORK=False để không mount/crawl/sửa queue. Root bị ngắt chưa có summary tương ứng cần resume trước. Analyze không đo lại crawl hoặc làm mới cache.

## 5. Report và benchmark

Giữ mọi report của các lượt. Breakdown tách new/retry/unclassified và complete/incomplete; unique corpus đếm base ID một lần. Retry time phải giữ, không giấu như không có chi phí. Thông số benchmark gồm wall toàn pipeline (discovery/crawl/background checkpoint/wait), samples RSS process tree, peak disk gồm staging, final corpus size. Snapshot checkpoint là cumulative session prefix, không phải benchmark cuối phiên. Final raw report ghi số đo toàn phiên; nén/upload final report và final UI export nằm ngoài benchmark crawl. CPU-only Colab và cold eligibility vẫn kiểm; retry/cache không thành cold benchmark đoạn mới.

Book repo riêng, tiếng Anh/GitHub Pages, bảng/hình sinh lúc build. Người làm Book dùng `aggregate_reports` theo mục 9; không cộng trực tiếp số rows của từng ZIP hoặc cộng thời gian checkpoint với final cùng run_id. Giữ cả source corpus để M2/M3; report ZIP không thay corpus.

## 6. Kiểm lỗi và điều kiện hoàn tất

- Operational success chưa thay cho audit. Kiểm discovery đủ scope, mọi version success/no_tex, refs đủ trang/trường bắt buộc, artifact audit và pending ledger.
- Final cell báo DRIVE BACKUP FAILED: source/report local còn; sửa quyền/dung lượng, chạy lại riêng cell backup.
- Background worker lỗi: collection dừng, stage local được giữ, ID chưa commit vẫn pending. Sửa Drive rồi chọn một lượt cold mới tự nhận pending hoặc resume rõ root; không xóa queue để né lỗi.
- Final raw-report upload lỗi không xóa checkpoint đã verified; queue vẫn giữ completion thật. Nếu còn phiên và metrics đã lưu, dùng analyze đúng root để xuất/lưu final UI report; nếu không, lần sau planner nhận phần chưa commit.
- Không bấm Stop/reset/xóa runtime khi đang muốn giữ nhóm chưa upload. Nếu buộc ngắt, chỉ các nhóm đã commit trên Drive được bảo vệ.

## 7. Chạy lại Colab từ bản GitHub vừa push

1. Mở notebook GitHub mới, lưu bản sao vào Drive cá nhân. Bản notebook cũ/checkout đang mở không tự cập nhật code mới; giữ dữ liệu phiên cũ tới khi backup đã verified.
2. Chọn accelerator **None**, Connect. Setup clone/cài dependency; không lưu API key trong source.
3. Chọn member và NEW_PAPERS_PER_SESSION=1 để kiểm lượt đầu, hoặc 100/200 khi sẵn sàng. Giữ full assignment/Drive folder và các flags tự động như mục 2.
4. Run All; chọn tài khoản Drive, cấp quyền **ở đầu**, xem preview rồi tiến độ checkpoint.
5. Khi xong xem status, audits, counts, final raw report và full backup. DOWNLOAD_REPORT_ZIP=False không tải về máy nhưng report vẫn trên Drive; bật True nếu muốn bản phụ.
6. Lượt sau không đổi ID, chỉ đổi new count nếu cần. Dùng retry-only khi muốn xử lý riêng phần lỗi. Lượt cũ chưa có queue cần restore/resume một lần để đăng ký.

## 8. Phạm vi của bản sao lưu tự động

Drive **MyDrive/arXivProject/Milestone1** có retry-state (tiến độ/member), checkpoints (source thật theo nhóm), session-reports (raw final report và corpus manifest stub), và thư mục run_id của full session backup cuối notebook.

Receipt ghi run_id/thời điểm/tên ZIP/size/SHA-256; ZIP CRC và hash được kiểm trước ack. Source đã tải tốt + hidden receipts + OAI cache của bài pending được restore và validate; TTL metadata/ref vẫn24 giờ. Lỗi/partial không được biến thành success, hash không chứng minh chất lượng nguồn.

Đóng tab/tắt máy không đảm bảo Colab chạy tới hết; kernel/VM có thể bị thu hồi. Checkpoint ở trong pipeline giảm phụ thuộc cell cuối. Mất runtime có thể phải tải lại nhóm đang crawl/upload/đang chờ; không hứa chỉ mất 39 bài. Dữ liệu đã commit trên Drive tồn tại độc lập runtime. Sao lưu không làm quota/runtime Colab vô hạn.

## 9. Tổng hợp dữ liệu các phiên và cả nhóm

Mỗi người chia sẻ/copy **nguyên cây Milestone1** vào folder riêng (ví dụ exports/Danh, exports/Khang), giữ retry-state/checkpoints/session-reports/full backups. Không đổi cấu trúc bên trong. Helper rebases layout receipt theo folder member mới, kiểm hash ZIP report và corpus được chọn, không âm thầm bỏ file thiếu/hỏng.

```python
from pathlib import Path
from crawling.reports import aggregate_reports
result = aggregate_reports([
    Path('/content/exports/Danh/retry-state/member-1.json'),
    Path('/content/exports/Khanh/retry-state/member-2.json'),
    Path('/content/exports/Khang/retry-state/member-3.json'),
    Path('/content/exports/Nguyen/retry-state/member-4.json'),
], Path('/content/book-data'))
```

papers_unique.csv có một row/ID hoàn tất và đường dẫn corpus ZIP thực; attempts.csv giữ từng run/ID với vai trò new/retry; benchmark_runs.csv có một record/run (prefix thiếu được gắn complete_measurement=False); summary.json có unique completed/new registered/retry attempts/pending. Stub final report không được chọn làm nguồn M2. Từ các bảng này người phụ trách viết Book sau, sinh thống kê/hình lúc build. Helper chưa tạo/publish Book hoặc thay việc kiểm tay/nghiệm thu.
