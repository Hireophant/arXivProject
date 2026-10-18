# Cách chạy Milestone 1 hiện tại: OAI-PMH arXivRaw

Đối chiếu ngày **17/10/2026** với [đề M1](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/), [hướng dẫn OAI chính thức](https://info.arxiv.org/help/oa/index.html) và [quy định truy cập arXiv](https://info.arxiv.org/help/api/tou.html).

## Phương án đã triển khai

Metadata của bài được giao, lịch sử versions và ngày gửi references đều lấy từ **một nguồn OAI-PMH `arXivRaw`**. Code không còn Query API, Atom, HTML metadata fallback hay Kaggle discovery.

```text
GET https://oaipmh.arxiv.org/oai
    ?verb=GetRecord
    &metadataPrefix=arXivRaw
    &identifier=oai:arXiv.org:2606.15734
```

Endpoint này thay địa chỉ `export.arxiv.org/oai2` từ tháng 3/2025. Ví dụ `ListRecords`/Sickle với prefix `arXiv` trong đề minh họa harvesting; `arXivRaw` phù hợp yêu cầu lấy lịch sử phiên bản. Project gọi `GetRecord` theo từng ID được giao, không cần harvest toàn repository hay xử lý resumption token hết hạn hằng ngày.

**Không dùng OAI header `datestamp` làm ngày gửi.** Nó là ngày metadata thay đổi. Code lấy ngày từ version `v1`; `revised_dates` lấy từ v2..vN. Lọc OAI bằng `from`/`until` cũng lọc ngày metadata thay đổi, nên không dùng cách đó để chọn toàn bộ bài gửi trong tháng được giao.

Parser kiểm ID ở header và raw metadata, title/authors, đủ phiên bản liên tục từ v1, ngày hợp lệ và đúng thứ tự. Tác giả được tách từ chuỗi raw, giữ nhóm trong ngoặc và hậu tố tên; nguyên văn XML vẫn lưu để kiểm tay các trường hợp tên phức tạp.

## Nhịp request và xử lý lỗi

- Tối thiểu **3 giây** mỗi request arXiv; notebook mặc định **3,1 giây**, kể cả retries. Mỗi tiến trình chạy tuần tự, một kết nối/request tại một thời điểm.
- Giới hạn áp dụng tổng các máy nhóm kiểm soát. Không chạy bốn notebook đồng thời để tăng tốc; cần xếp lịch hoặc điều phối chung nếu dùng nhiều máy.
- Lỗi tạm thời/429/503 được retry có giới hạn và tôn trọng `Retry-After`. Hết lượt retry thì ghi failed/partial, không chuyển sang nguồn metadata khác.
- Chỉ OAI `idDoesNotExist` hoặc record deleted được coi là không tìm thấy. HTTP 404/lỗi truy cập chưa chứng minh bài không tồn tại.

Tải source vẫn dùng `https://export.arxiv.org/src/{id}vN`, và lấy references vẫn dùng Semantic Scholar như đề yêu cầu. Đây là hai công việc riêng; metadata/ngày gửi arXiv của references vẫn tra bằng cùng OAI client. Chỉ tải source bài trong phạm vi được giao.

## Checkpoint, cache và báo cáo

Mỗi ID tra thành công được lưu ngay thành XML + receipt SHA-256 trong `<root>/metadata_cache/`. Discovery và lookup references dùng chung cache bộ nhớ/ổ đĩa, nên ID trùng không cần gọi lại. Cache metadata và references có tuổi tối đa 24 giờ; tuổi gốc không được gia hạn chỉ vì đọc cache. Cache hỏng, quá hạn hoặc thiếu thông tin nguồn phải làm mới. Lỗi không bị cache vĩnh viễn.

Manifest/receipts hiện tại là **schema 3.0**, có nguồn OAI rõ ràng. Bắt đầu corpus mới bằng root mới; không dùng manifest schema cũ. Khi ngắt giữa discovery, chạy `resume` cùng scope sẽ dùng các checkpoint hợp lệ đã lưu. Notebook xuất `metadata_stats.json` để phân biệt network requests, disk cache và memory cache; audit đối chiếu XML/hash/ID/ngày v1 bên cạnh source và cả hai reference stores.

`analyze` kiểm tính toàn vẹn của snapshot đã lưu mà không gọi mạng; việc đó không khẳng định snapshot còn mới trong 24 giờ. `resume` mới áp dụng thời hạn cache để thu thập tiếp.

Giữ `.tex`/`.bib` nguyên byte cho từng version; version không có TeX ghi `no_tex`. Giữ mọi reference ở `references_all.json`; `references.json` chỉ chứa pool arXiv duy nhất phục vụ matching. Không thay ngày gửi bằng `publicationDate`.

## Cấu hình và kiểm chứng

Notebook chính: [milestone1.ipynb](../../src/notebooks/milestone1.ipynb). Danh có phạm vi `2606.15734`–`2606.20733` (5.000 ID); preset trial là 100 ID đến `2606.15833`. Ba người còn lại điền phạm vi được giao thật. Đọc [hướng dẫn chạy](./CHAY_VA_KIEM_TRA_WINDOWS.md) để chọn cold/resume/analyze và sao lưu corpus/report bundle.

Trước đợt dọn cuối: **27 tests đạt**, notebook offline và integration chạy đạt bằng hai kernel mới. Sau đó toàn bộ tests/data/output và environment kiểm thử local đã xóa theo yêu cầu; số liệu lịch sử vẫn được giữ trong kế hoạch. Lần chạy Colab tiếp theo cần có corpus/audit mới riêng.

OAI không đảm bảo nhanh hơn cho phạm vi nhỏ: một request cho mỗi ID metadata duy nhất, gồm cả references. Lượt đầu một bài có 45 arXiv references cần 46 OAI requests và khoảng ba phút; chạy tiếp dùng cache sẽ ít request hơn. Đây là kiểm thử local một bài, chưa phải crawl đủ corpus hay benchmark Colab CPU.


## Đối chiếu yêu cầu Milestone 1

| Yêu cầu trong đề | Code/đầu ra hiện tại |
|---|---|
| Đúng scope TA giao, lấy cả hai đầu, mọi version kể cả v1 | Scope được xác minh trước chạy; OAI kiểm ID/header và đủ v1..vN; pipeline tải từng version |
| Metadata: ID/title/authors/ngày gửi/ngày revisions/venue | `metadata.json`, record trong manifest; ngày v1 và revision history từ raw XML |
| Chỉ `.tex`/`.bib`, giữ nguyên lệnh hình/bảng | `download.py` whitelist, xác minh bytes/inventory; không giữ ảnh, sty, cls, bbl |
| Version không có TeX vẫn có record | Trạng thái `no_tex`, thư mục rỗng và receipt |
| References mỗi publication qua S2, giữ mọi hàng local | Phân trang `/references`, flat fields `title,authors,externalIds,publicationDate,year,venue`; `references_all.json` giữ cả non-arXiv/null citedPaper |
| Pool matching chỉ arXiv, giữ IDs cũ, ngày gửi từ v1 | `references.json` riêng; IDs legacy không bị mất; lookup dùng cùng OAI client |
| Có retry/nhịp nghỉ, dữ liệu không bị mất khi chạy lại | Tuần tự 3,1 giây, Retry-After, per-ID XML checkpoint, receipts/hashes/nguồn, TTL 24 giờ; partial retry giữ complete store cũ |
| Statistics: papers, success, source bytes trước/sau, references/completeness | `metrics.py`, CSV và corpus figures; counts/mẫu số/quality warnings riêng cho non-arXiv |
| Discovery time, từng paper/mean, wall time end-to-end | Run summary và benchmark; discovery nằm trong thời gian hệ thống |
| RAM peak/mean, disk peak/final của hệ thống | Process-tree sampler, timestamped samples, tần suất và lỗi đo được xuất; peak là giá trị quan sát theo chu kỳ lấy mẫu |
| Audit/README/dependencies tái lập được | Notebook audits raw XML/metadata/source/hai reference stores; README và requirements pinned trực tiếp; environment được ghi trong report |
| M1 định nghĩa `papers`, `references`, chưa nộp corpus | Local JSON/CSV là trung gian; M3 mới xuất Parquet; giữ source local cho M2 |
| Benchmark cuối Colab CPU, public code và Book riêng | Notebook có guard và thông tin điều kiện; nghiệm thu cuối phải chạy thật trên Colab và xuất bản Book riêng |

Schema cuối do M1 định nghĩa:

- `papers`: `arxiv_id` non-null, `title`, `authors`, `submission_date`, `revised_dates`, `venue` nullable.
- `references`: `arxiv_id` non-null (bài trích dẫn), `ref_arxiv_id` non-null, `ref_title`, `ref_authors`, `ref_submission_date`, `ref_s2_id`.

Local arXiv reference store dùng key dấu gạch ngang cho ID hiện đại; CSV trả ID dấu chấm. Store matching được dedup theo arXiv ID; store đầy đủ giữ mọi hàng API, kể cả trùng. S2 references là snapshot theo publication, dịch vụ không bảo đảm danh sách riêng cho từng revision; source và ngày revision vẫn được giữ đầy đủ.

## Phân công code hiện tại

| Thành viên | Module |
|---|---|
| Khánh | `discover.py`: OAI, XML/version parser, metadata cache, ngày v1 |
| Khang | `download.py`: source từng version, extract/filter, receipts |
| Nguyên | `references.py`: S2 pagination, hai stores, completeness |
| Danh | `pipeline.py`, `metrics.py`, notebook: chạy chung, checkpoint, audit, thống kê và tài nguyên |

Các kiểu chung ở `src/crawling/__init__.py`. Cả nhóm dùng cùng notebook; không chạy riêng các mock để tạo corpus.

## Trạng thái nghiệm thu

Sau đợt dọn ngày 17/10/2026: **27 regression tests đạt**, hai kernel notebook offline/integration đạt và notebook analyze dữ liệu thật đạt. Toàn bộ corpus/cache/lượt chạy cũ đã được xóa trước cold run mới. Bộ test đã chạy đạt và được xóa theo yêu cầu sau khi kiểm chứng; checkout hiện không chứa `tests/`.

Để **hoàn thành/nộp M1 của cả nhóm**, còn cần crawl đủ bốn assignment, xử lý/giải thích lỗi, kiểm tay nguồn độc lập, benchmark cold Colab CPU, Jupyter Book tiếng Anh trong public repo riêng với bảng/hình sinh lúc build, GitHub Pages và nộp hai links Moodle trước hạn. Đây là các điều kiện nghiệm thu của đề; lượt chạy một bài trên Windows chỉ kiểm khả năng chạy của implementation.


## Bằng chứng lượt tải mới sau khi dọn

- Paper: `2606.15734` — *Retrievable Gradients: Continual Post-Training Without Cumulative Weight Drift*.
- Run ID: `59dc98b6-be0c-4c7d-b10f-96bb5606fa5f`; `status=success`, `cache_mode=cold`.
- End-to-end: **168,3166 giây**; 46 OAI network requests, 0 disk/memory cache hits. S2 trả 429 một lần, retry thành công; request log lưu số lần gọi thật.
- Đủ v1/v2; mỗi version có 5 TeX/BibTeX files. Tổng source trước lọc 1.094.243 bytes, sau lọc 345.101 bytes.
- Giữ 69 reference rows: 45 arXiv, 24 non-arXiv. Cả 45 arXiv references có đủ ngày v1; 17 non-arXiv rows chưa được S2 trả đầy đủ authors/S2 ID được giữ null và báo quality count.
- RAM peak quan sát 47.603.712 bytes. Môi trường Windows/Python 3.12.14, local development; không phải benchmark Colab CPU.
- **5 audit rows đều valid**: metadata, source v1/v2, cả hai reference stores, 46 raw XML checkpoints (ID/hash/ngày v1). Analyze không gọi mạng; ZIP CRC đạt.

Toàn bộ corpus, report, XML cache, ZIP, analyzed notebook và verification của lượt này đã được xóa trong đợt dọn cuối theo yêu cầu. Đường dẫn `data/milestone1/one-paper/` là đường dẫn lịch sử, không còn tồn tại. Các số liệu trên ghi lại kết quả đã quan sát; chúng không thay bằng chứng của lần crawl Colab mới.

Giữ README, đề tổng, doc kế hoạch, phân công, hướng dẫn thành viên, phương pháp OAI và hướng dẫn chạy. Doc kế hoạch chứa đầy đủ citations cho toàn `/src`. Notebook trong `src/` sạch outputs; runtime Colab sẽ tạo data mới khi chạy.

## Sao lưu Drive sau lượt chạy — 18/10/2026

Notebook hiện cấp quyền/mount Drive trước collection và tự bật SAVE_TO_DRIVE trên Colab, nén corpus/report local và copy hai ZIP lên MyDrive/arXivProject/Milestone1 theo run/lần sao lưu. Chỉ xuất receipt/VERIFIED sau kiểm CRC/hash; không ghi đè bản cũ hoặc xóa source khi lỗi. Xem [hướng dẫn Drive](./CHAY_VA_KIEM_TRA_WINDOWS.md#8-phạm-vi-của-bản-sao-lưu-tự-động). Bước này nằm ngoài benchmark, chạy cuối lượt; crawl OAI/pacing/cache không đổi.


## Retry qua runtime mới

Queue riêng cho member trong Drive/retry-state đăng ký scope trước crawl. Cold session hợp pending IDs với đoạn mới, retry trước và dedup; restore source/hidden receipts/OAI cache của bài pending từ ZIP verified, dùng validators hiện tại để quyết định reuse. Chỉ xóa pending khi metadata/all versions/references/audit đạt và corpus/report backup đã verified. Runtime bị ngắt hoặc backup lỗi giữ pending; không có periodic backup corpus nên bytes chưa backup có thể phải tải lại. not_found/metadata upstream thiếu vẫn pending và có thể lỗi tiếp. Resume giữ exact saved scope; local/offline/analyze không đăng ký hay acknowledge. OAI arXivRaw, TTL 24 giờ và pacing 3,1 giây không đổi. Scope/benchmark/citations/provenance xem kế hoạch mục 12 và hướng dẫn chạy mục 9.
