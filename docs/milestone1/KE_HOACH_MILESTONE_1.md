# Kế hoạch Milestone 1 — Thu thập dữ liệu bài báo arXiv

Cập nhật **17/10/2026** theo code hiện tại. Giữ tài liệu này để ghi phương pháp, quyết định kỹ thuật, nguồn tham khảo và tiến độ; cập nhật tại chỗ khi cách làm thay đổi.

Tài liệu liên quan: [đề tổng](../../ARXIV_PROJECT_FULL.md), [phân công bốn người](./PHAN_CONG_MILESTONE_1_4_NGUOI.md), [hướng dẫn sử dụng notebook](./HUONG_DAN_SU_DUNG_NOTEBOOK.md).

## 1. Mục tiêu và yêu cầu của đề

M1 resolve đúng dải ID TA giao, crawl **mọi version** kể cả v1, giữ source TeX/BibTeX nguyên nội dung và metadata của bài/references. Đề không bắt buộc harvest toàn repository. M1 chưa nộp corpus; dữ liệu local là đầu vào M2/M3. [1, 2]

Phần General Requirements của [đề tổng](../../ARXIV_PROJECT_FULL.md) yêu cầu: “Ensure your code is well-documented with clear comments.” Đồng thời tài liệu online được tham khảo phải có trích dẫn đầy đủ. Vì vậy module cần docstring giải thích vai trò/hợp đồng, comment giải thích các quyết định khó và dẫn tới mục tài liệu tham khảo bên dưới. Không chỉ ghi tên thư viện hoặc URL không rõ dùng làm gì. [1]

## 2. Phương án discovery hiện tại và vì sao phù hợp đề

Chỉ dùng **OAI-PMH `arXivRaw`** cho discovery, metadata, lịch sử phiên bản và ngày gửi arXiv references:

```text
GET https://oaipmh.arxiv.org/oai
verb=GetRecord
metadataPrefix=arXivRaw
identifier=oai:arXiv.org:{base_id}
```

`GetRecord` là verb chính thức của OAI-PMH để lấy metadata theo identifier. Đề đưa Sickle/`ListRecords` làm ví dụ bulk harvesting; không yêu cầu dùng thư viện Sickle hoặc đúng nguyên mẫu đó. Code dùng Requests + XML stdlib để kiểm soát pacing, lỗi giao thức, xác minh ID và checkpoint. Đây là lựa chọn triển khai theo yêu cầu resolve ID, không phải chuyển sang Query API. [2, 3, 4, 7, 8]

Chọn `arXivRaw` vì tài liệu arXiv xác nhận format này chứa lịch sử versions; format `arXiv` mô tả metadata của version mới nhất. Parser kiểm header/raw ID, title/authors, v1..vN liên tục và ngày theo thứ tự. Ngày gửi lấy từ v1, ngày revisions lấy từ v2..vN. Chuỗi tác giả raw được tách theo separator ngoài nhóm trong ngoặc, giữ hậu tố tên; XML gốc vẫn được lưu để kiểm tay tên phức tạp. [3]

Không dùng `from`/`until` để suy ra tháng gửi bài: OAI datestamp là ngày metadata được sửa. Một bài gửi tháng 6 nhưng sửa tháng 10 có thể nằm ngoài harvest tháng 6. `GetRecord` theo ID tránh nhầm phạm vi này. Phương án hiện tại không có phân trang OAI/resumption token, nên không cần xử lý token hết hạn hằng ngày. Không khẳng định cách này nhanh hơn bulk `ListRecords`: lượt đầu cần một OAI request cho mỗi ID duy nhất, gồm references. [3, 4]

## 3. Nhịp truy cập, cache và lỗi

- Chạy tuần tự, một request/kết nối tại một thời điểm; trước mỗi request arXiv nghỉ ít nhất **3 giây**, mặc định **3,1 giây**, kể cả retry. Giới hạn tính chung các máy nhóm kiểm soát; nhóm xếp lịch hoặc điều phối chung, không tăng máy để vượt giới hạn. [5]
- Retry có giới hạn cho lỗi tạm thời/429/5xx, tôn trọng `Retry-After`; hết lượt thì ghi failed/partial. Không fallback sang Query API/HTML/Kaggle.
- OAI `idDoesNotExist` hoặc header deleted mới được ghi không tìm thấy; HTTP 404/lỗi truy cập chưa chứng minh paper không tồn tại. [4]
- Lưu XML + receipt nguồn/ID/timestamp/SHA-256 sau từng ID thành công. Một OAI client dùng chung cho discovery và ngày references, nên ID trùng dùng cache.
- Cache metadata và references có TTL **24 giờ**. Đây là quyết định của nhóm để làm mới snapshot, không phải thời hạn bắt buộc của OAI. Không gia hạn tuổi gốc khi đọc cache, không cache lỗi vĩnh viễn.
- Manifest/receipt schema **3.0**; xác minh hash, identity và provenance trước khi dùng. Corpus schema cũ cần root mới. Analyze chỉ audit snapshot local, không gọi mạng hay khẳng định snapshot còn mới.

## 4. Tải và lọc source

Tải riêng từng version tại `https://export.arxiv.org/src/{id}vN`, dùng mirror theo đề, nhịp nghỉ như trên. Nhận diện tar/gzip, TeX đơn, PDF/DOCX hoặc dữ liệu lỗi theo nội dung. Archive có giới hạn kích thước/số entries; xử lý đường dẫn an toàn, không extract cả archive rồi xóa hình. [2, 6, 9]

