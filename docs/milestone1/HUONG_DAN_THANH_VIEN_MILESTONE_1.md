# Hướng dẫn thành viên bắt đầu và bàn giao Milestone 1

Cập nhật **17/10/2026**, giữ cùng [doc phân công](./PHAN_CONG_MILESTONE_1_4_NGUOI.md) và [doc kế hoạch](./KE_HOACH_MILESTONE_1.md). Kế hoạch là nơi ghi cách làm, quyết định kỹ thuật và đầy đủ nguồn tham khảo; hướng dẫn này mô tả việc thành viên cần kiểm và bàn giao.

## 1. Hiểu hiện trạng trước khi sửa

Đọc [đề tổng](../../ARXIV_PROJECT_FULL.md), README và contract `src/crawling/__init__.py`. Crawler đã triển khai, không còn là bộ prototype. Metadata/discovery/ngày gửi references chỉ dùng OAI-PMH **GetRecord + arXivRaw**; source ở export mirror và references từ S2 là hai công việc riêng theo đề.

Không khôi phục Query API/Atom/HTML/Kaggle discovery hoặc mock metadata vào run thật. Sickle/ListRecords trong đề là ví dụ bulk harvesting; cách GetRecord theo ID hiện tại được giải thích/cite trong kế hoạch.

## 2. Leader chuẩn bị và thành viên cài môi trường

Leader cung cấp code revision, phân công bốn người, range TA giao từng người và thông tin report repo. Danh có `2606.15734`–`2606.20733`; ba range khác vẫn cần được xác nhận. Không tự bịa range hoặc số phiên bản.

Tạo môi trường theo `environment.yml` hoặc `src/requirements.txt`, Python >= 3.11; mở notebook chung [milestone1.ipynb](../../src/notebooks/milestone1.ipynb). Chọn đúng kernel. [Hướng dẫn chạy Windows/Colab](./CHAY_VA_KIEM_TRA_WINDOWS.md) mô tả cấu hình cold/resume/analyze.

## 3. Làm đúng module và hợp đồng

Khánh: OAI; Khang: source; Nguyên: references; Danh: pipeline/metrics/report. Input/output và quyền ghi file ở doc phân công. Khi đổi tên field/status/schema, cập nhật tất cả consumer/test/notebook/docs cùng lúc. Schema hiện tại 3.0.

Notebook gọi nghiệp vụ từ `.py`; không chép crawler riêng vào cells. Pipeline dùng shared OAI client cho discovery và ngày gửi references. Các thử nghiệm dùng fake HTTP chỉ nằm trong tests, không tạo corpus chính thức.

## 4. Comments và citations khi chỉnh code

- Đọc yêu cầu General Requirements trong đề: code phải có documentation/comments rõ và trích dẫn đầy đủ tài liệu online đã dùng.
- Docstring giải thích mục đích, input/output, side effects hoặc lỗi quan trọng. Comment tập trung lý do: datestamp khác ngày v1, no_tex khác failed, giữ mọi references, trường/mẫu số, TTL và cache provenance.
- Khi tham khảo tài liệu mới, ghi tổ chức/tác giả, tên tài liệu, ngày/phiên bản nếu có, URL, ngày truy cập và phần áp dụng vào **mục 10 của kế hoạch**; cập nhật phần References của Book khi viết báo cáo.
- Không viết comment cam kết sai hành vi hoặc giữ hướng dẫn cũ sau khi đổi code. Không gán quyết định riêng như TTL 24 giờ thành quy định arXiv.
- Không chỉ đổi comment để nói đạt; phải đọc code/kiểm thử dữ liệu thực tương ứng.

## 5. Kiểm chứng và thử thật

27 regression tests và hai notebook kernels đã đạt trước khi dọn. Theo yêu cầu, thư mục tests, toàn bộ data/output tạm và environment local kiểm thử đã xóa; checkout không cung cấp các script test cũ. Xem kết quả lịch sử trong kế hoạch.

Lần chạy mới: mở notebook GitHub trên Colab CPU, thử một ID development với cold root mới, kiểm audit và so nguồn độc lập rồi mới tăng scope. Notebook preset hiện là 100 ID Danh, không phải một ID. [Hướng dẫn Colab từng bước](./CHAY_VA_KIEM_TRA_WINDOWS.md#7-chạy-lại-colab-từ-bản-github-vừa-push).

Giữ delay tối thiểu arXiv 3 giây, mặc định 3,1 giây; cả nhóm điều phối tuần tự vì giới hạn tính chung các máy. 429/503 có thể xảy ra, không giảm nhịp hoặc đổi sang metadata route cũ để né lỗi.

## 6. Kiểm tay theo vai trò

| Thành viên | Nội dung kiểm |
|---|---|
| Khánh | Metadata đúng ID, title/authors, đủ versions và ngày v1/revisions; đối chiếu raw XML/arXiv |
| Khang | Chỉ `.tex`/`.bib`, byte khớp archive, lệnh hình/bảng nguyên; no_tex empty có receipt |
| Nguyên | Đủ trang/mọi reference rows, pool arXiv riêng, legacy IDs/ngày OAI/provenance; missing fields được báo |
| Danh | Manifest/file counts, source/reference/raw cache audit, run_id, samples/benchmark/report ZIP và phạm vi |

Chỉ thử phá cache/file trên bản sao. Hash là bằng chứng toàn vẹn snapshot, không thay đối chiếu nguồn độc lập.

## 7. Ghi bằng chứng và bàn giao

Ghi code revision, scope/root/run_id, environment, lệnh và output kiểm, vài mẫu kiểm tay, dữ liệu lỗi và giới hạn. Không commit corpus, key, archive hoặc notebook outputs. Clear outputs notebook chính; giữ bản đã thực thi trong data/report snapshot.

Bàn giao module diff, kiểm thử và phần phương pháp/kết quả tiếng Anh cho Book, kèm citations. Không dùng số tham khảo/version hardcode từ một bài mẫu làm kết quả mọi bài. Chưa kiểm thì ghi chưa kiểm; API lỗi thì ghi lỗi, không điền dữ liệu đoán.

## 8. Tích hợp và hoàn thành M1

Danh tích hợp một pipeline thật, audit hai reference stores/source/raw checkpoints, thống kê và resource sampling. Cả nhóm crawl đủ bốn range, xử lý/giải thích lỗi, sao lưu corpus; benchmark cuối cold Colab CPU.

Báo cáo là Jupyter Book tiếng Anh repo công khai riêng trên GitHub Pages, bảng/hình sinh khi build từ dữ liệu thật. README code repo hướng dẫn cài/chạy. Kiểm public links và nộp code + report qua Moodle đúng hạn; M1 không nộp data, giữ corpus cho M2/M3.

Thử thật một bài đã thành công trước đợt dọn; corpus lịch sử đã xóa, số liệu được ghi ở [OAI hiện tại](./OAI_RAW_HIEN_TAI.md). Đây là kiểm software/local, không đánh dấu cả milestone đã hoàn thành.
