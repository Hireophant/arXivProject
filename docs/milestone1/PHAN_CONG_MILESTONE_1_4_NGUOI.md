# Phân công Milestone 1 — Khánh, Khang, Nguyên, Danh

Bản cập nhật ngày 12/10/2026, thay thế toàn bộ bản phân công cũ.

Căn cứ: [đề bài](../../ARXIV_PROJECT_FULL.md), [kế hoạch](./KE_HOACH_MILESTONE_1.md) và [hướng dẫn thành viên](./HUONG_DAN_THANH_VIEN_MILESTONE_1.md).

## 1. Quyết định chung

- **Khánh:** discovery và metadata bằng arXiv API.
- **Khang:** tải, nhận diện và xử lý nguồn từng phiên bản.
- **Nguyên:** lấy metadata tham khảo từ Semantic Scholar.
- **Danh:** điều phối, lưu tiến độ, thống kê, benchmark và tổng hợp báo cáo.
- **Chỉ dùng một notebook:** [milestone1.ipynb](../../src/notebooks/milestone1.ipynb). Không tạo notebook riêng cho từng thành viên.
- Viết hàm trong module .py mình phụ trách; notebook gọi hàm để thử, không chép toàn bộ thân hàm vào các cell.
- Phát triển bằng Jupyter trên máy; benchmark cuối Colab CPU. Báo cáo nộp bằng tiếng Anh trong repository Jupyter Book riêng.
- Chưa có phạm vi bài thầy giao. BERT/RoBERTa chỉ là mẫu phát triển, không phải dữ liệu nộp mặc định.
- Hiện tại là **prototype**: hàm nghiệp vụ chưa triển khai. Fixture và notebook chạy được không chứng minh crawler đã hoạt động.

## 2. Hợp đồng kỹ thuật — cả nhóm đọc trước

Nguồn chuẩn là `src/crawling/__init__.py` và chữ ký hàm trong các module. Không tự đổi tên khóa, kiểu dữ liệu hoặc keyword của hàm. Nếu cần đổi, phải thống nhất và cập nhật các bên dùng cùng lúc.

| Dữ liệu | Hình dạng và ý nghĩa |
|---|---|
| Scope | mode=ids/range, ids, start_id, end_id; chưa có phạm vi thật thì dùng fixture |
| HttpPolicy | timeout, số lần thử, nhịp arXiv/S2, trần backoff và User-Agent |
| PaperRecord | arxiv_id gốc, versions dạng list[int], metadata dạng PaperMetadata |
| DiscoveryResult | status, scope, requested_count, scope_complete, papers, issues, elapsed_seconds |
| DateLookupResult | dates: mã → ngày/None; errors: mã → lý do không lấy được |
| DownloadResult | ID/version, status, byte trước/sau, archive_bytes, số file, thời gian, attempts, used_cache, error |
| ReferenceResult | ID, status, references, số lượng/thiếu trường, đủ trang hay chưa, thời gian truy vấn, attempts/cache/error |
| Manifest | schema_version, run_id, scope, discovery, papers và updated_at |
| CorpusSummary | Số bài/phiên bản/trạng thái, tỷ lệ và trung bình kèm mẫu số |
| BenchmarkResult | Môi trường, CPU/cache, chu kỳ mẫu, thời gian, RAM/đĩa |
| RunResult | status, run_id, đường dẫn manifest/metrics, summary, benchmark |

**Quy ước:** mã arXiv gốc không có hậu tố v; phiên bản là int >=1. Path dùng ở input; output lưu JSON chỉ dùng primitive và chuỗi đường dẫn. Ngày dữ liệu YYYY-MM-DD theo UTC; timestamp truy vấn có múi giờ. Byte là int, giây là float. None là chưa biết, khác 0. Không nhầm API lỗi với danh sách rỗng.

**Protocol** chỉ quy định khuôn hàm, không phải mock. **Fixture** là dữ liệu mẫu trong fixtures.py. **Mock/fake** là hàm giả để kiểm tra điều phối, nếu cần thì viết trong môi trường kiểm tra, không thay code nghiệp vụ. Dữ liệu mẫu không được dùng làm kết quả báo cáo thật.

## 3. Khánh — Tìm bài, metadata và ngày gửi

**File sở hữu:** `src/crawling/discover.py`. Thử trong phần Khánh của notebook chung.

### Input nhận gì?

- discover_papers nhận Scope và keyword policy: HttpPolicy.
- fetch_paper nhận một mã arXiv gốc và policy.
- fetch_submission_dates nhận list mã arXiv và policy.

Ví dụ Scope phát triển:

```python
{"mode": "ids", "ids": ["1810.04805"], "start_id": None, "end_id": None}
```

### Quy trình làm

1. Đọc schema và fixtures.SCOPE, PAPER_BERT, DISCOVERY_RESULT, DATE_RESULT.
2. Viết fetch_paper trước: requests gọi arXiv API, đọc XML Atom để lấy title, authors, published và venue nếu có.
3. Xác minh lịch sử phiên bản. Không lấy mỗi latest hoặc một updated rồi coi đã có đủ lịch sử. Có thể bổ sung xác minh lịch sử trên trang abstract nếu API chưa cho đủ thông tin.
4. Viết discover_papers: mở rộng phạm vi đúng quy ước, chia batch/phân trang, thu PaperRecord và ghi issues của mã thiếu/lỗi.
5. Viết fetch_submission_dates: trả ngày gửi lần đầu cho mọi ID yêu cầu; thiếu ngày trả None và ghi errors.
6. Chờ giữa các yêu cầu, retry có giới hạn; không quét ngoài phạm vi.
7. Chạy thử trong phần Khánh của notebook chung và đối chiếu output thật.

### Output bàn giao

