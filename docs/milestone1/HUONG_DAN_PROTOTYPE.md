# Cách dùng bộ prototype Milestone 1

Đây là **khung hợp đồng và hàm chưa triển khai**, không phải crawler hoàn thành.
Mọi hàm nghiệp vụ có chữ ký và docstring tiếng Việt, thân hàm chỉ raise
NotImplementedError. Không cào mạng khi import hay khi chạy notebook mặc định.

## Những gì được chuẩn hóa

**Khánh đã chốt dùng arXiv API**, hướng requests + Atom/XML. Không cần
triển khai Kaggle hay OAI-PMH. Docstring discover.py mô tả tìm ID, phân trang,
metadata và xác minh phiên bản; thân hàm vẫn chưa triển khai.

- `src/crawling/__init__.py`: TypedDict dùng chung cho input/output; đọc trước.
- `src/crawling/fixtures.py`: hằng số mẫu đúng schema cho các thành viên phát triển
  không chờ nhau. Các số đo và danh sách rút gọn là giả lập, không dùng báo cáo nộp.
- Các module discover/download/references/pipeline/metrics: prototype theo phân công.
- Notebook chính: nạp mẫu, xem đầu vào/đầu ra và các lệnh gọi thật sau cờ RUN mặc định False.

**Điều chỉnh so với bản phân công cũ:** discovery trả DiscoveryResult thay vì list
đơn lẻ để ghi nhận bài lỗi/quét thiếu. Danh sách nằm ở `result['papers']`.
Tra ngày trả DateLookupResult gồm dates và errors thay vì dictionary ngày đơn lẻ.
Các hàm HTTP nhận keyword policy; collect_references nhận date_lookup đã gắn policy.
Chữ ký và kiểu trong source là hợp đồng mới nhất; không dùng mock theo chữ ký cũ.

## Ai nhận mẫu nào?

| Người | Input mẫu để làm ngay | Output phải theo |
|---|---|---|
| Khánh | SCOPE, HTTP_POLICY | DISCOVERY_RESULT, PAPER_BERT, DATE_RESULT |
| Khang | PAPER_BERT.arxiv_id + từng version + Path tạm | DOWNLOAD_RESULT/NO_TEX/FAILED |
| Nguyên | ID bài + Path tạm + DateLookup cùng kiểu DATE_RESULT | REFERENCE_RESULT/FAILED |
| Danh | DISCOVERY_RESULT, MANIFEST, RESOURCE_SAMPLES | RunResult, CorpusSummary, BenchmarkResult |

Fixture là hằng số, không có fake function chạy thay nghiệp vụ. Khi cần tiêm
dependency cho pipeline, nhóm tự viết fake function cùng chữ ký, chỉ trong môi
trường kiểm tra. Danh không cần chờ dữ liệu thật để làm bộ tổng hợp từ MANIFEST.
Luôn deepcopy khi sửa fixture để thử lỗi, tránh chia sẻ trạng thái.

## Protocol, fixture và mock khác nhau thế nào?

| Khái niệm | Trong bộ khung này | Hiểu đơn giản |
|---|---|---|
| Protocol | DiscoverCallable, DatesCallable, DownloadCallable, ReferencesCallable | Bản quy định một hàm phải nhận gì, trả gì |
| Hàm thật | discover_papers, download_version, collect_references... sau khi triển khai | Gọi dịch vụ/xử lý dữ liệu thực tế |
| Fixture | Các dictionary trong fixtures.py | Input/output mẫu đặt sẵn để người khác phát triển trước |
| Mock/fake | Chưa viết hàm thay thế sẵn trong bộ khung | Một hàm giả được viết khi kiểm tra, trả dữ liệu mẫu thay cho gọi mạng |

`__call__` trong Protocol mô tả chữ ký của hàm được nhận vào; không có nghĩa
nhóm phải tạo một object DiscoverCallable để dùng. `policy` là cấu hình thời
gian chờ, retry và User-Agent. Dấu `*` buộc truyền bằng tên: policy=policy.

Ví dụ đọc `DiscoverCallable`: “ai đưa hàm discovery vào pipeline, hàm đó phải
nhận scope, nhận keyword policy, trả DiscoveryResult”. Hàm discover_papers thật
đã có đúng khuôn này. Khang có thể lấy `DISCOVERY_RESULT['papers'][0]` từ
fixture để thử tải trước khi người 1 hoàn thành; riêng thao tác đó không cần
Protocol hay mock.