Chỉ giữ `.tex` và `.bib` nguyên byte, cùng cấu trúc thư mục. Không giữ `.sty`, `.cls`, `.bbl`, ảnh hoặc text khác; không sửa `figure`, `includegraphics` hay lệnh bảng trong TeX. Version không có TeX giữ record `no_tex`, thư mục rỗng và receipt; lỗi download là failed. Bytes trước/sau lọc dùng cùng cơ sở source chưa nén; archive bytes được ghi riêng. [2]

## 5. References và lưu dữ liệu

Semantic Scholar vẫn là nguồn references bắt buộc; nó không thay nguồn metadata arXiv. Endpoint dùng `/paper/ARXIV:{id}/references`, query fields phẳng `title,authors,externalIds,publicationDate,year,venue`. `citedPaper` là wrapper ở response, không phải prefix query fields; `authors.name` không dùng. Theo `next` để lấy hết trang; không đoán thiếu trang chỉ vì trang cuối đủ 100 hàng. [2, 10]

`references_all.json` giữ mọi hàng nhận được, gồm non-arXiv, entries trùng hoặc citedPaper chưa rõ. `references.json` giữ pool arXiv duy nhất cho matching. Giữ legacy IDs `archive/YYMMNNN`; bỏ version suffix trước tra ngày. Ngày gửi lấy v1 từ cùng OAI client, không thay bằng S2 `publicationDate`. [2, 3, 10]

Thiếu trang hoặc trường bắt buộc/ngày của pool arXiv làm job partial. Non-arXiv thiếu metadata từ S2 vẫn được giữ null và đếm chất lượng riêng; không đo completeness của mọi references bằng tỷ lệ của pool arXiv. References là snapshot theo publication; S2 không bảo đảm danh sách riêng cho từng revision. Partial retry không thay complete store tốt bằng dữ liệu thiếu.

Pipeline ghi manifest sau từng task. Source owner ghi source/receipt, reference owner ghi hai stores/receipt; pipeline ghi metadata/manifest. JSON/CSV là working format do nhóm chọn, không phải format bắt buộc của đề. Dataset cuối có 6 bảng; M1 định nghĩa `papers`, `references`, M3 mới xuất bản sharded Parquet. [2]

## 6. Thống kê, benchmark và báo cáo

`metrics.py` đếm papers/versions/status, success rates, source bytes trước/sau, mọi reference rows và arXiv matching pool. Các tỷ lệ/trung bình có mẫu số; giá trị chưa đo là None, không tự điền 0. Source coverage tính cả `no_tex` hợp lệ; paper success với nguồn TeX mọi version là chỉ số khác.

Sampler đo RSS của process tree bằng `psutil.Process.children(recursive=True)` và `memory_info().rss`; file bytes của corpus được đo riêng. Xuất samples/timestamps, chu kỳ 0,25 giây và lỗi đo. RAM/disk peak là peak **quan sát** theo lấy mẫu; không bảo đảm bắt mọi đỉnh rất ngắn. [11]

Wall time end-to-end bắt đầu trước discovery, gồm cả nghỉ/retry và dừng sampler; không lấy tổng task times làm wall time. Có discovery time, từng paper/mean, RAM peak/mean, disk peak/final và environment/cache_mode. Benchmark nghiệm thu phải cold Colab CPU; một bài local không thay benchmark cuối. [2, 12]

Jupyter Book tiếng Anh nằm trong public repo riêng, hosted GitHub Pages. Dùng dữ liệu thật xuất từ pipeline để sinh bảng/hình **lúc build**. Notebook/report ZIP cung cấp dữ liệu và figures kiểm tra; ZIP tự nó chưa phải Book nộp bài. Public code repo có README/requirements; nộp hai links qua Moodle trước hạn. [1, 2]

## 7. Comment và truy nguyên nguồn cho toàn bộ /src

Phạm vi rà soát gồm **tất cả 13 file trong `src/`**, không chỉ OAI. Phải phân biệt ba loại thông tin:

- **Tham khảo đặc tả/tài liệu API:** dùng endpoint, response fields, ý nghĩa ngày, contract hoặc cách gọi thư viện theo tài liệu; không đồng nghĩa chép code của trang đó.
- **Logic riêng của project:** scope/receipts/cache/status/denominators và cách phối hợp được thể hiện bằng code, comment và test; không gán chúng cho tác giả tài liệu thư viện.
- **Code copy/adapt từ nguồn ngoài:** nếu có phải ghi đúng đoạn/hàm, URL/revision, tác giả, license và thay đổi đã thực hiện. Không được lấy một link documentation để thay cho attribution của block code đã sao chép.

### 7.1. Bảng đối chiếu đủ từng file

