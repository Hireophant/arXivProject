# Chuẩn bị raw input M2 từ backup M1 trên Drive

Notebook: [milestone2_prepare.ipynb](../../src/notebooks/milestone2_prepare.ipynb).
Helpers: src/preparation/milestone2.py và validation.py, chỉ dùng Python >= 3.11 stdlib.

Thư mục đích đã chốt là **`preparationM2/raw_m1/<DATASET_NAME>/`**. PREPARATION_DIR đặt folder preparationM2; kết quả parser tương lai lưu riêng tại `Milestone2/parsed/<DATASET_NAME>/.`

## 1. Luồng sử dụng

1. Mở notebook bằng Colab, chọn accelerator None.
2. Đặt SOURCE_PATH tới **cả thư mục Milestone1** còn nguyên cấu trúc backup trên Drive, hoặc ZIP tải từ Drive chứa thư mục đó. Giữ checkpoint, full backup, session-report, receipts và retry-state.
3. Đặt PREPARATION_DIR tới thư mục preparationM2 riêng và DATASET_NAME đúng tài khoản, ví dụ Danh2, Khanh1. Một runtime ghi một dataset; không chạy đồng thời hai notebook cùng đích.
4. Chạy các cell theo thứ tự: cấu hình → setup/mount → preview → prepare → inventory → bàn giao.
5. Đọc preparation.json, blocked_versions.csv, backup_audit.jsonl. Khi thiếu/hỏng input, tìm lại backup gốc rồi chạy lại; notebook không crawl bù.

Ví dụ đường dẫn theo crawler M1 hiện tại:

~~~python
SOURCE_PATH = Path('/content/drive/MyDrive/arXivProject/Milestone1')
PREPARATION_DIR = Path('/content/drive/MyDrive/arXivProject/preparationM2')
DATASET_NAME = 'Danh2'
~~~

Nếu đã gom backup nhiều tài khoản/người dưới một thư mục cha, SOURCE_PATH có thể trỏ tới thư mục đó. Không bắt buộc folder phải mang tên acc1/danh: helper tìm backup receipts đệ quy. Tên DATASET_NAME chỉ đặt tên bộ output, không chứng minh nó chứa đủ bốn người.

Local dùng checkout hiện tại, sửa source/output sang đường dẫn local. File mẫu đã kiểm tra là Milestone1-20261027T125453Z-1-001.zip, queue Danh2, không phải toàn bộ nhóm. Không cần giải nén ZIP này trước.

Notebook clone repo khi chạy Colab mà chưa có checkout. **Code mới phải được push hoặc đưa lên runtime trước**; bản cũ trên GitHub thiếu helper sẽ dừng và hướng dẫn cập nhật, không tự pull đè checkout.

## 2. Dữ liệu được lưu

