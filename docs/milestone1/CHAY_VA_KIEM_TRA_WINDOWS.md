# Chạy Milestone 1 — Windows và Colab

Code hiện tại dùng **OAI-PMH `arXivRaw` duy nhất** cho discovery, metadata, lịch sử versions và ngày gửi references. Xem [cách triển khai và checklist M1](./OAI_RAW_HIEN_TAI.md). Đây là hướng dẫn chạy hiện tại; không cần các bản demo/phương án cũ.

## 1. Chuẩn bị

Mở Anaconda Prompt tại thư mục project:

```bat
conda env create -f environment.yml
conda activate arxiv-project
python -m jupyterlab
```

Đã có environment thì bỏ bước tạo; khi dependency thay đổi chạy `conda env update -f environment.yml --prune`. Chọn kernel Python của environment trong `src/notebooks/milestone1.ipynb`. Code cần Python >= 3.11. Có thể dùng venv và `python -m pip install -r src/requirements.txt` thay Conda.

Môi trường kiểm thử local `.venv` đã được dọn cùng dữ liệu/test tạm. Cần tạo environment từ YAML hoặc requirements khi chạy local lại; Colab cài dependencies bằng setup trong notebook.

## 2. Cấu hình thử đúng một bài

Notebook mặc định thử 100 ID của Danh. Muốn tải một bài, sửa dòng Danh trong `ASSIGNMENTS` thành:

```python
{'member': 'Danh', 'start_month': '2026-06', 'start_id': 15734,
 'end_month': '2026-06', 'end_id': 15734}
```

Giữ đủ bốn dòng thành viên; ba dòng còn lại có thể để None khi chọn Danh. Chọn:

```python
ALLOW_NETWORK = True
SELECTED_MEMBER = 'Danh'
MONTH_END_IDS = {}
RUN_MODE = 'cold'
EXISTING_ROOT = None
SCOPE_PURPOSE = 'development'
```

Trên Windows: `CLONE_REPOSITORY=False`, `INSTALL_DEPENDENCIES=False`, `REQUIRE_COLAB_CPU=False`. Trên Colab các tùy chọn setup/CPU được bật theo môi trường. Giữ delay arXiv/S2 mặc định **3,1 giây**, không giảm nhịp arXiv dưới 3 giây. Cả nhóm xếp lịch tuần tự vì giới hạn arXiv tính chung các máy được kiểm soát.

Restart kernel rồi Run All. Không bấm chạy thêm khi kernel đang bận. Ghi lại `Root`, `run_id`, report snapshot và ZIP. OAI discovery có log theo ID; lookup ngày reference có thể chờ vài phút, tùy số ID duy nhất và retries. Một bài có 45 arXiv references cần 46 OAI lookups ở lượt đầu.

## 3. Đọc kết quả

`success` cần discovery đủ scope, mọi source version hoàn thành hoặc `no_tex`, và references hoàn tất. Notebook chạy hết nhưng job partial/failed vẫn là dữ liệu chưa đủ.

Kiểm các bảng/hình và file sau trong report snapshot:

- `integrity_audit.csv`: metadata, source inventory/hash, hai reference stores và raw OAI checkpoints đều valid.
- `outstanding_tasks.csv`: không bỏ qua pending/failed/partial; thử lại hoặc giải thích cụ thể.
- `papers.csv`, `versions.csv`: đúng số versions, trạng thái và source bytes trước/sau lọc.
- `references_all.csv`: đủ mọi hàng S2; `references.csv`: pool arXiv, ngày gửi từ v1. Non-arXiv thiếu ngày gửi là bình thường; metadata thiếu khác được đếm riêng.
- `metadata_stats.json`: số OAI network attempts và cache hits của run.
- `benchmark.json`, resource samples/errors, environment/configuration: thời gian và tài nguyên thực đo, đúng điều kiện chạy.

