# arXiv Project — Milestone 1

Resolve assigned arXiv IDs, collect **every source version**, retain TeX/BibTeX and collect reference metadata. The shared notebook audits the corpus, reports coverage, measures resources, exports tables/figures and backs up both corpus and report to Google Drive on Colab.

## Current implementation

All arXiv discovery, paper metadata, version histories and reference submission dates use **OAI-PMH `arXivRaw` only**:

```text
https://oaipmh.arxiv.org/oai
verb=GetRecord
metadataPrefix=arXivRaw
identifier=oai:arXiv.org:{base_id}
```

Submission dates come from v1; revision dates come from v2..vN. OAI `datestamp` is a metadata modification date and must not replace a submission date. There is no Query API, Atom, HTML metadata fallback or Kaggle metadata implementation.

Source downloads use `https://export.arxiv.org/src/{id}vN`. References come from the paginated Semantic Scholar `/paper/ARXIV:{id}/references` endpoint; these are separate required collection tasks. Source files are downloaded only for assigned papers.

Requests run sequentially. arXiv requests wait at least **3 seconds**; the default is **3.1 seconds**, including retries. `Retry-After` is respected. This limit applies across all machines controlled by the group, so schedule collection runs sequentially. Metadata/reference caches expire after 24 hours; raw XML checkpoints survive an interrupted discovery. Failed requests remain visible and do not trigger another metadata method.

