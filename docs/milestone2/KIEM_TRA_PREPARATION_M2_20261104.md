# Kiểm tra preparation Danh2 và sửa lỗi chạy M2 — 04/11/2026

## Đầu vào đã xác minh

File người dùng cung cấp: `preparationM2-20261104T113728Z-1-001.zip` trong Downloads.
Đây là ZIP tải từ Drive bọc ngoài transport ZIP và receipt, không phải raw root để
trỏ trực tiếp vào parser. Transport bên trong:
`Danh2-d7db8153bb9111e26f61944e99edc8b3b43a50e8dcb78a07584b20844cf9d25a-50ed0574.zip`.

- SHA-256 khớp receipt: `fe12b8630d05d1c0a6ef4d827dd62c7e17efe89e5b8943ae408cb5b557ed3ae8`.
- Đã stage và kiểm toàn bộ raw: 1.666 bài / 2.189 versions; 2.100 ready TeX,
  82 verified no-TeX, 7 blocked. `valid=True`, `complete=False`, không còn batch pending.
- Snapshot: `d7db8153bb9111e26f61944e99edc8b3b43a50e8dcb78a07584b20844cf9d25a`.
- Không sửa ZIP gốc hoặc raw. Đây là tài khoản Danh2, không phải toàn bộ assignment nhóm.

## Thay đổi đã thực hiện

1. Sửa D3 với list lồng/đoạn sát wrapper; hỗ trợ nhãn tường minh, description và
   options chỉ dãn cách. Nhãn chứa command/structure chưa hỗ trợ vẫn error.
   Enumerate giữ ordered body/source/subtype để lưu working khi cấu trúc hợp lệ,
   nhưng numbering/style chưa review vẫn error, không tự publish.
2. Phân biệt `kern` (dimension) với `hskip/vskip` (glue); không nuốt chữ `plus/minus`
   dư, không tạo item giả từ khoảng dãn dòng đã nhận dạng chắc chắn.
3. Giữ label/comment/layout trong formula/figure của cả cha lẫn leaf; so coverage
   float như vùng được bảo vệ. Công thức, bảng và ảnh không bị chuyển nhầm kind.
4. Truyền `macro_context` tùy chọn từ gather của đúng version sang normalize_tree.
   Chỉ mở math alias có bằng chứng khai báo; giữ argument/label, literal/URL và dấu `*`.
   Khai báo mới chưa hỗ trợ làm mất hiệu lực bằng chứng cũ; providecommand không
   đè định nghĩa đã có, let sao chép nghĩa tại thời điểm khai báo. Không đổi wire schema.
5. Comments giữa command/optional/mandatory arguments được coi là TeX whitespace:
   sửa heading rỗng và citation/formatting bỏ sót đối số.
6. Root có documentclass trong included packages: lần theo active include tới
   document owner duy nhất. Literal documentclass không tạo root giả; class options
   vẫn được nhận. Hai document owners hoặc nhiều roots vẫn lỗi, không đoán theo tên file.
   Include resolver được đưa về một helper dùng chung; bỏ `_strip_line_comment`
   sau khi rg xác nhận không còn callers.
7. Retry Windows sharing lock nằm riêng trong parser M2 cho publish
   và atomic manifest M2; preparation được trả nguyên trạng theo yêu cầu người dùng: tối đa 5 lần, chỉ WinError 5/32/33; lỗi khác propagate.
   Không bỏ staging/read-back/hash hay ghi đè output tốt. M1 business logic không đổi.
8. Notebook hiển thị counts/status/path thực thay vì dump mọi diagnostic; audit đầy
   đủ vẫn nằm trên disk. Source notebook không nhúng outputs; không commit/push.

## Tối ưu đã được người dùng đồng ý

- D3 content đã giống byte-for-byte thì không tokenize hai lần để so lại.
- Citation được phân tích một lần/element trong mỗi lượt validate publication;
  vẫn kiểm và phát lỗi theo từng version, kể cả key trước một citation malformed.
