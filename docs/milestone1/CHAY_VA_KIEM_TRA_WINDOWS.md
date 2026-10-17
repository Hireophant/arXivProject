# Chạy và kiểm tra Milestone 1 trên Windows

Cấu hình notebook hiện tại: thử 100 ID Danh `2606.15734`–`2606.15833`,
`RUN_MODE="cold"`, `EXISTING_ROOT=None`, `SCOPE_PURPOSE="development"`.
Trên Colab, clone/install và kiểm tra CPU tự bật; trên Windows tự tắt.
Toàn phạm vi chính thức vẫn là `2606.15734`–`2606.20733`.
Đóng và mở lại notebook sau khi cập nhật file để tránh lưu đè cấu hình cũ.

Hướng dẫn đối chiếu ngày 16/10/2026 với `ARXIV_PROJECT_FULL.md` (phần Milestone 1),
`README.md`, notebook `src/notebooks/milestone1.ipynb` và pipeline hiện tại.
Các tài liệu phân công cũ còn mô tả cờ `RUN_KHANH`, `RUN_KHANG`, v.v.; notebook
hiện tại dùng `ASSIGNMENTS`, `ALLOW_NETWORK`, `RUN_MODE` như bên dưới.

## Phạm vi Danh từ dòng phân công bạn cung cấp

Dòng ảnh gửi trong chat ghi Danh, bắt đầu tháng `2026-06`, hậu tố `15734`,
kết thúc tháng `2026-06`, hậu tố `20733`. Cấu hình tương ứng:

```python
{'member': 'Danh', 'start_month': '2026-06', 'start_id': 15734,
 'end_month': '2026-06', 'end_id': 20733}
```

Đó là `2606.15734` đến `2606.20733`, gồm 5.000 ID cần kiểm tra (chưa phải
5.000 bài đã tìm thấy). Hai mốc cùng tháng nên `MONTH_END_IDS = {}`.
Ảnh này chỉ đủ điền phần Danh; chưa xác định phạm vi ba người còn lại.

Để thử ngay trong phần được giao, thay ví dụ BERT ở mục 4 bằng tháng `2026-06`,
`start_id=15734`, `end_id=15734`, giữ `SCOPE_PURPOSE='development'`.
Đạt rồi thử ba ID `15734` đến `15736`. Chỉ sau khi kiểm tra đạt mới chạy toàn
đoạn `15734` đến `20733` với `SCOPE_PURPOSE='assigned'`, cold root mới.
Số phiên bản và cấu trúc nguồn phải lấy từ phản hồi thật, không áp số v1/v2 của BERT.

Kiểm tra môi trường trực tiếp ngày 16/10/2026: Python 3.11.17 tại
`C:\Users\ADMIN\miniconda3\envs\arxiv-project\python.exe`; sáu thư viện trực tiếp
import thành công. Chưa dùng phép kiểm tra này để khẳng định API, corpus hay
benchmark Colab đã đạt.

## 1. Mục tiêu cần hoàn thành

Chạy trên Windows để kiểm tra và thu thập dữ liệu. Benchmark cuối theo đề phải
chạy trên Google Colab CPU-only. Notebook chạy hết không tự chứng minh milestone
đã xong; cần đủ phạm vi được giao, kiểm tra dữ liệu, báo cáo và nộp link.

- Thu thập đúng bài được TA giao; tải tất cả phiên bản, kể cả v1.
- Giữ nguồn TeX/BibTeX và các nguồn văn bản liên quan theo từng phiên bản.
  Bỏ ảnh nhị phân, giữ nguyên lệnh LaTeX về hình/bảng. Không cần cài LaTeX để crawl.
- Phiên bản không có TeX vẫn có bản ghi và trạng thái `no_tex`.
- Có metadata bài: title, authors, submission_date, revised_dates, venue nếu có.
- Có metadata tham khảo từ Semantic Scholar: chỉ giữ mục có arXiv ID,
  gồm title, authors, submission_date và semantic_scholar_id.
  Ngày xuất bản không thay cho ngày gửi arXiv. Tham khảo được lưu theo bài chính;
  Semantic Scholar không đảm bảo phân biệt danh sách tham khảo giữa các version.