~~~text
preparationM2/
  raw_m1/<DATASET_NAME>/
    .prepare-owner.json
    preparation.json
    input_validation.json
    manifest.json
    inventory.csv
    blocked_versions.csv
    backup_audit.jsonl
    provenance.jsonl
    <paper_key>/
      metadata.json
      reference_result.json
      references.json
      references_all.json
      sources/
        .v1.receipt.json
        v1/**/*.tex, **/*.bib
~~~

Source .tex/.bib giữ nguyên bytes và relative paths. Metadata lấy từ publication record trong manifest; reference result đầy đủ của snapshot tốt nhất được lưu riêng thay vì lặp toàn bộ references trong manifest chung. Manifest ghi backup được chọn cho references; provenance ghi backup/fingerprint cho source từng version. Không copy metric/caches/index SQLite không cần cho parser.

corpus.zip trong session-report thường chỉ có manifest. Helper vẫn dùng manifest để biết các publication/versions expected nhưng chỉ khôi phục source khi có per-version receipt và file thật. Không lọc bài vì Semantic Scholar references lỗi/rỗng.

## 3. Schema và điều kiện bàn giao

Đầu ra chuẩn bị có schema **m2-input-1.0**, không giả làm checkpoint crawler schema 3.0. Mỗi publication trong manifest.papers có:

- record: metadata và union của mọi expected version phát hiện trong các manifest hợp lệ.
- metadata_path, downloads: kết quả source đã xác minh nếu có; nếu blocked thì giữ kết quả tải M1 gốc (gồm error/attempts), null chỉ khi chưa có record tải. Luôn dựa version_states để quyết định có được parse.
- download_evidence: backup và DownloadResult M1 được chọn; provenance.jsonl giữ lịch sử các kết quả tải, kể cả thất bại. Inventory có thêm m1_source_status/m1_error để xem lỗi gốc.
- version_states: ready_tex, empty_no_tex, blocked_input.
- references: status, path tới reference_result.json, backup nguồn và pagination flag; kết quả đầy đủ nằm trong file được trỏ tới.

Đây là contract bổ sung cho adapter src/parsing/inputs.py tương lai. Adapter phải kiểm preparation.json có run_id trùng manifest, input_validation.json cùng run/snapshot và validate_prepared_corpus trả valid=True; giữ blocked trong coverage. Không gọi crawler load_manifest/resume với schema chuẩn bị này.

| Trạng thái | Ý nghĩa |
|---|---|
| in_progress | Chưa có completion marker cho lượt hiện tại; không dùng output như bộ hoàn chỉnh |
| ready | Có publication, mọi version phát hiện có TeX hợp lệ hoặc no_tex có bằng chứng, không có lỗi backup |
| partial | Có inventory nhưng còn source thiếu/xung đột hoặc lỗi đọc/khôi phục backup; xem audit |
| failed | Không khôi phục được publication inventory đáng tin |

ready chỉ áp dụng phạm vi các manifest tìm thấy trong SOURCE_PATH, không khẳng định toàn bộ assignment M1 hay toàn nhóm đã đủ. Preview hiển thị assignment/pending count từ queue để đối chiếu; queue không được dùng để bịa metadata/versions chưa crawl.

Parser nhận `preparationM2/raw_m1/<DATASET_NAME>/` làm input. Chỉ version ready_tex được parse; empty_no_tex giữ empty; blocked_input giữ lý do. Chuẩn bị raw input không đồng nghĩa M2 đã tạo elements/hierarchy/bibtex.

Helper tự đọc lại output trước khi trả kết quả: kiểm run/schema, đủ và duy nhất mỗi inventory row, counts/status, metadata/reference artifacts, source receipts/fingerprints và hash file thật. Báo cáo input_validation.json có valid, complete, run_id, snapshot_id và issues. Notebook dừng bàn giao khi kiểm tra không đạt.

- valid=True là dữ liệu đã lưu nhất quán với contract; bộ partial có thể valid nhưng vẫn còn blocked.
- complete=True chỉ khi toàn bộ version phát hiện đã có TeX/no_tex hợp lệ và không còn lỗi backup; vẫn cần đối chiếu assignment để xác nhận đủ cả nhóm.
- snapshot_id định danh nội dung/metadata/reference result và version states, không chứa đường dẫn máy hoặc run ID. Chạy lại cùng input hoặc copy sang vị trí khác giữ cùng snapshot. Chỉnh dữ liệu sau khi ký snapshot làm kiểm tra không đạt; chạy prepare lại từ backup để sửa.

Trước khi parse sau một lần copy hoặc ở runtime mới:

~~~python
from preparation import validate_prepared_corpus
check = validate_prepared_corpus(RAW_CORPUS_ROOT)
if not check['valid']:
    raise RuntimeError(check['issues'])
print(check['snapshot_id'], check['complete'])
~~~

Danh ghi snapshot_id này vào config/manifest/checkpoint parser. Khánh đối chiếu inventory nhóm; Khang/Nguyên ghi snapshot khi tạo mẫu kiểm để cả nhóm không âm thầm dùng những bản raw khác nhau.

## 4. Kiểm chứng và chạy lại

- Kiểm corpus.zip theo SHA-256/bytes của backup_receipt.json, rồi kiểm source file list/hash/bytes theo M1 source receipt 3.0.
- JSON được đọc từng khối có giới hạn dung lượng, không cấp sẵn bộ đệm theo kích thước manifest tối đa cho mỗi file nhỏ. Kiểm đường dẫn có cache trong một lượt; hash file vẫn được đọc lại và cache không tồn tại qua các lượt kiểm.
- File provenance được parse và đối chiếu backup/fingerprint của từng version dùng được cùng download/error evidence; file tồn tại nhưng hỏng JSON hoặc thiếu bằng chứng không được coi là valid.
- Nhiều retry/checkpoint cùng publication không tạo nhiều bài; các version hợp lệ được ghép vào cùng một publication.
- Hai copy hợp lệ có bytes khác nhau cho cùng publication/version → SOURCE_CONFLICT, chặn để review; không tự chọn theo ZIP lớn nhất.
- Khi chạy lại, hash source output được kiểm lại; file hỏng được khôi phục. Hash backup vẫn được kiểm, không tin marker cũ mù quáng.
- Không ghi vào thư mục M1 hoặc thư mục đích có dữ liệu cá nhân chưa do helper tạo. Không đổi raw nguồn khi thử parser.
- Nếu Colab ngắt, output còn in_progress; chạy lại cùng cấu hình, cùng dataset. File cũ ngoài manifest mới có thể còn trên disk: parser đọc inventory/manifest, không tự glob tất cả folder rồi suy ra versions.
- Nếu runtime ngắt sau khi data được ghi nhưng trước khi ký snapshot, run/snapshot có thể chưa khớp: không bàn giao, chạy lại notebook. input_validation.json và preparation.json phải thuộc cùng run; bước kiểm tươi là bắt buộc.
- Cần đủ dung lượng cho raw output và một archive/version đang staging. Một file lỗi ghi/thiếu dung lượng không được báo source thành công; xem audit và chạy lại sau khi giải quyết.
- Lỗi khóa file tạm thời trên Windows được retry có giới hạn; quyền ghi sai hoặc lỗi còn tồn tại vẫn báo thất bại, không biến thành success.

Các tests offline dùng ZIP/receipt nhỏ và thực thi code cells của notebook:

~~~powershell
python -m unittest discover -s tests -p test_m2_preparation.py -v
~~~

Thực thi notebook qua Jupyter kernel với input thật hoặc fixture:

~~~powershell
python tests/validate_m2_preparation_notebook.py --source <M1-folder-or-ZIP> --output data/validation/m2-notebook/preparationM2 --dataset Danh2
~~~

Lệnh cuối cần môi trường Jupyter của project; notebook executed nằm trong output kiểm thử, không commit. Kết quả local không được gọi là kiểm chứng ghi Drive thật.
