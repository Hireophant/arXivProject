# Hướng dẫn thành viên bắt đầu và bàn giao Milestone 1

Tài liệu dành cho leader Danh và các thành viên Khánh, Khang, Nguyên. Ghi lại quy trình từ nhận việc, giao prompt cho AI, triển khai, kiểm tra tay đến tích hợp, chạy Colab CPU và nộp báo cáo.

Đọc cùng [bản phân công](./PHAN_CONG_MILESTONE_1_4_NGUOI.md), [kế hoạch](./KE_HOACH_MILESTONE_1.md) và [đề bài](../../ARXIV_PROJECT_FULL.md). Prompt và ca kiểm tra chi tiết nằm trong bản phân công; tài liệu này hướng dẫn sử dụng chúng.

## 1. Hiểu mục tiêu và tình trạng ban đầu

Milestone 1 thu thập nguồn mọi phiên bản của các bài arXiv được giao, metadata bài và metadata tài liệu tham khảo; sau đó kiểm tra, thống kê, benchmark và báo cáo. Chưa cần parse cây nội dung, chuẩn hóa/deduplicate BibTeX hoặc huấn luyện mô hình của Milestone 2–3.

Tại thời điểm viết hướng dẫn, repository là bộ khung: hàm nghiệp vụ còn `NotImplementedError`, fixture là dữ liệu giả, notebook mặc định chưa gọi mạng. BERT/RoBERTa chỉ là mẫu phát triển; chưa có phạm vi chính thức từ thầy được ghi nhận trong tài liệu.

**Phân công đã bao phủ các phần chính, nhưng fill hết hàm và chạy xong bốn prompt chưa tự động đồng nghĩa hoàn thành milestone.** Còn phải kiểm tra bằng hàm thật, chạy phạm vi được giao, benchmark Colab CPU, hoàn thiện Jupyter Book và nộp hai link đúng hạn. Prompt Danh hiện yêu cầu báo rõ các phần chưa thực hiện, nên AI có thể làm đúng prompt mà những phần này vẫn còn.

## 2. Leader gửi gì cho nhóm?

Danh gửi link repository và yêu cầu mỗi người làm trên bản clone riêng ở máy mình. Mọi người cần biết tên phần phụ trách, file được sửa và tiêu chí bàn giao trước khi bắt đầu.

| Người | Công việc | Module phụ trách |
|---|---|---|
| Khánh | Discovery, metadata, xác minh mọi phiên bản, tra ngày gửi | `src/crawling/discover.py` |
| Khang | Tải và xử lý nguồn từng phiên bản, giữ text và bỏ ảnh | `src/crawling/download.py` |
| Nguyên | Metadata tham khảo từ Semantic Scholar và bổ sung ngày gửi | `src/crawling/references.py` |
| Danh | Pipeline, tiến độ/resume, thống kê, đo tài nguyên, tích hợp và báo cáo | `src/crawling/pipeline.py`, `src/crawling/metrics.py` |

Chỉ dùng một notebook: `src/notebooks/milestone1.ipynb`. Mỗi người sửa phần cell của mình trong bản clone riêng; Danh phối hợp merge lần lượt để không đè/mất cell.

## 3. Chuẩn bị repository và môi trường

1. Clone repository về máy. Nếu đã clone, cập nhật code mới nhất trước khi bắt đầu; giữ lại công việc đang làm, không reset/xóa thay đổi chưa bàn giao.
2. Tạo branch riêng, ví dụ `codex/khanh-discovery`, `codex/khang-download`, `codex/nguyen-references`, `codex/danh-integration`.
3. Dùng Python **3.11 trở lên**, tạo môi trường ảo và cài thư viện theo [README](../../README.md).
4. Mở **cả thư mục project** trong công cụ AI để AI đọc được tài liệu, schema, module và notebook. Chỉ gửi đoạn prompt vào một chat không có repository thì chưa đủ ngữ cảnh.
5. Mở Jupyter từ thư mục project và chọn Python kernel của môi trường vừa tạo.

Ví dụ lệnh trên Windows PowerShell, chạy tại thư mục project sau khi clone:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/requirements.txt
.\.venv\Scripts\python.exe -m jupyterlab
```

Trên macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python -m jupyterlab
```

Requirements hiện là phụ thuộc dự kiến, chưa phải môi trường đã kiểm chứng. Nếu cần thêm thư viện, báo Danh cập nhật requirements và kiểm tra trên môi trường sạch. Việc chỉ import bộ khung/xem fixture hiện dùng thư viện chuẩn.