| File trong /src | Thành phần dựa trên tài liệu/thư viện | Logic riêng và giới hạn truy nguyên | Nguồn |
|---|---|---|---|
| `crawling/__init__.py` | `TypedDict`, `Protocol`, `Literal`, `Callable`; các cột dữ liệu theo đề | Contract JSON, schema 3.0, trạng thái và quy ước đường dẫn của project; type hints không tự validate runtime | [1, 2, 13] |
| `crawling/discover.py` | OAI GetRecord/arXivRaw, XML namespaces, Requests GET, UTC/date parsing, stdlib hash/file I/O | `_authors`, `_parse_raw` invariants, scope expansion, TTL, checkpoint/provenance và shared cache là implementation của project | [3, 4, 5, 7, 8, 14] |
| `crawling/download.py` | Versioned export source, Requests streaming; `tarfile`, gzip/zip/XML, pathlib/tempfile/hashlib/os | Nhận diện payload, whitelist nguyên byte, giới hạn/path checks, no_tex, staging/rollback và receipts là implementation áp dụng yêu cầu đề | [2, 5, 6, 8, 9, 14] |
| `crawling/references.py` | S2 fields/citedPaper/offset-next, Requests và date/hash/JSON stdlib | Hai stores, dedup pool, OAI DateLookup, quality counters, completeness và partial preservation là thiết kế project | [2, 3, 8, 10, 14] |
| `crawling/pipeline.py` | `typing` introspection, threading/Event, perf_counter, subprocess, filesystem/JSON | `_typed` validator, assignment conversion, shared client, checkpoint, điều kiện success/cache mode và phạm vi benchmark do project viết | [2, 3, 5, 13, 14] |
| `crawling/metrics.py` | psutil Process RSS/children, stdlib CSV/JSON/statistics/threading/time | Mẫu số, None/0, source coverage/no_tex, các trung bình và xuất report là cách tổng hợp của project | [2, 11, 14] |
| `notebooks/milestone1.ipynb` | Colab runtime/Secrets/files.download; pandas DataFrame/Styler; Matplotlib pyplot; IPython display; stdlib Git/process/package/filesystem APIs | Configuration, guards, tables/audits/charts layout, benchmark checks và report bundle là notebook của project; chi tiết từng nhóm cells ở mục 7.2 | [1, 2, 12, 14, 15, 16, 17, 18] |
| `crawling/assignments.py` | Ảnh phân công TA do user cung cấp; OAI đối chiếu mốc tháng [3,4] | Bốn full ranges, verified month boundaries; thứ tự member tương thích queue | [2,3,4] |
| `crawling/checkpoints.py` | concurrent.futures ThreadPoolExecutor/Future, threading, ZIP/hash/copy [14,23–26] | Immutable snapshots, bounded2 in-flight, artifact audit/ack, flush + staged disk/RSS + final report stub | [14,18,23,24,25,26] |
| `crawling/reports.py` | CSV/JSON/ZIP/hash [14,23,24] | new/retry roles, chosen corpus/run dedup, actual prefix/final labels và portable member tree | [14,23,24] |
| `crawling/sessions.py` | JSON/filesystem/UUID, ZIP/hash [14, 23, 24], Colab Drive [18] | Queue theo member; register trước crawl, seed source/cache từ ZIP verified, acknowledge sau backup/audit; ticket, scope và provenance [mục 12] | [14, 18, 23, 24] |
| `crawling/backup.py` | ZIP/CRC, SHA-256 theo chunks, strict os.walk inventory, file copy/rename, Google Drive do notebook mount | Đối chiếu run_id; output ngoài input; hai archive local, attempt riêng, receipt ghi cuối; bảo toàn source/backup cũ khi lỗi | [14, 18, 23, 24] |
| `requirements.txt` | Cú pháp requirements `package==version`; các distribution dependencies của pipeline/notebook | Danh sách/version pins là cấu hình environment, không phải block thuật toán sao chép; đồng bộ `environment.yml`, không phải transitive lockfile | [8, 11, 15, 16, 17, 19, 20, 21, 22] |

Nguồn stdlib [14] bao gồm các API hỗ trợ xuất hiện trong imports: `collections.abc`, copy, csv, datetime/date/timezone, email.utils, gzip, hashlib, importlib, json, logging, math, os, pathlib, platform, re, shutil, stat, statistics, subprocess, sys, tempfile, threading, time, types, uuid và zipfile. XML/tar/typing quan trọng được cite riêng ở [7, 9, 13]. Sử dụng API thư viện không có nghĩa lấy mã nguồn triển khai bên trong thư viện vào project.

### 7.2. Notebook: nguồn áp dụng cho từng nhóm cells

| Cells (theo id trong notebook) | API/tài liệu áp dụng | Phần project tự tổ chức |
|---|---|---|
| Cell in Python version; `runtime-bootstrap`, `imports` | Python sys/importlib/subprocess/path [14]; Colab [12, 18]; pandas/Matplotlib/IPython [15–17] | Tìm project folder, lựa chọn clone/install, xử lý environment và import module |
| `configuration`, `environment` | Stdlib version/Git/process APIs [14], psutil [11], pandas [15] | Assignment/scope, cold/resume/analyze, CPU guard, ghi package/source revision |
| `collection` | Code pipeline/metrics nội bộ; filesystem/JSON/ZIP support [14] | Gọi pipeline thật, kiểm run_id, xuất configuration/environment/metadata stats |
| `coverage-tables`, `integrity-audit` | pandas/Styler [15], hash/file I/O [14], OAI identity/version semantics [3, 4] | Các bảng coverage, kiểm metadata/source/hai stores/raw checkpoints và outstanding tasks |
| `corpus-charts`, `resource-charts` | Matplotlib [16], pandas [15] | Chọn dữ liệu, axes/labels/layout, PNG/SVG; không có số liệu hardcode thay kết quả crawl |
| `benchmark-tables` | Yêu cầu benchmark [2, 12], pandas [15] | Điều kiện nghiệm thu, units, mẫu số và phân biệt local/Colab/cold/cache |
| `drive-connect`, `session-prepare` | Colab drive.mount [18], JSON/UUID/filesystem/ZIP/hash [14, 23, 24] | Mount/write check trước crawl; queue/member, retry-first union, seed/manifest và resume scope |
| `drive-backup`, `browser-download` | Google Colab drive.mount/files.download [18], ZIP/hash/filesystem [14, 23, 24] | Mount guard/offline skip, gọi helper backup hai archive, lỗi hiển thị và retry riêng cell; browser download chạy sau backup |
| `report-export`, markdown methods/submission | shutil/archive [14], IPython [17], Colab files API [18], đề [1, 2] | Report README/ZIP và hướng dẫn interpret/backup/nộp Book |