- DiscoveryResult; danh sách PaperRecord nằm ở result['papers'], không trả list đơn lẻ.
- Mỗi PaperRecord gồm ID, versions và metadata đầy đủ.
- DateLookupResult gồm dates và errors, để Nguyên bổ sung ngày tham khảo.
- Không ghi metadata.json trong discover.py. Danh ghi từ PaperRecord để tránh hai module cùng ghi.

### Ai dùng và có phải chờ ai không?

Danh dùng papers để gọi Khang và Nguyên; Nguyên dùng hàm tra ngày. Khánh không cần chờ module khác để làm.

### Kiểm tra đạt

- [ ] BERT có lịch sử phiên bản đúng khi đối chiếu, không hardcode [1,2].
- [ ] Metadata có tác giả, ngày, venue=None khi không có; không bịa giá trị.
- [ ] API lỗi/quét thiếu được phản ánh bằng issues và scope_complete, không âm thầm mất bài.
- [ ] Hàm tra ngày giữ mọi ID input, thiếu ngày có lý do.
- [ ] Viết phần phương pháp discovery/metadata bằng tiếng Anh cho báo cáo.

## 4. Khang — Tải và xử lý nguồn từng phiên bản

**File sở hữu:** `src/crawling/download.py`. Thử trong phần Khang của notebook chung.

### Input nhận gì?

```python
arxiv_id = "1810.04805"
version = 2
version_dir = Path("data/1810-04805/sources/v2")
# Thêm keyword policy=policy, use_cache=True/False.
```

Khi Khánh chưa xong, dùng fixtures.PAPER_BERT để lấy ID và versions, không phải chờ discovery thật.

### Quy trình làm

1. Viết prepare_source trước: nhận một gói nguồn local và thư mục đích.
2. Nhận diện tar/gzip, TeX đơn, PDF/Word-only hoặc dữ liệu hỏng. Không chỉ dựa vào đuôi file.
3. Giải nén an toàn; giữ văn bản như tex/bib/bbl/sty/cls và cấu trúc thư mục; bỏ ảnh nhị phân nhưng giữ lệnh hình/bảng trong TeX.
4. Đo byte trước/sau lọc cùng cơ sở chưa nén; archive_bytes đo riêng.
5. Viết download_version: tải đúng mã có phiên bản rồi gọi phần xử lý nguồn; timeout/retry/pacing và cache đã xác minh.
6. Ghi output nguyên tử, không làm hỏng nguồn tốt cũ khi lần thử mới lỗi.
7. Chạy thử trong phần Khang của notebook chung với input mẫu, rồi với PaperRecord thật Khánh bàn giao.

### Output bàn giao

- File nguồn trong version_dir, mỗi phiên bản một thư mục.
- DownloadResult có status success/no_tex/failed và số đo, error.
- no_tex chỉ khi xác minh không có TeX; giữ bản ghi phiên bản rỗng. Mạng lỗi phải failed, không phải no_tex.
- Khang không ghi manifest, metadata.json hoặc references.json.

### Ai dùng và có phải chờ ai không?

Danh nhận trạng thái để ghi manifest/thống kê. Milestone 2 đọc file nguồn. Khang làm ngay với fixture, không cần nguồn của Nguyên.

### Kiểm tra đạt

- [ ] Đúng bài và phiên bản, mở được nguồn, không lẫn v1/v2.
- [ ] File TeX không bị sửa nội dung; bỏ ảnh nhưng giữ lệnh hình/bảng.
- [ ] Thử nguồn không có TeX, archive hỏng và đường dẫn thoát thư mục.
- [ ] Không dùng dung lượng gói nén làm byte trước lọc.
- [ ] Thử lỗi mạng, cache và gọi lại không nhân đôi hoặc mất dữ liệu.
- [ ] Viết phần tải/giải nén/giới hạn bằng tiếng Anh cho báo cáo.

## 5. Nguyên — Metadata tài liệu tham khảo

**File sở hữu:** `src/crawling/references.py`. Thử trong phần Nguyên của notebook chung.

### Input nhận gì?

- Mã bài chính, ví dụ 1810.04805.
- paper_dir: Path của bài đó.
- date_lookup: hàm nhận list ID, trả DateLookupResult.
- Keyword policy và use_cache.

Không nhận nguồn LaTeX của Khang, vì lấy tham khảo qua mã bài trên Semantic Scholar.

### Quy trình làm

1. Đọc fixtures.REFERENCE_RESULT, REFERENCE_FAILED, DATE_RESULT để biết input/output chuẩn.
2. Viết collect_references gọi S2, lấy hết danh sách theo cơ chế phân trang endpoint đã chọn.
3. Lấy title/authors/paperId/externalIds; chỉ giữ mục có mã arXiv theo cách lưu đề gợi ý.
4. Gọi date_lookup bổ sung ngày gửi. Không dùng ngày xuất bản làm ngày gửi.
5. Lưu references.json và trả ReferenceResult gồm thống kê/đủ trang/thiếu trường/trạng thái.
6. Xử lý 429, not_found, thiếu trang/thiếu ngày; không ghi {} đè file tốt khi API lỗi.
7. Khi Khánh chưa xong, có thể viết hàm giả trong cell kiểm tra, nhận list[str], trả deepcopy(DATE_RESULT). Hàm giả chỉ phù hợp các ID mẫu đã khai báo, không dùng để chạy dữ liệu thật.
8. Khi Khánh xong, thay bằng partial(fetch_submission_dates, policy=policy); thử lại bằng ngày thật.

### Output bàn giao

- references.json của bài chính: mã tham khảo → tên, tác giả, ngày gửi và mã Semantic Scholar.
- ReferenceResult có số lượng trước/sau lọc, số thiếu trường, pagination_complete và lỗi.
- File thành công rỗng khác API lỗi; không tải nguồn toàn bộ các bài được tham khảo ngoài phạm vi được giao.

