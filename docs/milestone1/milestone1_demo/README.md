# Ví dụ làm tay Milestone 1

Ngày thực hiện: 11/10/2026. Đây là hai bài tự chọn để minh họa, không phải danh sách trợ giảng giao.

## Đã làm thật

| Bài | arXiv ID | Các phiên bản đã tải |
|---|---|---|
| BERT | 1810.04805 | v1, v2 |
| RoBERTa | 1907.11692 | v1 |

Nguồn kiểm tra metadata và lịch sử phiên bản:

- https://arxiv.org/abs/1810.04805
- https://arxiv.org/abs/1907.11692

Mỗi thư mục bài có `metadata.json` chép tay theo trang arXiv. Mỗi thư mục phiên bản có nguồn thật tải từ `https://export.arxiv.org/src/{id}v{version}`. File `source.download` là gói tải gốc, được giữ riêng để đối chiếu; các file được giải nén bên cạnh chỉ giữ phần văn bản có đuôi tex/bib/bbl/bst/sty/cls/txt/def/cfg/clo/ltx, không giữ hình ảnh nhị phân. Nội dung các file văn bản được giữ nguyên, kể cả lệnh chèn hình.

| Phiên bản | Gói tải nén (byte) | Văn bản giữ lại, chưa nén (byte) | Số file văn bản |
|---|---:|---:|---:|
| BERT v1 | 232356 | 139057 | 19 |
| BERT v2 | 316748 | 173865 | 24 |
| RoBERTa v1 | 45873 | 159629 | 25 |

Hai cột dung lượng dùng cách đo khác nhau (nén và chưa nén), không dùng chúng để tính phần trăm tiết kiệm do bỏ hình. Gói tải gốc vẫn còn nên tổng dung lượng thư mục bao gồm cả gói và phần giải nén.

## Xem tham khảo bằng tay

- `1907-11692/v1/main.bbl`, dòng 57–60: mục có khóa `devlin2018bert`, tác giả Devlin và cộng sự, tên bài BERT. Đối chiếu trang arXiv cho thấy bài tương ứng là `1810.04805`.
- `1810-04805/v2/main.bbl`, dòng 314–318: mục có khóa `vaswani-etal:2017:_atten`, tác giả Vaswani và cộng sự, tên bài Attention Is All You Need. Trang https://arxiv.org/abs/1706.03762 xác nhận mã bài `1706.03762`.

Đó chỉ là hai tham khảo được chọn để giải thích; mỗi bài còn nhiều tham khảo khác. Attention là bài được BERT tham khảo, không nằm trong hai bài chính đã tải ở ví dụ này. Milestone 1 yêu cầu metadata tham khảo, không yêu cầu tải toàn bộ nguồn của tất cả bài được tham khảo.

## Danh sách tham khảo và metadata đã lấy thành công

API lấy từng bài trả HTTP 429, nhưng API batch chính thức đã trả thành công dữ liệu cả hai bài trong một yêu cầu. Phản hồi gốc nằm trong `semantic_scholar_response.json` của mỗi bài.

| Bài | Tổng tham khảo Semantic Scholar trả về | Có mã arXiv, giữ trong references.json | Không có mã arXiv, chỉ giữ trong phản hồi gốc |
|---|---:|---:|---:|
| BERT | 63 | 35 | 28 |
| RoBERTa | 68 | 40 | 28 |

Hai file `references.json` đã được tạo. Mỗi mục có tên bài, danh sách tác giả, ngày gửi lên arXiv và mã Semantic Scholar. Ngày gửi được bổ sung bằng một truy vấn arXiv API cho 65 mã tham khảo khác nhau giữa hai bài; phản hồi gốc được lưu ở `reference_arxiv_metadata.xml`. Đã có ngày gửi cho toàn bộ 75 mục tham khảo trong hai file (một số bài được cả BERT và RoBERTa cùng tham khảo). Trường `publication_date` bổ sung giữ riêng ngày xuất bản Semantic Scholar trả về, có thể null và không dùng thay ngày gửi arXiv.

Ví dụ thật: `1907-11692/references.json` có khóa `1810-04805` tương ứng BERT; `1810-04805/references.json` có khóa `1706-03762` tương ứng Attention Is All You Need.

## Phần chưa hoàn thành

Ví dụ này chưa đo thời gian/RAM theo benchmark Colab và chưa tạo báo cáo Jupyter Book. Khi làm bài nộp, phải bổ sung các phần đó và chạy tự động trên phạm vi bài được giao.