- Có thống kê chất lượng, kích thước trước/sau lọc, thời gian, RAM và đĩa.
- Benchmark cuối: Colab CPU, đo từ trước discovery, ghi rõ cache/retry/nhịp API.
- Một repository code công khai; một repository Jupyter Book riêng, GitHub Pages.
  Bảng/biểu đồ của book phải sinh khi build từ dữ liệu thật đã lưu.
- Nộp Moodle link code và link báo cáo theo hạn TA. Giữ corpus cho milestone sau;
  Milestone 1 chưa cần upload dữ liệu lên Hugging Face.

## 2. Mở môi trường và kiểm tra thư viện

Mở **Anaconda Prompt**, chạy từng dòng:

```bat
cd /d C:\Users\ADMIN\Desktop\Do_an\arXivProject
conda activate arxiv-project
python --version
python -c "import sys; print(sys.executable)"
python -c "import jupyterlab, ipykernel, requests, pandas, matplotlib, psutil; print('IMPORT OK')"
python -m pip check
```

Kết quả mong đợi: đầu prompt có `(arxiv-project)`, Python 3.11.x, đường dẫn Python
nằm trong `miniconda3\envs\arxiv-project`, `IMPORT OK`, không báo xung đột pip.
`pip check` chỉ kiểm tra phụ thuộc Python, không thay thế test pipeline/API.

Nếu chưa có môi trường, chạy `conda env create -f environment.yml` trước activate.
Nếu file môi trường đã thay đổi, chạy `conda env update -f environment.yml --prune`.
Nếu gặp lỗi ToS, xử lý theo thông báo Conda trước; không sửa số phiên bản để chữa lỗi ToS.

Mở JupyterLab trong chính cửa sổ đã activate:

```bat
python -m jupyterlab
```

Mở `src/notebooks/milestone1.ipynb`. Nếu cần chọn kernel, chọn Python của
`arxiv-project`. Có thể thêm một cell kiểm tra rồi xóa cell sau khi kiểm:

```python
import sys
print(sys.executable)
print(sys.version)
```

Giữ terminal JupyterLab mở khi notebook đang chạy.

## 3. Chạy thử không gọi mạng

Ở mục **1. Setup**, giữ:

```python
ALLOW_NETWORK = False
CLONE_REPOSITORY = False
INSTALL_DEPENDENCIES = False
READ_COLAB_SECRET = False
```

Ở mục **2. Assigned ranges**, giữ `RUN_MODE='cold'`, `REQUIRE_COLAB_CPU=False`.
Để các assignment `None` vẫn được khi tắt mạng. Chọn **Kernel → Restart Kernel
and Run All Cells** (hoặc restart rồi Run All, tùy phiên bản giao diện).

Kỳ vọng: import/setup chạy, có thông báo chưa điền assignment và network disabled;
không có corpus hay số liệu crawl mới. Đây là kiểm tra môi trường, chưa là test API.
Không dùng các thông báo bỏ qua bước thu thập để kết luận crawler đã chạy thành công.

## 4. Chạy thử thật một bài BERT

Đây là ví dụ phát triển, không phải phạm vi chính thức. Bài mẫu là `1810.04805`.
Code phải tự xác minh lịch sử phiên bản, không tự nhập danh sách v1/v2.

Ở **1. Setup**, sửa:

```python
ALLOW_NETWORK = True
CLONE_REPOSITORY = False
INSTALL_DEPENDENCIES = False
READ_COLAB_SECRET = False
```

Ở **2. Assigned ranges**, thay đoạn cấu hình đầu bằng:

```python
ASSIGNMENTS = [
    {'member': 'Danh',   'start_month': '2018-10', 'start_id': 4805,
     'end_month': '2018-10', 'end_id': 4805},
    {'member': 'Khánh',  'start_month': None, 'start_id': None, 'end_month': None, 'end_id': None},
    {'member': 'Khang',  'start_month': None, 'start_id': None, 'end_month': None, 'end_id': None},
    {'member': 'Nguyên', 'start_month': None, 'start_id': None, 'end_month': None, 'end_id': None},
]
SELECTED_MEMBER = 'Danh'
MONTH_END_IDS = {}
RUN_MODE = 'cold'
EXISTING_ROOT = None
REQUIRE_COLAB_CPU = False
CREATE_REPORT_ZIP = True
DOWNLOAD_REPORT_ZIP = False
SCOPE_PURPOSE = 'development'
```

Chỉ thay cấu hình; giữ nguyên phần xử lý bên dưới. `Danh` ở ví dụ chỉ chọn dòng
cấu hình, không giới hạn pipeline chạy riêng module của Danh. Nếu chạy phần của
người khác, điền dòng của người đó và đổi SELECTED_MEMBER cho khớp.
Notebook bắt buộc có bốn dòng khác tên nhưng chỉ dòng được chọn cần điền để chạy.

Giữ POLICY mặc định; có thể thay user_agent bằng tên nhóm và email thật:

```python
'user_agent': 'ArxivCourseProject/0.1 (contact: email-that-cua-ban)',
```

Thay email mẫu bằng địa chỉ thực, không dùng API key ở đây. Giữ ít nhất 3 giây
giữa request arXiv; không giảm delay để chạy nhanh. Giữ s2_delay_seconds=3.1 lúc
thử; dịch vụ vẫn có thể trả 429 do giới hạn pool dùng chung.

Lưu notebook, restart kernel và Run All. Ghi lại dòng `Root:` hoặc `data root:`
trước bước Collection. Notebook có thể chỉ in dòng bắt đầu rồi chờ khá lâu vì
request, retry và lookup ngày tham khảo; chưa có tiến độ chi tiết từng request.
Không bấm Run All lần nữa khi kernel đang bận. Mỗi lần chạy cold với cấu hình
được thực thi lại sẽ sinh root mới và có thể tải lại toàn bộ.

Kết quả cần đọc: `Completed: success/partial/failed`, `run_id`, đường dẫn
`Per-run report snapshot` và `Report ZIP`. Nếu có exception thì xử lý exception
trước khi coi các cell sau là kết quả của lần chạy mới.

## 5. Kiểm tra kết quả thử

Output mặc định ở `C:\Users\ADMIN\Desktop\Do_an\arXivProject\data\milestone1`.
`RUN_FOLDER` và `run_id` là hai giá trị khác nhau; dùng đúng đường dẫn notebook in.

```text
data/milestone1/
  corpus/member-1/<RUN_FOLDER>/
    manifest.json
    1810-04805/
      metadata.json
      sources/v1/...
      sources/v2/...
      sources/.v1.receipt.json
      sources/.v2.receipt.json
      references.json
      .references_receipt.json
    metrics/run_summary.json
    metrics/resource_samples.json
    metrics/resource_errors.json
  reports/<run_id>/...
  archives/report-<run_id>.zip
```

`v1/v2` là lịch sử mẫu từng được kiểm tra; đối chiếu lịch sử hiện tại, không lấy
cấu trúc ví dụ làm nguồn quyết định số phiên bản.

Đọc lần lượt các mục của notebook:

| Mục | Điều cần kiểm |
|---|---|
| 5. Coverage and quality | Requested IDs=1; scope_complete=True; không discovery issue; đủ mọi version; không failed/pending |
| 6. Integrity audit | Mọi dòng audit valid=True; bảng outstanding tasks không có việc còn thiếu |
| 7. Corpus statistics | Có bảng/biểu đồ từ dữ liệu vừa thu, không từ mẫu giả |
| 8. End-to-end benchmark | Có samples, RAM/đĩa/thời gian; resource_errors rỗng; cold nếu tải mới |
| 9. Report export | Có JSON/CSV/figures và ZIP báo cáo |