### 7.3. Kết luận về code sao chép và mức bằng chứng

Rà source hiện tại, comment attribution, imports/calls của cả 13 file và lịch sử commit có sẵn chưa xác định được một block code cụ thể mang attribution copy/adapt từ repository hoặc bài viết ngoài project. **Đây không phải chứng nhận rằng mọi dòng code lịch sử đều nguyên bản**: repository không lưu đầy đủ lịch sử các nguồn mà từng thành viên có thể đã đọc.

Các đoạn triển khai/chỉnh sửa trong phiên làm việc hiện tại được viết theo yêu cầu project và đặc tả/API đã đối chiếu; không có block ngoài nào được nhận diện để khai báo là copy nguyên văn. Các citations bổ sung trong lần rà soát toàn `/src` là **tài liệu đối chiếu API đang dùng**, không phải bằng chứng code đã được chép từ những trang đó. Nếu thành viên xác nhận một đoạn cũ từng copy/adapt, bổ sung attribution đúng nguồn và license vào ngay hàm/đoạn đó và mục này.

Quyết định scope, checkpoint, receipts, TTL, tách stores và điều kiện trạng thái là thiết kế của project, không phải yêu cầu bắt buộc của arXiv. Comment ở từng module và notebook dẫn về mục này để người đọc tìm nguồn của đúng phần code.

## 8. Phạm vi, phân công và thứ tự thực hiện

Khánh phụ trách discovery/OAI, Khang source, Nguyên S2 references, Danh pipeline/metrics/notebook/báo cáo. Input/output và checklist từng người nằm ở [doc phân công](./PHAN_CONG_MILESTONE_1_4_NGUOI.md).

Cả bốn assignment đã điền sẵn, mỗi người 5.000 ID; mốc cuối tháng đã xác minh (xem mục 13). Chọn `SELECTED_MEMBER` và `NEW_PAPERS_PER_SESSION`; đặt số ID mới bằng 1 để thử, hoặc 100/200/300/400 tùy lượt. Giữ nguyên phạm vi đầy đủ để planner tự chọn ID mới và retry. Chi tiết thao tác nằm trong [hướng dẫn sử dụng notebook](./HUONG_DAN_SU_DUNG_NOTEBOOK.md).

1. Kiểm requirements/contracts và notebook kernel mới; suite lịch sử đã chạy đạt trước khi dọn.
2. Thử cold một ID thật, audit và so nguồn độc lập.
3. Crawl đủ assignment, resume phần thiếu, sao lưu corpus/report theo run.
4. Tổng hợp toàn nhóm, benchmark cold Colab CPU.
5. Build/publish Book, kiểm links, nộp Moodle; giữ corpus cho M2/M3.

## 9. Tiến độ và bằng chứng hiện tại

Code OAI đã triển khai, không còn là prototype. Lượt cold thật mới sau khi dọn dữ liệu: `2606.15734`, run `59dc98b6-be0c-4c7d-b10f-96bb5606fa5f`, success trong **168,3166 giây**; 46 OAI requests, không cache hits; đủ v1/v2 và 69 reference rows (45 arXiv có ngày v1, 24 non-arXiv). Có 17 non-arXiv rows thiếu metadata nguồn được giữ null/đếm riêng.

27 regression tests và hai kernel notebook offline/integration đã đạt; analyze dữ liệu thật không gọi mạng, 5 audit rows và ZIP CRC đạt. Corpus/report/verification từng ở `data/milestone1/one-paper/`; các artifacts này đã được xóa theo yêu cầu dọn cuối, chỉ còn số liệu lịch sử trong tài liệu. Bộ 27 tests và notebook fixtures cũng đã xóa sau lượt kiểm đạt cuối theo yêu cầu. Đây là kết quả lịch sử đã ghi, không còn script/artifact kèm checkout để chạy lại nguyên suite; khi sửa hành vi phải có kiểm chứng tương ứng mới.

Chưa crawl toàn bộ assignment, chưa benchmark Colab CPU cuối, chưa hoàn thành/publish Book và chưa nộp Moodle. Không dùng kết quả một bài để đánh dấu cả M1 hoàn thành.

## 10. Tài liệu tham khảo

Ngày truy cập/đối chiếu: **17/10/2026**. `n.d.` là trang không ghi ngày xuất bản cố định. Các citations là tài liệu kỹ thuật, không phải bằng chứng đã benchmark/crawl toàn corpus. Phiên bản chạy được ghi trong environment/report; không tự nâng dependencies chỉ vì trang docs mới hơn.