## 4. Đọc tài liệu và gửi đúng prompt cho AI

Mở [PHAN_CONG_MILESTONE_1_4_NGUOI.md](./PHAN_CONG_MILESTONE_1_4_NGUOI.md):

| Người | Phần công việc | Prompt cần chép | Kiểm tra tay |
|---|---|---|---|
| Khánh | Mục 3 | Mục 11 → Prompt Khánh | Mục 12 |
| Khang | Mục 4 | Mục 11 → Prompt Khang | Mục 13 |
| Nguyên | Mục 5 | Mục 11 → Prompt Nguyên | Mục 14 |
| Danh | Mục 6 | Mục 11 → Prompt Danh | Mục 15 |

Cả nhóm đọc thêm mục **1–2, 7–8 và 16–17** để hiểu quy ước chung, notebook, kiểm tra và ghi bằng chứng. Chép nguyên prompt của mình gửi AI trong chat đã mở project, rồi yêu cầu thực hiện đúng phạm vi.

AI phải đọc repository thực tế trước khi sửa, theo thứ tự mục 11:

1. `ARXIV_PROJECT_FULL.md`: Milestone 1, Requirement, Submission Format và Report Requirements.
2. Bản phân công: mục 1–2, phần người phụ trách, mục 7–8 và 11–17.
3. Tài liệu hướng dẫn thành viên này.
4. Toàn bộ kiểu dữ liệu và quy ước trong `src/crawling/__init__.py`.
5. Module được giao và chữ ký các module liên quan.
6. `src/crawling/fixtures.py` và phần của mình trong notebook chung.

Đề bài quyết định yêu cầu môn học; schema và chữ ký hiện tại quyết định giao diện trong nhóm. Khi tài liệu cũ khác giao diện, dùng bản phân công cập nhật và source hiện tại. Mâu thuẫn cần báo rõ để nhóm xử lý đồng bộ.

## 5. Triển khai đúng phạm vi và hợp đồng

Viết hàm thật trong module `.py` phụ trách. Notebook dùng để gọi hàm, kiểm tra và ghi bằng chứng; không chép toàn bộ thân hàm vào cell.

- Chỉ sửa module và cell được giao; có thể thêm helper private trong module theo bản phân công.
- Không tự đổi chữ ký, keyword, tên khóa, kiểu dữ liệu, Protocol hoặc schema trong `__init__.py`.
- Không sửa fixture để làm kết quả sai trông như đúng; dùng `deepcopy` khi thử biến thể.
- Không trả fixture thay dữ liệu thật trong crawler, không hardcode phiên bản/kết quả BERT.
- Không implement phần của thành viên khác. Nếu AI cần đổi giao diện chung, báo Danh và nhóm thống nhất trước khi cập nhật các bên dùng.
- Ghi đúng status, ngày, ID, đường dẫn và đơn vị; `None` là chưa biết, khác `0`. Không biến lỗi API thành danh sách rỗng hoặc `no_tex`.
- File/cache phải được xác minh theo `SourceReceipt` và `ReferenceReceipt` trong schema; không dùng việc thư mục tồn tại làm bằng chứng đã tải đúng.

Khánh đã chốt dùng **requests + XML Atom arXiv API**, không cần triển khai Kaggle/OAI-PMH. Discovery trả `DiscoveryResult`, danh sách nằm ở `result['papers']`; tra ngày trả `DateLookupResult` gồm `dates` và `errors`. Các hàm HTTP nhận keyword `policy`; `collect_references` nhận hàm tra ngày đã gắn policy khi tích hợp.

## 6. Fixture, Protocol và fake dùng thế nào?

| Khái niệm | Ý nghĩa |
|---|---|
| Hàm thật | Gọi dịch vụ hoặc xử lý dữ liệu thực tế sau khi triển khai |
| Fixture | Input/output mẫu đặt sẵn trong `fixtures.py`, cho phép phát triển độc lập |
| Protocol | Quy định một hàm được truyền vào phải nhận gì và trả gì |
| Mock/fake | Hàm/phản hồi giả chỉ phục vụ kiểm tra, viết trong môi trường kiểm tra |

`__call__` trong Protocol mô tả chữ ký; không cần tạo object Protocol để gọi hàm. `policy` chứa cấu hình timeout, retry, nhịp API và User-Agent; dấu `*` trong chữ ký buộc truyền đối số sau đó bằng tên, ví dụ `policy=policy`.

TypedDict/Protocol không tự xác minh toàn bộ dữ liệu lúc chạy. Người triển khai vẫn phải kiểm tra schema, giá trị và bất biến trước khi lưu/bàn giao.

