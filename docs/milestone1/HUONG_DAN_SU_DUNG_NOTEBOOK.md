# Hướng dẫn sử dụng notebook cào dữ liệu Milestone 1

Cập nhật **19/10/2026**. Hướng dẫn cho [milestone1.ipynb](../../src/notebooks/milestone1.ipynb), chạy nhiều lượt trên **Google Colab CPU**, lưu tiến độ và dữ liệu vào Drive cá nhân. Xem [kế hoạch/phương pháp và nguồn tham khảo](./KE_HOACH_MILESTONE_1.md), [phân công](./PHAN_CONG_MILESTONE_1_4_NGUOI.md).

Mỗi lần rảnh, chọn tên mình và số **ID mới** muốn xử lý, rồi chạy notebook. Planner tự chọn ID tiếp theo và thêm phần cần retry; không cần tự nhập khoảng ID cho từng lượt.

## 1. Mở notebook và chạy lần đầu

1. Mở [notebook trên Colab](https://colab.research.google.com/github/Hireophant/arXivProject/blob/master/src/notebooks/milestone1.ipynb), lưu một bản sao vào Drive cá nhân để giữ cấu hình của mình.
2. Chọn loại runtime **CPU**, accelerator **None**, rồi **Connect**. Code chạy trên máy Colab; máy cá nhân dùng để điều khiển và xem kết quả.
3. Tìm cell cấu hình có `SELECTED_MEMBER` và `NEW_PAPERS_PER_SESSION`, sửa theo mục 2.
4. Chọn **Runtime → Run all**. Các cell đầu tự lấy code từ GitHub và cài thư viện.
5. Khi cell **Connect Drive before collection** hỏi quyền, chọn tài khoản Drive của mình và cấp quyền. Bước này nằm **trước khi crawl**; notebook kiểm khả năng ghi Drive rồi mới đăng ký công việc.
6. Xem bảng tiến độ và dòng `This session` theo mục 4. Đợi các cell chạy đến cuối, kiểm thông báo lưu theo mục 5.

Lần đầu có thể đặt số ID mới bằng `1` để kiểm kết nối, audit và bản sao lưu, rồi tăng ở lượt kế tiếp. ID đã hoàn tất vẫn được ghi nhận trong đoạn ID của acc đã chọn.

**Khi lấy phiên bản code mới:** mở lại notebook từ liên kết GitHub trên và dùng runtime mới sau khi dữ liệu cũ đã được lưu. Notebook bản sao và checkout trong runtime đang dùng không tự cập nhật theo GitHub; cell setup dùng lại checkout đã tồn tại.

## 2. Hai biến cần chọn cho lượt chạy thông thường

```python
SELECTED_MEMBER = 'Danh'
NEW_PAPERS_PER_SESSION = 300
```

| Biến | Cách điền |
|---|---|
| `SELECTED_MEMBER` | Tên gốc hoặc thêm `1`, `2`: `Danh`, `Danh1`, `Danh2`, `Khánh`, `Khánh1`, `Khánh2`, `Khang`, `Khang1`, `Khang2`, `Nguyên`, `Nguyên1`, `Nguyên2`; giữ đúng dấu |
| `NEW_PAPERS_PER_SESSION` | Số nguyên dương: `1`, `100`, `200`, `300`, `400`… tùy thời gian rảnh; mặc định `100` |

**300 hoặc 400 đều được.** Đây là giới hạn ID mới của một lượt, không phải giới hạn cả dự án. Lượt sau có thể đổi từ 300 xuống 100 hoặc lên 400; gần cuối phạm vi thì planner chỉ lấy số còn lại.

| Acc | Bắt đầu | Kết thúc | Tổng ID | File tiến độ |
|---|---|---|---:|---|
| Danh | 2606.15734 | 2606.17400 | 1,667 | `member-1.json` |
| Khánh | 2602.19870 | 2602.21536 | 1,667 | `member-2.json` |
| Khang | 2609.02834 | 2609.04500 | 1,667 | `member-3.json` |
| Nguyên | 2601.23156 | 2602.01536 | 1,667 | `member-4.json` |
| Danh1 | 2606.17401 | 2606.19067 | 1,667 | `member-5.json` |
| Danh2 | 2606.19068 | 2606.20733 | 1,666 | `member-6.json` |
| Khánh1 | 2602.21537 | 2602.23203 | 1,667 | `member-7.json` |
| Khánh2 | 2602.23204 | 2603.00579 | 1,666 | `member-8.json` |
| Khang1 | 2609.04501 | 2609.06167 | 1,667 | `member-9.json` |
| Khang2 | 2609.06168 | 2609.07833 | 1,666 | `member-10.json` |
| Nguyên1 | 2602.01537 | 2602.03203 | 1,667 | `member-11.json` |
| Nguyên2 | 2602.03204 | 2602.04869 | 1,666 | `member-12.json` |

Giữ nguyên `ASSIGNMENTS`, thứ tự thành viên và `MONTH_END_IDS`. Không sửa đầu/cuối phạm vi thành 100/300/400 ID: planner cần toàn bộ phạm vi để theo dõi tiến độ lâu dài. Các phạm vi không giao nhau; mốc cuối tháng đã xác minh trong code.

## 3. Các biến giữ nguyên và tùy chọn khi cần

Với việc chia lượt tự động trên Colab, giữ cấu hình sau:

| Biến | Giá trị | Ý nghĩa |
|---|---|---|
| `ALLOW_NETWORK` | `True` | Cho phép tải dữ liệu; nằm ở cell setup đầu notebook |
| `RUN_MODE` | `'cold'` | Tạo thư mục lượt mới; vẫn dùng tiến độ cũ trên Drive |
| `EXISTING_ROOT` | `None` | Planner tự chuẩn bị lượt mới |
| `SCOPE_PURPOSE` | `'assigned'` | Cào trong phân công chính thức |
| `AUTO_PLAN_SESSIONS` | `True` | Tự chọn đoạn mới, tránh chọn lại ID đã hoàn tất |
| `SAVE_TO_DRIVE` | `IN_COLAB` | Tự bật lưu Drive khi chạy Colab |
| `AUTO_RETRY_FROM_DRIVE` | `IN_COLAB` | Tự thêm phần chưa hoàn tất vào lượt sau |
| `MAX_RETRY_PAPERS` | `40` | Tối đa 40 ID retry ngoài số ID mới mỗi lượt |
| `RETRY_ONLY` | `False` | Chạy mới và retry; đổi `True` khi chỉ muốn xử lý phần tồn đọng |
| `BACKGROUND_CHECKPOINTS` | `True` | Lưu từng nhóm trong lúc crawl |
| `CHECKPOINT_EVERY_PAPERS` | `40` | Chốt bản lưu sau mỗi 40 ID đã xử lý, gồm cả ID còn lỗi |
| `CREATE_REPORT_ZIP` | `True` | Xuất gói report cuối lượt |
| `DOWNLOAD_REPORT_ZIP` | `False` | Giữ report trên Drive; đổi `True` nếu muốn thêm bản tải qua trình duyệt |

Giữ đường dẫn mặc định:

```python
DRIVE_BACKUP_DIR = DRIVE_MOUNT_POINT / 'MyDrive/arXivProject/Milestone1'
```

Mỗi acc cấp quyền **Drive tương ứng**. Mỗi người có 3 acc, tổng vẫn 5.000 ID. Queue vẫn ở `retry-state/member-N.json`, không thêm thư mục mới. Danh/Khánh/Khang/Nguyên giữ member-1/2/3/4 và đọc lại completed/pending từ queue cũ. Ví dụ Danh đã lưu hoàn tất 500 ID đầu thì tiếp tục từ ID chưa làm, không về 0. Tiến độ và planner chỉ tính/chọn ID trong đoạn acc hiện tại; lịch sử, receipt và pending ngoài đoạn vẫn được giữ. Các acc thêm dùng member-5 đến member-12 theo bảng. Khi tổng hợp, cần giữ cả backup cũ; acc ở Drive khác không tự biết dữ liệu đã tải trên Drive trước đó. Các phiên sau phải dùng cùng tài khoản, cùng tên thành viên và cùng thư mục này để đọc đúng tiến độ. Chỉ chạy **một runtime cho mỗi acc tại một thời điểm**.

Giữ delay arXiv/S2 mặc định **3,1 giây** và các thiết lập retry API. Không giảm delay để tăng tốc; cả nhóm cần điều phối truy cập theo chính sách trong kế hoạch. Không cần API key để bắt đầu; nếu dùng S2 key thì dùng secret, không ghi vào notebook/code.

## 4. Đọc tiến độ và số bài thực tế của lượt

Cell cấu hình hiển thị toàn bộ scope 1.667 hoặc 1.666 ID của acc. Đó là phân công đầy đủ; **dòng `This session` ở cell chuẩn bị phiên mới cho biết số ID thực sự được chọn**.

| Trường ở bảng đầu phiên | Cách hiểu |
|---|---|
| `total` | 1.667 hoặc 1.666 ID được giao cho acc |
| `completed` | ID đạt điều kiện dữ liệu/audit và đã xác nhận lưu trên Drive |
| `pending` | ID đã đăng ký nhưng chưa hoàn tất an toàn: lỗi, bị ngắt hoặc chưa kịp xử lý |
| `unseen` | ID chưa được đăng ký vào lượt nào |
| `next_new_id` | ID mới tiếp theo sẽ được chọn |
| `last_saved_id` | ID trong nhóm lưu gần nhất; vẫn xem pending vì phía trước có thể còn bài lỗi |

Đây là tiến độ **trước khi chọn công việc mới của lượt hiện tại**. Ví dụ:

```text
Saved complete: 280/1667; pending: 20; unseen: 1367
This session: new = 300 retry = 20 actual unique IDs = 320
```

Lượt này chọn 300 ID mới và 20 ID retry, tổng 320 ID khác nhau. Retry **vẫn có trong report và thời gian đo**, được gắn vai trò riêng; không tính thành bài mới lần nữa. `session_counts.json` tách số mới/retry và số hoàn tất; `attempts.csv` ghi từng ID của từng lượt.

Planner đăng ký ID trước khi crawl, tránh bỏ sót khi runtime mất. ID hoàn tất không được chọn lại; ID lỗi vẫn ở queue và được retry có giới hạn. Nếu còn hơn 40 pending, phần vượt giới hạn chờ lượt khác; retry tiếp tục lỗi được đưa về cuối hàng đợi.

## 5. Trong lúc chạy và khi kết thúc

Đầu lượt cần lấy metadata qua OAI-PMH nên có thể phải đợi trước khi xuất hiện bản lưu source đầu tiên. Crawler lấy metadata, source các phiên bản và references; lỗi mạng có retry/backoff nên số ID không quyết định chính xác thời lượng.

Sau mỗi 40 ID xử lý, notebook chốt snapshot rồi cho worker nén/lưu/kiểm trên Drive, trong khi crawl có thể tiếp tục. Tối đa hai snapshot chờ; Drive chậm thì crawl có thể phải đợi. Nhóm cuối dưới 40 ID được chốt khi pipeline kết thúc bình thường.

| Thông báo | Ý nghĩa |
|---|---|
| `Checkpoint queued` | Đã xếp hàng lưu, **chưa xác nhận lưu xong** |
| `Checkpoint VERIFIED` | Nhóm đã được kiểm và ghi nhận trên Drive; trong nhóm vẫn có thể có ID lỗi đang pending |
| `Final session measurements saved on Drive` | Đã lưu report số đo cuối pipeline; source khôi phục từ checkpoints đã xác nhận |
| `Completed: success/partial/failed` | Trạng thái lượt; đọc audit và phần tồn đọng để biết còn thiếu gì |
| `Drive backup VERIFIED: ...` | Đã lưu và kiểm full backup cuối notebook; đường dẫn in ngay sau thông báo |
| `Retry queue saved: N pending IDs ...` | Tiến độ đã cập nhật; N ID còn chờ ở lượt sau |

Khi kết thúc, xem `integrity_audit.csv`, `outstanding_tasks.csv` và thống kê mới/retry. Có report không đồng nghĩa cả 5.000 ID đã hoàn tất. `no_tex` đã xác minh là trường hợp nguồn không có TeX hợp lệ; lỗi tải/thiếu metadata hoặc references vẫn cần xử lý.

## 6. Notebook trả ra gì và lưu ở đâu?

Notebook hiển thị tiến độ, bảng thống kê, audit, biểu đồ và đường dẫn kết quả. File làm việc nằm trong `/content/arxiv-data/`; corpus cụ thể được in ở dòng `Root:`. Đây là ổ runtime Colab, có thể mất khi runtime bị thu hồi; việc lưu lâu dài dựa vào Drive.

Trên Drive cá nhân, mở **MyDrive/arXivProject/Milestone1**:

```text
Milestone1/
  retry-state/
    member-1.json                 # tiến độ Danh; tên khác xem mục 2
  checkpoints/<run_id>/<lần_lưu>/
    corpus.zip                   # source thật của nhóm checkpoint
    report.zip                   # report tại thời điểm checkpoint
    backup_receipt.json          # thông tin kiểm bản lưu
  session-reports/<run_id>/<lần_lưu>/
    corpus.zip                   # chỉ manifest, không chứa source cho M2/M3
    report.zip                   # report số đo cuối pipeline
    backup_receipt.json
  <run_id>/<lần_lưu>/
    corpus.zip                   # đầy đủ corpus của lượt, từ cell backup cuối
    report.zip                   # report cuối notebook, gồm bảng/hình/audit
    backup_receipt.json
```

`run_id` nhận diện lượt chạy; mỗi lần lưu có thư mục riêng, không ghi đè lần trước. Nếu runtime ngắt giữa chừng thì có thể mới có checkpoints, chưa có full backup cuối lượt.

| Dữ liệu | Dùng để làm gì? | Cần giữ gì? |
|---|---|---|
| **Corpus** | Metadata, các source `.tex`/`.bib`, references, receipts/cache; dùng tiếp cho M2/M3 | Corpus ZIP thật trong checkpoints/full backups của **mọi lượt** |
| **Report** | Thống kê, thời gian/tài nguyên, bảng/hình, audit và new/retry để viết báo cáo | Report các lượt và thông tin run tương ứng |
| **Tiến độ + receipts** | Biết ID nào xong/còn lỗi, bản lưu nào chứa dữ liệu; phục hồi và tổng hợp | `retry-state`, `backup_receipt.json` cùng cấu trúc thư mục |

**Cách lưu đơn giản nhất: giữ nguyên cả cây `Milestone1` trên Drive**, chưa xóa ZIP cũ dù đã có phiên mới. Chỉ lấy `report.zip` thì thiếu source cho M2/M3. `corpus.zip` trong `session-reports` là manifest stub nên không thay corpus thật.

Mặc định `DOWNLOAD_REPORT_ZIP=False`: lưu Drive, **không tự tải file về máy**. Bạn có thể tải bản sao từ Drive khi cần. Không cần chờ bấm xác nhận lưu Drive ở cuối lượt vì đã cấp quyền đầu phiên; quyền ghi và dung lượng Drive vẫn phải còn hợp lệ.

Nếu đặt `DOWNLOAD_REPORT_ZIP=True` trước khi chạy, cell cuối gọi trình duyệt tải thêm **report ZIP** về máy. Trình duyệt có thể cần cho phép tải; tùy chọn này không tự tải corpus. Khi muốn lưu offline/đưa cho người khác, tải hoặc copy cả cây Drive để giữ đủ corpus, reports và tiến độ.

## 7. Chạy lượt tiếp theo

**Còn cùng runtime:**

1. Đợi lượt hiện tại và backup kết thúc; kiểm các thông báo VERIFIED và lỗi.
2. Giữ tên mình, `RUN_MODE='cold'`, `RETRY_ONLY=False`. Chỉ đổi `NEW_PAPERS_PER_SESSION` nếu muốn, ví dụ 300 xuống 100 hoặc lên 400.
3. Chạy **Run all** lại, hoặc chạy cell cấu hình và **tất cả cell phía dưới theo thứ tự**. Chỉ sửa chữ trong cell mà chưa chạy cell thì giá trị chưa đổi.
4. Xem bảng tiến độ mới và `This session`; planner tự lấy ID chưa làm cùng pending cần retry. Không cần reset runtime cho mỗi lượt.

**Ngày khác hoặc runtime đã mất:**

1. Mở notebook đang dùng bản code hiện hành và **Connect** runtime CPU.
2. Kiểm tra `SELECTED_MEMBER` đúng tên mình. Nếu bản sao notebook đã lưu đúng tên thì giữ nguyên.
3. Chỉ đổi `NEW_PAPERS_PER_SESSION` nếu muốn thay **số lượng ID mới xử lý trong lượt này**, ví dụ `300` hoặc `400`. Muốn chạy số lượng như lần trước thì giữ nguyên; đây không phải ID bắt đầu.
4. Chọn **Run all**. Nếu được hỏi quyền Drive, chọn **cùng tài khoản Google Drive đã lưu các lượt trước**. Giữ đường dẫn thư mục mặc định trong code, không cần nhập lại hoặc chọn thư mục mỗi lượt.
5. Notebook tự đọc tiến độ trên Drive, chọn các ID mới chưa làm và thêm phần pending cần retry từ bản lưu đã kiểm. Xem bảng tiến độ và dòng `This session` để biết lượt này xử lý bao nhiêu ID.

Thông thường, bạn chỉ cần kiểm đúng tên mình rồi chạy; thay số lượng bài là tùy chọn. Không cần tự nhớ đã chạy tới ID nào hoặc sửa khoảng ID bắt đầu/kết thúc.

Các thư mục làm việc nhiều lượt vẫn chiếm ổ Colab. Nếu cần runtime mới vì ổ gần đầy, chỉ chuyển sau khi đã kiểm dữ liệu cần giữ trên Drive.

**Ví dụ:** lượt đầu chọn 300, hoàn tất 280 và còn 20 pending. Lượt sau đặt 400 thì planner chọn tối đa 400 ID mới + 20 retry. Không đổi khoảng phân công thành “bắt đầu từ bài 301”, cũng không cộng 20 retry thành 20 bài mới.

Lượt cũ được tạo trước khi có queue chưa tự được nhập chỉ vì ZIP nằm trên Drive. Cần restore/resume một lần bằng code hiện hành để đăng ký tiến độ; xem mục 10.

## 8. Chỉ retry, tắt tab và xử lý lỗi lưu

**Chỉ xử lý tồn đọng:** đặt `RETRY_ONLY=True`, giữ `MAX_RETRY_PAPERS=40`, rồi chạy lượt mới. Không chọn ID mới; tối đa 40 retry/lượt. Có thể sửa giới hạn retry thành số nguyên không âm. Giữ số ID mới là số nguyên dương dù chế độ này không lấy ID mới.

Muốn cào tiếp phần chưa làm, đặt `RETRY_ONLY=False`. `No work selected` khi chỉ retry có thể chỉ nghĩa không còn pending; vẫn xem `unseen`. Khi hết ID mới, tiếp tục xử lý pending. Bảng cần đạt `completed=5000`, `pending=0`, `unseen=0`, kèm kiểm audit và yêu cầu đề.

**Đóng tab/tắt máy:** Colab có thể tiếp tục một thời gian nhưng không đảm bảo chạy hết. Chỉ các nhóm đã xác nhận lưu Drive được bảo vệ; có thể phải tải lại nhóm đang crawl, đang upload hoặc đang chờ. Không coi `Checkpoint queued` là đã lưu, cũng không hứa tối đa chỉ mất 39 ID. Lần sau Run all theo mục 7 để nhận việc pending.

**Nếu có lỗi:**

- Lỗi cấp quyền/kiểm ghi Drive đầu phiên: sửa tài khoản/quyền/dung lượng rồi nối Drive lại; notebook dừng trước crawl.
- `DRIVE BACKUP FAILED` hoặc `RETRY QUEUE UPDATE FAILED` ở cuối: giữ runtime và dữ liệu local, sửa kết nối/dung lượng, chạy lại **riêng cell backup cuối**. Nếu mount mất thì chạy cell nối Drive trước. Không chạy lại cấu hình/collection chỉ để thử lưu lại lượt này.
- Worker checkpoint lỗi: collection dừng, staging local được giữ, ID chưa xác nhận vẫn pending. Sau khi sửa Drive, có thể bắt đầu lượt cold mới để planner nhận pending hoặc resume root cũ có chủ đích.
- Upload raw final report lỗi: checkpoints đã xác nhận vẫn còn. Nếu runtime còn và metrics đã ghi, có thể analyze root đó để xuất/lưu report; nếu runtime mất, giữ checkpoints và tiếp tục pending ở lượt sau.

Không xóa queue để bỏ qua lỗi. Bản lưu được kiểm CRC/hash; kiểm byte vẫn cần đi cùng audit và đối chiếu vài mẫu dữ liệu nguồn.

## 9. Giữ kết quả để viết Book và làm M2/M3

Nhiều report ZIP vì chia nhiều lượt là bình thường. Có thể thu thập xong rồi tổng hợp viết Book một lần; không cần crawl lại 5.000 ID trong một lượt. Retry giữ thành lịch sử xử lý, còn corpus tổng hợp đếm mỗi base arXiv ID hoàn tất một lần.

Mỗi người bàn giao **nguyên cây Milestone1** vào thư mục riêng, ví dụ `exports/Danh`, `exports/Khanh`, `exports/Khang`, `exports/Nguyen`; giữ cấu trúc bên trong. Người làm báo cáo có thể dùng helper:

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

Ví dụ cần source repo đã setup và bốn cây dữ liệu thực sự nằm ở các đường dẫn đó; sửa theo nơi mình copy. Helper kiểm bản lưu và tạo `papers_unique.csv`, `attempts.csv`, `benchmark_runs.csv`, `summary.json`. Nó chưa tự viết/publish Book hoặc gộp source thành một thư mục M2; bảng papers chỉ đến ZIP corpus thật cần dùng.

Giữ report gốc để đọc chi tiết versions/references và sinh thống kê/hình lúc build Book. Không cộng report checkpoint với report cuối cùng của cùng `run_id`: checkpoint là số đo tích lũy tại thời điểm lưu. Không cộng số dòng mọi report thành tổng bài duy nhất. Book theo đề dùng tiếng Anh, repo công khai riêng/GitHub Pages; report ZIP là đầu vào, không phải Book hoàn chỉnh.

## 10. Nâng cao: resume/analyze và notebook trên Windows

**Lượt mới bình thường dùng `cold` và planner như trên.** Hai chế độ sau dành cho một corpus đã lưu cụ thể:

- `resume`: giải nén **full session corpus ZIP** hoặc dùng root local cũ; đặt `RUN_MODE='resume'`, `EXISTING_ROOT` là thư mục chứa `manifest.json`, giữ đúng member. Scope lấy từ manifest và phải thuộc phân công. Không dùng ZIP manifest stub trong `session-reports` để phục hồi source. Planner thông thường tự phục hồi pending nên không cần tự resume mỗi ngày.
- `analyze`: đặt `RUN_MODE='analyze'`, `EXISTING_ROOT` trỏ corpus có `metrics/run_summary.json`, `ALLOW_NETWORK=False`. Đọc số đo sẵn có, không đo lại crawl hoặc cập nhật queue; root bị ngắt chưa có summary tương ứng cần resume trước. Lưu/export mới lên Drive cần kết nối và bật mạng theo cấu hình notebook.

**Mở notebook trên Windows để đọc/analyze:** dùng Python >=3.11, cài môi trường từ `environment.yml` hoặc `src/requirements.txt`, mở Jupyter và chọn đúng kernel. Với corpus đã giải nén, cấu hình analyze như trên và dùng đường dẫn Windows cho `EXISTING_ROOT`. Quy trình cào nhiều phiên tự động và nối Drive trong hướng dẫn này dùng Colab.
