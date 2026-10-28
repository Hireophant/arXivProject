# Kế hoạch Milestone 2 — Đọc hiểu, cấu trúc hóa và chuẩn hóa bài báo

Ngày lập: **26/10/2026**. Đây là **kế hoạch cần thực hiện**, không phải báo cáo các việc đã hoàn thành.

Cập nhật **27/10/2026**: chốt content của node cha, quy tắc trạng thái/strict, identity references thiếu DOI và nghiệm thu tương tác của Book. Đây là quyết định triển khai của nhóm để làm rõ kế hoạch, không phải yêu cầu mới của giảng viên.

Đọc cùng [phân công chi tiết 4 người](./PHAN_CONG_MILESTONE_2_4_NGUOI.md), [đề tổng](../../ARXIV_PROJECT_FULL.md#milestone-parsing) và [kế hoạch M1](../milestone1/KE_HOACH_MILESTONE_1.md).

**Mục tiêu:** từ source LaTeX của mọi version trong M1, tạo cây nội dung sạch, dùng chung những nội dung trùng và hợp nhất tài liệu tham khảo để M3 sử dụng.

**Cách tổ chức:** đọc corpus M1 nhưng không sửa nó; xử lý từng publication với toàn bộ versions; lưu nội dung dùng chung và quan hệ cha–con theo version riêng biệt. Code nghiệp vụ nằm trong package mới `src/parsing/`, notebook chỉ cấu hình, gọi pipeline và hiển thị kết quả.

**Môi trường dự kiến:** tiếp tục Python >= 3.11, pandas, matplotlib và psutil của repo. Bộ khung dùng dataclass stdlib và JSON/JSONL làm working format. Chưa cài hoặc chọn thêm parser LaTeX/BibTeX; người phụ trách thử trên bộ mẫu ở giai đoạn 1, ghi lựa chọn và khóa phiên bản nếu bổ sung dependency. Không cần GPU, LLM hoặc mô hình pretrained để thực hiện kế hoạch này.

## 1. Hiểu M2 trong một phút

| Milestone | Công việc dễ hiểu | Sản phẩm |
|---|---|---|
| M1 | Tải nguyên liệu về | Metadata, `.tex`, `.bib`, reference metadata và mọi version |
| **M2** | **Đọc nguyên liệu, chia thành từng phần, làm sạch và gộp trùng** | **`elements`, `hierarchy`, `bibtex` và thống kê** |
| M3 | Ghép BibTeX entries với reference arXiv đúng | Pipeline học máy, predictions, đánh giá và dataset cuối |

Ví dụ, một bài có v1/v2. Mỗi version gọi nhiều file `.tex`. M2 phải biết file nào thực sự được dùng, section nào chứa câu nào, công thức nào là một khối riêng và tài liệu nào bị đổi citation key giữa hai version.

```text
Corpus M1 đã khôi phục và kiểm tra
              |
       Liệt kê bài + mọi version
              |
       Tìm root và ghép đúng include
              |
       +------+----------------------+
       |                             |
  Parse cây nội dung          Đọc .bib / chuyển bibitem
       |                             |
       |                     Hợp nhất entries toàn bài
       |                             |
       +--------- Citation key map --+
       |
  Đổi key trong citation -> cleanup -> chuẩn hóa math
       |
  Khử trùng elements giữa versions, giữ quan hệ từng version
       |
  elements + hierarchy + bibtex + coverage + measurements
       |
  Kiểm tra chất lượng -> Colab CPU -> Jupyter Book -> nộp 2 link
```

## 2. Phân biệt yêu cầu của đề và cách nhóm tổ chức

**Bắt buộc theo đề:** mọi publication M1, mọi version, compilation path, cây phân cấp, quy tắc node lá, cleanup, chuẩn hóa math, chuyển `bibitem`, hai mức dedup, ba bảng đầu ra, thống kê, benchmark Colab CPU, code tái lập được và Jupyter Book.

**Lựa chọn tổ chức trong kế hoạch này:** chia bốn người như mục 4, đặt tên module/hàm, có bộ mẫu hồi quy, manifest M2, checkpoint theo publication, file dữ liệu trung gian và các cổng kiểm tra. Các lựa chọn này giúp làm đủ đề, không phải quy định bổ sung của giảng viên.

**Chưa làm trong M2:** gán nhãn, xây feature, train model, MRR@5, bảng `predictions`, poster và xuất bản dataset Hugging Face. M2 vẫn phải giữ dữ liệu đủ đúng schema để M3 xuất sharded Parquet; có thể thử round-trip Parquet local sớm, nhưng không phải nộp data ở M2.

Không có deadline M2 cụ thể trong phần đề đã đọc. Nhóm phải tự điền hạn Moodle thực tế; các giai đoạn bên dưới là thứ tự làm việc, không phải lịch của giảng viên.

## 3. Điểm xuất phát của repository

- Thư mục raw Drive hiện chốt là preparationM2/raw_m1/<DATASET_NAME>/; notebook cấu hình PREPARATION_DIR. Helper đọc lại output và ghi input_validation.json cùng snapshot_id. Adapter parser gọi validate_prepared_corpus, kiểm run/snapshot và giữ đầy đủ blocked; parser ghi output riêng vào Milestone2/parsed. Khánh/Danh ký input theo P0 trong [phân công](./PHAN_CONG_MILESTONE_2_4_NGUOI.md), không xem notebook hoàn tất là đã đủ source toàn nhóm.

- Bổ sung 27/10/2026: đã có notebook [chuẩn bị raw input](../../src/notebooks/milestone2_prepare.ipynb) và helper src/preparation/; xem [hướng dẫn](./HUONG_DAN_CHUAN_BI_INPUT.md). Bước này khôi phục source/receipts từ backup M1 thành schema m2-input-1.0, chưa triển khai parser. Adapter src/parsing/inputs.py phải nhận schema chuẩn bị này, kiểm completion/run_id và giữ trạng thái input ready_tex/empty_no_tex/blocked_input theo hướng dẫn; metadata/reference result nằm tại các path trong manifest.

- `src/crawling/` và `src/notebooks/milestone1.ipynb` đã có. M2 tái sử dụng dữ liệu và quy ước ID, không viết lại crawler.
- Cập nhật 28/10/2026: đã có package `src/parsing/`, notebook M2 và test templates dưới dạng prototype chưa triển khai. [contracts.py](../../src/parsing/contracts.py) và docstrings từng prototype chốt API/wire format; không xem scaffold là parser hoàn chỉnh.
- `arXiv-report/` là checkout báo cáo riêng, được `.gitignore` của repo code loại trừ. Có sẵn bốn trang M2 trong `book/content/milestone2/`; các trang phương pháp đang là khung chờ thực nghiệm, không chứng minh parser đã chạy.
- Corpus có thể nằm trong các checkpoint/full backup M1 trên Drive. **ZIP corpus dạng manifest-only stub của session report không đủ làm input M2.** Phải khôi phục source thật từ checkpoint/full corpus đã xác minh.
- Không kết luận nhóm đã đủ dữ liệu M1 chỉ từ việc source code tồn tại. Bước đầu phải kiểm kê đầy đủ corpus, phiên bản còn thiếu và backup sử dụng.

## 4. Sáu nhóm việc và người chịu trách nhiệm

| Nhóm | Làm gì? | Chủ trì | Kết quả |
|---|---|---|---|
| A. Đầu vào và nhiều file | Kiểm corpus, liệt kê versions, tìm root, theo include | **Khánh** | Input đáng tin và luồng LaTeX đúng thứ tự |
| B. Cây nội dung | Section, paragraph, itemize, câu, công thức, hình/bảng | **Khang** | Cây thô cho từng version |
| C. Tài liệu tham khảo | Đọc `.bib`, chuyển `bibitem`, gộp fields, thống nhất key | **Nguyên** | BibTeX toàn publication và bản đồ key |
| D. Chuẩn hóa và lưu chung | Cleanup, math, rewrite citation, dedup, xuất bảng | **Danh** | Ba bảng đúng schema, đủ liên kết |
| E. Chất lượng và hiệu năng | Test, kiểm tay, coverage, benchmark, backup | **Cả 4** | Bằng chứng toàn corpus, không chỉ demo |
| F. Báo cáo và nộp | Mỗi người viết phần mình; Danh tích hợp Book | **Cả 4** | Book thực nghiệm và hai link công khai |

Chi tiết task, đường dẫn, người review và tiêu chí nhận bàn giao nằm trong [file phân công](./PHAN_CONG_MILESTONE_2_4_NGUOI.md).

## 5. Nhóm A — Chọn đúng input và đúng file

### A1. Kiểm kê corpus M1

- [ ] Đọc `manifest.json`, danh sách `record.versions`, trạng thái download và receipts; không suy ra số versions chỉ từ thư mục đang có.
- [ ] Khi hợp nhất nhiều backup, xác minh nguồn rồi chọn snapshot nhất quán; cùng `(arxiv_id, version)` không đếm nhiều lần vì có nhiều checkpoint/retry.
- [ ] Đối chiếu danh sách publication M1 với danh sách thực sự được đưa vào M2, kể cả bài partial; thiếu source phải hiện trong coverage.
- [ ] Phân biệt `success` có TeX, `no_tex` có bằng chứng, và `failed`/pending/hỏng source. `failed` không được đổi thành version rỗng.
- [ ] Giữ base arXiv ID đúng dot/slash; version là số nguyên riêng. Dùng lại quy ước `paper_directory` M1 cho đường dẫn, không lấy tên folder làm ID gốc.

### A2. Xác định compilation path

- [ ] Tìm file `.tex` có `\documentclass` đang có hiệu lực, bỏ khai báo trong comment.
- [ ] Từ root, theo `\input`/`\include` bắc cầu và giữ đúng thứ tự xuất hiện; xử lý file không ghi đuôi `.tex` và đường dẫn tương đối theo quy tắc đã kiểm chứng trên mẫu.
- [ ] Không theo lệnh trong comment; phân biệt `%` mở comment với `\%` trong văn bản.
- [ ] Lưu nguồn file/offset cho các đoạn đã ghép để khi parse sai biết phải mở file nào.
- [ ] File không reachable không được góp nội dung. Include lặp lại vẫn phải giữ lần xuất hiện; chỉ dùng recursion stack để chặn vòng lặp, không dùng visited-set làm mất include hợp lệ.
- [ ] Không có root, nhiều root khả nghi, include thiếu hoặc include động chưa giải được: ghi diagnostic; chỉ chọn root khi có bằng chứng/quy tắc xác định được, không âm thầm đoán rồi báo success.

**Ví dụ đạt:** `main.tex` gọi `intro.tex`, file này gọi `notation.tex`; cả ba được xử lý. `old_draft.tex` không được gọi thì bị bỏ. `% \input{old_draft}` không làm thay đổi kết quả.

## 6. Nhóm B — Dựng cây và chia đơn vị nội dung

- [ ] Tạo document root cho từng version có TeX parse được.
- [ ] Nhận chapter/section/subsection/subsubsection và paragraph; dùng stack cấp cấu trúc, không mặc định bài nào cũng đủ mọi cấp.
- [ ] Giữ section có dấu `*`, đặc biệt Acknowledgements và Appendices; xử lý `\appendix` để không bỏ phần cuối bài.
- [ ] Chia đoạn văn thành sentence leaves. Inline math nằm trong sentence, không thành một câu hoặc block formula riêng.
- [ ] Bảo vệ math, command arguments, `i.e.`, `et al.`, `Fig. 1`, URL và số thập phân trước khi xác định dấu chấm kết thúc câu.
- [ ] Equation/display math là block-formula leaves; figure và table là figure leaves. Bảng giữ nội dung có ý nghĩa, hình giữ caption/thông tin nguồn có sẵn dù M1 không tải ảnh.
- [ ] `itemize` là component cha; mỗi `item` là component con có sentence/formula/figure bên dưới. Xử lý itemize lồng nhau.
- [ ] Không đưa bibliography vào cây; chuyển vùng đó cho nhánh reference extraction. Không xóa cả phần sau References nếu sau đó còn appendix hợp lệ.
- [ ] Giữ citation command và key thô cho bước đổi key sau; không xóa `\cite` khi làm cây.

**Ví dụ đạt:** câu `As in Fig. 1, we use $x=3.14$. It works.` tạo hai sentence leaves; `$x=3.14$` vẫn nằm trong câu đầu. Một `equation` sau đó là leaf riêng.

**Giới hạn phải công bố:** macro tùy biến, điều kiện LaTeX hoặc môi trường không hỗ trợ cần diagnostic có vị trí. Đề không đòi nhóm viết lại toàn bộ TeX engine; nhưng chỉ “ghi limitation” không thay thế việc sửa các lỗi làm mất nội dung trong corpus được giao.

## 7. Nhóm C — BibTeX, bibitem và đổi citation key

### C1. Trích entries

- [ ] Đọc các file `.bib` được bài sử dụng qua khai báo bibliography và các `\bibitem` thuộc compilation path của từng version.
- [ ] Xử lý braces, multiline, trường thiếu, nhãn tùy chọn của `bibitem`; trích title, authors, year, DOI, journal, URL khi có căn cứ.
- [ ] Giữ entry chưa phân tích đủ trong dữ liệu trung gian cùng raw text/diagnostic; không bỏ để làm đẹp tỷ lệ và không bịa fields.
- [ ] File `.bbl` không nằm trong whitelist M1. Nếu TeX chỉ dẫn tới `.bbl` không có và cũng không có `.bib`/`bibitem` thay thế, ghi thiếu bibliography; không coi đó là bài không có references.

### C2. Hợp nhất trong và giữa versions

- [ ] Gom entry cùng tài liệu bằng DOI được chuẩn hóa khi có; khi thiếu DOI, so bằng chứng title/author/year đã chuẩn hóa. Không gộp chỉ vì cùng citation key, cùng năm hoặc title gần giống.
- [ ] Chọn canonical key ổn định; giữ map **theo version** `(version, old_key) -> canonical_key`. Cùng key ở v1/v2 có thể chỉ hai tài liệu khác nhau.
- [ ] Nếu cùng một old key ngay trong cùng version bị dùng cho hai tài liệu khác nhau, ghi conflict cần kiểm và không coi rewrite đã giải được; một map đơn không thể tự biết citation đó muốn trỏ tài liệu nào.
- [ ] Union fields: v1 có year, v2 có DOI, v3 thiếu year thì kết quả vẫn giữ cả year lẫn DOI.
- [ ] Khi cùng field có giá trị mâu thuẫn: giữ evidence, ghi conflict; ưu tiên bản có DOI nhất quán, rồi thông tin đầy đủ hơn, rồi version sớm hơn làm tie-break ổn định. Nếu identity còn mơ hồ, giữ hai entries để kiểm thay vì gộp nhầm.
- [ ] Chuyển `author` của BibTeX sang `authors: list[str]` nhưng giữ nguyên cách viết tên có căn cứ; không tự mở rộng initials.
- [ ] Danh dùng map để đổi từng key trong `\cite{a,b}`, không thay chuỗi toàn văn. Keys trùng tên thường ở văn bản không được đổi nhầm. Biến thể citation gặp trong corpus được nhận diện và ghi rõ phạm vi hỗ trợ.

**Ví dụ đạt:** v1 dùng `refA` có title/author/year; v2 dùng `refB` cho cùng tài liệu và thêm DOI. Chỉ còn một entry đủ fields; cả `\cite{refA}` và `\cite{refB}` đều trỏ tới canonical key.

Không xóa entries non-arXiv: bảng `bibtex` là nguồn trích từ bài, khác bảng `references` M1 chỉ xuất pool có arXiv ID. Không yêu cầu gọi Semantic Scholar để match ở M2.

### C3. Quy tắc identity khi thiếu DOI

Nguyên triển khai, Danh review. Tách **xác định cùng tài liệu** khỏi **chọn giá trị field sau khi đã xác định identity**; chính sách ưu tiên fields ở C2 không được dùng để bỏ qua bằng chứng hai tài liệu khác nhau.

Chuẩn so sánh phải có phiên bản và chỉ phục vụ identity; output vẫn giữ giá trị có căn cứ từ source:

- DOI: bỏ prefix `doi:`/`https://doi.org/`, trim và thống nhất hoa/thường; giữ nguyên phần identifier, không xóa dấu bên trong tùy tiện.
- Title: giải mã wrapper/ký tự LaTeX đã hỗ trợ, Unicode NFC, casefold phần prose và gộp khoảng trắng; giữ từ, số, dấu có nghĩa và biểu thức toán. Không xóa subtitle hoặc coi title gần giống là bằng nhau.
- Authors: parse thành danh sách có thứ tự, chuẩn Unicode/case/khoảng trắng; giữ ranh giới tên, dấu có nghĩa và tác giả tổ chức. Không tự mở rộng initials; `et al.`/`others` đánh dấu danh sách chưa đầy đủ.
- Year: số nguyên đã trích có bằng chứng; thiếu là null. Không coi null bằng một năm bất kỳ.

| Bằng chứng giữa hai occurrences | Quyết định mặc định |
|---|---|
| Cả hai có DOI hợp lệ giống nhau, không có bằng chứng identity trái ngược | Gộp; mâu thuẫn metadata không làm đổi identity được ghi field conflict và xử lý theo C2 |
| Cả hai có DOI hợp lệ khác nhau | Giữ riêng dù key/title giống; nếu có lý do cho rằng DOI nhập sai thì chờ review, không tự sửa DOI |
| Ít nhất một bên thiếu DOI; title không rỗng trùng chuẩn hóa, toàn bộ danh sách authors đầy đủ trùng đúng thứ tự, year có ở cả hai và bằng nhau | Gộp nếu không tạo xung đột DOI trong cluster |
| Title/authors trùng nhưng một bên thiếu year, hoặc initials đối chiếu với tên đầy đủ, hoặc chỉ có tác giả đầu + `et al.` | Chưa tự gộp; giữ riêng và tạo candidate cần review |
| Title trùng nhưng authors/year đã biết mâu thuẫn, không có DOI chung làm bằng chứng mạnh hơn | Giữ riêng; nếu source cho thấy có thể là metadata sai thì chuyển review |
| Chỉ trùng citation key, chỉ giống title, hoặc title bị thiếu | Không đủ để gộp tự động; cần evidence bổ sung nếu đưa vào review |

Không dùng phép nối bắc cầu mù quáng: A có DOI X, B thiếu DOI, C có DOI Y khác X thì B không được làm cầu nối X với Y dù title/authors/year trùng. Kiểm toàn cluster trước mỗi lần merge; cluster chứa nhiều DOI khác nhau phải được tách hoặc review. Sắp candidate theo thứ tự ổn định; khi B phù hợp nhiều cluster đối nghịch thì giữ B riêng chờ review, không chọn cluster gặp trước.

Ví dụ nghiệm thu: title chỉ khác `\textbf{...}`/khoảng trắng, authors đầy đủ và year giống nhau thì gộp; cùng title/year nhưng tác giả khác thì giữ riêng; `A. Nguyen` với `An Nguyen` hoặc year null thì chờ review. Trong ví dụ ba versions của đề, v3 thiếu year vẫn gộp được nếu còn DOI chung; nếu v3 cũng thiếu DOI, giữ candidate và review evidence liên version thay vì suy identity chỉ từ key cũ.

Mỗi quyết định review lưu occurrence IDs/version, raw fields, quy tắc/bằng chứng, kết luận merge/keep-separate, reviewer và commit/input hash. Candidate đã được đưa vào review nhưng chưa giải quyết là `REFERENCE_IDENTITY_REVIEW` mức error theo mục 9.3. Hai entries có bằng chứng khác tài liệu được giữ riêng không phải lỗi. Field conflict đã có cách chọn ổn định và giữ đủ provenance có thể là warning; thiếu year/DOI tự thân không phải lỗi parser.

Quyết định review là input có thể chạy lại: cấu hình `reference_review_path` trỏ file JSON local ngoài Git chứa các quyết định đã duyệt; null nghĩa là chưa có quyết định ngoài. Chỉ áp dụng quyết định khớp occurrence IDs và source fingerprint; evidence cũ sau khi source đổi phải review lại. Pipeline truyền quyết định vào unify, lưu bản đã áp dụng trong output và đưa hash file review vào cache key cùng input/config/code revision. Không sửa tay bảng BibTeX cuối rồi bỏ qua validator.

## 8. Nhóm D — Chuẩn hóa và dedup nội dung

### D1. Chuẩn hóa không mất nghĩa

- [ ] Bỏ `\centering`, placement option như `[htpb]`, rule trình bày như `\midrule` đúng ngữ cảnh; giữ text bên trong wrapper như `\textbf{...}`.
- [ ] Chuẩn hóa khoảng trắng prose; không làm hỏng command arguments, nội dung verbatim hoặc cấu trúc math bằng thay thế regex toàn văn.
- [ ] Inline math về `$...$`; display math về quy ước block thống nhất `\begin{equation}...\end{equation}`. Với align nhiều dòng phải bảo toàn cấu trúc toán bên trong, không đổi tên môi trường một cách mù quáng.
- [ ] Thay citation keys trước khi chốt cleaned content và tính dedup key.
- [ ] Kiểm tính ổn định: chuẩn hóa một nội dung đã chuẩn hóa không làm nội dung tiếp tục biến đổi.

### D2. Dùng chung nội dung, giữ cấu trúc từng version

- [ ] Dedup trong phạm vi một publication theo nội dung đã cleanup; không dùng fuzzy/semantic similarity để gộp câu chỉ gần nghĩa.
- [ ] Leaf hoặc component cùng loại và có cleaned content giống nhau giữa versions dùng cùng ID. `kind` tham gia định danh để không nhập nhầm heading và sentence chỉ vì cùng chữ.
- [ ] Root là container version riêng như ví dụ đề; root mapping được giữ trong manifest M2. Không tạo parent giả cho root trong `hierarchy`.
- [ ] ID có prefix publication key; phần phân biệt ổn định dựa trên kind/content, có kiểm collision bằng chuỗi thật. Không đưa `v1` vào mọi ID khiến mất khả năng chia sẻ.
- [ ] Parent được remap sau dedup; một element có thể thuộc hai parent khác nhau ở hai versions.
- [ ] Lưu số lượng occurrences trước dedup và rows sau dedup để tính reduction.

Ví dụ:

| version | node | parent |
|---|---|---|
| 1 | `paper#sentence1` | `paper#introduction` |
| 2 | `paper#sentence1` | `paper#background` |

`sentence1` chỉ có một row trong `elements`; hai quan hệ vẫn tồn tại trong `hierarchy`.

**Không đánh mất thứ tự/lần xuất hiện:** schema cuối không có `position` hay `occurrence_id`. Working format phải giữ occurrence tree và thứ tự riêng để kiểm cây ban đầu và bàn giao M3; không tự thêm cột vào schema xuất cuối. Nếu cùng nội dung lặp trong một version làm các cạnh thu gọn không thể diễn tả đầy đủ từng occurrence, công bố giới hạn của projection này và giữ sidecar để khôi phục. Không coi chỉ đọc ba bảng là khôi phục được mọi thứ tự gốc.

### D3. Content của node cha và đầu vào sinh ID

Khang giữ đủ cấu trúc/content thô; Danh tạo content chuẩn sau rewrite citation và cleanup, **từ con lên cha trước khi dedup**. Chuẩn `component_content_v1` sau đây thuộc `normalization_version`; đổi quy tắc phải đổi phiên bản và invalidate cache.

| Kind | `content` sau chuẩn hóa |
|---|---|
| `sentence`, `block_formula`, `figure` | Nội dung ngữ nghĩa của leaf; giữ dấu kết câu có trong source, math/citation đã chuẩn hóa; figure/table giữ caption và nội dung có sẵn |
| `heading` | Chỉ tiêu đề đã cleanup; không ghép toàn bộ subtree. Cấp section/subsection và vị trí nằm ở occurrence sidecar |
| `paragraph` | Nội dung các con theo thứ tự: nối hai sentence liền nhau bằng một space; khi có block formula/figure/list thì giữ ranh giới bằng một newline |
| `item` | Toàn bộ nội dung bên trong item, kể cả list lồng; áp dụng quy tắc nối sentence/block như paragraph, hai paragraph kề nhau cách một dòng trống |
| `itemize` | Biểu diễn LaTeX chuẩn `\begin{itemize}`, mỗi item thành `\item {<content của item>}` trên dòng riêng, rồi `\end{itemize}`; list lồng giữ nguyên wrapper và ranh giới item |
| `document` | Nhãn ổn định `Version N root`; ID/root mapping riêng theo version như ví dụ đề, không đưa root vào dedup theo content thông thường |

Quy tắc nối chỉ áp dụng giữa các child fragments, không thay whitespace bên trong math/verbatim. Không nhét ID con, citation key cũ, path, offset hoặc số version vào content của component dùng chung. Không dùng chuỗi rỗng mặc định cho paragraph/item có descendants mang nội dung. Component thật sự rỗng không có nghĩa được bỏ khỏi cây ngữ nghĩa nhưng vẫn ghi source span/diagnostic; heading thiếu tiêu đề có body được giữ và báo review, không tự bỏ body.

Ví dụ dưới đây dùng `\n` để viết gọn ký tự xuống dòng thật; IDs là tên minh họa cho kết quả so sánh, không phải hash phải hardcode:

| Input sau cleanup | Kind/content để dedup | ID kỳ vọng |
|---|---|---|
| v1 có paragraph `We study X. It works.` | `paragraph` / `We study X. It works.` | `paper#pA` |
| v2 cùng paragraph, chỉ khác wrapper/khoảng trắng gốc | Cùng kind và content với v1 | Cũng `paper#pA` |
| v2 có paragraph `We study Y. It works.` | `paragraph` / `We study Y. It works.` | ID khác `paper#pA`; sentence `It works.` vẫn có thể dùng chung |
| List gồm item `Alpha.` rồi `Beta.` | `itemize` / `\begin{itemize}\n\item {Alpha.}\n\item {Beta.}\n\end{itemize}` | ID khác list có hai item theo thứ tự ngược lại |
| Hai heading `Introduction` có body khác nhau | `heading` / `Introduction` | Dùng chung heading ID; các edges và occurrence tree vẫn giữ body của từng occurrence/version |

Fingerprint nhận bộ `(kind, content)` đã chuẩn hóa trong phạm vi publication; dùng serialization có ranh giới tường minh như JSON array UTF-8 để tránh va chạm do nối chuỗi. Hash chỉ rút gọn ID, phải kiểm lại kind/content thật khi trùng hash. Không đưa toàn subtree vào fingerprint của heading nhưng lại ghi title-only trong bảng. Counts toàn bộ elements có chứa text lặp giữa cha và con; thống kê lượng prose riêng chỉ đếm sentence occurrences, tránh cộng lặp content của cha.

## 9. Hợp đồng đầu ra và kiểm tra dữ liệu

### 9.1. Ba bảng theo đề

| Bảng | Cột và kiểu |
|---|---|
| `elements` | `element_id: string non-null`, `arxiv_id: string non-null`, `kind: dictionary<string>`, `content: string` |
| `hierarchy` | `arxiv_id: string non-null`, `version: int`, `element_id: string non-null`, `parent_id: string non-null` |
| `bibtex` | `arxiv_id: string non-null`, `citation_key: string non-null`, `entry_type: dictionary<string>`, `title: string`, `authors: list<string>`, `year: int nullable`, `doi: string`, `journal: string`, `url: string` |

Working files có thể là JSONL/JSON; khi xuất Parquet M3 phải khai báo schema tường minh, dictionary encoding cho cột phân loại, không serialize list authors thành một chuỗi JSON. Các fields không có thông tin được giữ thiếu đúng kiểu, không gán năm 0.

### 9.2. Working data đề xuất — không commit corpus vào code repo

```text
data/milestone2/<run_id>/
├── manifest.json                 # phạm vi, source fingerprints, root/version/status
├── papers/<paper_key>/
│   ├── elements.jsonl
│   ├── hierarchy.jsonl
│   ├── bibtex.jsonl
│   ├── occurrences.jsonl         # thứ tự/lần xuất hiện và vị trí source
│   ├── citation_key_map.json     # map theo version
│   ├── identity_decisions.json   # evidence tự động/review đã áp dụng, occurrence IDs
│   └── diagnostics.jsonl         # lỗi, fields conflicts, unresolved citation
└── metrics/
    ├── versions.csv
    ├── publications.csv
    ├── dedup.csv
    ├── resource_samples.csv
    └── run_summary.json
```

Mỗi `(publication, version)` có một trạng thái vận hành: `parsed`, `empty_no_tex`, `partial`, `failed`, `blocked_input`. Đây là lựa chọn nội bộ, không phải cột mới của dataset cuối. `empty_no_tex` chỉ khi có bằng chứng M1; không tạo fake element để biểu diễn empty.

- [ ] Không có duplicate `element_id`; `(arxiv_id, citation_key)` duy nhất trong BibTeX hợp nhất.
- [ ] Mọi `element_id`/`parent_id` của hierarchy tồn tại và cùng publication; version thuộc danh sách M1.
- [ ] Occurrence tree trước projection không cycle, mỗi occurrence ngoài root có đúng một parent, không có phần nội dung bị rơi ngoài root mà không được giải thích.
- [ ] Citation sau rewrite trỏ key tồn tại; thiếu entry được ghi unresolved và ảnh hưởng trạng thái chất lượng, không âm thầm bỏ citation.
- [ ] Output của empty version không có elements/hierarchy do version đó đóng góp; version vẫn có manifest row.
- [ ] Chạy lại cùng input/config/code tạo cùng IDs và nội dung; resume không nhân đôi rows.
- [ ] Giữ root mapping, source provenance và counts đủ để M3 dựng tables mà không parse lại.

### 9.3. Trạng thái chất lượng và chế độ strict

Status version là kết quả **sau cả gathering, hierarchy, bibliography, normalize/dedup và validation**, không chỉ là parser không ném exception. `parsed` nghĩa là xử lý trọn vẹn phần source có sẵn theo các quy tắc đã hỗ trợ; không khẳng định metadata vốn thiếu trong bài đã trở nên đầy đủ. Trạng thái ở bước hierarchy chỉ là tạm thời; metrics/checkpoint dùng status cuối sau validate. Mỗi version chỉ nhận một status cuối theo bảng dưới, theo thứ tự xét từ trên xuống:

| Điều kiện | Status | Diagnostic/evidence tối thiểu |
|---|---|---|
| M1 có receipt `no_tex` đã xác minh | `empty_no_tex` | Receipt/source fingerprint, không có node giả |
| TeX input của version chưa có hoặc receipt/hash không hợp lệ, chưa thể parse đáng tin | `blocked_input` | `SOURCE_MISSING`/`SOURCE_INTEGRITY`, mức error; không suy từ thư mục trống |
| Có input hợp lệ nhưng không xác định được root, parse không tạo được cây body đáng tin, hoặc schema/occurrence-tree integrity hỏng | `failed` | `ROOT_UNRESOLVED`/`PARSE_FATAL`/`INVALID_STRUCTURE`, mức error; giữ raw/evidence để sửa |
| Có cây body hợp lệ dùng được nhưng còn error: include thiếu, macro làm mất/không hiểu nội dung, bibliography được gọi bị thiếu, entry hỏng chưa xử lý, citation/key conflict hoặc identity đang chờ review | `partial` | `INCLUDE_MISSING`/`UNSUPPORTED_CONTENT`/`BIBLIOGRAPHY_MISSING`/`BIB_ENTRY_UNPARSED`/`CITATION_UNRESOLVED`/`KEY_CONFLICT`/`REFERENCE_IDENTITY_REVIEW`, vị trí và affected versions |
| Cây hợp lệ, xử lý đủ compilation path/bibliography có khai báo, không còn error sau validation | `parsed` | Có thể còn warning nhưng không có mất nội dung hoặc identity đang chờ giải quyết |

Warning hợp lệ gồm field vốn thiếu trong source, khác cách trình bày đã normalize được, hoặc field conflict đã có identity chắc chắn, cách chọn rõ và provenance đầy đủ. Không hạ error thành warning chỉ để tăng success rate. Citation unresolved thật luôn là error; bài thật sự không khai báo bibliography và không có citation không bị gán `BIBLIOGRAPHY_MISSING`. Include thiếu chỉ thành `partial` khi còn cây body hợp lệ, nếu không thì `failed`.

Lỗi bibliography hợp nhất phải gắn lại các versions chứa occurrences/citations bị ảnh hưởng rồi tính lại status. Lỗi schema/structure chung không định vị được version phải chặn cả publication, đánh `failed` cho mọi version có TeX đã góp vào output đó và ghi phạm vi trong audit; không đổi receipt `empty_no_tex` thành lỗi parse. `error`/`warning` cùng mã diagnostic được dùng thống nhất bởi mọi module.

`ParseConfig.strict` mặc định **True**, điều khiển việc chấp nhận output chứ không đổi cách tính status:

- `strict=True`: publication chỉ được publish vào bộ ba bảng đã nghiệm thu khi mọi expected version thuộc `parsed`/`empty_no_tex`, không còn error cấp publication và validation đạt. Nếu chưa đạt, giữ working output/audit để sửa, đặt `export_ready=False`; không thay output tốt của lần trước bằng dữ liệu mới chưa đạt và không dùng output cũ như kết quả của input mới.
- `strict=False`: cho phép ghi ba bảng **working partial** từ phần có cấu trúc hợp lệ, kèm status/diagnostics và `export_ready=False` khi còn lỗi. Không ghi rows vi phạm schema/foreign keys để dùng downstream. Chế độ này phục vụ debug/pilot; không biến partial thành dữ liệu đã nghiệm thu cho M3.
- Cả hai chế độ đều tiếp tục các publication độc lập sau lỗi đã được ghi nhận; không bỏ version khỏi inventory. Lỗi toàn run khiến không thể đọc input/ghi audit phải báo fatal và dừng rõ ràng. Publication toàn `empty_no_tex` hợp lệ có ba bảng rỗng và có thể `export_ready=True`.

`ParseRunResult.status=success` chỉ khi mọi publication expected đều `export_ready=True` và output/audit đã ghi thành công; `partial` nếu còn lỗi nhưng giữ được ít nhất một version `parsed`/`partial`/`empty_no_tex` với audit đọc lại được; còn lại là `failed`. Ghi output thất bại là run/publication error `OUTPUT_WRITE_FAILED`, không sửa status parse để che lỗi lưu trữ. Metrics success chỉ đếm `parsed`; công bố riêng bảng lỗi bibliography/citation để giải thích vì sao cây body có thể hợp lệ nhưng version vẫn partial.

## 10. Thống kê, hiệu năng và Jupyter Book

### 10.1. Tỷ lệ phải có mẫu số

Đặt `N_expected` là số version theo metadata M1; phân hoạch mỗi version vào đúng một trạng thái ở mục 9.2. Công bố số đếm từng trạng thái và kiểm tổng bằng `N_expected`.

- `parse_success_rate = N_parsed / (N_parsed + N_partial + N_failed)`: thành công toàn pipeline M2 trong các version có input đã được đem parse theo mục 9.3, gồm kiểm bibliography/citation; mẫu số 0 thì để null/không áp dụng. Nếu báo riêng body-tree success phải đặt tên khác và nêu định nghĩa.
- `resolved_version_coverage = (N_parsed + N_empty_no_tex) / N_expected`: xem empty hợp lệ là đã xét, nhưng không gọi đó là parse thành công.
- `attempt_coverage = (N_parsed + N_partial + N_failed) / (N_expected - N_empty_no_tex)`: cho thấy phần chưa có input/blocked không bị giấu khỏi báo cáo.
- Bảng coverage từng publication phải có mọi version, status, lý do lỗi và nguồn input; không chỉ có tỷ lệ gộp toàn nhóm.
- `dedup_reduction = 1 - rows_after / occurrences_before`, tách theo kind và references; mẫu số 0 thì null. Định nghĩa rõ entries-before là tổng entry occurrences qua các versions, không phải unique keys.

Các công thức này là quy ước báo cáo của nhóm, phải ghi lại trong Book. Chưa đo thì không tự điền 0 hoặc số minh họa vào bảng kết quả thật.

### 10.2. Benchmark chính thức

- [ ] Chạy Google Colab với accelerator **None**, ghi Python/packages, CPU/RAM, commit, config và snapshot input.
- [ ] Chạy full parsing với output mới, không dùng parsed cache làm kết quả parse mới. Thử resume đo riêng.
- [ ] Đo wall time từ trước đọc/xác minh input M1 đã khôi phục tới sau ghi output, kiểm tra và flush checkpoint trong pipeline. Ghi rõ khôi phục ZIP/setup environment và xuất bản Book ngoài khoảng đo; nếu đo kèm thì báo riêng phần đó.
- [ ] Xuất tổng wall time, thời gian từng publication, mean theo số publication thực xử lý; ghi riêng số publications blocked. Không lấy tổng task times thay wall time.
- [ ] Đo peak RAM process tree bằng psutil với chu kỳ công bố; peak lấy mẫu là observed peak. Đo final output bytes và theo dõi disk còn đủ cho input/output/temp.
- [ ] Giữ raw samples và benchmark receipts; nếu phải chia phiên Colab, công bố phạm vi và số đo từng run, không trình bày tổng các lượt retry như một benchmark liền mạch.

Không có mức giới hạn thời gian chạy của đề; disk bị giới hạn bởi Colab. Không bắt buộc cold network crawl M1 lại trong benchmark parser M2.

### 10.3. Book có sẵn — bổ sung, không tạo Book mới

| Trang trong repo báo cáo | Phần cần hoàn thiện | Người viết |
|---|---|---|
| `book/content/milestone2/01_overview.md` | Phạm vi thực tế, pipeline, đầu vào/đầu ra, links | Khánh + Danh |
| `book/content/milestone2/02_parsing.md` | Compilation path, hierarchy, sentence splitting, ví dụ và giới hạn | Khánh + Khang |
| `book/content/milestone2/03_standardization.md` | Cleanup/math, reference union/key rename, content dedup | Nguyên + Danh |
| `book/content/milestone2/04_m2_stats.ipynb` | Coverage từng bài, counts/dedup, runtime/RAM/storage từ dữ liệu thật | Cả 4; Danh tích hợp |

- [ ] Mở rộng `arXiv-report/scripts/sync_data.py` hoặc thêm script M2 riêng trong report repo để nhận các metrics đã xác minh, không phá luồng M1.
- [ ] Bảng/hình phải tính và render khi build Book; input snapshot có run ID/hash, không dán screenshot hoặc hardcode kết quả.
- [ ] Sửa các ví dụ khung sai: inline math ở trong sentence, không phải leaf độc lập; nhiều candidate root không mặc nhiên unambiguous.
- [ ] Xóa lời hứa/placeholder chưa được thực hiện; trình bày limitations thật và nguồn tham khảo thực sự đã dùng. Mỗi người cung cấp attribution nếu copy/adapt code ngoài.
- [ ] Build sạch, notebook execute được, GitHub Pages public và hai link nộp mở được khi không đăng nhập.

### 10.4. Deliverables tương tác trên Book

Đề chấm interactivity; nhóm chọn hai deliverables dưới đây để kiểm được. Danh tích hợp tại `04_m2_stats.ipynb`, Khánh kiểm coverage, Khang/Nguyên review số liệu tương ứng. Dùng Plotly đã có trong hướng báo cáo hiện tại và HTML/JavaScript phía trình duyệt khi cần; khai báo/khóa dependency thực tế trong **repo báo cáo**, không thêm dependency chỉ phục vụ Book vào parser nếu parser không dùng.

| Deliverable | Hành vi cần có | Dữ liệu và kiểm đối chiếu |
|---|---|---|
| Bảng coverage publication/version có bộ lọc | Tìm theo arXiv ID và lọc status; hiển thị version, lý do lỗi, shard/run ID; có tổng số dòng sau lọc và thao tác reset | Lấy từ inventory/status thật, bao gồm empty/blocked/failed; Khánh đối chiếu ít nhất một publication nhiều versions và một ca lỗi nếu có |
| Biểu đồ thời gian theo publication | Hover thấy arXiv ID, run ID, số versions, wall time/đơn vị và status; zoom/reset; lọc theo shard/run bằng dropdown hoặc legend | Lấy per-publication measurements thật; Danh đối chiếu điểm hover với metrics gốc; blocked chưa đo không được vẽ time=0 |

Mọi bảng/điểm dữ liệu và mã tương tác được sinh từ snapshot khi build; trang HTML đã xuất phải hoạt động khi không có Python kernel/Colab session đang chạy và không cần quyền truy cập Drive. Ghi run ID/input hash, phạm vi benchmark, units và mẫu số gần hình/bảng. Không trộn measurements các run khác môi trường thành một benchmark chung.

**Nghiệm thu:** build sạch thực sự execute notebook; mở trang HTML build và URL GitHub Pages ngoài đăng nhập; thử tìm một ID, lọc status có dữ liệu, lọc ra rỗng/reset, hover/zoom/reset và chọn run/shard nếu snapshot có nhiều nhóm. Tất cả thao tác phải cập nhật đúng và không lỗi tải JavaScript. Lưu build log + checklist thao tác/kết quả + URL/commit; ảnh/video chỉ là evidence kiểm UI, không thay hình/bảng sinh lúc build. Nếu corpus không có ca lỗi hoặc chỉ có một run, ghi rõ ca không áp dụng và kiểm hành vi tương ứng bằng fixture riêng, không chèn số liệu giả vào Book kết quả.

## 11. Thứ tự triển khai và các cổng kiểm tra

| Giai đoạn | Việc chính | Có thể làm đồng thời | Chỉ chuyển bước khi |
|---|---|---|---|
| 0. Chốt input/hợp đồng | Khôi phục nguồn thật, chọn bộ mẫu, ký tên contracts | Cả 4 đọc đề và thống nhất schema | Biết đủ bài/version và không nhầm stub với corpus |
| 1. Bản tối thiểu | Khánh ghép file; Khang parse; Nguyên đọc entries; Danh validator/normalizer | Mỗi người dùng fixture cùng contract | Một bài có nhiều file và >= 2 versions đi hết pipeline |
| 2. Hoàn thiện quy tắc | Sentence, math, itemize, bibliography, key maps, dedup | B/K và C có thể tiến song song | Bộ test đặc thù trong file phân công đạt |
| 3. Kiểm thật | Chạy pilot đa dạng, review chéo với TeX/PDF, sửa lỗi | Mỗi người kiểm nhóm ca mình | Không còn lỗi mất nội dung/gộp nhầm chưa giải thích trên bộ kiểm |
| 4. Toàn corpus | Chia shard publication, checkpoint, tổng hợp, retry phần lỗi | 4 người chạy shard khác nhau | Mọi version có status; lỗi/missing đã xử lý hoặc công bố rõ |
| 5. Benchmark/báo cáo | Colab CPU, sinh metrics, build/publish Book | Mỗi người viết phần mình | Checklist nghiệm thu cuối đủ bằng chứng |

Mỗi người vẫn sở hữu module chuyên môn, nhưng khi chạy toàn corpus có thể giữ phạm vi bài M1 của mình. Bốn người dùng cùng commit/config; không chia các versions của một publication sang hai shard rồi dedup độc lập. M2 xử lý offline có thể chạy các shard độc lập; sửa dữ liệu crawl M1 là luồng riêng và vẫn theo policy M1.

Không ghi “hoàn thành M2” chỉ vì có demo hoặc tổng số rows lớn. Nếu còn input thiếu/lỗi ảnh hưởng yêu cầu, phải ghi unresolved và tình trạng thực tế; không tự coi diagnostic là đã hoàn thành yêu cầu.

## 12. Checklist nghiệm thu milestone 2

- [ ] Có đối chiếu toàn bộ publication M1 và mọi version, không chỉ một mẫu.
- [ ] Root/compilation path chính xác; comments và file thừa không đi vào nội dung.
- [ ] Cây có cấp hợp lý; leaf là sentence/block formula/figure, table theo figure.
- [ ] Itemize có phân cấp; không tách sai math/commands/abbreviations/URL/decimal.
- [ ] Giữ Acknowledgements/Appendices; bibliography nằm ở nhánh BibTeX riêng.
- [ ] Cleanup giữ ý nghĩa, math thống nhất, normalize ổn định.
- [ ] `.bib`/`bibitem` được xử lý; fields không biết không bị bịa.
- [ ] References dedup trong/giữa versions, union fields và cite key rewrite đúng.
- [ ] Content exact dedup sau cleanup; dùng chung element và giữ edges theo version.
- [ ] Content của paragraph/item/itemize theo D3; đổi nội dung/thứ tự làm đổi ID đúng, không gộp mọi container rỗng.
- [ ] Ba bảng đúng schema; local occurrence/order/root/source mapping đủ để bàn giao M3.
- [ ] Version no_tex được ghi empty, thiếu/hỏng input không bị báo empty/success.
- [ ] Status/diagnostics/strict/export_ready theo mục 9.3; không nghiệm thu publication còn error.
- [ ] Identity thiếu DOI theo C3, không merge bắc cầu qua DOI đối nghịch; review có bằng chứng.
- [ ] Test, kiểm tay và review chéo có bằng chứng; unresolved không bị che.
- [ ] Đủ coverage từng publication và counts trước/sau dedup, mẫu số rõ.
- [ ] Benchmark Colab CPU có wall/mean/peak RAM/final output bytes và raw evidence.
- [ ] Code cùng public repo M1, docstrings/comments/citations, requirements và README chạy lại được.
- [ ] Book M1 được mở rộng M2 ở repo riêng; figures/tables thực sự sinh khi build.
- [ ] Bảng coverage lọc/tìm kiếm và biểu đồ hover/zoom hoạt động trên Pages theo mục 10.4.
- [ ] Corpus/output/metrics có backup đọc lại được và sẵn sàng cho M3; không nộp data M2.
- [ ] Hai link public code + Book đã kiểm và được nhóm nộp Moodle trước hạn thực tế.

## 13. Tóm tắt dễ nhớ

**Khánh đọc đúng file. Khang chia đúng cây. Nguyên gom đúng references. Danh làm sạch, dùng chung nội dung và nối pipeline. Cả bốn kiểm dữ liệu, chạy corpus, viết phần báo cáo và kiểm tra bàn giao.**

Làm đủ các mục nghiệm thu, có bằng chứng trên toàn phạm vi và hoàn tất hai link nộp thì mới xem M2 hoàn thành. Chỉ có code, chỉ có ba bảng hoặc chỉ có trang Book khung đều chưa đủ.

## 14. Nguồn và phạm vi tài liệu

1. Đề tổng lưu trong repo: [ARXIV_PROJECT_FULL.md — Milestone 2](../../ARXIV_PROJECT_FULL.md#milestone-parsing). Đây là căn cứ yêu cầu trong lần lập kế hoạch; không thực hiện đối chiếu website mới trong lần này.
2. Các phần Logistics/Regulations và M3 trong [đề tổng](../../ARXIV_PROJECT_FULL.md): một code repo, một Book riêng, quy định trích dẫn, không nộp data trung gian và schema cuối.
3. [Kế hoạch M1](../milestone1/KE_HOACH_MILESTONE_1.md), [phân công M1](../milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md), [hướng dẫn notebook M1](../milestone1/HUONG_DAN_SU_DUNG_NOTEBOOK.md): tên thành viên và nguồn corpus/backup.
4. Source M1 đã đọc để đặt hợp đồng tương thích: `src/crawling/__init__.py`, `pipeline.py`, `download.py`, `reports.py`; môi trường: `src/requirements.txt`, README và `.gitignore` hiện tại.
5. Khung báo cáo local `arXiv-report/book/content/milestone2/` và README của checkout báo cáo. Đường dẫn này thuộc repo báo cáo riêng, không được nhầm là source đã track trong repo code.

Chưa có kết quả benchmark hoặc tỷ lệ parse M2 được xác nhận bởi tài liệu này. Khi triển khai, cập nhật quyết định/thư viện/nguồn và bằng chứng tại chỗ, giữ ranh giới rõ giữa kế hoạch với kết quả thực tế.