Số tham khảo thay đổi theo lần cập nhật API; không yêu cầu đúng số 35 ghi trong
lịch sử phát triển. Phải kiểm phân trang đầy đủ, đủ trường bắt buộc và lỗi tra ngày.
`no_tex` không là lỗi mạng nhưng cũng không được tính là tải được TeX.
Run status success vẫn có thể bao gồm phiên bản no_tex; đọc cả số đếm chi tiết.

Trên Windows, dòng `Eligible as Colab benchmark ...: False` là bình thường.
Đang thử development nên các điều kiện assigned/Colab có thể False; không sửa
nhãn thành assigned hoặc Colab để làm bảng kiểm xanh.

Ngoài audit tự động, làm đối chiếu độc lập:

1. Mở trang abstract BERT `https://arxiv.org/abs/1810.04805`, so title, toàn bộ
   tác giả, ngày v1 và lịch sử sửa với metadata/manifest.
2. Mở từng thư mục source, xác nhận có TeX, giữ lệnh figure/table, không còn ảnh
   nhị phân. Không bắt buộc bài nào cũng có `.bib`: có bài dùng `\bibitem`.
3. Nếu kiểm byte nguồn, tải archive của đúng version độc lập vào thư mục tạm
   ngoài corpus; so các file text được giữ. Không dùng PDF để đối chiếu byte TeX.
4. Lấy vài mục references.json, đối chiếu ID/tên/tác giả/S2 ID với Semantic
   Scholar và ngày gửi v1 với arXiv. references.json mô tả bài được trích dẫn,
   không phải metadata bài chính. Không cần tải source của các bài tham khảo.

Audit hash chỉ chứng minh file local khớp receipt, không chứng minh nội dung đã
khớp nguồn độc lập. Lưu ghi chú đối chiếu và những thiếu sót để viết báo cáo.

## 6. Test chạy tiếp và xem lại

### Resume cùng bài và root

Giữ ALLOW_NETWORK=True và assignment BERT y hệt, đổi:

```python
RUN_MODE = 'resume'
EXISTING_ROOT = r'C:\Users\ADMIN\Desktop\Do_an\arXivProject\data\milestone1\corpus\member-1\ROOT_THAT_DA_IN'
SCOPE_PURPOSE = 'development'
```

Thay ROOT_THAT_DA_IN bằng root thực tế có manifest.json, không dùng đường dẫn
reports hoặc archives. Restart kernel rồi Run All. Discovery vẫn gọi mạng;
nguồn/tham khảo hợp lệ được xác minh receipt trước khi dùng cache. Kiểm used_cache,
cache_hits, attempts và benchmark.cache_mode (resume/mixed). Run_id mới được tạo,
report cold cũ giữ riêng. Không dùng số đo resume làm số đo tải mới.

Có thể thử ngắt bằng nút Interrupt sau khi đã có checkpoint, rồi resume đúng root.
Không xóa corpus để thử; giữ bản cold/report gốc trước thử gián đoạn hoặc file hỏng.
Sau khi resume, kiểm lại đủ source, references, audit và outstanding tasks.
Nếu mạng lỗi ở discovery, resume có thể chưa tái xác minh được kết quả cũ của run;
không tự đổi pending thành success bằng tay.

### Analyze không gọi mạng

Với một run đã hoàn tất lưu summary khớp manifest:

```python
ALLOW_NETWORK = False        # ở Setup
RUN_MODE = 'analyze'         # ở Assigned ranges
EXISTING_ROOT = r'C:\...\corpus\member-1\ROOT_THAT'
REQUIRE_COLAB_CPU = False
```

Restart kernel rồi Run All. Đọc bảng/biểu đồ từ dữ liệu và số đo đã lưu.
Nếu báo summary thuộc run cũ thì resume để hoàn tất run bị ngắt trước; không sửa run_id.

## 7. Điền phạm vi chính thức