### Ai dùng và có phải chờ ai không?

Danh thống kê; Milestone 3 dùng tham khảo để matching. Nguyên làm song song với Khang, dùng date_lookup giả để phát triển trước khi Khánh bàn giao.

### Kiểm tra đạt

- [ ] kept_references == len(references), total chưa biết=None.
- [ ] Xác minh lấy đủ trang; thiếu trang phải partial.
- [ ] Thiếu ngày/thông tin được ghi rõ, không bịa.
- [ ] Phân biệt success/partial/not_found/failed, không ghi đè output tốt bởi lỗi.
- [ ] Không cố định số tham khảo BERT/RoBERTa vì dịch vụ có thể cập nhật.
- [ ] Viết phần S2, độ phủ và giới hạn bằng tiếng Anh cho báo cáo.

## 6. Danh — Điều phối, số đo và báo cáo

**File sở hữu:** `src/crawling/pipeline.py`, `metrics.py`; điều phối notebook chung, README, requirements và repo Jupyter Book.

### Input nhận gì?

Scope, data_root: Path, HttpPolicy và các hàm thật/fake cùng Protocol. Để làm trước dùng MANIFEST, RESOURCE_SAMPLES, CORPUS_SUMMARY, BENCHMARK và RUN_RESULT trong fixtures.py.

### Quy trình làm trước khi các module khác xong

1. Viết summarize_corpus từ MANIFEST; kiểm tra bằng CORPUS_SUMMARY.
2. Viết summarize_benchmark từ RESOURCE_SAMPLES; kiểm tra bằng BENCHMARK.
3. Viết tạo đường dẫn an toàn, khởi tạo/đọc/ghi manifest và save_paper_metadata.
4. Viết run_pipeline gọi các dependency theo đúng chữ ký; khi cần thử điều phối dùng fake cùng giao diện trong cell kiểm tra, không viết lại nghiệp vụ của các thành viên.
5. Làm resume: bỏ qua output đã xác minh, tiếp tục phần còn thiếu/lỗi, không dựa duy nhất vào manifest cũ.
6. Viết bộ lấy mẫu RAM process tree và đĩa trong lúc chạy, dừng/join trong finally.
7. Tạo khung báo cáo tiếng Anh và bảng/biểu đồ đọc từ kết quả đã lưu.

### Quy trình ghép khi nhận hàm thật

1. Gọi Khánh lấy DiscoveryResult.
2. Với từng PaperRecord: tạo thư mục, lưu metadata.json.
3. Với mỗi version: gọi Khang, ghi kết quả vào manifest.
4. Gọi Nguyên cho bài chính, truyền hàm tra ngày của Khánh đã gắn policy.
5. Ghi tiến độ sau từng tác vụ; tổng hợp kết quả và lỗi.
6. Chạy vài bài từ kernel sạch; lỗi module nào giao đúng chủ module sửa.
7. Có phạm vi chính thức thì chạy corpus và benchmark cuối Colab CPU.
8. Ghép phần phương pháp/nhận xét do Khánh, Khang, Nguyên viết; build Book từ dữ liệu thật.

### Output bàn giao

- RunResult: status, run_id, manifest_path, metrics_path, summary và benchmark.
- Corpus theo bài/phiên bản; manifest.json và metrics/run_summary.json dưới data_root.
- Notebook chung gọi hàm thật, số liệu có mẫu số/cache mode/môi trường rõ ràng.
- README cài/chạy, requirements đã kiểm chứng, Jupyter Book repo riêng trên GitHub Pages.
- Nhóm nộp hai link Moodle; chưa nộp corpus ở Milestone 1.

### Kiểm tra đạt

- [ ] Summary và benchmark đúng fixture kỳ vọng, không dùng fixture làm báo cáo thật.
- [ ] Pipeline nhận đúng hàm thật, không còn fake khi chạy corpus nộp.
- [ ] Thử gián đoạn/chạy tiếp và manifest hỏng; không mất kết quả tốt.
- [ ] Không gộp no_tex vào số phiên bản có nguồn TeX thành công.
- [ ] Đo từ đầu đến cuối, cả chờ/retry và process con; có đỉnh đĩa lúc chạy.
- [ ] Build Book sinh bảng/biểu đồ, không cào lại toàn bộ mỗi lần build.
- [ ] Cả nhóm góp báo cáo, không dồn mọi nội dung cho Danh.

## 7. Một notebook chung: sử dụng thế nào?

Notebook có phần Khánh, Khang, Nguyên, Danh và phần tích hợp. Mỗi người chạy cell import/cấu hình rồi phần của mình.

1. Viết code thật vào module .py phụ trách.
2. Chạy fixture trong phần tương ứng để hiểu hợp đồng, không coi đây là kiểm tra hàm thật.
3. Sau triển khai, bật cờ RUN của phần mình ở ô setup rồi chạy cell gọi thật. Cờ phần khác giữ False. Nguyên chỉ bật USE_REAL_DATES sau khi Khánh làm xong.
4. Muốn kiểm từ kernel sạch: sửa dòng cờ của phần mình thành True ngay trong mã ô setup, rồi Restart Kernel → Run All. Phần khác giữ RUN=False. Khi chỉ chạy riêng: chạy setup đã sửa, rồi các ô phần mình; không cần chạy phần khác. Trước commit sửa cờ lại False và clear output.
5. Kiểm tra nội dung output, schema, file lưu và tình huống lỗi. Không chỉ nhìn cell không báo lỗi.
6. Khi ghép hoàn chỉnh, Danh bật các call thật cần cho luồng, chạy lại từ kernel sạch và xác minh corpus.

