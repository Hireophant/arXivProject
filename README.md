# arXiv Project — Milestone 1 prototype

This repository currently contains **interfaces and fixtures only**. Every business
function raises `NotImplementedError`. It does not yet crawl, benchmark, or complete
Milestone 1. No assigned arXiv range has been received.

## Structure and ownership

| File | Responsibility |
|---|---|
| `src/crawling/__init__.py` | Shared TypedDict schemas and callable protocols |
| `src/crawling/fixtures.py` | Synthetic input/output samples; no network requests |
| `discover.py` | Member 1: discovery, metadata, version history, reference dates |
| `download.py` | Member 2: versioned sources, safe extraction, text retention |
| `references.py` | Member 3: Semantic Scholar references and metadata |
| `pipeline.py`, `metrics.py` | Member 4: integration, resume, measurements, summaries |
| `src/notebooks/milestone1.ipynb` | Local Jupyter entry point and fixture walkthrough |

## Cài môi trường và chạy bằng Conda

Dùng **Miniconda hoặc Anaconda**. File `environment.yml` khai báo môi trường
**`arxiv-project`**, Python **3.11** và các thư viện cần cho notebook.

### 1. Cài lần đầu

Mở Terminal trên macOS/Linux hoặc **Anaconda Prompt** trên Windows, chuyển vào
thư mục repository `arXivProject`. Ví dụ trên macOS:

```bash
cd ~/Documents/arXivProject
```

Tạo môi trường một lần, kích hoạt rồi mở JupyterLab:

```bash
conda env create -f environment.yml
conda activate arxiv-project
python -m jupyterlab
```

Nếu môi trường `arxiv-project` đã được tạo trên máy, bỏ qua lệnh tạo và dùng các
lệnh ở phần bên dưới. Không cần tạo thêm `.venv` hoặc cài lại bằng pip khi dùng Conda.

### 2. Chạy những lần sau

Mở terminal tại thư mục project rồi chạy:

```bash
conda activate arxiv-project
python -m jupyterlab
```

Trong JupyterLab:

1. Mở `src/notebooks/milestone1.ipynb`.
2. Chọn kernel **Python 3 (ipykernel)** của môi trường vừa kích hoạt.
3. Chọn **Run → Run All Cells** để chạy các cell mặc định với dữ liệu mẫu.

Nếu dùng VS Code, mở notebook rồi chọn **Select Kernel → Python Environments →
arxiv-project**.

**Tình trạng hiện tại:** notebook chạy dữ liệu mẫu (fixture); các hàm crawler thật
vẫn còn `NotImplementedError`. Chạy notebook thành công chưa có nghĩa crawler đã
hoạt động. Các cờ `RUN_...` mặc định là `False`. Sau khi triển khai phần của mình,
đổi cờ tương ứng thành `True`, restart kernel rồi chạy phần đó; giữ cờ các phần
khác ở `False`. Trả cờ về `False` trước khi commit.

### 3. Dừng chạy

Nhấn **Ctrl+C** tại terminal đang chạy JupyterLab và xác nhận dừng nếu được hỏi.
Sau đó thoát môi trường:

```bash
conda deactivate
```

### 4. Cập nhật thư viện

Khi `environment.yml` thay đổi, chạy tại thư mục project:

```bash
conda env update -f environment.yml --prune
```

Giữ danh sách thư viện trong `environment.yml` và `src/requirements.txt` đồng bộ.
File `requirements.txt` vẫn dùng cho pip/Colab. YAML khai báo Python và các phụ
thuộc trực tiếp, chưa phải lockfile khóa chính xác mọi phiên bản trên mọi hệ điều hành.

### 5. Nếu không kích hoạt được Conda

Nếu `conda activate` yêu cầu khởi tạo shell, trên macOS dùng Zsh chạy:

```bash
conda init zsh
```

Nếu dùng Bash, chạy `conda init bash`. Đóng rồi mở lại terminal, sau đó chạy lại
`conda activate arxiv-project`. Trên Windows, dùng **Anaconda Prompt**.

Đã kiểm tra trên **macOS Apple Silicon, Python 3.11.17**: import thành công các thư
viện và thực thi toàn bộ notebook với các cờ mặc định chỉ dùng fixture.

Trên Colab, tải/clone source, cấu hình đường dẫn `src` và cài
`src/requirements.txt`. Benchmark cuối cùng phải chạy ở chế độ **CPU-only**.

## Data and reporting

Keep corpus, temporary archives, logs and credentials outside versioned source.
Semantic Scholar credentials, if used, belong in `S2_API_KEY` or Colab Secrets.
Do not commit scraped outputs embedded in notebook cells. Never report fixture
timings or reference counts as measured results.

The English milestone report belongs to a separate public Jupyter Book repository
on GitHub Pages. Tables and figures must be generated during book compilation from
saved real results. Final submission for Milestone 1 consists of the public code
repository link and report link through Moodle, not an intermediate data upload.

Implementation guidance in Vietnamese: [member onboarding and handoff guide](docs/milestone1/HUONG_DAN_THANH_VIEN_MILESTONE_1.md).
Full specification: [ARXIV_PROJECT_FULL.md](ARXIV_PROJECT_FULL.md).