1. HCMUS CS Teaching Assistants. (n.d.). *Introduction to Data Science — Project Statement*, General Requirements. [Trang gốc](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/). Bản đối chiếu local: [ARXIV_PROJECT_FULL.md](../../ARXIV_PROJECT_FULL.md). Dùng cho yêu cầu comments, complete citations, ngôn ngữ và cách tổ chức project.
2. HCMUS CS Teaching Assistants. (n.d.). *Project Milestone 1 — Crawling*. [Trang gốc](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/). Dùng cho assigned-ID discovery, mọi versions, source filtering, references, statistics, Colab và Book/nộp bài.
3. arXiv. (n.d.; mục thay đổi March 2025). *Open Archives Initiative (OAI)*. [Tài liệu chính thức](https://info.arxiv.org/help/oa/index.html). Dùng cho endpoint mới, supported metadata formats, history trong arXivRaw, datestamps và resumption tokens.
4. Lagoze, C., Van de Sompel, H., Nelson, M., & Warner, S. (2002, June 14). *The Open Archives Initiative Protocol for Metadata Harvesting, Version 2.0*, §4.1 GetRecord. [Đặc tả OAI-PMH](https://www.openarchives.org/OAI/openarchivesprotocol.html#GetRecord). Dùng cho verb, identifier/metadataPrefix và protocol errors; ví dụ endpoint cũ trong đặc tả không được dùng làm endpoint arXiv hiện tại.
5. arXiv. (n.d.). *Terms of Use for arXiv APIs*, Rate limits. [Quy định chính thức](https://info.arxiv.org/help/api/tou.html). Dùng cho tối đa một request mỗi ba giây, một connection và tổng các máy được kiểm soát.
6. arXiv. (n.d.). *Media types*. [Tài liệu chính thức](https://info.arxiv.org/help/mimetypes.html). Dùng để hiểu source payload formats; whitelist `.tex`/`.bib` cụ thể đến từ đề [2].
7. Python Software Foundation. (n.d.). *xml.etree.ElementTree — The ElementTree XML API*. [Python documentation](https://docs.python.org/3/library/xml.etree.elementtree.html). Dùng cho parse XML/namespaces; kiểm ID và version invariants do project bổ sung.
8. Requests contributors. (n.d.). *Requests — Developer Interface*. [API documentation](https://requests.readthedocs.io/en/latest/api/). Dùng cho GET/query params, timeout, response lifecycle, streaming và exceptions; pacing/retry được project xử lý riêng.
9. Python Software Foundation. (n.d.). *tarfile — Read and write tar archive files*. [Python documentation](https://docs.python.org/3/library/tarfile.html). Dùng cho duyệt/đọc archive members; project kiểm path/size và chỉ copy entries được phép thay vì extract toàn bộ.
10. Allen Institute for AI. (n.d.). *Semantic Scholar Academic Graph API*, Paper Data: Get paper references. [API reference](https://api.semanticscholar.org/api-docs/graph#tag/Paper-Data/operation/get_graph_get_paper_references). Dùng cho `/references`, fields, `citedPaper`, offset/next pagination; bộ regression và lượt gọi thật kiểm request fields thực dùng.
11. Rodolà, G., & psutil contributors. (n.d.). *psutil — Process and System Utilities for Python*, Process API. [Documentation](https://psutil.io/). Dùng cho RSS/process tree; chu kỳ lấy mẫu và công thức tổng hợp là thiết kế project.
12. Google. (n.d.). *Colaboratory Frequently Asked Questions*. [Colab FAQ](https://research.google.com/colaboratory/faq.html). Dùng cho runtime/accelerator và tính tạm thời của VM; yêu cầu benchmark CPU-only đến từ đề [2].
13. Python Software Foundation. (n.d.). *typing — Support for type hints*, Python 3.11 documentation. [Tài liệu typing](https://docs.python.org/3.11/library/typing.html). Đối chiếu TypedDict/Protocol/Literal/Callable và type introspection trong contracts/pipeline; runtime validation là code riêng.
14. Python Software Foundation. (n.d.). *The Python Standard Library*, Python 3.11 documentation. [Mục lục API chuẩn](https://docs.python.org/3.11/library/index.html). Đối chiếu nhóm API hỗ trợ liệt kê ở mục 7.1: files/JSON/CSV/hash/dates/processes/threads/time/archives; không dùng link này để khai báo nguồn sao chép của một thuật toán.
15. pandas development team. (n.d.). *Table Visualization — pandas User Guide*. [Styler documentation](https://pandas.pydata.org/docs/user_guide/style.html). Đối chiếu DataFrame/Styler.format và hiển thị bảng notebook; bảng, chỉ số và dữ liệu do project chọn.
16. Matplotlib development team. (n.d.). *matplotlib.pyplot — Matplotlib API Reference*. [Pyplot documentation](https://matplotlib.org/stable/api/pyplot_summary.html). Đối chiếu subplots, bar/hist/plot, labels/layout và savefig PNG/SVG; không sử dụng một chart template bên ngoài đã được nhận diện.
17. IPython development team. (n.d.). *IPython.display — API documentation*. [Display/Markdown documentation](https://ipython.readthedocs.io/en/stable/api/generated/IPython.display.html). Đối chiếu display và Markdown trong notebook; không phải nguồn của nội dung report.
18. Google Colaboratory contributors. (n.d.). *colabtools: google.colab.userdata, google.colab.files and google.colab.drive*. [Secrets API source](https://github.com/googlecolab/colabtools/blob/main/google/colab/userdata.py), [files API source](https://github.com/googlecolab/colabtools/blob/main/google/colab/files.py), [Drive mount API source](https://github.com/googlecolab/colabtools/blob/main/google/colab/drive.py). Đối chiếu gọi userdata.get, drive.mount và files.download từ notebook; project import package, không chép implementation của Google.
19. Python Packaging Authority. (n.d.). *pip — Requirements File Format*. [Requirements documentation](https://pip.pypa.io/en/stable/reference/requirements-file-format/). Đối chiếu cú pháp version pins trong requirements.txt; không xác nhận environment đã cài mới/chạy đạt.
20. Project Jupyter contributors. (n.d.). *JupyterLab Documentation*. [Tài liệu chính thức](https://jupyterlab.readthedocs.io/en/stable/). Vai trò JupyterLab trong dependency/setup notebook; không có source JupyterLab được vendored vào `/src`.
21. IPython/Jupyter contributors. (n.d.). *IPython Kernel for Jupyter*. [ipykernel documentation](https://ipykernel.readthedocs.io/en/stable/). Vai trò kernel trong notebook/environment; project dùng package, không chép implementation kernel.
22. Pallets Projects. (n.d.). *Jinja Documentation*. [Jinja documentation](https://jinja.palletsprojects.com/en/stable/). Dependency phục vụ pandas Styler; project không có custom Jinja template trong `/src` để gán attribution.

23. Python Software Foundation. (n.d.). *zipfile — Work with ZIP archives*. [Python documentation](https://docs.python.org/3/library/zipfile.html). Đối chiếu tạo/đọc ZIP và testzip CRC cho hai archives; không dùng CRC thay tính đúng của corpus. Truy cập 18/10/2026.
24. Python Software Foundation. (n.d.). *hashlib — Secure hashes and message digests*. [Python documentation](https://docs.python.org/3/library/hashlib.html). Đối chiếu SHA-256 incremental/chunks để kiểm bản sao mà không nạp cả ZIP vào RAM. Truy cập 18/10/2026.

25. Python Software Foundation. (n.d.). *concurrent.futures — Launching parallel tasks*. [API chính thức](https://docs.python.org/3/library/concurrent.futures.html). ThreadPoolExecutor(max_workers=1), Future.result, shutdown(wait=True); project tự giới hạn2 snapshot chờ, không dùng map buffersize của Python mới. Truy cập18/10/2026.
26. Python Software Foundation. (n.d.). *threading — Thread-based parallelism*. [API chính thức](https://docs.python.org/3/library/threading.html). Resource sampler và worker lifecycle/join; không xem thread là bảo đảm thực thi nếu VM bị thu hồi. Truy cập18/10/2026.

Khi tham khảo thêm hoặc thay đổi cách làm, bổ sung tác giả/tổ chức, tên tài liệu, ngày/phiên bản nếu có, URL, ngày truy cập và nội dung đã áp dụng vào mục này; đồng bộ comment liên quan trong code và phần References của Book.

## 11. Bổ sung sao lưu Drive — 18/10/2026 (lịch sử, được mở rộng ở mục13)

**Mục tiêu:** sau khi Collection/report hoàn tất, notebook Colab tự đề nghị mount Drive và sao lưu cả corpus lẫn report, kiểm SHA-256 trước khi báo thành công. User đã yêu cầu tích hợp bước sao lưu đã mô tả vào code.

**Cách làm:** `crawling/backup.py` dùng Python stdlib để tạo hai ZIP trên ổ local, kiểm CRC, copy qua file tạm và đối chiếu hash. Mỗi lần thử có thư mục riêng dưới run_id; receipt được ghi cuối cùng, không ghi đè bản cũ. Notebook mount Drive và gọi helper trước bước browser download report.

**Ràng buộc:** không thêm dependency; không đổi crawl/pacing/benchmark; tắt Drive khi chạy local hoặc ALLOW_NETWORK=False. Xác minh run_id của corpus/report, từ chối output nằm trong input và không xóa source khi backup lỗi. Đây là backup cuối lượt, chưa phải checkpoint Drive giữa chừng. Test/file tạm dùng để kiểm rồi dọn theo yêu cầu hiện tại.

**Các bước:**

- [x] Test trước: ZIP có đủ file, hash/receipt đúng; reject run lệch và path lồng; lỗi copy/hash không tạo receipt hoàn tất, không ảnh hưởng backup cũ.
- [x] Thêm helper + cấu hình/cell Drive trong notebook, giữ browser download sau backup và thông báo lỗi có thể retry riêng cell.
- [x] Rà soát độc lập; kiểm notebook local/offline/mount thành công và mount lỗi bằng fixture; cập nhật hướng dẫn/citations, dọn test tạm rồi commit/push. Hành vi hỏi quyền cuối lượt của phiên bản này đã được thay bằng cấp quyền đầu phiên ở mục 12.

**Kết quả kiểm 18/10/2026:** 13 checks đạt: archive/file bytes/CRC/hash/receipt; run mismatch; output nested; retry độc lập; lỗi copy/hash; thư mục nguồn không đọc được phải fail, no_tex rỗng vẫn giữ; Colab thành công và auth lỗi; local và network-off không mount, mount chưa xác nhận không báo thành công. Test dùng filesystem thật ở thư mục tạm và giả lập biên Colab, chưa thay kiểm cấp quyền/mount Drive thật của người dùng. Test/data tạm đã được dọn trước commit theo yêu cầu. Không cần cài dependency mới.

**Review:** đã tái hiện và sửa P2 silent omission của shutil.make_archive bằng inventory traversal có onerror=raise, zip từng entry và giữ thư mục no_tex rỗng. Không báo backup hoàn tất nếu không đọc được subtree.


## 12. Drive đầu phiên và retry qua phiên — 18/10/2026 (lịch sử, được mở rộng ở mục13)

**Yêu cầu đã được user chốt:** cấp quyền Drive trước crawl; bài/file lỗi tự được thử lại ở phiên sau. Triển khai trực tiếp trong checkout hiện tại, giữ docs phân công/kế hoạch; test và dữ liệu tạm được dọn trước commit.

**Thiết kế:** thêm `crawling/sessions.py` dùng stdlib, queue riêng theo member trên Drive. Cold session hợp scope mới với ID còn pending (retry trước, không trùng); đăng ký toàn scope trước crawl. Sao chép có kiểm hash các source/receipts/cache của bài pending từ corpus ZIP đã verified sang root local mới, rồi dùng cache validators hiện tại; `resume` giữ nguyên scope đã lưu. Chỉ xác nhận ID hoàn tất sau backup verified + trạng thái metadata/all versions/references + integrity audit. Nếu chết giữa crawl/backup thì queue vẫn còn toàn ID đã đăng ký. Không có backup corpus định kỳ giữa crawl; cache OAI/S2 vẫn TTL 24 giờ. Retry có thể gồm bài not_found hoặc thiếu metadata upstream, không cam kết lần sau sẽ hết lỗi. Mỗi member chạy tuần tự; ticket phát hiện phiên cũ cố xác nhận sau khi phiên mới bắt đầu, không phải hỗ trợ chạy song song cùng member.

**Files:** thêm sessions.py; sửa notebook (drive-connect trước environment/collection; session-prepare trước collection; backup không hỏi quyền muộn; session metadata trong report). Không thay đổi 3,1 giây pacing, OAI arXivRaw, source bytes hay schema corpus. Report retry/cached không được coi là cold benchmark của riêng đoạn mới. Đồng bộ README và năm docs hiện có; citations Python filesystem/JSON/UUID/ZIP/hash và Colab drive.mount.

**Kế hoạch kiểm thử — dùng writing-plans và test-driven-development:**

- [x] Viết test RED cho prepare_session/finish_session/seed_pending: pending hợp scope, retry trước, dedup, member isolation, resume exact-scope, queue corrupt/concurrent ticket; không bỏ pending trước verified backup; discovery/source/reference/audit lỗi còn pending; no_tex hợp lệ; idempotent finish.
- [x] Thêm API `prepare_session(state_path, member, scope, extend=True)`, `seed_pending(plan, root)`, `finish_session(state_path, plan, manifest, backup, invalid_ids=())`; snapshot/hash/paths an toàn, không tự xóa source hoặc backup cũ.
- [x] Test notebook mount trước crawl, auth fail dừng trước network crawl, local/offline/analyze không sửa queue; fixture hai phiên thật qua ZIP/Drive giả lập; cache source đúng được tái sử dụng, phần lỗi được gọi lại.
- [x] Rà soát độc lập toàn thay đổi; kiểm source/notebook, docs, dọn test/cache/data, commit và push bản đã xác minh.

**Review focus:** state/ZIP hỏng phải fail và giữ queue; không lẫn member; completion cũ không xóa queue phiên mới; Drive backup lỗi không làm mất ID thành công chưa lưu; restore giữ hidden receipt và thư mục no_tex rỗng. Chuẩn bị/restore/backup nằm ngoài benchmark pipeline; report ghi scope thực tế và retry origin. Tổng hợp Book toàn nhóm vẫn là công việc riêng.


**Kết quả kiểm:** 17 behavioral checks đạt. Có hai lượt pipeline thật với HTTP fixture (v1 tốt, v2 lỗi rồi thành công), sau đó chạy các cell notebook thật từ Drive connect/environment/session prepare qua collection, coverage, integrity audit, PNG/SVG, benchmark, report ZIP, Drive backup/queue và browser-download giả lập trong hai phiên. Đã kiểm analyze không đổi queue, resume configuration nhận lại combined scope, backup lỗi vẫn giữ pending và browser fallback, queue read I/O lỗi không reset dữ liệu. Lần đầu fixture bật REQUIRE_COLAB_CPU trên máy có accelerator bị guard chặn đúng; fixture đổi sang development và không dùng kết quả đó làm Colab benchmark. Lỗi import NumPy do fixture restore sys.modules đã sửa trong test bằng preload, không sửa production để né guard. Nguồn/network và mount boundary giả lập; chưa cấp quyền Google Drive thật trên máy này. Rà soát độc lập không có finding cần sửa. Không đổi dependencies runtime; môi trường kiểm tạm và tests/data được dọn trước commit.

**Attribution:** sessions.py và các cell mới do project triển khai theo chính sách trên, dùng stdlib/Colab API đã cite ở [14, 18, 23, 24]; không có block ngoài được nhận diện là copy/adapt. Không thêm dịch vụ queue hoặc lưu credential. Phiên này sửa thêm lỗi tồn tại/đọc queue: chỉ FileNotFoundError mới được coi là queue mới, không dùng exists() để nuốt lỗi permission/I/O.


## 13. Chạy linh hoạt, tiến độ và backup nền — 18/10/2026

**User đã yêu cầu triển khai/thử:** nhập đủ phạm vi 4 người theo ảnh TA, mở phiên thấy tiến độ, chọn 100/200 bài mới, không đếm trùng, backup nền mỗi 40 bài trong khi crawl tiếp. Giữ docs hiện có; triển khai trực tiếp, tự kiểm rồi commit/push.

**Phạm vi chính xác từ ảnh:** Danh 2606.15734–2606.20733; Khánh 2602.19870–2603.00579; Khang 2609.02834–2609.07833; Nguyên 2601.23156–2602.04869. OAI GetRecord arXivRaw đã xác minh 2601.23286 và 2602.24290 tồn tại, ID kế tiếp mỗi tháng trả idDoesNotExist (nghỉ 3,1 giây/request); MONTH_END_IDS tương ứng 23286/24290. Mỗi phạm vi 5.000 ID, bốn phạm vi không giao nhau. Giữ thứ tự member cũ để không lẫn retry-state.

**Thiết kế:** planner gắn queue với assignment đầy đủ, dùng completion ledger đã backup verified để chọn ID chưa đăng ký, retry riêng có giới hạn, no-work an toàn. Migrate queue v1 từ receipts cũ, không tự đánh dấu source chưa có receipt là hoàn tất. Preview hiển thị tổng/đã lưu/pending/chưa tới/ID tiếp theo và new/retry của lượt. Report đánh dấu vai trò theo ID; corpus/count cuối dùng ID duy nhất, thời gian retry không bị giấu.

Pipeline gọi checkpoint sau mỗi bài đã xử lý (gồm lỗi). Main thread chốt snapshot local bất biến của tối đa 40 bài cùng receipts/cache/metadata/samples; worker đơn nén/copy/hash/commit queue, crawl tiếp. Giới hạn 2 snapshot đang chờ, worker chậm thì backpressure. Flush nhóm cuối và đợi worker trước khi kết thúc đo toàn pipeline. Stage nằm trong measured root để tính disk overhead, xóa stage sau upload verified; snapshot lỗi giữ local và queue chưa ack. Chỉ các ID có đủ kết quả/artifacts đạt kiểm tra mới được ghi completed. Progress được cập nhật ngay từ checkpoint, không cần chờ cell cuối hoặc browser download. Mất runtime vẫn có thể mất nhóm chưa verified. Không hứa chạy nền liên tục khi đóng tab/tắt máy.

Giữ final report ZIP mỗi lượt; thêm dữ liệu tiến độ/new/retry và khả năng tổng hợp CSV/JSON sau từ receipts, chọn một kết quả hoàn tất cho mỗi ID, không cộng trùng checkpoint/final report. Raw resource samples/time phải được lưu trong lúc chạy; snapshot prefix bị ngắt không được giả là benchmark cuối đủ phiên. Không giảm pacing hoặc bỏ version/reference.

**Thực hiện theo writing-plans + test-driven-development, một review độc lập cuối:**

- [x] RED/GREEN: bốn assignment đúng và disjoint; preview/plan 100 rồi 200, retry-only, no-work, migrate, không chọn lại completed hoặc pending như new, assignment/member mismatch fail.
- [x] RED/GREEN: callback pipeline; background immutable snapshot/reuse receipts; crawl tiếp khi worker đang upload; queue đầy chờ; copy/audit lỗi không ack; flush cuối; stale ticket không ghi; resource/backup overhead được ghi rõ.
- [x] RED/GREEN: report new/retry tags và dedup aggregation theo ID/receipt, checkpoint vs final không đếm trùng, report prefix đo thật có nhãn giới hạn.
- [x] Cập nhật notebook preview/config/member/startup, docs/citations; chạy fixture nhiều phiên qua pipeline/notebook thật; rà soát độc lập; dọn test/data/env rồi commit/push.

**Ràng buộc:** một runtime/member, không reset queue khi I/O lỗi, giữ receipts/ZIP trên Drive; actual Colab auth/user browser chưa thể kiểm ở local. Dùng Python stdlib threading/concurrent.futures/JSON/ZIP/hash/shutil theo [14,23,24], Colab mount [18]; bổ sung citations futures/threading khi triển khai.


**Kiểm chứng cuối:** 16 behavioral checks đạt qua unittest discovery; thêm2 regression stdlib đạt cho manual resume được gắn retry (không new) và auto planner vẫn bỏ qua completed. Bao gồm đủ4x5000 ID/disjoint; thay đổi new count; legacy completion/progress; retry-only/no-work; assignment/member mismatch; retry rotation; background upload bị giữ bằng Event nhưng crawl vẫn sang bài mới; giới hạn2 snapshot/backpressure; source root thay đổi sau freeze không thay bytes ZIP; upload lỗi giữ stage/pending; sampler chỉ bỏ qua FileNotFound khi stage bị dọn (permission vẫn lỗi); final report giữ audit failure; aggregate không đếm checkpoint+final+retry trùng, kiểm ZIP source/report và portable folder sau khi copy.

Fixture notebook chạy các cell thật (imports/configuration/mount/environment/prepare/collection/coverage/audit/charts/benchmark/export/backup) qua nhiều visit trong runtime mới/cùng runtime: source v1 tốt được reuse, v2 lỗi được tải lại, ID mới tăng đúng, retry-only không có pending không gọi mạng, thay new count không sửa endpoints, analyze không ghi queue hoặc gọi API. Mount/auth và HTTP được giả lập; test dùng local Windows Python3.14 với dependency pins project. Không coi fixture là benchmark Colab thật, chưa test OAuth/DriveFS thật trên tài khoản user. AST11 module +32 cell, outputs sạch; source/download/reference contracts/dependency pins không đổi.

**Review/fix:** reviewer độc lập phát hiện3 P2; đã tái hiện RED rồi sửa GREEN: lỗi retry đứng đầu làm starvation → chuyển lỗi xuống cuối; final raw report override audit fail → lưu audit verdict và truyền vào counts/aggregate; aggregate chỉ kiểm report mà thiếu source → kiểm source ZIP tồn tại/size/hash trước tính completed. Bổ sung regression cho portable member tree và opt-out retry không làm bỏ qua new-limit; bật/tắt retry không tự crawl toàn5.000. Tất cả checks cuối đạt.

**Giới hạn/cách bàn giao:** có thể mất nhóm chưa commit khi VM mất; không hứa chạy tiếp lúc tắt máy. Checkpoint/report upload overhead thực đo trong pipeline, final raw-report export nằm ngoài benchmark và được ghi provenance. session-reports/corpus.zip chỉ manifest stub, không phải source M2; completed ledger không bao giờ trỏ stub. Giữ nguyên cây từng member khi tổng hợp (helper rebase layout runUUID/attempt có kiểm); aggregate trả unique completed/new registered/retry attempts, không tự viết/publish Book. Tests/data/output và môi trường tạm được dọn trước commit theo yêu cầu user; docs phân công/kế hoạch được giữ/cập nhật.