Official sources: [arXiv OAI](https://info.arxiv.org/help/oa/index.html), [rate limits](https://info.arxiv.org/help/api/tou.html), [course statement](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/). The copied statement is [ARXIV_PROJECT_FULL.md](ARXIV_PROJECT_FULL.md); its examples describe available tools, while this repository implements the OAI method above.

## Setup and execution

Python **3.11 or later** is required. From the project root:

```bash
conda env create -f environment.yml
conda activate arxiv-project
python -m jupyterlab
```

For an existing environment, use `conda env update -f environment.yml --prune`. A pip environment can install `python -m pip install -r src/requirements.txt`. Direct dependencies are pinned; transitive dependencies are not fully locked.

Open [src/notebooks/milestone1.ipynb](src/notebooks/milestone1.ipynb), choose the correct Python kernel and configure before Run All:

- `ASSIGNMENTS`: four member rows with verified `YYYY-MM` months and numeric ID suffixes; select one with `SELECTED_MEMBER`.
- Danh's full assignment is `2606.15734`–`2606.20733` (5,000 IDs). The notebook preset is a **100-ID development trial**, ending at `15833`. For one paper, set `end_id=15734`; for the full assignment, use `20733` and `SCOPE_PURPOSE='assigned'`.
- Other assignments remain blank until supplied. Ranges include both endpoints. Cross-month ranges require verified `MONTH_END_IDS`; missing boundaries are never guessed.
- `ALLOW_NETWORK=False` skips collection. `RUN_MODE='analyze'` reads an existing corpus without network.

| Mode | Configuration | Result |
|---|---|---|
| `cold` | `EXISTING_ROOT=None`, fresh generated root | New collection and end-to-end measurements |
| `resume` | Existing corpus root, exactly the same scope | Verify cached artifacts, refresh expired metadata/references and retry incomplete work |
| `analyze` | Existing corpus root | Rebuild audits, tables, figures and ZIP from the stored run |

On Colab choose **Hardware accelerator: None**. Setup can clone the repository and install dependencies automatically. Upload the current source or push it before cloning: uncommitted local changes are not available from GitHub. `SAVE_TO_DRIVE=IN_COLAB` enables the final Drive backup. Authorize Drive when prompted after report export. Both ZIPs are compressed locally, copied and hash-verified in `MyDrive/arXivProject/Milestone1/<run_id>/<backup-attempt>/`; `backup_receipt.json` marks a completed backup. Each attempt is independent. This is an end-of-run backup, not periodic protection during collection, and is outside the crawl benchmark. Set `SAVE_TO_DRIVE=False` to opt out; local or `ALLOW_NETWORK=False` skips Drive. On a Drive failure, keep the local corpus and rerun only the backup cell; the report browser download remains available.

Colab Secrets or the `S2_API_KEY` environment variable can provide an optional Semantic Scholar key; never store keys in the notebook.

See the [run guide](docs/milestone1/CHAY_VA_KIEM_TRA_WINDOWS.md), [method and M1 checklist](docs/milestone1/OAI_RAW_HIEN_TAI.md), [plan and full citations](docs/milestone1/KE_HOACH_MILESTONE_1.md), [four-member responsibilities](docs/milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md) and [member handoff guide](docs/milestone1/HUONG_DAN_THANH_VIEN_MILESTONE_1.md).

## Modules and local outputs

| Owner | Files | Responsibility |
|---|---|---|
| Khánh | `src/crawling/discover.py` | OAI metadata, complete version history, submission dates, XML checkpoints |
| Khang | `src/crawling/download.py` | Versioned sources, safe extraction, TeX/BibTeX receipts |
| Nguyên | `src/crawling/references.py` | Complete Semantic Scholar pagination, both reference stores |
| Danh | `src/crawling/pipeline.py`, `metrics.py`, `backup.py` | Orchestration, manifests, coverage, resource measurement, exports and verified backups |

Shared contracts are in `src/crawling/__init__.py`; manifest/receipt schema is **3.0**. Start a new corpus root for this schema. Cache identity, source, timestamps and hashes are validated before reuse.

```text
<corpus>/manifest.json
<corpus>/metadata_cache/<hashed-id>.xml, <hashed-id>.json
<corpus>/<paper>/metadata.json
<corpus>/<paper>/sources/vN/**/*.tex, **/*.bib
<corpus>/<paper>/sources/.vN.receipt.json
<corpus>/<paper>/references_all.json
<corpus>/<paper>/references.json
<corpus>/<paper>/.references_receipt.json
<corpus>/metrics/run_summary.json, resource_samples.json, resource_errors.json
```

Only `.tex`/`.bib` are retained, byte-for-byte, including original figure/table commands. A valid version without TeX has an empty `no_tex` record. `references_all.json` retains **every returned reference**, including non-arXiv and unresolved rows. `references.json` is the unique arXiv matching pool; reference submission dates come from the same OAI client. Missing non-arXiv metadata is reported separately. Missing pages or required arXiv fields/dates make the job partial. A partial retry cannot overwrite a previous complete reference store.

Notebook report snapshots contain `papers.csv`, `versions.csv`, `references.csv`, `references_all.csv`, summary/benchmark/configuration/environment JSON, `metadata_stats.json`, integrity audits, outstanding tasks and PNG/SVG figures. The report ZIP contains report outputs; the separate **corpus.zip** contains sources, metadata, references, raw XML checkpoints and metrics. The Drive backup cell saves both. Only a folder with `backup_receipt.json` is a verified completed backup; integrity verification does not replace the corpus quality audit.

## Verification and submission

Before the final cleanup, **27 regression tests** and fresh offline/integration notebook kernels passed. A real one-paper cold run also passed source/reference/OAI audits and report ZIP checks. The test suite, all local crawl data and generated validation outputs were then removed at the user's request. This source-only checkout does not contain `tests/` or those historical artifacts; the recorded results are described in the [plan](docs/milestone1/KE_HOACH_MILESTONE_1.md) and [M1 checklist](docs/milestone1/OAI_RAW_HIEN_TAI.md).

For the next validation, open the notebook from the pushed GitHub version in a fresh Colab CPU runtime, collect one paper first, and inspect its actual audits and outstanding tasks. The main notebook stays clear of embedded outputs. The added backup helper was separately checked with 13 stdlib checks (real local archives/copies plus simulated Colab mount success/failure). Google Drive authorization on a real Colab session still happens in the user's browser.

To complete the actual milestone, collect all assigned ranges and versions, resolve/report outstanding issues, compare samples with independent sources, run the final **cold Colab CPU benchmark**, and maintain a **separate public English Jupyter Book repository hosted on GitHub Pages**. Its tables/figures must be generated during book compilation from real results. Submit the public code and report links through Moodle before the deadline. Local one-paper verification does not establish full coverage or the final benchmark.

M1 defines the `papers` and `references` dataset tables but submits no corpus. Preserve local data for M2/M3. The final M3 dataset has six tables: `papers`, `references`, `elements`, `hierarchy`, `bibtex`, `predictions`. Only references with arXiv IDs enter the published matching table; all crawled rows remain local. Do not commit corpus, keys, archives or notebook outputs.