Chỉ thay ví dụ BERT khi đã có phạm vi của thầy/TA. Với ID `2310.01234`, điền
tháng `'2023-10'` và hậu tố số `1234` (hoặc chuỗi `'01234'`). Không nhập cả ID
vào start_id/end_id, không thêm hậu tố v1. Python tự thêm số 0 đầu theo tháng.
Không viết literal số nguyên `01234` vì Python không cho phép.

Ví dụ cách chuyển định dạng, KHÔNG phải phạm vi được giao:

```python
{'member': 'Danh', 'start_month': '2023-10', 'start_id': 1234,
 'end_month': '2023-10', 'end_id': 1236}
```

Hai đầu được tính, nên ví dụ yêu cầu ba ID: 2310.01234, 2310.01235, 2310.01236.
Để chạy chính thức đổi SCOPE_PURPOSE='assigned', RUN_MODE='cold',
EXISTING_ROOT=None. Thử một nhóm nhỏ thuộc phạm vi bằng development trước;
không báo nhóm nhỏ là đã phủ hết assignment.

Nếu qua nhiều tháng, MONTH_END_IDS phải có ID cuối ĐÃ XÁC MINH của từng tháng
trước tháng kết thúc. Không đoán từ hình minh họa và không điền 99999. Nếu phạm vi
trước tháng 04/2007 hoặc dùng ID kiểu cũ, cấu hình tháng hiện tại không hỗ trợ:
cần cấu hình Scope ids đã xác minh riêng trước khi chạy.

Mỗi SELECTED_MEMBER chỉ chạy một đoạn. Lặp cho bốn đoạn, hoặc phân công mỗi người
chạy đoạn mình. Kiểm tổng hợp không thiếu/không trùng phạm vi được giao.
Notebook chưa tự gộp bốn run thành báo cáo toàn nhóm. Tổng hợp JSON/CSV theo
run_id/arxiv_id/version; tỷ lệ toàn nhóm phải tính lại từ tổng tử số/mẫu số,
không lấy trung bình đơn giản các tỷ lệ của bốn đoạn khác kích thước.

## 8. Khi gặp lỗi

| Hiện tượng | Làm gì |
|---|---|
| ModuleNotFoundError | So sys.executable; chọn đúng kernel; cập nhật môi trường nếu thiếu package |
| Network disabled | Bật ALLOW_NETWORK ở Setup rồi chạy lại các cell từ đầu |
| Fill all four range fields | Điền bốn trường của dòng SELECTED_MEMBER; không phải bắt buộc điền cả bốn thành viên để thử một dòng |
| Timeout/429/5xx | Đọc outstanding_tasks.csv hoặc discovery issues; đợi, kiểm mạng/key, resume đúng root; không liên tục chạy cold |
| S2 404/not_found | Kiểm ID và khả năng bài chưa được S2 lập chỉ mục; ghi giới hạn, không coi đó là danh sách rỗng hợp lệ |
| Missing submission dates/partial | Tra ngày tham khảo chưa hoàn tất; resume và kiểm lại trường thiếu |
| Cold run requires a new empty root | Dùng cold root mới hoặc resume root cũ; không xóa dữ liệu để bỏ qua lỗi |
| Resume scope differs | Giữ assignment đúng scope trong manifest; đổi phạm vi thì dùng root mới |
| Integrity valid=False | Giữ bản sao, xem file/receipt lỗi; resume để owner xác minh/tải lại; không sửa hash bằng tay |
| Final benchmark requires Colab CPU | Trên Windows đặt REQUIRE_COLAB_CPU=False; chỉ bật True khi chạy Colab CPU |

Key S2 tùy chọn. Nếu đã có key, đặt trong Anaconda Prompt TRƯỚC khi mở JupyterLab:

```bat
set "S2_API_KEY=KEY_THAT_CUA_BAN"
python -m jupyterlab
```

Thay placeholder bằng key thực, không đưa key vào notebook/Git/ảnh chụp.
Nếu Jupyter đã mở trước khi set key, dừng và mở lại từ terminal chứa biến môi trường.
Không có key vẫn có thể thử nhưng có thể bị giới hạn pool dùng chung.

