# Phân công Milestone 2 — Khánh, Khang, Nguyên, Danh

Ngày lập: **26/10/2026**. Mọi checkbox là việc **chưa được xác nhận hoàn thành**. Tài liệu này phân công để nhóm thực hiện, không xác nhận đã triển khai parser.

Cập nhật **27/10/2026**: đồng bộ bốn bổ sung trong kế hoạch: C3 (reference identity), D3 (component content), 9.3 (status/strict) và 10.4 (Book tương tác). Owners/reviewers và ca nghiệm thu dưới đây phải dùng cùng các quy tắc đó.

Đọc trước [kế hoạch M2](./KE_HOACH_MILESTONE_2.md) và [đề tổng — M2](../../ARXIV_PROJECT_FULL.md#milestone-parsing). Giữ tên thành viên và cách phân vai chuyên môn như [M1](../milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md), điều chỉnh theo bài toán parsing.

## 0. Bắt đầu từ đâu và dữ liệu nào được dùng?

Bổ sung 27/10/2026: chốt thư mục raw trên Drive là **preparationM2**, thêm kiểm đọc lại/snapshot và hướng làm từng phần. Đã có code chuẩn bị input. Cập nhật 28/10/2026: đã tạo prototype trong src/parsing/; hàm nghiệp vụ vẫn chưa triển khai. Schema nằm trong [contracts.py](../../src/parsing/contracts.py); hướng dẫn triển khai nằm ngay trong docstring từng prototype. Prompt riêng ở mục 14–15.

**Luồng chung:** backup Milestone1 → notebook milestone2_prepare.ipynb → `preparationM2/raw_m1/<DATASET_NAME>/` → input adapter + parser → `Milestone2/parsed/<DATASET_NAME>/` → metrics/Book. Không ghi kết quả parse vào raw đã chuẩn bị.

Notebook [chuẩn bị input](../../src/notebooks/milestone2_prepare.ipynb), helper src/preparation/ và [hướng dẫn](./HUONG_DAN_CHUAN_BI_INPUT.md) đã có. Người chạy cần checkout chứa code mới, mount đúng Drive và chỉnh:

~~~python
SOURCE_PATH = Path('/content/drive/MyDrive/arXivProject/Milestone1')
PREPARATION_DIR = Path('/content/drive/MyDrive/arXivProject/preparationM2')
DATASET_NAME = 'Danh2'  # đổi theo tài khoản thực tế
RAW_CORPUS_ROOT = PREPARATION_DIR / 'raw_m1' / DATASET_NAME
~~~

RAW_CORPUS_ROOT phải là thư mục **có manifest.json**, không phải folder preparationM2 ở cấp ngoài. Mỗi người chuẩn bị đủ ba tài khoản M1 của mình hoặc trỏ notebook vào cây backup đã gom đủ ba tài khoản; không chỉ chạy một ZIP rồi coi là đã đủ 5.000 bài.

### P0. Chuẩn bị và ký nhận input trước khi tích hợp parser

| Task | Người thực hiện / review | Hướng làm | Bàn giao / điều kiện nhận |
|---|---|---|---|
| P0.1 Chạy notebook trên backup thật | Mỗi người làm ba tài khoản của mình; Khánh review inventory, Danh review kỹ thuật | Giữ nguyên M1, chọn đúng SOURCE_PATH/DATASET_NAME, chạy hết notebook; một runtime ghi một đích | RAW_CORPUS_ROOT, preparation.json, input_validation.json, inventory/blocked/audit; notebook hoàn tất kiểm đọc lại |
| P0.2 Kiểm phạm vi toàn nhóm | Khánh chủ trì; mỗi người xác nhận account | Lập data/preparationM2/group_inputs.csv ngoài Git; một dòng mỗi dataset/account, đủ 12 account hoặc có mapping nếu đã gom; đối chiếu assignment M1, chống trùng publication/version | member, account, raw_root, run_id, snapshot_id, status, paper_count, versions_expected/ready_tex/empty_no_tex/blocked, backup_errors, reviewer; chênh lệch có lý do |
| P0.3 Xử lý blocked | Người sở hữu account tìm backup; Khánh xác minh, Danh sửa helper nếu có bug | Đọc reason/m1_error, tìm đúng ZIP/receipt hoặc quay lại luồng sửa lỗi M1; chạy prepare lại, đối chiếu snapshot | Danh sách version/lỗi/cách xử lý/evidence; không tạo TeX rỗng, đổi lỗi thành no_tex hay xóa version khỏi mẫu số |
| P0.4 Chọn mẫu phát triển chung | Khang chọn cấu trúc; Nguyên chọn bibliography; Khánh xác nhận source; Danh đóng config | Chọn publication có mọi versions từ raw đã kiểm, bao phủ S1–S13; đặc điểm không có dùng fixture và ghi rõ | ID/version/source spans + snapshot_id, cây/entries kỳ vọng; cả nhóm dùng cùng mẫu và config |
| P0.5 Chốt contract, nối một ca xuyên pipeline | Danh chủ trì; cả bốn review | Tạo types/API mục 3, nối một publication nhiều file có ít nhất hai versions; kiểm input trước adapter và kiểm output sau assemble | Một ca chạy xuyên pipeline, test integration và contract chung; mở rộng trên nền này |

**Điều kiện dùng input:** input_validation.json có valid=True, run_id khớp preparation.json/manifest và snapshot_id khớp lần kiểm hiện tại. Chạy validate_prepared_corpus(RAW_CORPUS_ROOT) khi copy dữ liệu, đổi source và trước lượt parse mới; receipt cũ không thay việc kiểm thật.

- valid=True, complete=True: mọi version phát hiện trong dataset có source hợp lệ hoặc no_tex có bằng chứng, không có lỗi backup.
- valid=True, complete=False: raw nhất quán nhưng còn blocked/lỗi backup được ghi nhận. Được code/pilot trên ready_tex, vẫn giữ mọi expected version trong coverage; chưa ký toàn corpus hoàn thành.
- valid=False, run đang in_progress hoặc run/snapshot không khớp: dừng bàn giao, sửa input/chạy lại notebook. Không bắt parser tự đoán và bỏ lỗi.

ZIP mẫu đã kiểm chỉ thuộc account Danh2, không phải toàn nhóm. Notebook chạy xong chứng minh xử lý được backup đang có; kiểm đủ assignment và xử lý source thiếu vẫn là P0.2/P0.3.

## 1. Ai làm gì?

| Người | Phần chính | Hiểu đơn giản | Review chính |
|---|---|---|---|
| **Khánh** | Input M1, root/include, coverage, xác minh source | Đưa đúng bài và đúng file vào parser | Khang review gathering; Danh review coverage |
| **Khang** | Hierarchy, sentence splitter, leaves, itemize | Chia bài thành cây nội dung đúng | Khánh review cây; Nguyên review citation/bibliography boundary |
| **Nguyên** | `.bib`, `bibitem`, reference dedup, field union, key map | Gom tài liệu tham khảo thành một bộ thống nhất | Danh review key map; Khang review boundary |
| **Danh** | Cleanup/math, cite rewrite, element dedup, pipeline, benchmark | Làm sạch và nối các phần thành sản phẩm cuối | Khang review normalization; Khánh review pipeline/metrics |

**Trách nhiệm chung:** mỗi người tự viết test và phần Book của mình, kiểm corpus của mình, review phần được giao và bàn giao số liệu. Danh tích hợp Book chứ không viết thay toàn bộ nội dung của ba người còn lại.

## 2. Quy tắc phối hợp trước khi code

- [ ] Cả 4 đọc M2 và thống nhất đầu ra. Thông tin “đề bắt buộc” xem kế hoạch; tên file/hàm và quy tắc phối hợp dưới đây là thiết kế nhóm đề xuất.
- [ ] Khánh + Danh đối chiếu toàn bộ corpus M1, chọn backup thật và liệt kê input thiếu. Không dùng session-report stub làm TeX corpus.
- [ ] Chốt package `src/parsing/`, một notebook `src/notebooks/milestone2.ipynb`, dữ liệu chạy dưới `data/milestone2/` ngoài Git.
- [ ] Danh chủ trì khai báo contracts; ba người còn lại review và cùng chốt trước khi triển khai consumer. Thay contract phải thông báo và cập nhật tất cả consumer trong cùng đợt tích hợp.
- [ ] Mỗi module có một owner. Thay module người khác phải phối hợp owner, không tự chép một bản helper rồi để hai chuẩn khác nhau.
- [ ] Xây test từ các ca cụ thể trước, chạy thấy lỗi, triển khai rồi chạy lại; commit theo deliverable có thể kiểm. Không đặt mục tiêu số lượng test thay cho bao phủ hành vi.
- [ ] Mỗi người có thể dùng nhánh `codex/m2-<ten>-<phan-viec>` nếu nhóm chọn cách làm qua nhánh. Đây là gợi ý, không yêu cầu tạo nhánh ngay khi đọc kế hoạch.
- [ ] Không sửa raw M1; rewrite citation chỉ trên biểu diễn M2. Không commit corpus, ZIP, metrics thật hoặc notebook output chứa data vào repo code.

## 3. Các file dự kiến và hợp đồng bàn giao

Phần **đã có để chuẩn bị input**, Danh bảo trì và Khánh review: src/preparation/milestone2.py, src/preparation/validation.py, src/notebooks/milestone2_prepare.ipynb và tests/test_m2_preparation.py. Không viết lại restore trong từng module parser; dùng raw root/snapshot đã ký ở P0.

### 3.1. Quyền sở hữu file

| File dự kiến | Owner | Trách nhiệm |
|---|---|---|
| `src/parsing/contracts.py` | Danh; cả 4 duyệt | Kiểu input/output/status và schema thống nhất |
| `src/parsing/__init__.py` | Danh | Export public API, không chứa nghiệp vụ |
| `src/parsing/inputs.py` | Khánh | Adapter manifest/receipts M1, inventory, coverage source |
| `src/parsing/gather.py` | Khánh | Tìm root, include traversal, source map, bibliography locations |
| `src/parsing/hierarchy.py` | Khang | Cây thô, cấp cấu trúc, math/figure/itemize và reference blocks |
| `src/parsing/sentences.py` | Khang | Tách sentence có bảo vệ ngữ cảnh |
| `src/parsing/bibliography.py` | Nguyên | Đọc `.bib` và chuyển `bibitem` |
| `src/parsing/reference_dedup.py` | Nguyên | Identity, union fields, canonical keys theo publication |
| `src/parsing/normalize.py` | Danh | Cleanup, math, cite rewrite trên node |
| `src/parsing/content_dedup.py` | Danh | Element IDs, mapping và hierarchy theo version |
| `src/parsing/validation.py` | Danh | Schema/integrity và audit toàn publication |
| `src/parsing/serialization.py` | Danh | JSON/JSONL round-trip, review input và atomic write |
| `src/parsing/pipeline.py` | Danh | Điều phối, checkpoint, resume và export working data |
| `src/parsing/metrics.py` | Khánh | Coverage/count/reduction tables; nhận số đo do pipeline cấp |
| `src/parsing/benchmark.py` | Danh | Wall time, process-tree RAM samples, output bytes |
| `src/notebooks/milestone2.ipynb` | Danh | Chọn input/config, chạy và hiển thị/audit; không nhét parser vào cell |
| `tests/test_m2_*.py` | Mỗi người triển khai template test của mình | Ca hồi quy và integration |
| `README.md`, `src/requirements.txt`, `environment.yml` | Danh tích hợp; mọi người cung cấp thay đổi | Hướng dẫn và môi trường M2, giữ M1 chạy được |

Các file trên đã có bộ khung ngày 28/10/2026; có tên file không có nghĩa đã triển khai. Bổ sung serialization.py (Danh) để chốt IO/review format. Đường dẫn Book ở mục 9 thuộc checkout/repo báo cáo riêng. Chữ “dự kiến” trong các task bên dưới chỉ hướng triển khai, không cho phép thay schema/API đã chốt.

### 3.2. Schema đã chốt, không tự sửa trong nhánh owner

Nguồn chính thức: [contracts.py](../../src/parsing/contracts.py), semantics/wire format ghi trực tiếp trong docstring từng type và hàm serialization. Dùng dataclass keyword-only; types đầy đủ gồm SourceSpan, BibliographyLocation, BibliographyExtraction, diagnostics/decisions/conflicts và run/checkpoint records. Không tự đổi thành dictionaries giữa owner.

- Khánh nhận raw m2-input-1.0 đã prepare; crawler schema 3.0 đi qua notebook prepare trước.
- Khang trả occurrence tree có spans/position và bibliography blocks typed, chưa normalize/dedup.
- Nguyên trả BibliographyExtraction có occurrences **và diagnostics**, kể cả trường hợp không đọc được entry nào. unify nhận list BibliographyExtraction toàn publication, không list entries trần.
- Danh normalize trên copies, assemble shared IDs, finalize status rồi serialize đúng working schema m2-working-1.0.
- Nội dung nodes theo D3, identity theo C3, status theo 9.3; public signatures chi tiết nằm trong source. Đổi contract phải qua Danh cập nhật đồng bộ, không tự merge schema khác nhau.

### 3.3. API và cách phát triển độc lập

Đọc signature/type hints và docstring ngay trong từng prototype; không cần tài liệu API riêng. Bổ sung `validation.finalize_publication`, module `serialization` và types metrics/benchmark để không phải đoán format lúc ghép.

[Fixtures chung](../../tests/m2_support/fixtures.py) dựng sẵn GatherResult, raw/normalized VersionTree, BibliographyExtraction, UnifiedBibliography và expected ParsedPublication. Chỉ là mẫu synthetic, không chạy prototype upstream, không chứng minh corpus thật. Mỗi owner tự viết test và fixtures bổ sung trong files riêng, không chờ module người khác hoàn thành.

`tests/test_m2_<module>.py` đã tạo placeholder test có skip rõ ràng; thay bằng assertions thật rồi xóa placeholder khi triển khai. Không lấy suite toàn skipped làm bằng chứng đạt. Prompt từng người và prompt Danh ghép/dọn cuối ở mục 14–15.

### 3.4. Quy tắc nối raw input với parser

Khánh gọi validate_prepared_corpus trước khi đọc schema m2-input-1.0. Hàm có sẵn trong package preparation, trả valid, complete, run_id, snapshot_id, issues và counts. Danh đưa snapshot_id, RAW_CORPUS_ROOT và code/config revision vào log/manifest parser; source/snapshot đổi phải invalidate checkpoint liên quan.

| Raw input | VersionInput | Hành vi parser / dữ liệu giữ lại |
|---|---|---|
| ready_tex | source_status=tex, source_dir đúng inventory | Parse compilation path; giữ fingerprint/source spans |
| empty_no_tex | source_status=no_tex, không đưa nội dung cho parser | VersionTree rỗng, status empty_no_tex, không có fake root/element |
| blocked_input | source_status=blocked, source_dir=None | Giữ version + reason/m1_error trong diagnostics/coverage, không báo parse thành công |

metadata_path trỏ metadata bài; references.path trỏ reference_result.json đầy đủ M1. Đây là pool metadata M1/M3; Nguyên vẫn trích bibliography M2 từ .bib/bibitem trong source. downloads có thể giữ claim success cũ từ M1 dù source hiện blocked: dùng version_states + kiểm receipt thật, không chỉ downloads.status.

Nếu publication xuất hiện trong nhiều dataset, Khánh đối chiếu fingerprints trước khi chốt shard; cùng version khác bytes phải review, cùng bytes chỉ giữ một nguồn dùng. Không parse/dedup các versions của một bài ở những shard khác nhau.

## 4. Khánh — Đầu vào, compilation path và coverage

### KH1. Kiểm kê và làm adapter M1

**Hướng làm:** Đọc raw root đã ký ở P0, kiểm validation/run/snapshot rồi sinh một PublicationInput cho mỗi arxiv_id. Duyệt record.versions đầy đủ, map trạng thái theo mục 3.4, đối chiếu receipt/path trong inventory. Đưa reason/m1_error vào diagnostics của blocked; chưa dựng cây/cleanup. Bàn giao fixtures/output types sớm cho các consumer.

**Files:** `inputs.py`, `tests/test_m2_inputs.py`.

- [ ] Đọc quy ước M1 trong `src/crawling/__init__.py`, `pipeline.py`, receipts và hướng dẫn backup.
- [ ] Lập inventory expected publications/versions; đối chiếu file thật, source status và hash. Báo missing/corrupt thay vì tự tạo thư mục rỗng.
- [ ] Xác minh/checkpoint/full backup và hợp nhất theo publication-version. Không đếm checkpoint/final/retry thành nhiều bài.
- [ ] Giữ metadata và references M1 làm đầu vào M3; parser không lọc publication vì S2 references rỗng.
- [ ] Viết adapter theo API mục 3, giữ đúng ID legacy và version int.
- [ ] Chốt 28/10: chỉ nhận output chuẩn bị m2-input-1.0; backup corpus M1 schema 3.0 phải đi qua notebook prepare trước, theo [hướng dẫn input](./HUONG_DAN_CHUAN_BI_INPUT.md). Với output chuẩn bị, kiểm preparation.json đã kết thúc và run_id khớp manifest; map ready_tex -> tex, empty_no_tex -> no_tex, blocked_input -> blocked trong VersionInput. version_states là căn cứ, không suy source hợp lệ chỉ từ downloads.status có thể là claim M1 cũ.

**Test bắt buộc:** bài có 3 versions nhưng thiếu v2 vẫn có đủ 3 version records, v2 blocked; `no_tex` có receipt khác thư mục thiếu; hai backup cùng bài không nhân đôi; ID có slash không bị hỏng; report stub bị nhận diện không đủ source.

**Bàn giao:** `PublicationInput`, inventory CSV, danh sách input cần phục hồi và hướng dẫn chọn corpus. **Reviewer:** Danh. **Đạt khi:** không mất expected version và mọi source được dùng có provenance xác minh được.

### KH2. Tìm root và theo include

**Hướng làm:** Tách nhận diện comment/command có ngoặc cân bằng trước, tìm root đang có hiệu lực, rồi duyệt input/include bằng recursion stack theo thứ tự gặp. Ghi file/offset ngay khi ghép đoạn. Kiểm include lặp/comment để tránh visited-set làm mất nội dung. Tách khai báo bibliography thành bib_paths cho Nguyên; không đọc mọi file trong folder.

**Files:** `gather.py`, `tests/test_m2_gather.py`.

- [ ] Tìm `\documentclass` không nằm trong comment; quy tắc root ambiguity có diagnostic rõ.
- [ ] Theo include đệ quy, đúng thứ tự; xử lý suffix `.tex` và relative paths theo quy tắc có test.
- [ ] Không theo commented include, không đọc file thừa, không bỏ include lặp hợp lệ.
- [ ] Phát hiện missing include, vòng lặp, include ra ngoài source root và macro path chưa giải được.
- [ ] Cung cấp flattened LaTeX, source map và danh sách `.bib` bài thật sự khai báo.

**Test bắt buộc:** include sâu 3 cấp; `% \input{old}` không được mở; `\%` không cắt sai văn bản; include lặp hai lần giữ hai occurrences; cycle báo lỗi hữu hạn; nhiều root/không root không được báo ready giả; `.bib` không được dùng không tự nhập vào.

**Bàn giao:** `GatherResult` trên fixture và ít nhất một bài thật nhiều file nếu corpus có. **Reviewer:** Khang. **Đạt khi:** so được thứ tự và nội dung với source đang compile của bài kiểm.

### KH3. Coverage/counts và vận hành shard

**Hướng làm:** Lấy expected counts từ input manifest và status cuối từ pipeline; join theo arxiv_id/version để lộ version rơi mất. Tính lại tử số/mẫu số khi gộp shard, không trung bình tỷ lệ. Xuất CSV có snapshot/run ID; đối chiếu fixture tính tay và inventory nhóm trước khi gửi Book.

**Files:** `metrics.py`, `tests/test_m2_metrics.py`.

- [ ] Tính counts từng trạng thái, coverage từng publication/version theo công thức trong kế hoạch mục 10.
- [ ] Chỉ lấy status cuối sau bibliography/dedup/validation theo kế hoạch 9.3; tách body-tree validity với end-to-end success, thống kê error codes và export_ready.
- [ ] Đếm occurrences và rows distinct riêng; reference entries-before là occurrences qua versions.
- [ ] Mẫu số 0 xuất null/không áp dụng; không đổi chưa đo thành 0.
- [ ] Khi chạy shard của Khánh, kiểm input và giữ output/log/run ID; tổng hợp các shard theo publication duy nhất.

**Test bắt buộc:** fixture có parsed/empty/partial/failed/blocked cùng lúc; tổng status bằng expected; tỷ lệ khớp tính tay; tổng hợp hai lần cùng run không nhân đôi; cây body hợp lệ nhưng thiếu bibliography/cite unresolved vẫn partial và không tăng N_parsed; warning thiếu field vốn không có vẫn cho parsed.

**Bàn giao:** tables/CSV có units và denominators, không chỉ ảnh. **Reviewer:** Danh.

### KH4. Viết và review báo cáo

**Hướng làm:** Viết phần input/root/include từ các ca đã kiểm của mình, dẫn tới snapshot và source spans. Giải thích rõ expected, empty, blocked và cách gộp backup. Khi review pipeline, truy ngược một bài nhiều versions từ inventory đến output/coverage để phát hiện phần bị bỏ.

- [ ] Viết input/multi-file trong trang overview và parsing; đưa ví dụ root/include từ ca kiểm thật.
- [ ] Cung cấp coverage data cho notebook thống kê và giải thích thiếu dữ liệu nếu có.
- [ ] Review pipeline của Danh về không mất version, resume và counts; ký kiểm tra các chỉ số coverage trong Book.

## 5. Khang — Hierarchy, sentence, math blocks và figures

### KG1. Dựng khung cây

**Hướng làm:** Nhận flattened LaTeX từ Khánh, phân vùng body/heading/math/float/list/bibliography trước khi xóa command. Dựng occurrence tree bằng stack cấp heading và môi trường; node có local_id, parent, position, source spans. Xử lý prose trước section đầu và cấu trúc nhảy cấp. So với cây kỳ vọng P0.4; bàn giao cây thô, chưa tự dedup/shared ID.

**Files:** `hierarchy.py`, `tests/test_m2_hierarchy.py`.

- [ ] Nhận `GatherResult`, phân vùng cấu trúc trước khi cleanup làm mất command.
- [ ] Tạo document root và stack headings; xử lý cấp bị nhảy, paragraphs và các section không đánh số.
- [ ] Giữ acknowledgements/appendix và content sau bibliography nếu còn cấu trúc hợp lệ.
- [ ] Tách bibliography blocks khỏi body nhưng giữ chúng cho Nguyên.
- [ ] Giữ source spans, occurrence IDs và position; root khác với shared content ID cuối.
- [ ] Bàn giao đủ child fragments/thứ tự để Danh tạo content paragraph/item/itemize theo D3; không để placeholder rỗng trở thành content cuối của mọi node cha.

**Test bắt buộc:** bài bắt đầu bằng subsection; `\section*{Acknowledgements}`; `\appendix`; References rồi Appendix; câu trước section đầu; braces/command lồng nhau không làm rơi text.

**Bàn giao:** `VersionTree` thô, sơ đồ cây kỳ vọng so cây thực. **Reviewer:** Khánh; Nguyên kiểm bibliography boundary.

### KG2. Tách sentences an toàn

**Hướng làm:** Bảo vệ span math, command arguments, URL/decimal và abbreviations rồi mới tìm dấu kết câu trên prose. Khôi phục nguyên nội dung và mapping vị trí; tránh placeholder làm sai source spans. Splitter nhận text span, không nhận nguyên figure/bibliography. Lưu input và expected sentence boundaries cho từng ca.

**Files:** `sentences.py`, `tests/test_m2_sentences.py`.

- [ ] Bảo vệ inline math, command arguments, URL, decimal, abbreviations rồi mới tách dấu kết thúc câu.
- [ ] Không split tại dấu chấm trong `i.e.`, `et al.`, `Fig. 1`, `$x=3.14$` và `\ref{sec.1}`.
- [ ] Giữ citation command trong câu cho Danh rewrite; giữ text cuối đoạn không có dấu chấm như một prose unit có diagnostic/quy tắc được giải thích.
- [ ] Khôi phục nguyên nội dung vùng được bảo vệ, không lộ placeholder vào output.

**Test bắt buộc:** `As in Fig. 1, we use $x=3.14$. It works.` có 2 sentences và đủ math; URL có dot không bị băm; `\cite{a,b}` còn nguyên; command chứa dấu chấm không bị cắt giữa ngoặc.

**Bàn giao:** danh sách input/expected sentences và module dùng được trong hierarchy. **Reviewer:** Khánh.

### KG3. Hoàn thiện các loại node

**Hướng làm:** Math display và figure/table là leaf; inline math ở trong sentence. itemize/item tạo component theo từng cấp rồi thêm leaves bên trong. Giữ caption/nội dung bảng, tách bibliography cho Nguyên và quay lại body khi còn appendix. Cung cấp child fragments/thứ tự để Danh tạo component content theo D3.

- [ ] Inline math nằm trong sentence; equation/display math thành `block_formula`.
- [ ] Figure/table thành `figure`; giữ caption và nội dung bảng có nghĩa, không yêu cầu ảnh đã bị M1 lọc.
- [ ] Itemize/item là các component, có leaf bên trong; xử lý danh sách lồng nhau.
- [ ] Đánh diagnostic cho môi trường/macro chưa hỗ trợ, thử mở rộng khi nó xuất hiện trong corpus thật.

**Test bắt buộc:** `equation`, `$$...$$`, `\[...\]`, block nhiều dòng; figure không có ảnh local nhưng có caption; table có `\midrule`; itemize hai cấp có công thức. Kiểm mọi body leaf thuộc sentence/block_formula/figure.

**Bàn giao:** cây đầy đủ trên bộ mẫu và thống kê loại node trước cleanup. **Reviewer:** Danh kiểm normalizer nhận đủ nội dung, Nguyên kiểm citation không mất.

### KG4. Kiểm tay và báo cáo

**Hướng làm:** Chọn ca thật có các đặc điểm S1–S4, so cây với source và PDF khi có; ghi ID/version/span, lỗi và commit sửa. Báo cáo bằng ví dụ trước/sau có dữ liệu thật. Review normalize để chắc wrapper bị bỏ nhưng text/math/citation và ranh giới node không bị mất.

- [ ] Chọn ca thật nhiều file, math nhiều, bảng, itemize và appendix nếu corpus có; so cây với TeX và PDF khi có sẵn.
- [ ] Chạy shard của Khang cùng commit/config; lập issue cho mọi ca parse thiếu.
- [ ] Viết phần hierarchy/sentence/leaf trong Book, sửa ví dụ template gọi inline math là leaf riêng.
- [ ] Review cleanup/math của Danh để chắc ý nghĩa và node boundaries không bị phá.

## 6. Nguyên — BibTeX, hợp nhất entries và citation key map

### NG1. Đọc `.bib` và chuyển `bibitem`

**Hướng làm:** Dùng bib_paths của gather và bibliography_blocks của tree. Đọc .bib có braces/multiline bằng parser đã thử hoặc bộ đọc có trạng thái; không split theo dòng/dấu phẩy. Với bibitem, tách entry theo command, trích fields có evidence và giữ raw/span. Trả BibOccurrence riêng từng version; references.json M1 không thay bibliography M2.

**Files:** `bibliography.py`, `tests/test_m2_bibliography.py`.

- [ ] Nhận bibliography locations từ Khánh và raw bibliography blocks từ Khang.
- [ ] Đọc BibTeX multiline/nested braces/chuỗi tác giả; nếu dùng thư viện thì thử bộ mẫu, ghi dependency/version và nguồn đã dùng.
- [ ] Chuyển `\bibitem[nhãn]{key}` thành fields có cấu trúc; giữ raw/evidence khi thiếu thông tin.
- [ ] Map `author` -> `authors: list[str]`, year -> int nullable; không suy tác giả đầy đủ từ initials hoặc bịa entry type.
- [ ] `.bbl` bị thiếu được báo thiếu input bibliography; `.bib` không có khi bài thực dùng `bibitem` không phải lỗi.

**Test bắt buộc:** một bài chỉ có bibitem; một bài dùng `.bib`; title có nested braces; author tổ chức; năm thiếu; entry hỏng vẫn có raw diagnostic; `bibitem` có nhãn tùy chọn.

**Bàn giao:** `BibOccurrence` toàn bộ versions và bảng tỷ lệ fields trích được/thiếu. **Reviewer:** Khang kiểm ranh giới trích, Danh kiểm kiểu dữ liệu.

### NG2. Nhận diện trùng và union fields

**Hướng làm:** Gom occurrences toàn publication, chuẩn DOI/title/full authors/year theo C3 và kiểm identity trên toàn cluster. Chốt canonical key ổn định, union nonmissing fields rồi sinh map theo version. Candidate cần review phải có evidence chạy lại qua reference_review_path. Bàn giao entries/key map/conflicts/decisions cùng fixture ba versions.

**Files:** `reference_dedup.py`, `tests/test_m2_reference_dedup.py`.

- [ ] Normalize DOI, title/author/year phục vụ so sánh nhưng giữ nội dung gốc có ý nghĩa trong output.
- [ ] Dedup entries trùng trong một version và giữa versions, không cross-publication.
- [ ] Chọn canonical key ổn định, xử lý key collision và sinh map `(version, old_key)`.
- [ ] Cùng key nhưng hai tài liệu trong chính một version phải có conflict cần kiểm, không tùy tiện chọn một đích rồi báo rewrite thành công.
- [ ] Union nonmissing fields; ghi mâu thuẫn và provenance theo chính sách kế hoạch mục 7, không ghi đè bằng null.
- [ ] Trường hợp identity mơ hồ chuyển review, không gộp mạnh để tăng reduction.
- [ ] Áp dụng bảng quyết định C3: thiếu DOI chỉ auto-merge khi title + toàn bộ authors đầy đủ + year trùng; thiếu year/initials/et al. cần evidence review, không chỉ dựa citation key.
- [ ] Kiểm DOI trên toàn cluster trước merge; candidate thiếu DOI nối được hai cluster có DOI đối nghịch phải đứng riêng chờ review, không phụ thuộc thứ tự duyệt.
- [ ] Xuất identity_decisions với evidence, affected versions, reviewer và kết luận; candidate còn chờ review phát diagnostic `REFERENCE_IDENTITY_REVIEW` mức error theo mục 9.3.
- [ ] Áp dụng quyết định review từ config qua API khi occurrence IDs/fingerprint khớp; quyết định cũ sai source không được tự dùng lại. Danh lưu identity_decisions.json để chạy lại và audit.

**Test bắt buộc:** ví dụ 3 versions title/author/year -> thêm DOI -> mất year vẫn ra đủ fields; khác key cùng DOI thành một entry; cùng key khác DOI không bị gộp; title gần giống nhưng khác tài liệu giữ riêng; cùng key v1/v2 có thể map hai canonical keys; cùng key hai tài liệu trong một version tạo conflict, không giả vờ giải được.

**Bổ sung ca C3:** không DOI nhưng title chỉ khác wrapper/spacing và full authors/year trùng thì merge; thiếu year hoặc initials/full-name thì pending review; title/year trùng nhưng authors khác giữ riêng; B thiếu DOI không nối A(DOI X) với C(DOI Y); đổi thứ tự input vẫn cùng quyết định. Ca v3 thiếu cả year/DOI phải có review evidence trước khi merge và union fields, không suy identity từ key.

**Bàn giao:** `UnifiedBibliography`, conflicts, identity_decisions và counts-before/after. **Reviewer:** Danh.

### NG3. Kiểm citation rewrite cùng Danh

**Hướng làm:** Tạo fixtures câu chỉ khác cite key, nhiều keys/optional arguments và unresolved cite. Đưa key map cho Danh, đối chiếu câu sau rewrite với unified entries rồi với content dedup. Chỉ nhận bàn giao khi cả hai người chạy được ca tích hợp và không còn key cũ ngoài phạm vi đã ghi diagnostic.

- [ ] Cung cấp fixture `\cite{old1,old2}`, key collisions theo version, optional citation arguments và citation chưa có entry.
- [ ] Đối chiếu toàn bộ keys đã dùng với entries sau hợp nhất; phân biệt unresolved thật với key đổi tên chưa áp dụng.
- [ ] Giữ non-arXiv entries trong `bibtex`, không lọc theo pool `references` M1.

**Bàn giao:** test tích hợp references -> rewritten sentences -> content dedup, chứng minh câu chỉ khác citation key được chia sẻ sau rewrite. **Reviewer:** Khang kiểm câu không mất nội dung.

### NG4. Kiểm thật và báo cáo

**Hướng làm:** Kiểm tay các reference xuất hiện qua nhiều versions, ghi rõ lý do merge/keep-separate và fields giữ lại. Tổng hợp missing fields, review/conflict/unresolved rates bằng mẫu số thật. Đưa ví dụ source → occurrences → unified entry → rewritten citation vào Book, không trộn với counts S2 của M1.

- [ ] Kiểm tay entry identity, fields union và cite rename trên các cặp versions thật; chưa có dạng bibitem trong mẫu thật thì bổ sung fixture và ghi rõ giới hạn mẫu.
- [ ] Chạy shard Nguyên, giữ run/evidence; cung cấp thống kê missing fields/conflicts/unresolved citations.
- [ ] Viết phần reference extraction/dedup của `03_standardization.md` với ví dụ thật và limitations.
- [ ] Review report số entries trước/sau; không trộn BibTeX counts với S2 reference counts.

## 7. Danh — Chuẩn hóa, lưu chung, pipeline và benchmark

### DA1. Contracts và chuẩn hóa

**Hướng làm:** Chốt types/API trước P0.5, nhận tree của Khang và key map của Nguyên. Rewrite key trong citation command, cleanup theo node kind, chuẩn hóa math rồi tạo component content từ con lên cha theo D3. Không đọc/sửa trực tiếp source dưới preparationM2. Kiểm normalize hai lần bằng một lần trước khi gửi assemble.

**Files:** `contracts.py`, `__init__.py`, `normalize.py`, `tests/test_m2_normalize.py`.

- [ ] Định nghĩa types/API ở mục 3 và schema mục 9 kế hoạch; cả nhóm review trước consumer.
- [ ] Cleanup theo loại node; giữ text bên trong wrapper, caption/table content, citation và math.
- [ ] Math về quy ước chung; bảo toàn align nhiều dòng và escape, không replace command toàn văn.
- [ ] Rewrite cite bằng version-specific key map trước khi fingerprint nội dung; key thường ngoài citation không bị đổi.
- [ ] Normalize có tính idempotent, source spans/provenance không mất.
- [ ] Tạo component content từ con lên cha đúng D3 sau cite rewrite/cleanup; cố định `component_content_v1` trong normalization_version và giữ ranh giới math/verbatim/list.

**Test bắt buộc:** `\textbf{Result}` giữ `Result`; bỏ centering/placement/midrule đúng ngữ cảnh; inline/block math thống nhất; align còn các hàng/biểu thức; cite nhiều key và optional args; chữ thường trùng tên key không đổi; normalize hai lần bằng một lần.

**Bổ sung ca D3:** paragraph/item có body không nhận content rỗng; paragraph hai câu nối đúng; block giữ newline; itemize hai items và itemize lồng giữ wrappers/ranh giới; đổi thứ tự items đổi content; heading chỉ giữ title. Normalization lần hai phải giữ nguyên cả content component, không ghép descendants thêm lần nữa.

**Bàn giao:** trees đã chuẩn hóa, không sửa raw corpus. **Reviewer:** Khang; Nguyên review citation rewrite.

### DA2. Element dedup và integrity

**Hướng làm:** Nhận trees đã normalize của mọi versions, fingerprint kind/content trong cùng publication, cấp shared ID rồi remap edges theo version. Giữ occurrence/order/source sidecar. Sau assemble kiểm schema/foreign keys/citation và tính status/export_ready theo 9.3; kiểm câu đổi parent và paragraph/list khác content trước khi chạy shard.

**Files:** `content_dedup.py`, `validation.py`, `tests/test_m2_content_dedup.py`, `tests/test_m2_validation.py`.

- [ ] Tập hợp mọi version của một publication; exact match sau cleanup, phân biệt kind, root mapping riêng từng version.
- [ ] Sinh ID ổn định có publication prefix; kiểm hash collision bằng nội dung thật, không chỉ tin hash.
- [ ] Remap edges qua ID chung; giữ quan hệ theo version và occurrence/order sidecar.
- [ ] Kiểm schema/nullability, duplicate IDs/keys, same-publication foreign keys, expected version và citation integrity.
- [ ] Kiểm occurrence tree trước projection, không ép bảng dedup mất occurrences thành cây giả; nêu giới hạn khi schema không có position.
- [ ] Validator dùng bảng trạng thái 9.3, tập hợp lỗi mọi module và affected versions; tính export_ready ở cấp publication, không chỉ kiểm parser exception.

**Test bắt buộc:** một câu không đổi nhưng đổi parent ở v2 chỉ có một element và đủ hai version edges; hai câu chỉ gần nghĩa không gộp; khác whitespace/format sau cleanup gộp; tất cả versions no_tex không có fake node; nội dung lặp trong một version vẫn có đủ occurrence/order; orphan/cross-paper edge bị phát hiện.

**Bổ sung ca D3/9.3:** paragraphs khác body phải khác ID dù cùng parent; cùng paragraph sau cleanup dùng chung ID; đảo items làm đổi itemize ID; cùng heading title/body khác nhau vẫn giữ đúng occurrence edges; fingerprint phân biệt ranh giới kind/content. Root ambiguity không có cây tin cậy -> failed; mất một include nhưng còn cây hợp lệ -> partial; entry hỏng/cite unresolved/identity review -> partial trên versions affected; schema hỏng không được publish; field vốn thiếu chỉ warning; toàn no_tex hợp lệ export_ready=True.

**Bàn giao:** `ParsedPublication`, audit report và ba bảng không lẫn provenance fields vào schema cuối. **Reviewer:** Khánh review coverage/IDs, Khang review cây.

### DA3. Pipeline, checkpoint và notebook

**Hướng làm:** Notebook parser riêng nhận RAW_CORPUS_ROOT từ preparationM2 và OUTPUT_ROOT ở Milestone2/parsed. Kiểm input, ghi snapshot, nối một publication qua các API mục 3 rồi mới thêm loop/checkpoint sau validate/export. Cache key chứa snapshot, code/config/normalization và review hash. Kiểm ngắt/resume/source đổi; không nhúng restore backup vào parser.

**Files:** `pipeline.py`, `src/notebooks/milestone2.ipynb`, `tests/test_m2_pipeline.py`.

- [ ] Nối đúng thứ tự API: load -> gather -> tree/entries -> unify -> normalize -> assemble -> validate -> export.
- [ ] Mỗi publication được xử lý với tất cả versions trong cùng shard; checkpoint sau khi output và audit xong.
- [ ] Resume dựa input fingerprint + config + normalization/code revision; input/code đổi phải invalid cache liên quan, không dùng output cũ mù quáng.
- [ ] Ghi file tạm và publish hoàn chỉnh; lỗi không đè output tốt cũ, không nhân đôi rows khi chạy lại.
- [ ] Notebook chọn corpus/output/scope, preview inventory, chạy, audit và export; log lỗi rõ, không gom hết thành success.
- [ ] Cập nhật README/requirements/environment theo dependency thật; giữ notebook/source M1 tương thích.
- [ ] strict=True mặc định chặn publish publication chưa export_ready nhưng giữ working/audit; strict=False cho phép lưu working partial có cấu trúc hợp lệ, status không đổi. Ghi phạm vi output mới/cũ, không đánh dấu cache của input cũ là thành công của input mới.
- [ ] Đọc reference_review_path và truyền quyết định C3 đã xác minh vào unify; hash review file tham gia cache key. Bổ sung ca review đổi làm invalidate, source đổi làm quyết định cũ hết hiệu lực; chạy lại cùng review/source tái lập cùng kết quả.

**Test bắt buộc:** bài nhiều file/two versions đi hết pipeline; mixed no_tex/failed/parsed đủ status; ngắt sau một publication rồi resume; source đổi làm invalidate; lỗi giữa ghi output không để publication nửa vời thành complete; fresh run tạo IDs giống lần trước.

**Bổ sung ca strict:** cùng input lỗi cho cùng version status ở cả hai chế độ; strict=True giữ audit và không publish partial; strict=False chỉ ghi working partial hợp lệ/export_ready=False; lỗi một publication vẫn chạy publication độc lập; run không success khi còn blocked/error hoặc ghi output thất bại; toàn no_tex đủ audit/output có thể success. Giữ output tốt cũ nhưng không dùng nó che input mới chưa đạt.

**Bàn giao:** lệnh/API chạy được trong môi trường sạch và notebook smoke run. **Reviewer:** Khánh + Khang.

### DA4. Benchmark và tổng hợp Book

**Hướng làm:** Xác minh raw, chạy output parse mới trên Colab CPU và đo đúng boundary kế hoạch 10.2. Giữ measurements theo run/publication; chuẩn bị backup có evidence riêng, không gọi là benchmark parser. Nhận coverage/node/bib metrics có snapshot từ bốn shard rồi tích hợp Book; kiểm bảng coverage filter và runtime hover/zoom trên Pages.

**Files:** `benchmark.py`, `tests/test_m2_benchmark.py`; phần Book ở mục 9.

- [ ] Đo wall/per-paper/mean/peak process-tree RAM/final output bytes, lưu raw samples + environment + input snapshot + commit.
- [ ] Benchmark thật trên Colab CPU-only, output mới; tách smoke/resume khỏi benchmark mới. Measurement boundary theo kế hoạch mục 10.2.
- [ ] Nhận coverage/counts từ Khánh, hierarchy evidence từ Khang và bib metrics từ Nguyên; kiểm đơn vị/mẫu số trước khi tổng hợp.
- [ ] Sync metrics vào repo báo cáo; notebook thống kê thực thi lúc build, không hiển thị kết quả giả khi input mất.
- [ ] Build sạch và kiểm trang public sau deploy; kiểm hai links nộp với cả nhóm. Đề xuất nhóm nộp Moodle sau khi checklist đạt.
- [ ] Tích hợp bảng coverage tìm ID/lọc status và biểu đồ thời gian hover/zoom/lọc run theo mục 10.4; dependency UI nằm ở report repo. Trang Pages phải hoạt động không cần kernel/Drive session.

**Kiểm bắt buộc:** sampler ghi được values/timestamps/errors, output bytes khớp inventory; local smoke không bị gắn nhãn Colab benchmark; build Book thiếu metrics phải báo lỗi/chưa có dữ liệu rõ, không lặng lẽ dùng demo.

**Bổ sung kiểm Book:** Khánh đối chiếu dòng coverage/filters với inventory, Danh đối chiếu hover values/units với metrics; Khang + Nguyên thử lọc rỗng/reset và zoom/reset trên HTML build + Pages ngoài đăng nhập. Ghi build log, URL/commit và checklist thao tác, không chỉ ảnh tĩnh; snapshot ít run/status ghi ca N/A và kiểm fixture riêng theo 10.4.

**Bàn giao:** benchmark receipts/samples, Book build log/URL và README chạy lại. **Reviewer:** cả ba người; mỗi người ký phần số liệu mình cung cấp.

## 8. Bộ mẫu chung, review chéo và chạy toàn corpus

### 8.1. Bộ mẫu tối thiểu theo đặc điểm

Nhóm chọn bài thật từ corpus nếu có đặc điểm tương ứng; nếu chưa có thì dùng fixture source nhỏ để kiểm hành vi, ghi rõ fixture không chứng minh tỷ lệ thành công toàn corpus.

| Mã ca | Đặc điểm phải kiểm | Chủ test | Người kiểm tay |
|---|---|---|---|
| S1 | Multi-file sâu, file thừa, commented include | Khánh | Khang |
| S2 | Section*, appendix, references không nuốt phần sau | Khang | Khánh + Nguyên |
| S3 | Sentence có abbreviation, URL, decimal, command và math | Khang | Khánh |
| S4 | Equation/align, hình/bảng, itemize lồng | Khang + Danh | Nguyên |
| S5 | Bibitem và `.bib` có fields thiếu/nested braces | Nguyên | Khang |
| S6 | Cùng reference đổi key, union fields qua 3 versions | Nguyên | Danh |
| S7 | Câu giống nhau đổi parent qua versions | Danh | Khánh |
| S8 | No_tex, source thiếu/hỏng, all-empty publication | Khánh + Danh | Khang |
| S9 | Include cycle, nhiều root, key collision, unresolved cite | Owner tương ứng | Người review ở mục 1 |
| S10 | Resume, invalidation, deterministic IDs, repeated occurrence | Danh | Khánh |
| S11 | Component content: body khác/cùng, heading cùng title, đảo item, normalize lặp | Khang + Danh | Khánh |
| S12 | Identity thiếu DOI/year/initials và cluster DOI đối nghịch, review decisions | Nguyên | Danh |
| S13 | Diagnostic -> final status, affected versions, strict và export_ready | Danh | Khánh + Nguyên |
| S14 | Book coverage filter/search và runtime hover/zoom/reset trên Pages | Danh | Khánh + Khang + Nguyên |

Mỗi ca cần input, expected và output thực. Kiểm tay ghi publication/version/path/vị trí, kết quả, lỗi và commit sửa; không chỉ ghi “đã xem PDF”.

S1–S13 kiểm bằng unit/integration fixtures và corpus thật tương ứng; S14 là nghiệm thu build/browser theo kế hoạch 10.4, không yêu cầu giả lập trình duyệt trong unittest. Các ca là công việc phải thực hiện sau khi triển khai, chưa phải test đã chạy. Prototype và test templates đã có, nhưng skipped placeholders không tính đạt.

### 8.2. Cách chạy kiểm tra dự kiến

Sau khi owner thay test placeholders bằng tests thật, từ project root:

```powershell
python -m unittest discover -s tests -p 'test_m2_*.py' -v
```

Nhóm dùng `unittest` stdlib để không bắt buộc thêm test runner. Test dùng imports `src.parsing...`; notebook thêm `<repo>/src` để dùng `parsing...` theo môi trường hiện tại. Nếu đổi quy ước import, Danh cập nhật tất cả test/notebook/README cùng lúc. Kết quả đạt phải có test thật được discover và không có failure/error; “Ran 0 tests” không tính đạt.

Đây là lệnh **dự kiến khi triển khai**, chưa được chạy như bằng chứng parser đã hoạt động. Chạy thêm suite M1 hiện có để phát hiện regression khi sửa dependency hoặc shared source; không cần chạy suite cho việc chỉ viết hai tài liệu kế hoạch này.

### 8.3. Shard toàn corpus và sửa lỗi

- [ ] Mỗi người vận hành phần publication từ assignment M1 của mình hoặc shard được thống nhất không giao nhau; không chia một bài theo version cho nhiều người.
- [ ] Chạy cùng code/config, ghi source snapshot và run ID. Các account M1 phụ không được tính thành thành viên mới.
- [ ] So union input/output toàn nhóm; publication trùng chỉ tổng hợp một lần với nguồn chọn rõ.
- [ ] Owner module sửa lỗi theo nhóm nguyên nhân; người chạy shard chạy lại bài affected, không chấp nhận partial thành success để kịp số lượng.
- [ ] Backup output/metrics/diagnostics đọc lại được; từng người giữ source M1 và parsed output M2 riêng biệt.

## 9. Phân công viết báo cáo và nộp bài

Các đường dẫn sau nằm trong **repo báo cáo riêng**; checkout local là `arXiv-report/`. Commit ở repo báo cáo, không trông chờ `git add` trong repo code sẽ lấy thư mục đã ignore.

| Trang/file trong report repo | Người viết chính | Nội dung/bằng chứng |
|---|---|---|
| `book/content/milestone2/01_overview.md` | Khánh + Danh | Input scope thật, pipeline, ba bảng, trạng thái xử lý |
| `book/content/milestone2/02_parsing.md` | Khánh + Khang | Root/include, source map, hierarchy, sentence/leaf rules và ca kiểm |
| `book/content/milestone2/03_standardization.md` — reference | Nguyên | Trích fields, identity, union, conflicts, key map và cite rewrite cùng Danh |
| Cùng trang — cleanup/math/content dedup | Danh; Khang review | Quy tắc chuẩn hóa, shared elements, per-version parent edges |
| `book/content/milestone2/04_m2_stats.ipynb` | Khánh cung cấp coverage; Khang node stats; Nguyên bib stats; Danh tích hợp | Counts/rates/reduction/performance từ metrics thật; bảng coverage filter/search và biểu đồ hover/zoom theo 10.4, render lúc build |
| `scripts/sync_data.py` hoặc script M2 riêng, `_toc.yml`, `_config.yml`, references | Danh tích hợp; mỗi người đưa citations | Dữ liệu đúng nguồn, execute/build sạch, M1 không bị hỏng |
| Public links và kiểm nộp | Cả 4; Danh điều phối | Public code + Book GitHub Pages; không nộp intermediate data |

Văn bản kế hoạch nội bộ bằng tiếng Việt. Báo cáo tiếp tục tiếng Anh theo Book M1 hiện có; kiểm ngôn ngữ chính thức của chương trình trước khi nộp. Mỗi người dẫn nguồn đã thật sự dùng, phân biệt code copy/adapt và ý tưởng tự triển khai.

## 10. Tiến độ theo cổng bàn giao

| Cổng | Khánh | Khang | Nguyên | Danh | Điều kiện chung |
|---|---|---|---|---|---|
| G0 | Inventory/input mẫu | Cây + component content kỳ vọng | Entries + identity cases kỳ vọng | Contracts/schema/status/strict | P0.1–P0.4 có raw/snapshot/inventory ký nhận; cả 4 duyệt interfaces và biết input thiếu |
| G1 | Gather chạy | Tree tối thiểu | Extract entries | Pipeline tối thiểu | Một bài nhiều file, >= 2 versions qua toàn luồng |
| G2 | Comment/path/errors | Sentence/math/itemize | Union/key collisions/identity | Normalize/dedup/validate/strict | P0.5 và các ca S1–S13 có test tương ứng đạt |
| G3 | Kiểm input thật | Kiểm cây thật | Kiểm reference thật | Kiểm integration | Review chéo có evidence, lỗi quan trọng được sửa |
| G4 | Shard + coverage | Shard + node stats | Shard + bib stats | Shard + aggregate/benchmark | Bao phủ toàn M1, mọi version có trạng thái |
| G5 | Ký coverage/Book | Ký parsing/Book | Ký bib/Book | Build/links/README | S14 và checklist cuối đạt, nhóm hoàn tất nộp |

Thứ tự phụ thuộc: G0 -> G1 -> G2 -> G3 -> G4 -> G5. Trong G1/G2, Nguyên có thể làm bibliography fixtures song song với Khang; Danh làm validator/normalizer bằng fixture theo contract. Không phải chờ một người làm xong toàn bộ mới bắt đầu người tiếp theo.

## 11. Bảng đối chiếu yêu cầu — không để sót việc

| Yêu cầu đề | Owner triển khai | Bằng chứng nghiệm thu |
|---|---|---|
| Mọi publication, mọi version | Khánh + Danh | Inventory đối chiếu M1, coverage từng bài |
| Root/documentclass, input/include bắc cầu, bỏ comment/file thừa | Khánh | KH2/S1, source map + kiểm thật |
| Hierarchy tự nhận cấp và document root | Khang | KG1, cây kỳ vọng/thực tế |
| Sentence không split sai math/command/abbreviation/URL/decimal | Khang | KG2/S3 |
| Block formula, figure; table là figure | Khang + Danh | KG3/S4 và node-kind audit |
| Itemize phân cấp | Khang | KG3/S4 |
| Không đưa references vào cây; giữ ack/appendix | Khang + Nguyên | KG1/S2 |
| Cleanup định dạng | Danh | DA1, kiểm text/caption/table giữ nghĩa |
| Inline/block math thống nhất | Danh + Khang | DA1/S4 |
| Bibitem -> BibTeX | Nguyên | NG1/S5, fields + raw provenance |
| Reference dedup trong/giữa versions | Nguyên | NG2/S6/S9 |
| Citation key rename | Nguyên map; Danh rewrite | NG3/DA1, cite integrity audit |
| Union fields | Nguyên | NG2, ví dụ ba versions không mất year/DOI |
| Content exact match sau cleanup, shared ID | Danh | DA2/S7 |
| Component content có nghĩa trước fingerprint (quy tắc nhóm D3) | Khang + Danh | DA1/DA2/S11 |
| Identity thiếu DOI có evidence, không merge qua DOI đối nghịch (quy tắc nhóm C3) | Nguyên | NG2/S12 |
| Status/strict/export_ready nhất quán (quy tắc nhóm 9.3) | Danh; Khánh metrics | DA2/DA3/KH3/S13 |
| Parent edges đúng theo version | Danh + Khang | S7, occurrence-to-table audit |
| Version không TeX ghi empty, không bỏ | Khánh + Danh | KH1/DA2/S8 |
| Đúng ba bảng M2 | Danh; Nguyên schema bib | DA2 validator, schema review |
| Parsing success, coverage, counts trước/sau | Khánh + cả 4 | KH3 và Book notebook thực thi |
| Wall time, mean/publication, peak RAM, final output size | Danh | Colab CPU evidence, raw samples |
| Code/requirements/README chạy lại được | Tất cả; Danh tích hợp | Môi trường sạch, tests + notebook |
| Một public code repo tích lũy từ M1 | Danh + cả nhóm | Repo/commit history công khai |
| Book cũ, repo riêng, hình/bảng sinh khi build | Tất cả; Danh tích hợp | Clean build log, public Pages |
| Interactivity của Book | Danh; cả nhóm review | DA4/S14, checklist HTML + Pages theo 10.4 |
| Hai link Moodle đúng hạn, không nộp data M2 | Cả nhóm | Kiểm links + xác nhận nộp thực tế |

## 12. Mẫu bàn giao cho mỗi task

```text
Task ID: KH1 / KG2 / NG2 / DA3 ...
Owner + reviewer:
Commit và các file đổi:
Input/snapshot/config:
Output và nơi lưu (không commit corpus):
Lệnh kiểm đã chạy và số tests thực sự chạy:
Ca thật/kiểm tay và kết quả:
Diagnostics, limitations, lỗi còn lại:
Consumer đã nhận và chạy thử:
Phần Book/citations đã cập nhật:
Kết luận: đạt / cần sửa, kèm lý do.
```

Task chỉ “đạt” khi reviewer đọc output và consumer dùng được; gửi mỗi file Python hoặc ảnh kết quả chưa đủ. Bằng chứng fixture và bằng chứng corpus thật được ghi riêng.

## 13. Checklist chốt toàn nhóm

- [ ] P0 hoàn tất: raw roots dưới preparationM2 có validation/run/snapshot đã ký; group_inputs.csv đối chiếu đủ 12 accounts hoặc mapping gộp tương ứng. Các version blocked vẫn nằm trong coverage và có người chịu trách nhiệm xử lý.

- [ ] Khánh ký input/root/include/coverage, Khang ký hierarchy/sentences/leaves.
- [ ] Nguyên ký extraction/union/key map, Danh ký cleanup/rewrite/dedup/schema/pipeline.
- [ ] C3/D3/9.3 được hiện thực và S11–S13 đạt: component content, reference identity và status/strict/export_ready.
- [ ] Tests và review chéo đạt; raw diagnostics/lỗi tồn đọng được xem xét thật.
- [ ] Union bốn shard đối chiếu đủ publication và version M1, không đếm trùng checkpoint/retry.
- [ ] Không thiếu source bị giả làm empty; không partial bị giả làm success.
- [ ] Ba bảng, occurrences/root/key map/provenance và metrics được backup, đọc lại được cho M3.
- [ ] Benchmark CPU Colab thật, đủ bốn số đo bắt buộc và phạm vi đo rõ.
- [ ] Mỗi người hoàn thiện phần Book mình; build thật sinh hình/bảng từ snapshot thật.
- [ ] S14 đạt: bảng coverage tìm/lọc và runtime chart hover/zoom hoạt động trên HTML build và public Pages, số liệu khớp snapshot.
- [ ] README/environment/notebook tái lập được, code repo public giữ lịch sử M1/M2.
- [ ] Public Book cùng repo báo cáo M1, không còn placeholder được trình bày như kết quả.
- [ ] Hai links đã kiểm ngoài đăng nhập và nhóm nộp Moodle trước hạn đã xác nhận.

**Định nghĩa hoàn thành:** code + dữ liệu toàn phạm vi đã kiểm + thống kê/benchmark có bằng chứng + Book thực nghiệm + hướng dẫn tái lập + nộp đúng hai link. Không đánh dấu hoàn thành chỉ vì từng người nói module mình chạy được.

## 14. Prompt giao AI riêng cho từng người

Copy **nguyên khối của người mình**. Cả bốn dùng cùng commit bộ khung làm base. AI phải đọc source thật; không chỉ dựa prompt để đoán schema. Mọi kết quả cuối cần người phụ trách tự kiểm tay và gửi phản hồi bàn giao theo mẫu mục 12. Danh quản lý shared schema/dependencies, ghép cuối theo mục 15.

### 14.1. Khánh — copy gửi AI

```text
Bạn triển khai phần Khánh của Milestone 2 trong repo arXivProject. Đọc ARXIV_PROJECT_FULL.md phần M2, docs/milestone2/KE_HOACH_MILESTONE_2.md, PHAN_CONG_MILESTONE_2_4_NGUOI.md phần KH1–KH4, docstrings từng prototype, src/parsing/contracts.py và docstrings các file dưới đây.

Chỉ sửa src/parsing/inputs.py, gather.py, metrics.py; tests/test_m2_inputs.py, test_m2_gather.py, test_m2_metrics.py; bàn giao bằng phản hồi cuối theo mẫu mục 12, không tạo doc riêng. Có thể thêm test fixture/helper prefix khanh trong tests/m2_support, không sửa fixtures.py chung. Không sửa contracts, package init, modules của người khác, README/requirements/environment, tài liệu chung hoặc report pages chung. Dependency mới ghi đề xuất vào bàn giao cho Danh. Không tự commit/push/merge.

Triển khai các public prototypes đúng signature/types hiện có, thêm private helpers khi cần. inputs chỉ nhận raw m2-input-1.0 đã prepare, gọi read-back validation, giữ tất cả expected versions kể cả blocked/no_tex và snapshot. gather root documentclass active, input/include bắc cầu, đúng thứ tự và include lặp, comment/escaped percent/cycle/missing/root ambiguity; bibliography locations và source maps theo Unicode offsets contract. metrics nhận finalized publication fixtures độc lập, đủ 5 status, đúng mẫu số và null khi chưa đo. Không gọi pipeline hay viết parser cây thay Khang.

Viết tests thật từ S1/S8/S9 và KH3; thay skipped placeholders, không sửa schema để test qua. Dùng shared fixtures làm input cho metrics, TemporaryDirectory cho nguồn gather, fixture backup preparation cho adapter. Không cần chờ upstream/downstream. Nếu raw thật chưa có, hoàn thành phần test độc lập, ghi kiểm thật chưa làm; không bịa evidence.

Cuối cùng bắt buộc hướng dẫn Khánh tự kiểm tay: mở inventory của một bài >=2 versions, so từng version/path/status với source; mở root và các includes, đánh thứ tự text, đối chiếu flattened latex và source_map ở một include sâu/lặp; kiểm commented include không xuất hiện và file thừa không vào. Chọn no_tex và missing nếu corpus có, xác nhận không bị nhầm. Tính tay một fixture metrics mixed status rồi so CSV/tỷ lệ. Reviewer Khang xem gathering, Danh xem input/coverage. Ghi ID/version/snapshot/path/range/expected/actual và lỗi còn lại trong phản hồi bàn giao theo mẫu mục 12; AI không thay người ký đã kiểm tay.

Trước bàn giao: dọn debug prints, backup .bak/.orig, helper trùng không dùng do CHÍNH BẠN tạo. Scratch/output thực đặt dưới data/milestone2-dev/khanh/ ngoài Git. Xóa placeholder test chỉ sau khi có tests thật thay thế và chạy lại đạt; không xóa tests fail/skipped để giấu thiếu việc. Không xóa contracts/shared fixtures/source người khác/raw/outputs cũ. Liệt kê files đổi, dependencies, lệnh + pass/fail/skip thực, contract requests, citations và giới hạn. Giữ diff chỉ trong ownership để Danh merge thuận lợi.
```

### 14.2. Khang — copy gửi AI

```text
Bạn triển khai phần Khang của Milestone 2 trong arXivProject. Đọc đề M2, kế hoạch/phân công KG1–KG4 và S2/S3/S4/S9/S11, src/parsing/contracts.py và docstrings hierarchy.py/sentences.py.

Chỉ sửa src/parsing/hierarchy.py, sentences.py; tests/test_m2_hierarchy.py, test_m2_sentences.py; bàn giao bằng phản hồi cuối theo mẫu mục 12, không tạo doc riêng. Có thể thêm fixture/helper prefix khang riêng, không sửa shared fixtures.py, contracts, init, modules người khác, dependency chung hoặc report pages chung. Dependency mới đề xuất Danh trong bàn giao. Không tự commit/push/merge.

Giữ public signatures; triển khai private scanner/parser có bảo vệ math/commands/braces/comment/verbatim trước khi split. Nhận GatherResult bằng fixtures có sẵn, không gọi gather upstream chưa làm. Cây occurrence document/heading/paragraph/itemize/item và leaves sentence/block_formula/figure; inline math ở trong sentence, table kind figure/subtype table; section* ack/appendix phải giữ. Bỏ bibliography khỏi body nhưng giữ BibliographyBlock có raw/spans cho Nguyên; không cắt hết phần sau References. Giữ local_id ổn định/position siblings/source spans/heading_level; normalized_with=None. Container raw content phải đầy đủ và children không làm mất text; không làm normalization, shared IDs hay dedup thay Danh.

Viết expected tree/sentences do người đọc xác định; dùng make_gathered hoặc tự dựng typed GatherResult cho test độc lập. Bổ sung escaped percent, câu lặp, abbreviation/URL/decimal, math block/align, table/caption, itemize lồng, prose trước heading, appendix sau bibliography. Lỗi macro mất nội dung phải diagnostic chứ không xóa im lặng. Thay skipped placeholders bằng assertions thật. Không sửa schema/fixture chung để khớp implementation.

Cuối cùng bắt buộc hướng dẫn Khang kiểm tay: tự vẽ cây cho một bài thật nhiều file và một bài nhiều math/list/table nếu có; chọn ít nhất một paragraph, ghi ranh giới từng sentence, so source/PDF khi có với nodes. Mở math xem inline không bị thành leaf riêng; block/table đúng kind, caption/rows còn; check itemize cha/con và sibling order, ack/appendix còn, references không lẫn body. Mở ranges của câu lặp để chắc spans đúng lần xuất hiện. Reviewer Khánh kiểm cây, Nguyên kiểm bibliography boundary. Ghi ID/version/snapshot/spans/expected/actual trong phản hồi bàn giao theo mẫu mục 12, phần chưa có raw ghi chưa kiểm thật, AI không thay chữ ký người.

Trước bàn giao dọn file nháp/debug và helper trùng do bạn tạo, scratch/output dưới data/milestone2-dev/khang/ ngoài Git. Bỏ placeholder test sau khi có test thật thay thế; không xóa test fail để xanh. Không đụng file chung/raw/module người khác. Bàn giao danh sách diff, API, test pass/fail/skip thực, citations/dependencies, limitations và phần văn bản Book riêng để Danh ghép, không sửa trang chung gây conflict.
```

### 14.3. Nguyên — copy gửi AI

```text
Bạn triển khai phần Nguyên của Milestone 2 trong arXivProject. Đọc đề M2, kế hoạch C1–C3 và phân công NG1–NG4/S5/S6/S9/S12, src/parsing/contracts.py và docstrings bibliography.py/reference_dedup.py.

Chỉ sửa src/parsing/bibliography.py, reference_dedup.py; tests/test_m2_bibliography.py, test_m2_reference_dedup.py; bàn giao bằng phản hồi cuối theo mẫu mục 12, không tạo doc riêng. Có thể thêm fixtures prefix nguyen riêng. Không sửa contracts/shared fixtures/init, normalizer/pipeline/gather/hierarchy, requirements/README/environment/report pages chung. Ghi dependencies và đề xuất contract vào bàn giao cho Danh, không tự commit/push/merge.

Giữ đúng API typed: extract_entries trả BibliographyExtraction có occurrences + diagnostics, unify_entries nhận list extractions của mọi versions. Dùng GatherResult/VersionTree/BibOccurrence dựng sẵn để làm độc lập; không chờ Khánh/Khang và không implement lại module họ. Đọc chỉ .bib khai báo và bibitem blocks, multiline/braces/optional labels; fields unknown giữ None/[], entry hỏng giữ raw với entry=None/error, missing .bbl không tự coi bibliography rỗng. Đừng lấy metadata references M1 làm bibliography M2 hay lọc entries non-arXiv.

Identity/union theo C3: DOI đúng, thiếu DOI chỉ full ordered authors + normalized title + year khớp, không nối bắc cầu qua DOI đối nghịch; year thiếu/initials mơ hồ có review evidence. Canonical key deterministic theo contract, map (version,old_key), same key trong một version mơ hồ phải error/không đoán. Union fields không mất year khi v3 bỏ, giữ conflicts/decisions/provenance, review occurrence IDs/fingerprint phải khớp. Chỉ xuất key_map cho Danh, không viết lại normalize/rewrite code. Tests đảo input order, key collisions, missing entries/fields và stale reviews.

Cuối cùng hướng dẫn Nguyên tự kiểm tay: mở source và output một bibitem, một .bib có nested braces/tác giả tổ chức, một reference qua >=2 versions; gạch từng field có evidence, so authors/year/DOI, kiểm unknown không bị bịa. Lần theo old_key từng version -> unified key -> entry, tự xác nhận lý do merge/keep/pending và union fields. Chọn same-key different-DOI, missing-year, bridge-conflict fixtures để kiểm không gộp nhầm; kiểm reviewer quyết định thật khớp fingerprints. Khi Danh tích hợp, cùng kiểm câu cite trước/sau và content dedup. Reviewer Khang kiểm boundary, Danh kiểm identity/key map. Ghi ID/version/snapshot/span/evidence/expected/actual trong phản hồi bàn giao theo mẫu mục 12; chưa có raw ghi chưa kiểm thật, AI không ký thay.

Trước bàn giao dọn debug/file .bak/.orig và helpers trùng do bạn tạo; scratch/output dưới data/milestone2-dev/nguyen/ ngoài Git. Bỏ placeholder test sau khi có tests thật chạy đạt, không xóa fail/skip để che thiếu. Không xóa shared fixtures/raw/module khác. Bàn giao diff/test pass-fail-skip/dependencies/citations/limitations và phần reference Book riêng, Danh ghép trang chung.
```

### 14.4. Danh — phần triển khai riêng, copy gửi AI

```text
Bạn triển khai phần Danh của M2 trong arXivProject. Đọc đề M2, phân công DA1–DA4/S4/S7/S8/S10–S14, kế hoạch C3/D3/9.3/10, docstrings các prototype và src/parsing/contracts.py/docstrings.

Trong giai đoạn độc lập chỉ triển khai normalize.py, content_dedup.py, validation.py, serialization.py, pipeline.py, benchmark.py, src/notebooks/milestone2.ipynb; tests tương ứng; bàn giao bằng phản hồi cuối theo mẫu mục 12. Không implement lại Khánh/Khang/Nguyên. Shared contracts/fixtures/dependencies Danh quản lý nhưng không đổi schema chỉ để test qua; nếu thật sự cần đổi, ghi lý do/input và đồng bộ consumers sau khi nhóm nhận revision mới. Chưa có yêu cầu thì không tự commit/push.

Dùng raw/normalized tree, unified bibliography và expected publication fixtures để phát triển riêng normalize/assemble/validate/serialization; không chờ upstream. Cleanup giữ semantics, normalize math/cites theo version trước dedup, rebuild component D3 bottom-up, idempotent, không mutate raw. Exact dedup theo kind/content và deterministic IDs, root version riêng, giữ occurrence/order/spans; projected graph không phải occurrence tree. Validate schema/cites/occurrences, finalize status sau mọi bước, strict chỉ chặn publish không thay status. All-no_tex hợp lệ vẫn giữ coverage, blocked/partial không biến success.

Serialize đúng wire format (đặc biệt tuple key map, int version keys, null/authors lists), atomic/staging/read-back, checkpoint input/config/code/review hash, reject stale cache, không đè output tốt bằng input mới lỗi. Pipeline chỉ nối public APIs chứ không copy logic owner. Chưa merge upstream thì unit tests độc lập đạt nhưng real integration phải ghi pending, không mock mọi thứ để tuyên bố xong. Benchmark Colab CPU fresh, wall/mean/process-tree peak/output bytes và raw evidence; local smoke không gọi Colab benchmark. Notebook gọi helpers, không nhét parser trong cells hoặc in số giả.

Cuối cùng Danh tự kiểm tay: một bài thật nhiều file >=2 versions từ raw đến ba bảng, một câu unchanged đổi parent vẫn một element/đủ edges, repeated occurrences đúng thứ tự; paragraph đổi body và item đảo thứ tự có ID khác. So cite keys với bibtex sau rewrite, kiểm math/table/caption còn nghĩa. Đọc lại JSON để so authors/null/key map/root/version status. Chạy lại source/config/code/review đổi để xác nhận cache invalid, làm lỗi write trong fixture và kiểm output tốt không bị che. Tính tay wall/mean/output bytes một mẫu, nhìn Colab CPU settings; mở Book HTML/Pages thử search/filter/hover/zoom/reset. Ghi evidence/limitations/checks người thật trong phản hồi bàn giao theo mẫu mục 12, reviewer Khánh/Khang/Nguyên ký phần liên quan.

Trước bàn giao giữ diff chỉ ownership; scratch dưới data/milestone2-dev/danh/. Dọn debug, backup files, temporary duplicate helpers do mình tạo; thay placeholder tests bằng tests thật và bỏ placeholder sau khi đạt. Không xóa contracts/fixtures/test thật/raw hay module của người khác. Chỉ sang merge/cleanup cuối khi nhận đủ các nhánh và được Danh yêu cầu theo mục 15.
```

## 15. Prompt Danh ghép cuối và tự dọn phần dư

Prompt này dùng **sau khi ba người bàn giao**, không chạy lúc mới có bộ khung. Cơ chế dọn nằm trong workflow của AI; không có Git hook tự xóa file khi pull/merge. Không thể bảo đảm không conflict nếu các nhánh sửa ngoài ownership; phân vùng files giúp giảm conflict, Git conflict còn lại phải xem nội dung.

```text
Tôi là Danh, người tích hợp M2. Hãy ghép các phần đã được nhóm bàn giao vào bộ khung chung. Trước khi merge, đọc git status để giữ thay đổi đang có, đọc src/parsing/contracts.py, docstrings các prototype và bốn phản hồi bàn giao của thành viên theo mẫu mục 12. Xác định rõ nhánh/commit hoặc files bàn giao thực tế, base revision, dependencies, tests và phần kiểm tay còn thiếu. Nếu chưa có thông tin nhánh thì hỏi tôi; không tự đoán branch/commit hoặc tuyên bố đã nhận đủ.

So diff theo owner trước, không copy cả folder đè checkout. Contracts/public signatures/fixtures dùng chung phải khớp 1.0; nếu owner tự đổi thì đối chiếu input/expected, sửa consumer về contract hoặc đề xuất một revision đồng bộ có lý do. Merge từng phần, chạy tests tương ứng sau mỗi phần, rồi integration thực xuyên load/gather/tree/extract/unify/normalize/assemble/finalize/export/metrics. Không dùng mock tất cả owner để thay bằng chứng pipeline thật. Book/dependency/shared README chỉ cập nhật tập trung một lần; không làm hỏng M1.

Trong cùng lượt tích hợp, chủ động DỌN PHẦN DƯ do quá trình phát triển M2 tạo ra khi đủ bằng chứng: xóa file nháp/debug/.bak/.orig/helper duplicate đã được thay thế trong ownership đã nhận; bỏ test placeholder @skip sau khi xác nhận các acceptance cases đã có assertions thật chạy đạt; bỏ temporary compatibility adapter không còn callers sau khi đã cập nhật mọi consumer và test. Dùng rg tìm references trước khi xóa helper; ghi file nào xóa và lý do. Không tạo wrapper/fallback thứ hai chỉ để né contract conflict. Mỗi public module chỉ giữ một implementation, mỗi logic chung một nơi có owner.

Không xóa contracts.py, shared fixture hữu ích, test thật, test fail để làm xanh, notebook prepare, code M1, corpus/raw, working outputs, review decisions hoặc evidence. Không coi tất cả skipped tests là dư; nếu acceptance chưa làm thì giữ trạng thái chưa hoàn thành. Không dùng git clean -fd, reset --hard, xóa wildcard hay hook tự chạy khi merge. Scratch trong data/ vốn ngoài Git không tham gia merge; không cần xóa dữ liệu người dùng. Chỉ xóa file có nguồn gốc/đích thay thế rõ, bất định thì liệt kê để tôi quyết định.

Sau cleanup chạy tests M2 và regression M1 thích hợp trong môi trường đủ dependencies, notebook smoke và read-back. Tìm NotImplementedError/TODO/demo/skipped trong phạm vi source M2/tests/Book; báo phần chưa làm, không xóa marker thay implementation. Trước khi chốt yêu cầu người phụ trách kiểm tay output thật theo bốn bàn giao, Danh review xuyên pipeline; không tự ghi chữ ký người. Nếu thiếu corpus/Colab/Pages thì ghi kiểm tương ứng pending, không gọi M2 hoàn thành. Bàn giao diff/cleanup list, tests pass-fail-skip, integration evidence, remaining risks và hướng chạy. Chỉ commit/push khi tôi đã yêu cầu; không tự merge PR lên remote.
```