| Người | Mẫu có thể dùng ngay | Output phải theo |
|---|---|---|
| Khánh | `SCOPE`, `HTTP_POLICY` | `DISCOVERY_RESULT`, `PAPER_BERT`, `DATE_RESULT` |
| Khang | ID/version từ `PAPER_BERT`, thư mục thử | Các fixture `DownloadResult` thành công/no_tex/lỗi |
| Nguyên | ID bài, thư mục thử, DateLookup cùng kiểu `DATE_RESULT` | Các fixture `ReferenceResult` thành công/lỗi |
| Danh | `DISCOVERY_RESULT`, `MANIFEST`, `RESOURCE_SAMPLES` | `RunResult`, `CorpusSummary`, `BenchmarkResult` |

Khang làm ngay bằng ID/version mẫu, không cần đợi Khánh. Nguyên có thể dùng fake DateLookup trong cell kiểm tra để làm độc lập; ID không biết phải trả `None` và errors, không bịa ngày. Danh làm metrics/manifest/pipeline bằng fixture và fake dependency đúng chữ ký trong lúc các bạn làm module thật.

Khi Khánh bàn giao, Nguyên thay bằng `partial(fetch_submission_dates, policy=policy)`, bật `USE_REAL_DATES=True` và chạy lại bằng ngày thật, không dùng cache từ lần fake ngày. Fixture/fake không được dùng làm kết quả corpus hoặc báo cáo cuối.

## 7. Chạy phần mình trong notebook chung

1. Mở `src/notebooks/milestone1.ipynb`, chọn đúng kernel của project.
2. Chạy setup và đọc fixture của phần mình để hiểu input/output. Bước này chưa chứng minh hàm thật chạy đúng.
3. Sau khi implement, sửa cờ của mình thành `True` ngay trong ô setup: `RUN_KHANH`, `RUN_KHANG`, `RUN_NGUYEN` hoặc `RUN_DANH_METRICS`. Giữ cờ người khác và tích hợp là `False` khi thử riêng.
4. Restart Kernel → Run All để kiểm từ trạng thái sạch, hoặc chạy setup rồi các cell phần mình. Không phụ thuộc biến của lần chạy cũ.
5. Kiểm nội dung output, schema và file tạo ra; không chỉ nhìn cell không báo lỗi.
6. Thực hiện kiểm tra tay và ca lỗi theo mục tương ứng của bản phân công.

Các phần được thiết kế để chạy độc lập sau setup. Nguyên chỉ dùng `USE_REAL_DATES=False` trong giai đoạn thử độc lập, không dùng kết quả đó làm dữ liệu cuối.

Đọc cell trước khi Run All để tránh vô tình gọi mạng nhiều lần. Giữ pacing/retry theo quy định; không gọi đồng thời vượt giới hạn dịch vụ vì nhiều người cùng phát triển. Thử 429/timeout bằng fake HTTP, không cố spam API để tạo lỗi thật. API key S2 đọc từ môi trường `S2_API_KEY`, không paste vào notebook/log.

## 8. Kiểm tra tay và sửa lỗi

Làm đầy đủ các ca trong mục 12–15 của bản phân công. Bảng dưới đây là định hướng, không thay các ca chi tiết:

| Người | Đối chiếu và ca cần kiểm |
|---|---|
| Khánh | So ID, tiêu đề, toàn bộ tác giả, ngày và lịch sử phiên bản với arXiv; thử ID thiếu, scope sai, lỗi API, mã cũ; không hardcode số phiên bản |
| Khang | Mở nguồn từng version; kiểm cấu trúc và hash file text không đổi, lệnh hình còn, ảnh bị bỏ; tự cộng byte; thử TeX/gzip/tar/PDF-only, archive hỏng, traversal/link, giới hạn giải nén, lỗi mạng và cache hỏng |
| Nguyên | Kiểm S2 đủ trang, chọn vài reference thật đối chiếu title/authors/S2 ID/ngày v1; kiểm `references.json`, lọc arXiv IDs, gộp trùng; thử thiếu trang/ngày, 404, 429/timeout và cache/file hỏng |
| Danh | Tính lại metrics mẫu, JSON round-trip, trạng thái pending/partial/no_tex, resume và scope khác; kiểm file/receipt hỏng, tích hợp thật và sampler RAM/đĩa khi chạy/lỗi/ngắt |

Kiểm qua năm lớp: **chạy được → đúng hợp đồng → đúng nội dung → chịu lỗi → ghép được**. Không tuyên bố S2 cung cấp đúng danh sách tham khảo riêng của từng phiên bản nếu dịch vụ không hỗ trợ.

