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

- All four full assignments are recorded in `crawling/assignments.py` from the instructor sheet. Choose `SELECTED_MEMBER`; do not edit the assigned endpoints each visit.
- Set `NEW_PAPERS_PER_SESSION=100` or `200`. Startup progress shows saved complete/pending/unseen/next new ID; planner adds up to `MAX_RETRY_PAPERS=40` retries without counting them as new. `RETRY_ONLY=True` selects only pending work. Empty selection safely skips collection.
- Keep `RUN_MODE='cold'`, `EXISTING_ROOT=None`, `SCOPE_PURPOSE='assigned'`, automatic planning/retry/Drive enabled. One-paper smoke test: set the new-paper count to 1, not the assignment endpoint. Cross-month boundaries were verified by paced OAI GetRecord (Jan 23286, Feb 24290).
- `ALLOW_NETWORK=False` skips collection. `RUN_MODE='analyze'` reads an existing corpus without network.

| Mode | Configuration | Result |
|---|---|---|
| `cold` | `EXISTING_ROOT=None`, fresh generated root | New collection and end-to-end measurements |
| `resume` | Existing corpus root, exactly the same scope | Verify cached artifacts, refresh expired metadata/references and retry incomplete work |
| `analyze` | Existing corpus root | Rebuild audits, tables, figures and ZIP from the stored run |

On Colab choose **Hardware accelerator: None**. Setup can clone the repository and install dependencies automatically. Upload the current source or push it before cloning: uncommitted local changes are not available from GitHub. `SAVE_TO_DRIVE=IN_COLAB` enables the final Drive backup. Authorize Drive at the beginning, before collection. The mount/write check stops collection on failure. `AUTO_RETRY_FROM_DRIVE=True` carries this member's pending IDs into the next cold segment; successful source versions are restored from verified backups and revalidated. Both ZIPs are compressed locally, copied and hash-verified in `MyDrive/arXivProject/Milestone1/<run_id>/<backup-attempt>/`; `backup_receipt.json` marks a completed backup. Each attempt is independent. The member queue at `retry-state/member-N.json` registers all planned IDs before collection and acknowledges complete, audited IDs only after a verified backup. Keep this queue and its referenced ZIP folders; run only one runtime per member. Background checkpoints now save every 40 processed IDs, including partial outcomes, during collection. One worker uploads immutable snapshots while crawling continues; a two-snapshot bound provides backpressure. Pipeline measurements include checkpoint CPU/RAM/disk/upload wait. The additional final notebook export/backup remains outside the crawl benchmark. Set `SAVE_TO_DRIVE=False` to opt out; local or `ALLOW_NETWORK=False` skips Drive. On a Drive failure, keep the local corpus and rerun only the backup cell; the report browser download remains available.

Colab Secrets or the `S2_API_KEY` environment variable can provide an optional Semantic Scholar key; never store keys in the notebook.

See the [notebook usage guide](docs/milestone1/HUONG_DAN_SU_DUNG_NOTEBOOK.md), [plan, method and full citations](docs/milestone1/KE_HOACH_MILESTONE_1.md) and [four-member responsibilities](docs/milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md).

## Modules and local outputs

| Owner | Files | Responsibility |
|---|---|---|
| Khánh | `src/crawling/discover.py` | OAI metadata, complete version history, submission dates, XML checkpoints |
| Khang | `src/crawling/download.py` | Versioned sources, safe extraction, TeX/BibTeX receipts |
| Nguyên | `src/crawling/references.py` | Complete Semantic Scholar pagination, both reference stores |
| Danh | `src/crawling/pipeline.py`, `metrics.py`, `backup.py`, `sessions.py`, `assignments.py`, `checkpoints.py`, `reports.py` | Orchestration, manifests, coverage, resource measurement, exports and verified backups |

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

Before the final cleanup, **27 regression tests** and fresh offline/integration notebook kernels passed. A real one-paper cold run also passed source/reference/OAI audits and report ZIP checks. The test suite, all local crawl data and generated validation outputs were then removed at the user's request. This source-only checkout does not contain `tests/` or those historical artifacts; the recorded results are described in the [plan](docs/milestone1/KE_HOACH_MILESTONE_1.md).

