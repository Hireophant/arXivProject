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

## Environment and running

Use Python 3.11 or later. The prototype imports only the standard library.
For the intended notebook environment, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/requirements.txt
.\.venv\Scripts\python.exe -m jupyterlab
```

Open `src/notebooks/milestone1.ipynb` and select the environment's Python kernel.
The default cells only inspect fixtures. Real calls are gated by `RUN_... = False`
in the setup cell. After implementation, edit your flag to `True`, restart the
kernel and run your section (or Run All with other flags off). Reset flags before
committing. Dependencies are
provisional, not a verified lockfile. Record tested versions after implementation.
On Colab, load the source tree, configure the `src` path and install requirements;
the final performance benchmark must use CPU-only mode.

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