Nếu sai, gửi AI input, lỗi/output thực tế và kết quả mong đợi có nguồn đối chiếu; yêu cầu sửa trong phạm vi module. Chạy lại ca liên quan sau khi sửa. Lỗi liên quan schema/giao diện chung phải báo Danh để xử lý đồng bộ.

## 9. Ghi bằng chứng ngay khi làm

Trong cell Markdown cuối phần mình, điền bảng theo mục 17 của bản phân công:

| Ngày/môi trường | Hàm/case | Input + nguồn đối chiếu | Mong đợi | Thực tế/file | Kết luận + giới hạn |
|---|---|---|---|---|---|
| Điền sau khi chạy | Case đã thử | ID/root thử/nguồn | Điều cần đạt | Kết quả thật | Pass/Fail/Chưa thử |

Ghi đã thử gì, kiểm bằng cách nào, còn lỗi hay giới hạn nào. Không ghi pass cho ca chưa chạy; không chỉ bàn giao câu “AI làm xong rồi”. Lưu mô tả và cách tái hiện, không nhúng key/corpus hàng loạt vào notebook. Các file dữ liệu đối chứng giữ ngoài phần source được commit.

Mỗi người viết phần **phương pháp, công cụ và giới hạn bằng tiếng Anh** cho báo cáo. Danh tổng hợp, nhưng các thành viên vẫn chịu trách nhiệm giải thích phần mình. Có thể chuẩn bị nội dung phương pháp trước; số liệu và phân tích kết quả bổ sung sau chạy thật/Colab.

## 10. Chuẩn bị commit và bàn giao cho Danh

Trước commit:

- Đưa cờ RUN về `False`; cấu hình notebook mặc định không gọi mạng.
- Clear output và execution count của notebook.
- Kiểm diff: chỉ sửa module/cell được giao, không làm mất phần người khác.
- Không commit corpus, API key, archive, log hay output cào hàng loạt vào repo code.
- Các thư viện mới cần báo Danh cập nhật requirements.

Mỗi người gửi cho Danh:

1. Branch/commit hoặc PR chứa code đúng chữ ký/schema.
2. Cách chạy phần mình: setup, cờ và cell cần chạy.
3. Kết quả/file thật và bằng chứng đối chiếu; nơi giữ dữ liệu thử ngoài repo code nếu cần kiểm lại.
4. Các ca lỗi đã thử, kết quả và ca chưa thử.
5. Vấn đề còn tồn tại, giới hạn và phụ thuộc cần ghép lại.
6. Đoạn tiếng Anh mô tả phương pháp, công cụ và giới hạn cho báo cáo.

Code `.py` có thể phát triển song song trên clone riêng. Với notebook chung, không sửa cell người khác; phối hợp các thay đổi setup chung qua Danh, merge lần lượt và kiểm đủ phần/cell sau merge. Không tạo notebook riêng cho từng thành viên.

## 11. Danh tổng hợp và nghiệm thu tích hợp

Danh có thể làm trước metrics bằng fixture, manifest JSON round-trip, pipeline bằng fake dependency, resume, sampler RAM/đĩa và khung báo cáo. Chưa cần chờ cả ba module thật mới bắt đầu phần mình.

Khi nhận code:

1. Review và merge từng phần, giữ nguyên giao diện chung và các cell notebook.
2. Ghép discovery/metadata của Khánh, download của Khang, references của Nguyên và hàm tra ngày thật của Khánh.
3. Hoàn thiện notebook chung; bật `RUN_INTEGRATION` khi muốn thử luồng thật, chọn root thử mới riêng với benchmark.
4. Chạy vài bài từ kernel sạch. Kiểm metadata, nguồn riêng từng version, references, manifest, receipts và metrics khớp ID/path/status.
5. Thử gián đoạn/chạy tiếp và output/cache hỏng. Không chỉ dựa vào trạng thái success trong manifest.
6. Lỗi ở module nào giao chủ module sửa, rồi kiểm lại ca liên quan và tích hợp.

Chạy vài bài thành công chứng minh luồng mẫu hoạt động, chưa thay chạy phạm vi thầy giao. Không còn fake ngày/fake dependency trong kết quả cuối. Nguồn không có TeX đã xác minh phải ghi riêng; lỗi mạng không được ghi thành không có TeX.

## 12. Chạy corpus chính thức và benchmark Colab CPU

Khi có phạm vi và deadline chính thức từ thầy/Moodle:

1. Kiểm cấu hình scope đúng phạm vi, không mặc định lấy BERT/RoBERTa hoặc keyword tùy ý thay thế.
2. Clone/cài môi trường sạch trên Colab, cấu hình đường dẫn `src` cho notebook và chọn **CPU-only**. Ghi phiên bản Python/package và môi trường thực tế.
3. Chạy toàn phạm vi bằng hàm thật, đủ mọi phiên bản. Ghi nhận ID thiếu, nguồn không có TeX và lỗi/metadata thiếu; sửa/thử lại theo chính sách, không giấu dữ liệu chưa thu được.
4. Benchmark tải mới dùng root mới, cold cache; không tự xóa corpus cũ. **Bật bộ đo từ trước discovery**, lấy mẫu suốt lúc chạy, gồm chờ/retry, RAM process tree và dung lượng đĩa có file tạm.
5. Lưu thời gian discovery, thời gian mỗi bài, wall time toàn luồng, RAM peak/mean, đĩa peak và dung lượng cuối; ghi nhịp lấy mẫu, cache mode và lỗi đo nếu có.
6. Lưu manifest, kết quả thật và dữ liệu xuất phục vụ báo cáo. Không dùng lần resume/cache làm đại diện cho tải mới, không dùng fixture làm số liệu đo.

## 13. Báo cáo, xuất bản và nộp bài

Danh ghép phần phương pháp/giới hạn do từng người viết, thêm thống kê và phân tích từ kết quả thật. Hoàn thiện **Jupyter Book tiếng Anh ở repository công khai riêng**, host trên GitHub Pages.

- Bảng/biểu đồ phải sinh trong lúc build Book từ dữ liệu kết quả đã lưu; không chỉ dán ảnh chụp và không cào lại corpus mỗi lần build.
- Báo cáo gồm cách thu thập, công cụ/thư viện, độ phủ bài/phiên bản, tỷ lệ thành công, kích thước trước/sau bỏ ảnh, tham khảo, thời gian và RAM/đĩa; giải thích mẫu số, dữ liệu thiếu và giới hạn.
- Kiểm README cài/chạy và requirements trên môi trường sạch. Code dùng một repository công khai chung, giữ lịch sử tiến độ; không commit corpus/key/output hàng loạt.
- Mở bản Book đã xuất bản, kiểm nội dung, bảng/biểu đồ và link hoạt động.
- Nhóm nộp **link repository code + link báo cáo qua Moodle đúng hạn**. Milestone 1 không nộp corpus giữa kỳ; giữ corpus làm đầu vào Milestone 2–3.

## 14. Checklist hoàn thành của leader

- [ ] Có phạm vi và deadline chính thức.
- [ ] Bốn phần đã triển khai, đúng hợp đồng và có bằng chứng kiểm tra thật.
- [ ] Notebook chung chạy từ kernel sạch bằng hàm thật, không còn fake trong kết quả cuối.
- [ ] Đã xử lý toàn phạm vi, kiểm đủ phiên bản và ghi rõ lỗi/thiếu dữ liệu.
- [ ] Đã kiểm gián đoạn/resume và cache/file không hợp lệ.
- [ ] Có benchmark thật Colab CPU và thống kê với mẫu số/điều kiện chạy rõ.
- [ ] Có README, requirements đã kiểm chứng và repository code công khai.
- [ ] Jupyter Book tiếng Anh ở repo riêng đã build/publish; bảng/biểu đồ sinh khi build.
- [ ] Đã kiểm hai link và nộp Moodle đúng hạn; giữ corpus cho các milestone sau.

Thứ tự thực hiện: **prompt theo phân công → hàm thật từng người → kiểm tra tay/ca lỗi → bàn giao → Danh tích hợp → toàn phạm vi và Colab CPU → báo cáo → nộp link**.

## 15. Tin nhắn leader có thể gửi nguyên cho nhóm

> Mọi người clone/cập nhật repo, tạo branch riêng rồi mở cả project bằng AI. Vào `docs/milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md`, đọc phần mình và chép prompt tương ứng ở mục 11 gửi AI. Implement đúng module được giao, thử trong phần mình của notebook chung, rồi kiểm tra tay theo mục 12/13/14. Ghi kết quả và phần chưa thử vào notebook. Khi bàn giao, gửi branch/PR, cách chạy, bằng chứng kiểm tra, lỗi còn lại và phần phương pháp tiếng Anh. Trước commit tắt cờ RUN, clear output và không đưa dữ liệu/key lên repo. Danh sẽ ghép các module, kiểm tích hợp và điều phối chạy Colab cùng báo cáo.