Protocol giúp IDE/type checker phát hiện chữ ký không khớp; Python không tự
kiểm tra toàn bộ giá trị trả về lúc chạy chỉ vì có Protocol/TypedDict. Khi ghép
vẫn cần kiểm tra dữ liệu và thử luồng thực tế. Không tạo thân hàm mock trong
source nghiệp vụ; giữ đúng yêu cầu chỉ prototype.

## Dùng notebook

Chọn Python >=3.11. Từ thư mục project chạy Jupyter, mở
`src/notebooks/milestone1.ipynb`. Notebook tìm src từ thư mục project hoặc
src/notebooks; Colab cần tải/clone code rồi cấu hình SRC trỏ tới thư mục src.
Prototype import bằng thư viện chuẩn, chưa phải cài requirements để xem mẫu.
Phụ thuộc requirements là gợi ý chưa khóa; không coi là môi trường đã benchmark.

Các ô gọi crawler thật được bảo vệ bởi cờ RUN=False trong ô setup; chỉ bật cờ
phần mình sau triển khai. Mỗi phần dùng biến riêng, chạy được sau setup mà
không cần chạy phần người khác. USE_REAL_DATES=False chỉ dành thử độc lập;
bật True khi Khánh đã triển khai và chạy lại không cache trước khi dùng ngày thật. TypedDict
không xác minh dữ liệu tự động khi chạy: implementer phải viết kiểm tra schema,
ngày, ID, null/status và bất biến trước khi ghi file/bàn giao.

## Đối chiếu yêu cầu đề và người chịu trách nhiệm

| Yêu cầu Milestone 1 | Prototype/công việc phụ trách |
|---|---|
| Phạm vi được giao, đủ phiên bản, metadata bài | discover_papers, fetch_paper |
| Nguồn mọi phiên bản; nhiều dạng gói; PDF-only giữ bản ghi | download_version, prepare_source |
| Giữ văn bản/BibTeX và lệnh hình, bỏ ảnh nhị phân | prepare_source |
| Metadata tham khảo S2, mã cũ, ngày gửi | collect_references + fetch_submission_dates |
| Lưu nguồn/metadata/references, lỗi và resume | pipeline + module ghi nguồn/tham khảo |
| Thống kê thành công, kích thước trước/sau, tham khảo | summarize_corpus |
| Thời gian end-to-end, RAM/đĩa toàn hệ thống, Colab CPU | collect_resource_samples + summarize_benchmark + run_pipeline |
| README môi trường/cách chạy, requirements, code công khai | Danh và cả nhóm, sau triển khai |
| Jupyter Book riêng; bảng/biểu đồ sinh lúc build | export_report_data + notebook báo cáo ở repo riêng |
| Nộp hai link Moodle đúng hạn, không nộp corpus giữa kỳ | Nhóm làm thủ công sau khi kiểm tra |

Giao diện khớp nhau là điều kiện cần, không đủ để tuyên bố hoàn thành đồ án:
vẫn phải triển khai đúng thuật toán, xác minh corpus trong phạm vi được giao,
benchmark thật, báo cáo và nộp. Cây prototype không tự tạo repo Book hoặc publish.

## Checklist bàn giao từng module

- Đúng chữ ký hàm và toàn bộ trường output trong __init__.py, không đổi tên khóa.
- Trả đúng status; null khác 0; không giấu thiếu trang/thiếu phiên bản.
- Đơn vị, ngày, mã và đường dẫn đúng quy ước; JSON round-trip không đổi schema.
- Nguồn/file cũ hợp lệ không bị lỗi mới ghi đè; cache phải được xác minh.
- Thử dữ liệu bình thường, không có TeX, API 429, thiếu ngày, mã cũ và resume.
- Không commit corpus, key, log hay output cào hàng loạt vào repository code.
- Báo cáo/README nộp viết tiếng Anh; prototype/comment nội bộ viết tiếng Việt.

## Một notebook chung

Chỉ dùng src/notebooks/milestone1.ipynb, chia phần Khánh/Khang/Nguyên/Danh. Không tạo notebook riêng. Quy trình kiểm tra và phối hợp sửa file nằm trong [bản phân công mới](./PHAN_CONG_MILESTONE_1_4_NGUOI.md), mục 7–8.

Mục 11–17 của bản phân công có prompt cho AI từng người, hướng dẫn mở browser/
file để kiểm tra tay, ca lỗi, nghiệm thu và ghi bằng chứng trong notebook.
SourceReceipt/ReferenceReceipt trong __init__.py quy định cache đã xác minh;
CorpusSummary bổ sung tỷ lệ metadata tham khảo đầy đủ và mẫu số. Đây là quy
ước của nhóm, không phải tất cả đều là tên trường do thầy yêu cầu.
