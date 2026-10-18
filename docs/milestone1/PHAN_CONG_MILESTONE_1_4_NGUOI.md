# Phân công Milestone 1 — Khánh, Khang, Nguyên, Danh

Cập nhật **17/10/2026** theo implementation hiện tại. Giữ doc phân công này; khi thay đổi phương pháp thì sửa nội dung, không xóa tài liệu.

Đọc [đề tổng](../../ARXIV_PROJECT_FULL.md), [kế hoạch/phương pháp và citations](./KE_HOACH_MILESTONE_1.md), [hướng dẫn thành viên](./HUONG_DAN_THANH_VIEN_MILESTONE_1.md) và [cách chạy](./CHAY_VA_KIEM_TRA_WINDOWS.md).

## 1. Quyết định chung

- Khánh: discovery/metadata/ngày gửi bằng **OAI-PMH GetRecord + arXivRaw duy nhất**.
- Khang: tải nguồn mọi version qua export mirror, chỉ giữ `.tex`/`.bib` nguyên byte.
- Nguyên: lấy đủ S2 references, giữ mọi hàng local và pool arXiv riêng.
- Danh: điều phối, checkpoints, statistics, resources, notebook, tổng hợp Book.
- Một notebook chung: [milestone1.ipynb](../../src/notebooks/milestone1.ipynb); nghiệp vụ nằm trong các module `.py`.
- Code đã triển khai và thử thật một bài; data/test local đã dọn sau kiểm chứng, số liệu lịch sử được giữ trong kế hoạch. Phạm vi Danh đã biết, ba phạm vi còn lại chưa được điền.
- Chú thích rõ input/output, quyết định khó và giới hạn. Tài liệu tham khảo ghi đầy đủ trong [kế hoạch, mục 10](./KE_HOACH_MILESTONE_1.md#10-tài-liệu-tham-khảo).

## 2. Hợp đồng kỹ thuật chung

`src/crawling/__init__.py` là nguồn kiểu dữ liệu chuẩn; manifest/receipts **3.0**. Đổi hợp đồng phải cập nhật các consumer cùng lúc.

| Contract | Vai trò |
|---|---|
| Scope | IDs hoặc range; pipeline xác minh assignment và không đoán mốc tháng |
| HttpPolicy | Timeout/attempts, arXiv/S2 delay, backoff, User-Agent |
| PaperRecord / DiscoveryResult | Metadata, mọi versions, scope coverage/issues, nguồn OAI |
| DateLookupResult | Ngày v1/None, errors theo ID, nguồn OAI |
| DownloadResult | success/no_tex/failed, bytes trước/sau/archive, file count, elapsed/cache/error |
| ReferenceResult | Mọi reference rows, pool arXiv, counts/completeness/pagination, nguồn ngày OAI |
| Manifest / RunResult | Checkpoints, summary/benchmark và metadata_stats |

ID gốc giữ dot/slash; version là int riêng. Ngày YYYY-MM-DD theo UTC; retrieval timestamp có timezone. None là chưa biết, khác 0. Không biến API error thành empty result.

## 3. Khánh — Discovery, metadata và ngày gửi

**File:** `src/crawling/discover.py`.

**Input:** Scope/ID/list IDs và policy; pipeline tạo một `OaiClient` dùng chung với `cache_dir=<corpus>/metadata_cache`.

**Cách làm hiện tại:**

1. Chuẩn hóa modern/legacy IDs, mở rộng đúng scope, gọi tuần tự `GetRecord` tại endpoint mới.
2. Dùng `metadataPrefix=arXivRaw`, kiểm OAI header/raw ID, title/authors, history đủ v1..vN và ngày hợp lệ.
3. Lấy submission_date từ v1 và revised_dates từ các version sau, không từ OAI datestamp.
4. Nghỉ tối thiểu 3 giây, mặc định 3,1; retry/Retry-After, ghi issues rõ khi lỗi.
5. Checkpoint XML/receipt theo ID, TTL 24 giờ; share cache khi references hỏi cùng ID. Không Query API/Atom/HTML/Kaggle fallback.

**Bàn giao:** PaperRecord/DiscoveryResult/DateLookupResult, không tự ghi metadata bài vào thư mục publication; pipeline ghi metadata.json. XML và OAI receipt thuộc module này.

**Kiểm đạt:** đúng scope/ID, history và ngày v1; không hardcode versions; cache hỏng/hết hạn refresh; ID không tồn tại khác HTTP lỗi; giải thích lựa chọn GetRecord/arXivRaw và citations trong phần phương pháp Book.

## 4. Khang — Source từng version

**File:** `src/crawling/download.py`.

**Input:** base ID, version, version_dir, policy/use_cache. **Output:** DownloadResult, source files và `.vN.receipt.json`.

1. Tải đúng `https://export.arxiv.org/src/{id}vN`, tuần tự theo nhịp arXiv.
2. Nhận diện archive/TeX/PDF/DOCX và dữ liệu lỗi; extract an toàn có giới hạn.
3. Chỉ giữ `.tex`/`.bib`, nguyên byte và lệnh hình/bảng; không giữ sty/cls/bbl/ảnh.
4. Đo before/after trên source chưa nén; archive_bytes riêng. Source không có TeX là empty no_tex có record, mạng lỗi là failed.
5. Xác minh inventory/hash/cache; publish source/receipt có staging/rollback. Không ghi manifest/references.

**Kiểm đạt:** mọi version đúng ID; bytes nguyên vẹn; no_tex khác lỗi mạng; xử lý tar/gzip/TeX đơn và archive lỗi/path traversal; viết phương pháp/giới hạn/citations.

## 5. Nguyên — References

**File:** `src/crawling/references.py`.

**Input:** ID bài chính, paper_dir, DateLookup, policy/use_cache. Pipeline truyền `OaiClient.submission_dates` thật. Fixture chỉ từng được dùng trong bộ kiểm thử lịch sử; các file test đã dọn theo yêu cầu.

1. Dùng S2 `/paper/ARXIV:{id}/references`, fields phẳng và pagination `next`; lấy đủ các trang, xử lý 429/Retry-After.
2. Giữ **mọi** hàng ở `references_all.json`, cả non-arXiv, trùng và unresolved. `references.json` là pool arXiv duy nhất phục vụ matching.
3. Giữ IDs legacy, bỏ suffix version khi lookup; ngày gửi từ OAI v1, không dùng publicationDate.
4. Đếm non-arXiv missing metadata riêng; thiếu trang/trường bắt buộc/ngày pool arXiv phải partial.
5. Receipt kiểm cả hai stores/hashes, tuổi và nguồn OAI. Partial retry lưu `.partial.json`, giữ complete store cũ.

**Bàn giao:** hai reference stores, receipt và ReferenceResult; không tải source mọi cited paper ngoài phạm vi.

**Kiểm đạt:** không mất hàng/trang; total khác unique arXiv; đúng provenance/ngày; cache không dùng dữ liệu cũ/hỏng; trình bày S2 coverage và giới hạn version-specific references.

## 6. Danh — Pipeline, số đo và báo cáo

**Files:** `pipeline.py`, `metrics.py`, `backup.py`, notebook chung, README/requirements và phối hợp Book repo.

1. Xác minh assignment/scope, cold root mới hoặc resume cùng scope. Chỉ một OAI client cho discovery/ngày references.
2. Ghi metadata/manifest sau mỗi task; gọi source từng version, references theo publication; không che pending/failed/partial.
3. Đo từ trước discovery đến toàn run, gồm nghỉ/retry; sampler RSS process tree/disk, xuất samples/errors/denominators và environment.
4. Audit metadata, raw OAI checkpoints, source inventory/hash, hai reference stores; xuất CSV/JSON/figures/report ZIP.
5. Backup cuối lượt: hai ZIP local rồi copy Drive/kiểm hash, receipt ghi cuối; lỗi không xóa corpus hoặc bản sao cũ.
6. Tổng hợp đủ phạm vi bốn người, kiểm tay độc lập, benchmark cold Colab CPU. Sao lưu corpus riêng với ZIP báo cáo.
7. Book tiếng Anh repo riêng sinh bảng/hình lúc build, GitHub Pages; chuẩn bị links nộp Moodle.

**Kiểm đạt:** counts đúng với file, denominators rõ, None khác 0, no_tex không bị bỏ, wall time không phải tổng task times, peak là observed; cold/resume/analyze và notebook môi trường sạch chạy được.

## 7. Notebook, phạm vi và bằng chứng

Danh: full `2606.15734`–`2606.20733`, preset development 100 ID đến `15833`; thử một ID dùng `end_id=15734`. Ba thành viên khác điền range thật của TA. Không dùng BERT/RoBERTa fixture làm assignment mặc định.

Bộ kiểm thử đã chạy đạt trước khi xóa theo yêu cầu. Với checkout hiện tại, thử một ID thật trên Colab, audit và kiểm tay rồi tăng scope. Bằng chứng hiện tại: 27 regression tests, notebook offline/integration và cold một bài thật; xem [OAI hiện tại](./OAI_RAW_HIEN_TAI.md). Một bài không chứng minh đủ assignment/Colab benchmark.

## 8. Kiểm tra tay và bàn giao

| Người | Kiểm độc lập | Bàn giao |
|---|---|---|
| Khánh | So ID/title/authors/version dates với arXiv; mở raw XML receipt | Phương pháp OAI, mẫu đã kiểm, giới hạn parser |
| Khang | So bytes TeX/BibTeX với archive tải độc lập; no_tex/inventory | Source filtering/format/size statistics |
| Nguyên | So vài S2 rows, pagination và ngày v1; đếm cả hai pools | Reference quality/completeness/limitations |
| Danh | So counts với manifest/files, run IDs, sampler và report | Toàn scope, benchmark/audit và Book integration |

Mỗi người bàn giao code diff, lệnh kiểm, output thực, lỗi còn lại, kiểm tay đã làm, phần viết tiếng Anh và citations đã dùng. Không ghi đã đạt nếu mới có fixture hoặc chỉ file tồn tại. Không tự gửi tin nhắn/publish/nộp bài thay nhóm khi chưa được giao.

## 9. Checklist nghiệm thu cả nhóm

- [ ] Đủ bốn assignment và mọi version, source hoặc no_tex hợp lệ.
- [ ] Metadata/references/source bytes và outstanding tasks đã kiểm độc lập.
- [ ] Thống kê đủ mẫu số, nguồn số đo và giới hạn.
- [ ] Cold benchmark Colab CPU thật; corpus/report được sao lưu.
- [ ] Code có comments/docstrings rõ và citations đầy đủ trong kế hoạch/Book.
- [ ] Public code repo + Book repo/GitHub Pages, hình/bảng sinh lúc build, nộp hai links Moodle đúng hạn.

Code crawler đã được thử; các checklist nghiệm thu toàn nhóm chưa tự động được đánh dấu chỉ vì một bài chạy success.