**Không chạy lại toàn bộ cell mạng nhiều lần vô tình.** Đọc cell trước Run All, dùng cache có kiểm tra; benchmark tải mới dùng điều kiện cold riêng và ghi rõ. Không dùng API đồng thời vượt giới hạn chỉ vì nhiều người cùng phát triển.

**Dùng một file chung nhưng tránh xung đột:** mỗi người chỉ sửa cell phần mình, không sửa/xóa cell người khác; không đồng thời lưu cùng bản file. Merge lần lượt, bỏ output cào và execution_count trước commit. Code .py có thể làm song song; chỉnh notebook cần phối hợp. Không tạo notebook thử riêng theo yêu cầu nhóm.

Notebook mặc định chỉ chạy fixture, call thật nằm sau cờ RUN=False, nên chạy sạch hiện tại chỉ xác nhận bộ mẫu hoạt động. Không sửa raise NotImplementedError thành trả fixture trong code thật chỉ để notebook xanh.

## 8. Chạy không lỗi chưa đủ: kiểm tra theo 5 lớp

| Lớp | Phải chứng minh |
|---|---|
| 1. Chạy được | Import và Restart kernel → Run All không phụ thuộc biến cũ |
| 2. Đúng hợp đồng | Đủ khóa, kiểu đúng, ngày/ID/đơn vị đúng; không đổi chữ ký |
| 3. Đúng nội dung | Đủ phiên bản, nguồn đúng, metadata đáng tin, tham khảo đủ trang |
| 4. Chịu lỗi | PDF-only, mạng lỗi, 429, thiếu ngày, mã cũ, resume được ghi nhận đúng |
| 5. Ghép được | Hàm thật nối với nhau và ghi output đủ để dùng Milestone 2–3 |

Mỗi thành viên ghi ngắn các trường hợp đã thử, kết quả và hạn chế trong phần notebook của mình. Chỉ sửa code phần mình; nếu hợp đồng có vấn đề, báo nhóm trước khi đổi.

## 9. Mốc làm song song và bàn giao

| Mốc | Khánh | Khang | Nguyên | Danh |
|---|---|---|---|---|
| Làm độc lập | API/metadata với Scope mẫu | Nguồn với PaperRecord mẫu | S2 với ID mẫu/date_lookup giả | Manifest/metrics/pipeline bằng fixture |
| Bàn giao | DiscoveryResult + hàm tra ngày | DownloadResult + nguồn | ReferenceResult + references.json | Notebook tích hợp + danh sách lỗi |
| Chạy thật | Soát phạm vi/phiên bản | Soát nguồn | Soát tham khảo | Điều phối corpus và benchmark |
| Báo cáo | Viết phần mình tiếng Anh | Viết phần mình tiếng Anh | Viết phần mình tiếng Anh | Tổng hợp, build, kiểm tra link |

Bàn giao gồm code đúng chữ ký, cách gọi, output/file thật, tình huống lỗi đã thử và nội dung báo cáo. Dữ liệu mẫu cho phép làm song song, nhưng chạy tích hợp và benchmark thật phải chờ module thật.

## 10. Checklist cuối nhóm

- [ ] Có phạm vi chính thức và deadline từ thầy/Moodle.
- [ ] Đủ bài/phiên bản được ghi nhận, lỗi không bị giấu.
- [ ] Nguồn văn bản và metadata đúng, tham khảo có nguồn gốc và thiếu trường rõ ràng.
- [ ] Notebook chung chạy với hàm thật từ kernel sạch, không còn dữ liệu giả trong kết quả nộp.
- [ ] Benchmark Colab CPU và thống kê với mẫu số/điều kiện chạy rõ.
- [ ] Code công khai, README/requirements đầy đủ; không commit corpus, key, log hay output cào hàng loạt.
- [ ] Jupyter Book tiếng Anh ở repo riêng, bảng/biểu đồ sinh lúc build.
- [ ] Nộp link code + báo cáo Moodle đúng hạn; giữ corpus cho Milestone 2–3.

## 11. Cách giao việc cho AI của từng thành viên

**Đọc mục này cùng mục của chính mình; không chỉ đưa tên file cho AI.** AI phải đọc repository thực tế trước khi sửa. Thứ tự đọc:

1. `ARXIV_PROJECT_FULL.md`: phần Milestone 1, Requirement, Submission Format và Report Requirements.
2. File phân công này: mục 1–2, phần người phụ trách, mục 7–8 và 11–17.
3. `docs/milestone1/HUONG_DAN_THANH_VIEN_MILESTONE_1.md`.
4. `src/crawling/__init__.py`: toàn bộ kiểu dữ liệu và quy ước.
5. Module được giao; xem chữ ký các module liền kề để biết cách ghép.
6. `src/crawling/fixtures.py` và phần mình trong notebook chung.

Nếu kế hoạch cũ dùng tên người/chữ ký khác, ưu tiên bản phân công này và schema hiện tại. Đề bài quyết định yêu cầu môn học; schema quyết định giao diện trong nhóm. Phát hiện mâu thuẫn phải ghi rõ, không âm thầm đổi hợp đồng.

### Prompt Khánh — chép gửi AI

```text
Tôi là Khánh, triển khai discovery của Milestone 1 trong repository này.
Đọc các tài liệu theo mục 11 của PHAN_CONG_MILESTONE_1_4_NGUOI.md,
rồi thực hiện phần Khánh và các ca kiểm tra mục 12.
Được sửa src/crawling/discover.py và các cell Khánh trong notebook chung.
Triển khai fetch_paper, discover_papers, fetch_submission_dates bằng requests
và XML Atom arXiv API; xác minh mọi phiên bản, không dùng Kaggle/OAI-PMH.
Giữ nguyên chữ ký, TypedDict, Protocol và schema output. Có thể thêm helper
private trong discover.py. Không implement module của thành viên khác.
Không trả fixture thay dữ liệu thật. Không hardcode phiên bản hay kết quả BERT.
Thử lỗi bằng fake HTTP ở cell kiểm tra, không spam API để tạo 429 thật.
Dùng đúng một src/notebooks/milestone1.ipynb; giữ mặc định không gọi mạng.
Sau cùng báo file đã sửa, cách chạy từng cell, kết quả đã thực sự kiểm tra,
việc tôi cần mở browser kiểm tra bằng tay, hạn chế và phần chưa kiểm chứng.
```