So vài bài/versions với arXiv, so bytes nguồn với archive tải độc lập, so references với S2 và ngày v1. Hash chứng minh tính toàn vẹn snapshot; kiểm tay nguồn độc lập giúp đánh giá tính đúng.

Corpus gồm source, metadata, raw XML cache, receipts và manifest. **ZIP báo cáo không thay cho bản sao lưu corpus.** Giữ cả hai cho M2/M3.

## 4. Tiếp tục hoặc chỉ phân tích

```python
RUN_MODE = 'resume'
EXISTING_ROOT = r'C:\duong-dan\corpus'
```

Chọn đúng scope cũ. `resume` kiểm cache, làm mới metadata/references quá 24 giờ, retry phần lỗi. Các XML đã tra thành công được lưu ngay theo ID nên discovery bị ngắt vẫn có thể tiếp tục. Không đổi root/cold để tiếp tục một run cũ.

Muốn đọc lại snapshot mà không gọi mạng:

```python
ALLOW_NETWORK = False
RUN_MODE = 'analyze'
EXISTING_ROOT = r'C:\duong-dan\corpus'
```

Analyze lấy scope và số đo từ run đã lưu, không đo lại tốc độ crawl hay xác nhận metadata còn mới. Corpus thử local trước đây đã được xóa trong đợt dọn cuối. Khi chạy Colab, dùng đúng đường dẫn corpus được notebook in ra; không dùng đường dẫn lịch sử đã xóa.

## 5. Tăng phạm vi và benchmark Colab

Danh được giao `2606.15734`–`2606.20733` (5.000 ID). Ba người còn lại điền đúng phạm vi TA giao. Khoảng lấy cả hai đầu; nếu qua tháng thì cung cấp `MONTH_END_IDS` đã xác minh, không suy đoán ID cuối tháng.

Để chạy toàn đoạn Danh: `end_id=20733`, `SCOPE_PURPOSE='assigned'`. Nếu chia nhiều đoạn tuần tự để phù hợp phiên Colab, lưu scope/root riêng và tổng hợp không trùng/không thiếu. Không coi 100-ID trial hoặc một bài là đủ assignment.

1. Đưa code mới lên GitHub hoặc upload toàn bộ `src/` cùng notebook. Clone remote không chứa thay đổi chưa push trên máy này.
2. Mở Colab, chọn **Hardware accelerator: None**; giữ `REQUIRE_COLAB_CPU=True`.
3. Dùng runtime-local disk `/content/arxiv-data`, cold root mới, scope được ghi rõ, nhịp API/retry mặc định. Không dùng cached run làm cold benchmark.
4. Run All; kiểm coverage, integrity audit, lỗi sampler và bảng điều kiện benchmark.
5. Tải ZIP báo cáo và sao lưu corpus trước khi runtime mất. Nếu bị ngắt, giữ snapshot của lần đó, phục hồi cùng root và resume; ghi rõ cache_mode.

Thống kê toàn nhóm phải có mẫu số/cách tổng hợp rõ. Không cộng RAM peak của bốn máy rồi gọi là RAM peak quan sát của một hệ thống; không cộng thời gian các đoạn chạy song song thành wall time end-to-end.

## 6. Điều kiện hoàn thành M1

- Thu thập đủ phạm vi nhóm và mọi version; có source hoặc empty `no_tex` hợp lệ.
- Chỉ `.tex`/`.bib` nguyên byte, lệnh hình/bảng còn nguyên; giữ mọi reference local.
- Metadata, references, scope, counts và kiểm tay đạt; lỗi còn lại giải thích trung thực.
- Báo cáo đủ success rates, reference completeness, kích thước trước/sau, discovery/paper/system time, RAM peak/mean và disk peak/final.
- Benchmark cold Colab CPU thật, nguồn số đo và điều kiện chạy có thể kiểm chứng.
- Public code repo có README/requirements; Jupyter Book tiếng Anh ở repo công khai riêng, hosted GitHub Pages, sinh bảng/hình lúc build.
- Mở được hai link và nộp Moodle trước hạn TA. M1 không nộp data; corpus giữ cho các milestone sau.