## 9. Benchmark cuối trên Colab CPU

Mở notebook từ repository đã push hoặc upload notebook/source cùng phiên bản.
Trong Colab chọn **Runtime → Change runtime type → Hardware accelerator: None**.
Tài liệu: https://research.google.com/colaboratory/faq.html

Ở Setup:

```python
ALLOW_NETWORK = True
CLONE_REPOSITORY = True
INSTALL_DEPENDENCIES = True
READ_COLAB_SECRET = False    # True nếu đã tạo secret S2_API_KEY và cấp quyền
```

Nếu cài thư viện yêu cầu restart session, restart rồi đặt INSTALL_DEPENDENCIES=False
và chạy lại setup. Clone dùng source remote, không gồm chỉnh sửa local chưa push.
Clone không tự pull checkout đã tồn tại; dùng runtime mới khi cần revision sạch.

Điền phạm vi chính thức của người được chọn và đặt:

```python
RUN_MODE = 'cold'
EXISTING_ROOT = None
SCOPE_PURPOSE = 'assigned'
REQUIRE_COLAB_CPU = True
CREATE_REPORT_ZIP = True
DOWNLOAD_REPORT_ZIP = True
```

Giữ data_root mặc định `/content/arxiv-data` để đo trên đĩa runtime. Chạy pipeline,
kiểm lại chất lượng và các điều kiện benchmark; lưu môi trường, cấu hình, nhịp
API, samples, lỗi, cold/resume rõ ràng. Kết quả partial vẫn phải báo trung thực;
không giấu no_tex hoặc đổi tên kết quả resume thành cold.

Tải ZIP báo cáo và sao lưu corpus riêng sau khi đo; ZIP không chứa corpus.
Các file trong VM Colab có thể mất khi runtime kết thúc, không phải tự lưu vào Drive.
Nếu ngắt rồi resume, đó là kết quả phục hồi, không thay thế phép đo cold liên tục.
Đo lại cold trên root mới nếu cần phép đo tải mới; giữ cả kết quả trước đó để giải thích.

Mỗi đoạn có benchmark riêng; nêu rõ nếu nhóm đo bằng nhiều run. Tổng thời gian
các đoạn nối tiếp khác thời gian nhóm chạy song song. Không cộng RAM peak của
bốn máy và gọi là RAM peak quan sát của một hệ thống.

## 10. Checklist hoàn thành và nộp

- [ ] Đã xác nhận toàn phạm vi chính thức của cả nhóm và các version.
- [ ] Có nguồn hoặc no_tex hợp lệ cho từng version; lỗi chưa giải quyết được ghi rõ.
- [ ] Metadata bài và tham khảo đúng trường/kiểu/ngày, đã kiểm tra nguồn độc lập.
- [ ] Audit file đạt; outstanding tasks đã xử lý hoặc giải thích đầy đủ.
- [ ] Có thống kê toàn nhóm với mẫu số và cách tính rõ ràng.
- [ ] Có benchmark Colab CPU thật, điều kiện cache/nhịp API/retry được ghi lại.
- [ ] Corpus và report bundle đã sao lưu, sẵn cho Milestone 2.
- [ ] Code công khai, README/requirements đủ để người khác chạy.
- [ ] Jupyter Book tiếng Anh trong repo riêng, GitHub Pages truy cập công khai.
- [ ] Book giải thích cách crawl, công cụ, chất lượng, thống kê, hiệu năng, lỗi,
      giới hạn và trích dẫn; bảng/biểu đồ sinh lúc build từ dữ liệu thật.
- [ ] Đã thử mở hai link khi chưa đăng nhập và nộp Moodle trước hạn TA.

Không commit data/, ZIP, key hay output crawl nhúng trong notebook. Trước commit,
clear outputs và kiểm diff. Hướng dẫn này không tự chạy crawl, không tạo phạm vi
thay cho TA, không chứng nhận dữ liệu đã thu hoặc benchmark đã đạt.