### Prompt Khang — chép gửi AI

```text
Tôi là Khang, triển khai tải và xử lý nguồn Milestone 1.
Đọc tài liệu theo mục 11, rồi làm phần Khang và mục 13.
Được sửa src/crawling/download.py và các cell Khang trong notebook chung.
Triển khai prepare_source trước, download_version sau. Dùng ID/version từ
fixture để làm độc lập; không gọi discovery hay đợi Khánh hoàn thành.
Tải đúng version qua export.arxiv.org/src, giữ text nguyên nội dung/cấu trúc,
bỏ ảnh nhị phân, không xóa lệnh hình. Xử lý TeX đơn, gzip, tar, PDF-only,
archive hỏng, giải nén an toàn và giới hạn dung lượng.
Giữ chữ ký/schema, phân biệt no_tex/failed, byte nén/chưa nén, cache qua
SourceReceipt đã quy định. Có thể thêm helper private cùng module.
Không sửa module khác/fixtures/schema để làm test xanh. Dùng một notebook,
giữ mạng tắt mặc định. Báo kết quả thực đã thử và cách mở file kiểm tra tay.
```

### Prompt Nguyên — chép gửi AI

```text
Tôi là Nguyên, triển khai metadata tham khảo Milestone 1.
Đọc tài liệu theo mục 11, rồi làm phần Nguyên và mục 14.
Được sửa src/crawling/references.py và các cell Nguyên trong notebook chung.
Triển khai collect_references: Semantic Scholar đủ trang, giữ arXiv IDs,
gộp API trùng ID, bổ sung ngày gửi qua DateLookup, lưu references.json
nguyên tử; không parse BibTeX hay tải nguồn các bài tham khảo.
Giữ chữ ký/schema; tuân ReferenceReceipt, status và bộ đếm thiếu trường.
Nếu Khánh chưa xong dùng fake DateLookup trong cell kiểm tra: mọi ID yêu cầu
đều có trong dates; ID không biết=None và có errors. Không bịa ngày.
Có thể thêm helper private. Không sửa các module khác/fixtures/schema.
API key chỉ đọc từ môi trường, không lưu notebook/log. Thử 429/timeout bằng
fake HTTP. Chỉ một notebook, mạng tắt mặc định. Báo cách đối chiếu tay,
ca đã kiểm chứng, ca chưa thử và giới hạn độ phủ của dịch vụ.
```

### Prompt Danh — chép gửi AI

```text
Tôi là Danh, triển khai pipeline/metrics và tích hợp Milestone 1.
Đọc tài liệu theo mục 11, rồi làm phần Danh và mục 15–17.
Được sửa src/crawling/pipeline.py, metrics.py, phần Danh/tích hợp của
notebook chung, README và requirements. Không viết lại nghiệp vụ của bạn khác.
Giữ nguyên chữ ký/schema/Protocol. Trước hết kiểm metrics bằng fixture,
sau đó manifest JSON round-trip, điều phối qua fake dependency đúng chữ ký
trong notebook, rồi ghép hàm thật. Dùng deepcopy fixture, không sửa mẫu gốc.
Resume phải xác minh receipt qua module sở hữu file; thử lỗi và chạy tiếp.
Đo end-to-end, RAM process tree, đĩa lúc chạy; dừng sampler trong finally.
Không báo benchmark giả hoặc gộp no_tex thành có TeX; số thiếu là None.
Một notebook duy nhất, mạng tắt mặc định. Báo bằng chứng kiểm tra đã chạy,
cách kiểm tra tay, phần chưa thực hiện: corpus được giao, Colab CPU,
Jupyter Book tiếng Anh repo riêng, xuất bản/nộp link do nhóm thực hiện.
```

**Giới hạn sửa chung:** không tự sửa `__init__.py`, fixtures hay cell người khác. Nếu thiếu hợp đồng, ghi đề xuất cho nhóm cùng duyệt và cập nhật đồng bộ. Có thể thêm thư viện cần thiết nhưng báo Danh cập nhật requirements và thử môi trường sạch. Helper private không được làm thay đổi public signature. Test helper/fake chỉ phục vụ kiểm tra trong notebook; không có fake âm thầm trong crawler thật.

## 12. Khánh: mở và kiểm tra bằng tay thế nào?