For the next validation, open the notebook from the pushed GitHub version in a fresh Colab CPU runtime, set NEW_PAPERS_PER_SESSION=1 first, and inspect its actual audits and outstanding tasks. The main notebook stays clear of embedded outputs. The earlier cross-session feature passed 17 checks; current flexible planning/background backup/aggregation verification is recorded in plan section 13, including real pipeline/notebook cells with HTTP and Colab boundaries simulated. Google Drive authorization on a real Colab session still happens in the user's browser.

To complete the actual milestone, collect all assigned ranges and versions, resolve/report outstanding issues, compare samples with independent sources, run the final **cold Colab CPU benchmark**, and maintain a **separate public English Jupyter Book repository hosted on GitHub Pages**. Its tables/figures must be generated during book compilation from real results. Submit the public code and report links through Moodle before the deadline. Local one-paper verification does not establish full coverage or the final benchmark.

M1 defines the `papers` and `references` dataset tables but submits no corpus. Preserve local data for M2/M3. The final M3 dataset has six tables: `papers`, `references`, `elements`, `hierarchy`, `bibtex`, `predictions`. Only references with arXiv IDs enter the published matching table; all crawled rows remain local. Do not commit corpus, keys, archives or notebook outputs.


## Multiple Colab sessions and retry

| Member | Assigned inclusive range | IDs |
|---|---|---:|
| Danh | 2606.15734–2606.20733 | 5,000 |
| Khánh | 2602.19870–2603.00579 | 5,000 |
| Khang | 2609.02834–2609.07833 | 5,000 |
| Nguyên | 2601.23156–2602.04869 | 5,000 |

Choose only the member and new-paper count each visit, authorize that person's own Drive BEFORE collection, and Run All. Maintain the member-row order and Drive root; one runtime per member. A completed ID is not selected again. Queues migrate existing receipt ledgers; old unregistered runs need one restore/resume to register. Retry failures rotate behind deferred IDs, so a permanent upstream not_found cannot block other pending work. Assignment changes or unreadable state stop instead of resetting progress.

`BACKGROUND_CHECKPOINTS=True`, `CHECKPOINT_EVERY_PAPERS=40` saves processed groups to `Milestone1/checkpoints/`. Source/receipts/cache snapshots are frozen locally before background ZIP/copy/hash/queue acknowledgement. Good source versions are restored for retries; OAI/reference caches still expire after 24 hours. Groups that fail validation remain pending. The last group (<40) is flushed and the worker joined before pipeline measurement ends. Do not assume only 39 papers can be lost: an uploading or queued group is not protected until its receipt/state commit completes.

Final raw measurements are also saved from inside the running pipeline to `Milestone1/session-reports/`, even if later UI cells never run. Its corpus ZIP is a **manifest-only stub**, not M2 source data. Completed-paper ledger pointers always identify real checkpoint/full-corpus ZIPs. The notebook's final cell additionally saves the full session corpus and the richer report/audit/figures in the normal run folder. Browser report download defaults off (`DOWNLOAD_REPORT_ZIP=False`) because Drive retains the reports.

Closing a tab or powering off the client does not guarantee that Colab will keep executing. A lost runtime can require redownloading work without a committed checkpoint. Open a new session later to read Drive progress. If continuing in the same runtime, wait for the current pipeline/backup to finish, change the new-paper count if desired, then rerun configuration and all later cells (or Run All); each cold visit gets a new root. When only the final backup fails, retry that cell rather than starting another collection. A background-worker error stops collection and preserves local stage/pending IDs; use a new planned visit or explicit resume after fixing Drive.

For the Book, preserve each member's entire `Milestone1` tree (including `retry-state`, `checkpoints`, `session-reports`, and full backups). Copy each tree under a different member folder. `aggregate_reports([state_paths...], output_dir)` in `crawling.reports` rebases known receipt layouts to those copied trees, verifies source/report ZIP hashes, and generates `papers_unique.csv`, `attempts.csv`, `benchmark_runs.csv`, `summary.json`. One base ID is counted once; new/retry roles and all run timing remain available. Interrupted cumulative-prefix measurements stay marked incomplete; do not sum checkpoint and final measurements of one run. Book tables/plots should read these outputs during build; this helper does not create/publish the Book itself.