- Không cache qua publication/run, không bỏ validation, không thêm worker.
- Đối chiếu riêng 5 bài thật, cùng logic sửa lỗi trước/sau tối ưu: **18,90 → 9,06 giây**,
  toàn bộ parsed payload kể cả diagnostics có SHA-256 giống hệt. Đây là đo local
  trên mẫu, không cam kết tốc độ full corpus hay benchmark CPU Colab.

## Kiểm chứng và cách chạy

Bộ test cuối: **294 PASS, 0 FAIL, 0 SKIP** (253 M2, 41 M1) trong môi trường
conda Python 3.11.17 với dependencies đã khóa. Một số lượt trước gặp WinError 5
ở test M1 `test_source_404_and_s2_429_only_retries_s2_then_quarantines` /
`test_new_account_has_independent_queue`; log được giữ, lượt cuối toàn suite đã qua
không sửa code crawling M1. Các ca sửa lỗi có test RED → GREEN.
Regression, profile, before/after payloads,
source hashes và audit nằm dưới `data/milestone2-dev/prepared-check-e63280e6/`.
Review độc lập phát hiện các edge cases đã được bổ sung test/sửa lại; không tự
thay reviewer con người cho source/PDF/bibliography.

- `baseline/summary.json`: 50 bài / 89 versions, 22 failed, 40 bài ghi working,
  8 export-ready. Mẫu cố ý gồm các input blocked, không đại diện tỷ lệ toàn shard.
- `delivered/summary.json`: kết quả trên cùng mẫu với code cuối; file chứa code SHA,
  stage timings và mọi audit. Kết quả: **4 parsed, 62 partial, 9 failed, 7 empty_no_tex, 7 blocked_input**;
  **47/50 bài ghi và đọc lại working**, 8/50 export-ready. Nhận diện thêm source có
  nhiều document thật được giữ ambiguous; không tự chọn main và bỏ supplementary.
- `notebook-smoke/`: chạy notebook thật trên 3 bài/8 versions có source bytes đối
  chiếu với ZIP mới. Cả 3 working publications được đọc lại; status vẫn partial.
- `review-needed.csv`: input thiếu, root/citation/bibliography cần quyết định.

Đã tạo hai notebook preset **local**, cùng gọi source hiện tại, không nhúng parser:

- `data/milestone2-dev/prepared-check-e63280e6/Danh2-local-pilot.ipynb`: 3 bài thật
  để người phụ trách mở kiểm output.
- `data/milestone2-dev/prepared-check-e63280e6/Danh2-local-full.ipynb`: toàn bộ raw
  đã stage. Chọn kernel conda `arxiv-project`; Run All sẽ chạy thật và tạo output
  local riêng. Benchmark/Drive backup tắt, strict bật; partial/failed không publish.

Trên Colab, cần checkout chứa các sửa local này, giải nén ZIP tải Drive để lấy
transport ZIP + receipt, mount Drive, đặt PREPARED_ARCHIVE tới ZIP **bên trong**,
RAW_CORPUS_ROOT/OUTPUT_ROOT trên local Colab, STAGE_INPUT=True, RUN_PARSER=True.
Không dùng path Windows của preset local trên Colab. Trên Colab cần cập nhật checkout
tới commit tích hợp mới nhất và dùng runtime/module cache sạch. CPU benchmark/Drive durability/Book-Pages là
các bước riêng, chưa được chứng minh bằng local smoke.

## Phần không thể tự xác nhận hoàn thành

Người dùng xác nhận chưa có backup khác; giữ 7 versions blocked:

| ID / version | Bằng chứng M1 |
|---|---|
| 2606.19457 v2 | Source HTTP 404 |
| 2606.19913 v1 | Case-colliding archive paths |
| 2606.19996 v2 | Source HTTP 404 |
| 2606.20274 v2 | Source HTTP 404 |
| 2606.20366 v1, v2 | Nguồn hỏng/chưa nhận dạng; chưa xác minh no-TeX |
| 2606.20466 v1 | Case-colliding archive paths |