1. Mở Jupyter, chọn kernel Python của project, **Restart Kernel**. Chạy ô thiết lập chung, ô fixture Khánh; chưa gọi crawler ở bước này.
2. Sau triển khai bật `RUN_KHANH=True`, chạy ô gọi thật. Ô này dùng danh sách mẫu `1810.04805`, `1907.11692`; không phải phạm vi nộp. Chờ đúng pacing, xem `khanh_live`.
3. Mở browser tại [BERT](https://arxiv.org/abs/1810.04805) và [RoBERTa](https://arxiv.org/abs/1907.11692). So từng bài: ID, tiêu đề, **toàn bộ** tác giả, Submission history. Đếm phiên bản trên trang; `versions` phải khớp lịch sử thực tế, không mặc định luôn [1,2].
4. So `submission_date` với ngày v1; `revised_dates` với ngày v2 trở đi theo thứ tự phiên bản. Ngày chuẩn UTC; nhiều phiên bản có thể cùng ngày, không tự loại trùng ngày. Venue không có nguồn thì None, không suy từ tiêu đề.
5. Gọi tra ngày cho `1706.03762`, so ngày gửi lần đầu trên [trang bài](https://arxiv.org/abs/1706.03762). Thêm ID trùng: output chỉ một khóa mỗi ID. Với list rỗng phải trả hai dict rỗng.
6. Trong cell test của mình, dùng fake HTTP để trả timeout, 429 rồi success, entry thiếu trường, phản hồi sai version và không tìm thấy. Đối chiếu retries không quá policy, issues không mất ID; không bật mạng để cố gây lỗi. Scope sai mode hoặc range ngược phải ValueError trước gọi mạng.
7. Thử một mã arXiv cũ lấy từ nguồn đã xác minh: giữ ID `archive/YYMMNNN` trong dữ liệu. Không tự sửa thành mã hiện đại. Ghi rõ nếu chưa thử mã cũ.

**Đạt:** từng ID yêu cầu thuộc papers hoặc issues; PaperRecord không có metadata/lịch sử chưa xác minh. requested_count đếm ID duy nhất sau mở rộng scope. success chỉ khi scope_complete và issues rỗng; partial nếu có dữ liệu/đã xác minh được một phần nhưng còn issues; failed khi toàn bộ không xác minh được do lỗi vận hành. Trường hợp tất cả ID đã xác minh không tồn tại: partial, scope_complete=True, papers=[], issues not_found. Không gọi là đã crawl thành công.

**Bàn giao:** code + cách gọi fetch/discover/dates + bảng đối chiếu 2 bài + các lỗi đã thử + output thật có nguồn/ngày kiểm tra. Danh cần hàm, không chỉ cần ảnh output.

## 13. Khang: mở và kiểm tra bằng tay thế nào?

1. Restart Kernel, chạy setup và phần Khang, **không cần chạy phần Khánh**. Fixture cung cấp ID/version độc lập. Dùng `data/manual/khang/` làm vùng thử, không ghi lên corpus chính.
2. Nhờ AI tạo gói kiểm tra nhỏ trong cell Khang: `main.tex` chứa chữ Việt, `\\input`, lệnh hình/bảng; file con `.tex`, `.bib`, `.sty`, ảnh nhị phân. Gọi prepare_source. Mở thư mục output bằng Explorer/editor: text và cấu trúc thư mục còn nguyên; ảnh bị bỏ; lệnh hình trong TeX còn nguyên. So SHA-256 trước/sau **từng file text**; mở nhìn vài dòng chưa đủ chứng minh không bị sửa.
3. Tự cộng byte file chưa nén trong gói trước lọc, và byte các file đã giữ. So với source_bytes_before/after; file_count chỉ đếm file giữ, không đếm thư mục/receipt. Gói nén đo ở archive_bytes, không dùng thay số trước lọc.
4. Thử gói local: TeX đơn, gzip TeX đơn, tar gzip nhiều file, PDF hợp lệ không TeX, archive hỏng. PDF-only -> no_tex; archive hỏng -> failed. File ngẫu nhiên không được coi là PDF-only thành công. Với no_tex, giữ bản ghi phiên bản, không tạo TeX giả.
5. Tạo tar thử có tên `../escape.tex` và link thoát thư mục, gọi prepare_source ở vùng thử. Phải từ chối; kiểm tra ngoài thư mục đích không có file mới. Gói vượt giới hạn bung nén phải dừng có lỗi, không giải nén hết mới kiểm.
6. Bật RUN_KHANG, gọi download_version v1. Mở [trang v1](https://arxiv.org/abs/1810.04805v1), kiểm đúng version. Tải nguồn đối chứng từ endpoint export được chỉ trong đề, mở danh sách archive và đối chiếu file text; không dùng PDF làm nguồn TeX đối chứng. Sau đó thử v2 ở **thư mục v2 khác**.
7. Chạy lại cùng input với use_cache=True: hash nguồn không đổi, attempts=0, used_cache=True. Sửa một file trong vùng thử rồi chạy lại: cache phải bị phát hiện sai và tải lại; không được báo dùng cache tốt. Thử timeout giả khi đang có nguồn tốt: trả failed, file tốt cũ không bị thay bằng dữ liệu lỗi.

**Bàn giao:** code + hai DownloadResult thật + cây thư mục v1/v2 + bảng byte + bằng chứng hash/text + các ca lỗi/cache. Không cần có Khánh mới bắt đầu được.

## 14. Nguyên: mở và kiểm tra bằng tay thế nào?

1. Restart Kernel, chạy setup và phần Nguyên; không cần chạy Khánh/Khang. Xem fixture trước. Ô gọi thật có `USE_REAL_DATES=False`: fake ngày chỉ biết ID mẫu, trả None + errors cho ID khác; output thật S2 với fake ngày có thể partial là đúng.
2. Bật RUN_NGUYEN sau khi implement. Nếu API cần key, đặt `S2_API_KEY` ở môi trường trước khi mở Jupyter; không paste key vào cell. Nếu 429 hết retry, ghi rõ bị chặn; đây không phải test thành công hay danh sách thật rỗng.
3. Mở Semantic Scholar trên browser, tìm BERT bằng mã `1810.04805` và xác nhận đúng tiêu đề. Chọn khoảng 3 tham khảo có arXiv ID từ output thực tế. Với mỗi mục so title/authors/S2 ID qua trang tương ứng hoặc JSON API; mở trang arXiv của bài tham khảo để so ngày v1. Nếu chỉ có 1–2 mục đối chiếu được, ghi đúng số đã kiểm, không bịa đủ 3.
4. Mở file references.json bằng editor. Top-level là dict; mã mới đổi dấu chấm thành gạch ngang; mã cũ giữ nguyên; không thêm tham khảo không có arXiv ID. So nội dung file đúng result['references']; kept_references == len(references).
5. Kiểm dấu vết phân trang của AI: endpoint, offset/next, số mục từng trang, lý do kết thúc. Tổng trước lọc khác số sau lọc/gộp. Browser có thể hiện khác phạm vi API; không lấy số trên browser làm bằng chứng duy nhất đã lấy đủ trang. Khi chưa biết total, để None.
6. Fake HTTP trong cell kiểm tra: trang 1 thành công/trang 2 lỗi -> partial, pagination_complete=False; 404 bài chính -> not_found; timeout hết retry -> failed. Lỗi không ghi {} đè file tốt. Thử danh sách hợp lệ rỗng -> success với kept=0 (phân biệt lỗi).
7. Fake ngày thiếu -> missing_submission_dates tăng và incomplete_references tăng theo **số mục**, không theo số trường. publication_date=None riêng lẻ không tính thiếu vì không phải trường bắt buộc. Thử mục API trùng arXiv ID: gộp một khóa; xung đột không giải quyết được -> partial.
8. Khi Khánh hoàn thành, bật USE_REAL_DATES, chạy lại bằng partial(fetch_submission_dates, policy=...). Đối chiếu ngày thật, cache chỉ dùng khi receipt/schema/hash hợp lệ. Sửa file ở vùng thử: phải phát hiện cache sai. Output dùng fake ngày không được dùng nộp.

**Bàn giao:** code + ReferenceResult/file thật + bảng đối chiếu tham khảo + phân trang/ca lỗi đã kiểm + giới hạn indexing/version của S2. Không tuyên bố S2 liệt kê đúng tham khảo của từng phiên bản nếu dịch vụ không hỗ trợ.

## 15. Danh: mở và kiểm tra bằng tay thế nào?

1. Restart Kernel, chạy setup và phần Danh độc lập. Bật RUN_DANH_METRICS sau khi implement. Hai assert so toàn bộ summary/benchmark phải qua; fixture deepcopy, không sửa giá trị kỳ vọng theo output sai.
2. Tính lại tay MANIFEST mẫu: 1 bài, 2 phiên bản thành công; byte mỗi version 1000 trước/400 sau -> trung bình version 1000/400, tổng bài 2000/800; tham khảo trước lọc 2, giữ 1 đầy đủ -> trung bình metadata đầy đủ 1.0; thời gian bài 13 giây. RAM mẫu 1000/2000/1500 -> peak 2000, mean 1500; peak disk 1200, cuối 1000. Đây là số giả kiểm công thức.
3. Tạo các bản deepcopy khác: một version None -> pending; failed/no_tex tách riêng; reference partial không tính success; không có bài -> tỷ lệ None và mẫu số 0. Tự tính trước rồi đối chiếu. Bài thiếu size một version không góp vào trung bình size cả bài.
4. Dùng vùng `data/manual/danh/` và fake dependency cùng Protocol trong cell test. Fake phải ghi output/receipt tương ứng nếu muốn thử cache file; chỉ trả dict chưa đủ. Thử initialize/save/load manifest: mở JSON đọc tay, khóa downloads là chuỗi, dữ liệu round-trip không đổi. JSON hỏng hoặc schema khác phải báo lỗi, không tự reset.
5. Chạy fake pipeline với download lỗi có kiểm soát ở v2; mở manifest thấy v1 xong/v2 lỗi. Chạy tiếp khi fake v2 thành công; v1 được xác minh cache, v2 được thử lại. Thử scope khác khi resume: từ chối. Thử references/file nguồn bị thay đổi: module phải kiểm receipt và xử lý lại. Không sửa corpus chính để thử mất dữ liệu.
6. Khi ghép thật: bật RUN_INTEGRATION, dùng root mới `data/manual/integration/`, scope mẫu. Mở Explorer kiểm metadata.json, sources/v1, v2, references.json, receipt, manifest và metrics; so ID/path/status từng nơi. Chạy lại resume và đọc cache_mode/attempts. Các run dùng root khác nhau để không lẫn kết quả.
7. Mở sampler khi chạy; xem có mẫu đầu/giữa/cuối, elapsed tăng, RAM gồm process tree, disk gồm file tạm dưới root. Task Manager chỉ hỗ trợ đối chiếu thô, không dùng một ảnh sau chạy làm số RAM đỉnh. Khi lỗi/KeyboardInterrupt, sampler phải dừng; xem resource_errors.json nếu đo lỗi, không giả số 0.
8. Final: clone/cài môi trường sạch trên Colab, chọn CPU, ghi phiên bản Python/package và cấu hình máy; chạy phạm vi thật với root mới/cache cold. Ghi wall time từ trước discovery, thời gian bài của run hiện tại, đỉnh đo được và chu kỳ mẫu. Không dùng số cache/resume gọi là tải mới.
9. Build Book ở repository riêng từ JSON/CSV đã thu, không cào lại trong build. Mở bản HTML/GitHub Pages, kiểm bảng/biểu đồ thực sự sinh lúc build, tiếng Anh, các link hoạt động. Cài README trên môi trường sạch trước chốt requirements. Nhóm tự nộp hai link Moodle đúng hạn.

**Bàn giao:** code metrics/pipeline, notebook tích hợp, hướng dẫn chạy sạch, bằng chứng resume, số đo thật và báo cáo. Chạy mẫu 2 bài thành công chỉ chứng minh luồng mẫu; chưa thay chạy toàn phạm vi thầy giao.

## 16. Quy ước bổ sung để các AI không tự chọn khác nhau

### Đường dẫn và người ghi file

```text
data_root/
  manifest.json                         # Danh
  1810-04805/
    metadata.json                       # Danh
    references.json                     # Nguyên
    .references_receipt.json             # Nguyên, ReferenceReceipt
    sources/
      v1/...                            # Khang
      .v1.receipt.json                   # Khang, SourceReceipt
      v2/...
      .v2.receipt.json
  metrics/
    run_summary.json                     # RunResult, Danh
    resource_errors.json                 # list[str], Danh; [] nếu không lỗi đo
```

Mã cũ: thư mục đổi `/` thành `-` để không tạo thư mục con tùy ý; ID trong record/manifest giữ nguyên. Khóa references.json mã cũ giữ nguyên. Path trong output tương đối với data_root. Thư mục thử manual do notebook quản lý, không trộn với root benchmark. Sidecar receipt là quy ước kỹ thuật của nhóm, không phải yêu cầu file do thầy đặt ra.

Receipt lưu theo TypedDict trong __init__.py. Thứ tự ghi: chuẩn bị file tạm -> xác minh -> thay file dữ liệu -> ghi receipt nguyên tử -> pipeline cập nhật manifest. Ngắt giữa hai bước khiến cache không đủ bằng chứng thì thử lại. Không tự xoá root để benchmark. resume=False gặp root đã có corpus/manifest thì báo ValueError và chọn root mới.

`export_report_data` ghi vào output_dir: `summary.json` (CorpusSummary), `benchmark.json` (BenchmarkResult), `papers.csv` (mỗi bài), `versions.csv` (mỗi version), `references.csv` (mỗi bài chính/mã tham khảo). CSV có run_id, arxiv_id; versions thêm version; references thêm reference_arxiv_id. Trường thiếu trống; JSON thiếu None là null. papers.csv gồm trạng thái nguồn/tham khảo, thời gian và các số đếm; versions.csv chứa DownloadResult; references.csv chứa ReferenceMetadata. Lưu `run_id.txt` cho hai JSON không có run_id trong schema. Không thay kiểu của metrics/run_summary.json. Book đọc bộ này từ nơi nhóm giữ dữ liệu báo cáo; không commit corpus vào repo code.

### Phạm vi, retry, thời gian và thống kê

- Phạm vi hiện hỗ trợ IDs cụ thể hoặc range hiện đại cùng YYMM và độ dài hậu tố. Phạm vi thầy khác định dạng phải thống nhất cách mở rộng trước khi chạy; không tự suy ra keyword/category thay thế. Range có khoảng trống phải ghi issues not_found, không giấu mẫu số.
- Pipeline tuần tự. Mỗi module HTTP chờ service delay **trước mọi request**, kể cả request đầu và retry; dùng timeout, max_attempts gồm lần đầu, backoff hữu hạn và Retry-After. Đây là lựa chọn đơn giản để không gọi dồn khi chuyển module. Kiểm tài liệu API chính thức hiện hành lúc triển khai, đặc biệt giới hạn S2; không hardcode một con số từ ví dụ rồi bỏ xử lý 429.
- status success của pipeline nghĩa là xử lý xong phạm vi và không lỗi/pending/partial. no_tex là tình trạng đã xác minh, báo riêng; success không có nghĩa mọi bài đều có TeX. failed khi không có tác vụ dữ liệu nào thành công và lỗi vận hành ngăn xử lý; các kết quả dở dang còn lại partial.
- Kích thước nguồn: tổng byte file chưa nén, cặp trước/sau cùng tập dữ liệu. Receipt/manifest không thuộc size nguồn, nhưng thuộc disk toàn hệ thống. Không suy byte trước lọc từ output đã bỏ ảnh; cache lấy số gốc từ receipt có xác minh.
- Hai tỷ lệ tham khảo khác nhau: reference_success_rate = số job success / số bài; average_reference_completeness_rate = trung bình tỷ lệ mục giữ lại có đủ metadata bắt buộc trên từng bài đủ trang và kept>0. Báo cả mẫu số, không gọi đây là độ chính xác matching của ML. Không có mục đủ điều kiện -> None.
- Mỗi lần run có run_id mới; thời gian hiện tại không cộng run cũ. Byte gốc cache vẫn dùng thống kê corpus, nhưng thời gian/attempts/cache phải phản ánh lần gọi hiện tại. PaperState.elapsed_seconds đo từ trước lưu metadata đến sau nguồn/tham khảo của bài, không bao discovery toàn cục; discovery.elapsed_seconds và wall toàn run báo riêng.
- RAM mean là trung bình mẫu, peak là peak quan sát, không hứa bắt được mọi đột biến. Lỗi lấy mẫu lưu riêng và phải nêu giới hạn trong báo cáo. Thời gian wall dùng monotonic/perf_counter; timestamp truy nguồn dùng UTC.

## 17. Ghi bằng chứng và xác định đã hoàn thành

Trong cell Markdown cuối **phần mình của notebook chung**, điền bảng này sau chạy; không ghi “pass” cho ca chưa thử:

| Ngày/môi trường | Hàm/case | Input + nguồn đối chiếu | Mong đợi | Thực tế/file | Kết luận + giới hạn |
|---|---|---|---|---|---|
| Điền sau khi chạy | Ví dụ cache file hỏng | Root thử + version | Phát hiện sai hash | Ghi kết quả thật | Pass/Fail/Chưa thử |

Ghi tóm tắt không có key/corpus hàng loạt. Clear output trước commit; giữ bảng mô tả ca và hướng dẫn tái hiện. Mỗi người đọc lại diff, kiểm chỉ sửa module/cell được giao và không làm thay đổi interface của người khác.

**Trình tự nghiệm thu:** fixture/schema -> hàm thật độc lập -> đối chiếu tay và ca lỗi -> tích hợp thật -> đúng phạm vi được giao -> benchmark Colab CPU -> Book/README/requirements -> nộp link. Các hàm hoàn thành và ghép chạy được chưa tự động đồng nghĩa hoàn thành Milestone 1. Hiện khung vẫn prototype; chưa có phạm vi thầy giao, chưa có benchmark cuối và báo cáo nộp.