## Kiểm chứng trước khi dọn

27 regression tests và hai notebook kernels offline/integration đã đạt trước khi xóa `tests/`, data và environment kiểm thử local theo yêu cầu. Các lệnh gọi file test cũ không còn áp dụng cho checkout này. Bằng chứng lịch sử được ghi trong kế hoạch; lần chạy Colab mới phải có kết quả/audit riêng. Notebook chính luôn clear outputs trước commit.

## 7. Chạy lại Colab từ bản GitHub vừa push

1. Mở [notebook từ GitHub trên Colab](https://colab.research.google.com/github/Hireophant/arXivProject/blob/master/src/notebooks/milestone1.ipynb), chọn **File → Save a copy in Drive** và đặt tên mới để phân biệt với bản cũ.
2. Nếu còn runtime cũ, sao lưu dữ liệu muốn giữ rồi chọn **Runtime → Disconnect and delete runtime**. Bước này xóa VM cũ; chỉ restart kernel không làm mới checkout đã clone. [Colab FAQ](https://research.google.com/colaboratory/faq.html).
3. Chọn **Runtime → Change runtime type → Hardware accelerator: None**, lưu và Connect. Dùng runtime CPU.
4. Ở Setup giữ `ALLOW_NETWORK=True`, `READ_COLAB_SECRET=False` nếu không dùng key. `CLONE_REPOSITORY` và `INSTALL_DEPENDENCIES` tự bật trên Colab. Repository branch là `master`.
5. Ở Assigned ranges, thử Danh **một ID** bằng `start_id=15734`, `end_id=15734`, hai tháng `2026-06`. Giữ đủ bốn dòng, `SELECTED_MEMBER='Danh'`, `MONTH_END_IDS={}`. Chọn `RUN_MODE='cold'`, `EXISTING_ROOT=None`, `SCOPE_PURPOSE='development'`, `REQUIRE_COLAB_CPU=True`; giữ delay 3,1 giây.
6. Chạy các cells Setup đến Imports trước, chờ clone/install xong. Nếu Colab yêu cầu restart vì cài dependencies, restart session rồi chạy lại Setup/Imports. Kiểm source là `/content/arXivProject`.
7. **Runtime → Run all**. Kiểm bảng environment có source revision đúng bản push, CPU-only và runtime Colab. Nếu lệch revision thì dừng trước collection, tạo VM mới và mở lại link GitHub; setup không tự pull vào checkout cũ.
8. Chờ Collection hoàn tất; một bài có hàng chục reference IDs thường cần vài phút. 429/503 có thể làm lâu hơn. Đọc `status`, audit valid và outstanding tasks; không bấm Run All liên tiếp khi đang chạy.
9. Tải report ZIP theo cell cuối. Sao lưu corpus riêng vì ZIP báo cáo không chứa toàn bộ source/cache. Ví dụ cell tùy chọn sau khi pipeline kết thúc:

```python
from google.colab import files
import shutil
corpus_zip = shutil.make_archive('/content/m1-corpus-backup', 'zip', root_dir=str(ACTIVE_ROOT))
files.download(corpus_zip)
```

10. Nếu partial/failed do dịch vụ, giữ runtime/root, đặt `RUN_MODE='resume'`, `EXISTING_ROOT` bằng **Root đã in**, giữ đúng assignment rồi chạy lại; không dùng cold để tiếp tục. Thử một bài đạt mới nâng lên 100 ID (`end_id=15833`) hoặc assignment đầy đủ (`20733`, scope_purpose assigned) ở cold root mới.

Không chạy hai notebook crawl đồng thời. Report và corpus nằm trong VM Colab tạm thời, cần tải/sao lưu trước khi xóa runtime hoặc phiên kết thúc.