Ngoài ra còn root thực sự ambiguous, body rỗng/section chưa hỗ trợ, citation/key
conflicts, bibliography thiếu và identity không đủ bằng chứng. Không tự ký review,
đổi strict để quảng cáo thành công hoặc coi các diagnostics lặp là số cặp unique.
Danh/Khánh/Khang/Nguyên cần xử lý review queue; coverage toàn nhóm, Colab CPU và
Book/Pages còn pending. Code có thể chạy và ghi audit/working thật; **chưa có cơ sở
gọi toàn bộ M2 hoàn thành hay mọi publication export-ready**.


## Cập nhật 05/11/2026 — giữ preparation nguyên trạng

- Theo yêu cầu người dùng, trả `src/preparation/milestone2.py` đúng bản HEAD;
  cả `src/preparation/` và notebook prepare không còn diff. Không cần chạy lại prepare.
- Retry xuất output nằm riêng trong `parsing.serialization`, không import helper
  từ preparation. M2 tiếp tục dùng snapshot raw đã chuẩn bị và đã kiểm trước đó.
- Sửa kiểm tra heading: title không rỗng là outline metadata, có thể không có con
  (ví dụ marker Appendix). Không coi heading như paragraph/item rỗng. Vẫn giữ kiểm
  heading rỗng, heading_level, document/container leaf, D3, FK và occurrence integrity.
- Test tái hiện Appendix marker đã FAIL trước sửa và PASS sau sửa. Cả 295 tests
  cuối đều PASS, 0 fail/skip. Không sửa business logic M1.
- Kiểm lại hai bài thật `2606.19508` và `2606.20283`, v1/v2: cả 4 phiên bản đã
  ghi và đọc lại working thành công, vẫn partial/export_ready=False vì các lỗi
  nội dung/citation/bibliography còn lại. Evidence ở `appendix-repair.json` và
  `appendix-repair/` trong thư mục prepared-check. Chưa chạy lại toàn bộ pilot50
  sau sửa heading này; giữ thống kê pilot cũ với đúng source hashes của nó.
- Trạng thái tại lượt kiểm thử trước yêu cầu push: chưa commit/push. Nguồn thiếu và review của người phụ trách vẫn pending.

## Bàn giao Drive cho bốn người và M3 — 05/11/2026

- Bản parser trước phần cập nhật Drive đã push trong commit `92d4def`.
- Notebook M2 bật backup mặc định, mount Drive khi bắt đầu parse/benchmark trên
  Colab. Chọn `MEMBER_NAME` và `DATASET_NAME`; đích lưu là
  `MyDrive/arXivProject/Milestone2/parsed/<member>/<dataset>/<run_id>/`.
- Giữ mọi ZIP và receipt, kể cả batch chỉ có metadata. Backup bao gồm working/
  published/checkpoints, audit của bài lỗi, profile, metrics, environment/timing,
  lỗi cấp run và `run_manifest.json` đầy đủ. `manifest.json` trong từng ZIP vẫn là
  manifest của riêng batch, tương thích restore hiện tại.
- Metadata không đổi có thể nằm trong batch trước. Receipt có `batch_number`
  và `metadata_files` đầy đủ để xác định trạng thái và hash cần dùng; không chỉ
  lấy ZIP cuối, không cộng trùng metrics tích lũy của cùng một run.
- Cho M3, giữ cả preparationM2 gốc/receipts và backup M2 của cả bốn người. Chọn
  publication export-ready sau review; giữ partial/failed làm bằng chứng sửa tiếp.
  Không thay đổi preparation hay schema/API consumer trong lượt cập nhật này.
- Kiểm cuối: **303 tests PASS, 0 fail/skip**, gồm M1 regression, notebook smoke và
  pipeline thật xuyên parse/export/read-back/backup/restore trên filesystem local.
  Reviewer không còn phát hiện chặn. Log local:
  `data/milestone2-dev/prepared-check-e63280e6/drive-handoff-final-regression.log`.
  Chưa kiểm Google Drive thật/Colab, toàn corpus, Book/Pages và review tay; bảy
  phiên bản thiếu nguồn vẫn giữ nguyên trạng thái. Chưa gọi M2 hoàn thành.
