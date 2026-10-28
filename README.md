# arXiv Project — Milestone 1

Resolve assigned arXiv IDs, collect **every source version**, retain TeX/BibTeX and collect reference metadata. The shared notebook audits the corpus, reports coverage, measures resources, exports tables/figures and backs up both corpus and report to Google Drive on Colab.

## Current implementation

Assigned-paper discovery, metadata and complete version histories still use **OAI-PMH `arXivRaw`** at `https://oaipmh.arxiv.org/oai`. All available source versions are downloaded separately from `https://export.arxiv.org/src/{id}vN`. References still come from the fully paginated Semantic Scholar endpoint.

Reference submission dates now use **verified v1 cache → Cornell Kaggle metadata index → OAI fallback**. A current OAI discovery record takes priority. The notebook builds the compact SQLite index once, stores a verified immutable copy in Drive `metadata-index/`, then queries a local copy. Per-member v1 cache batches persist across sessions in `v1-cache/member-N/`. Each hybrid reference receipt carries its own date evidence, so corpus ZIPs/checkpoints remain independently auditable without the shared index. Source/manifest schema 3.0 and all existing Drive progress/backup paths are preserved; the updated reader supports both old OAI and new hybrid receipts.

Use a **new notebook/runtime after the current run finishes**; keep the same member, Drive root, queues and old ZIPs. Start with one new ID. Do not mix old reader modules with hybrid outputs. Kaggle setup failures stop explicitly; supply a local snapshot or disable Kaggle to continue with cache + OAI. See the [optimization and migration guide](docs/milestone1/TOI_UU_REFERENCE_DATES.md) for configuration, folder layout and validation.

Requests remain sequential, with arXiv pacing at least 3 seconds (default 3.1) and Retry-After respected. The limit applies across machines under the group's control: multiple accounts do not multiply arXiv quota. Schedule arXiv collection sequentially; one runtime per member also protects the Drive queue. OAI/S2 live caches expire after 24 hours; the separate verified v1 cache defaults to 365 days. Historical audits verify integrity without imposing the live freshness TTL.

Index preparation/download/copy/verification is included in pipeline wall/RAM/disk measurements; `reference_date_stats.json` identifies snapshot, cache hits, OAI fallback and cold versus reused index. No full-corpus speedup has been measured yet. Official sources: [Cornell metadata](https://www.kaggle.com/datasets/Cornell-University/arxiv), [OAI](https://info.arxiv.org/help/oa/index.html), [rate limits](https://info.arxiv.org/help/api/tou.html), [course statement](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/).

## Setup and execution

### Prepare raw inputs for Milestone 2

Open [src/notebooks/milestone2_prepare.ipynb](src/notebooks/milestone2_prepare.ipynb)
to restore an M1 Drive backup folder or downloaded ZIP into a separate
`preparationM2/raw_m1/<DATASET_NAME>/` folder. It verifies archive/source receipts,
combines versions across retries, preserves raw TeX/BibTeX and writes coverage,
provenance and blocked-version inventories. This is input preparation; the M2
parser is a later step. The helper uses only Python stdlib.

Set SOURCE_PATH, PREPARATION_DIR and DATASET_NAME, then run all cells.
The default Drive destination is `preparationM2/raw_m1/<DATASET_NAME>/`.
Preparation reads saved files back and writes input_validation.json with a
stable snapshot_id. Recheck with validate_prepared_corpus before parsing;
valid partial inputs retain their blocked versions and do not claim full coverage.
Keep one writer per dataset and the full original backup tree. New preparation
code must be available in the Colab checkout. See the
[input preparation guide](docs/milestone2/HUONG_DAN_CHUAN_BI_INPUT.md) for paths,
resume, schema m2-input-1.0 and the handoff to the future parser.

### Run Milestone 1

Python **3.11 or later** is required. From the project root:

```bash
conda env create -f environment.yml
conda activate arxiv-project
python -m jupyterlab
```

For an existing environment, use `conda env update -f environment.yml --prune`. A pip environment can install `python -m pip install -r src/requirements.txt`. Direct dependencies are pinned; transitive dependencies are not fully locked.

Open [src/notebooks/milestone1.ipynb](src/notebooks/milestone1.ipynb), choose the correct Python kernel and configure before Run All:

- All twelve account assignments (three per person) are recorded in `crawling/assignments.py` from the instructor sheet. Choose `SELECTED_MEMBER`; do not edit the assigned endpoints each visit.
- Set `NEW_PAPERS_PER_SESSION=100` or `200`. Startup progress shows saved complete/pending/unseen/next new ID; planner adds up to `MAX_RETRY_PAPERS=40` retries without counting them as new. `RETRY_ONLY=True` selects only pending work. Empty selection safely skips collection.
- Keep `RUN_MODE='cold'`, `EXISTING_ROOT=None`, `SCOPE_PURPOSE='assigned'`, automatic planning/retry/Drive enabled. One-paper smoke test: set the new-paper count to 1, not the assignment endpoint. Cross-month boundaries were verified by paced OAI GetRecord (Jan 23286, Feb 24290).
- `ALLOW_NETWORK=False` skips collection. `RUN_MODE='analyze'` reads an existing corpus without network.

| Mode | Configuration | Result |
|---|---|---|
| `cold` | `EXISTING_ROOT=None`, fresh generated root | New collection and end-to-end measurements |
| `resume` | Existing corpus root, exactly the same scope | Verify cached artifacts, refresh expired metadata/references and retry incomplete work |
| `analyze` | Existing corpus root | Rebuild audits, tables, figures and ZIP from the stored run |

On Colab choose **Hardware accelerator: None**. Setup can clone the repository and install dependencies automatically. Upload the current source or push it before cloning: uncommitted local changes are not available from GitHub. `SAVE_TO_DRIVE=IN_COLAB` enables the final Drive backup. Authorize Drive at the beginning, before collection. The mount/write check stops collection on failure. `AUTO_RETRY_FROM_DRIVE=True` carries this member's pending IDs into the next cold segment; successful source versions are restored from verified backups and revalidated. Both ZIPs are compressed locally, copied and hash-verified in `MyDrive/arXivProject/Milestone1/<run_id>/<backup-attempt>/`; `backup_receipt.json` marks a completed backup. Each attempt is independent. The account queue at `retry-state/member-N.json` registers all planned IDs before collection and acknowledges complete, audited IDs only after a verified backup. Keep this queue and its referenced ZIP folders; run only one runtime per member. Background checkpoints now save every 40 processed IDs, including partial outcomes, during collection. One worker uploads immutable snapshots while crawling continues; a two-snapshot bound provides backpressure. Pipeline measurements include checkpoint CPU/RAM/disk/upload wait. The additional final notebook export/backup remains outside the crawl benchmark. Set `SAVE_TO_DRIVE=False` to opt out; local or `ALLOW_NETWORK=False` skips Drive. On a Drive failure, keep the local corpus and rerun only the backup cell; the report browser download remains available.

Colab Secrets or the `S2_API_KEY` environment variable can provide an optional Semantic Scholar key; never store keys in the notebook.

See the [notebook usage guide](docs/milestone1/HUONG_DAN_SU_DUNG_NOTEBOOK.md), [plan, method and full citations](docs/milestone1/KE_HOACH_MILESTONE_1.md) and [four-member responsibilities](docs/milestone1/PHAN_CONG_MILESTONE_1_4_NGUOI.md).


## Milestone 2 implementation scaffold

`src/parsing/` contains typed prototypes; business functions raise `NotImplementedError`.
Read [contracts.py](src/parsing/contracts.py) for the shared schema and each function's
docstring for its inputs, implementation steps, edge cases and manual checks.
The [assignment](docs/milestone2/PHAN_CONG_MILESTONE_2_4_NGUOI.md) includes per-member
AI prompts and Danh's final merge/cleanup prompt (sections 14–15).
[Synthetic fixtures](tests/m2_support/fixtures.py) let members test independently.
The [M2 notebook template](src/notebooks/milestone2.ipynb) defaults to `RUN_PARSER=False`.
Owner tests currently have skipped placeholders; these are not completed parser tests.


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
<corpus>/metrics/run_summary.json, resource_samples.json, resource_errors.json, reference_date_stats.json
<corpus>/permanent_tasks.json  # preserved failed-task decisions for interrupted/restored retries
```

Only `.tex`/`.bib` are retained, byte-for-byte, including original figure/table commands. A valid version without TeX has an empty `no_tex` record. `references_all.json` retains **every returned reference**, including non-arXiv and unresolved rows. `references.json` is the unique arXiv matching pool; reference submission dates come from the verified hybrid resolver (legacy OAI receipts remain readable). Missing non-arXiv metadata is reported separately. Missing pages or required arXiv fields/dates make the job partial. A partial retry cannot overwrite a previous complete reference store.

Notebook shows a summary dashboard after collection and final backup. Tables preview at most five data rows; grouped diagnostics preview at most ten groups. Display units are MiB/GiB and min:sec; CSV/JSON keep numeric bytes/seconds for reproducibility. Drive size is the actual size of verified ZIPs/receipts for the current run, including checkpoint duplicates, and stays unknown without committed backup evidence.

Notebook report snapshots contain `permanent_failures.csv`, `papers.csv`, `versions.csv`, `references.csv`, `references_all.csv`, summary/benchmark/configuration/environment JSON, `metadata_stats.json`, integrity audits, outstanding tasks and PNG/SVG figures. The report ZIP contains report outputs; the separate **corpus.zip** contains sources, metadata, references, raw XML checkpoints and metrics. The Drive backup cell saves both. Only a folder with `backup_receipt.json` is a verified completed backup; integrity verification does not replace the corpus quality audit.

## Verification and submission

Run the current offline regression suite from the project root:

```bash
python -m unittest discover -s tests -v
# Optional: execute all notebook cells with fake HTTP/Drive, writing under data/validation.
python tests/validate_notebook.py
```

The suite exercises source/reference receipts, reference-date provenance, backup restoration, old queue migration, permanent/transient retries, interrupted resumes, notebook syntax and compact presentation. HTTP and Drive storage are simulated in tests; this does not replace a real Colab CPU benchmark or browser Drive authorization. The source notebook is delivered without embedded outputs.

To complete the actual milestone, collect all assigned ranges and versions, resolve/report outstanding issues, compare samples with independent sources, run the final **cold Colab CPU benchmark**, and maintain a **separate public English Jupyter Book repository hosted on GitHub Pages**. Its tables/figures must be generated during book compilation from real results. Submit the public code and report links through Moodle before the deadline. Local one-paper verification does not establish full coverage or the final benchmark.

M1 defines the `papers` and `references` dataset tables but submits no corpus. Preserve local data for M2/M3. The final M3 dataset has six tables: `papers`, `references`, `elements`, `hierarchy`, `bibtex`, `predictions`. Only references with arXiv IDs enter the published matching table; all crawled rows remain local. Do not commit corpus, keys, archives or notebook outputs.


## Multiple Colab sessions and retry

| Acc | Bắt đầu | Kết thúc | Tổng ID | File tiến độ |
|---|---|---|---:|---|
| Danh | 2606.15734 | 2606.17400 | 1,667 | `member-1.json` |
| Khánh | 2602.19870 | 2602.21536 | 1,667 | `member-2.json` |
| Khang | 2609.02834 | 2609.04500 | 1,667 | `member-3.json` |
| Nguyên | 2601.23156 | 2602.01536 | 1,667 | `member-4.json` |
| Danh1 | 2606.17401 | 2606.19067 | 1,667 | `member-5.json` |
| Danh2 | 2606.19068 | 2606.20733 | 1,666 | `member-6.json` |
| Khánh1 | 2602.21537 | 2602.23203 | 1,667 | `member-7.json` |
| Khánh2 | 2602.23204 | 2603.00579 | 1,666 | `member-8.json` |
| Khang1 | 2609.04501 | 2609.06167 | 1,667 | `member-9.json` |
| Khang2 | 2609.06168 | 2609.07833 | 1,666 | `member-10.json` |
| Nguyên1 | 2602.01537 | 2602.03203 | 1,667 | `member-11.json` |
| Nguyên2 | 2602.03204 | 2602.04869 | 1,666 | `member-12.json` |

Each person now has three accounts (base name, `1`, `2`), with 1,667 / 1,667 / 1,666 IDs. Select the account with `SELECTED_MEMBER`. Account queues use `retry-state/member-N.json`; Danh/Khánh/Khang/Nguyên retain member-1/2/3/4 and read their existing completion receipts. The planner counts/selects only IDs in the current segment while preserving all older history and pending work. Extra accounts use member-5 through member-12 as listed above.

Choose only the member and new-paper count each visit, authorize that person's own Drive BEFORE collection, and Run All. Maintain the member-row order and Drive root; one runtime per member. A completed ID is not selected again. Queues migrate existing receipt ledgers; old unregistered runs need one restore/resume to register. Transient/unknown failures rotate behind deferred IDs. Confirmed terminal failures are kept in `permanent_failures` and excluded from automatic selection; they are never counted as completed. Assignment changes or unreadable state stop instead of resetting progress.

`BACKGROUND_CHECKPOINTS=True`, `CHECKPOINT_EVERY_PAPERS=40` saves processed groups to `Milestone1/checkpoints/`. Source/receipts/cache snapshots are frozen locally before background ZIP/copy/hash/queue acknowledgement. Good source versions are restored for retries; OAI/reference caches still expire after 24 hours. Groups that fail validation remain pending. The last group (<40) is flushed and the worker joined before pipeline measurement ends. Do not assume only 39 papers can be lost: an uploading or queued group is not protected until its receipt/state commit completes.

Final raw measurements are also saved from inside the running pipeline to `Milestone1/session-reports/`, even if later UI cells never run. Its corpus ZIP is a **manifest-only stub**, not M2 source data. Completed-paper ledger pointers always identify real checkpoint/full-corpus ZIPs. The notebook's final cell additionally saves the full session corpus and the richer report/audit/figures in the normal run folder. Browser report download defaults off (`DOWNLOAD_REPORT_ZIP=False`) because Drive retains the reports.

Closing a tab or powering off the client does not guarantee that Colab will keep executing. A lost runtime can require redownloading work without a committed checkpoint. Open a new session later to read Drive progress. If continuing in the same runtime, wait for the current pipeline/backup to finish, change the new-paper count if desired, then rerun configuration and all later cells (or Run All); each cold visit gets a new root. When only the final backup fails, retry that cell rather than starting another collection. A background-worker error stops collection and preserves local stage/pending IDs; use a new planned visit or explicit resume after fixing Drive.

For the Book, preserve each member's entire `Milestone1` tree (including `retry-state`, `checkpoints`, `session-reports`, and full backups). Copy each tree under a different member folder, retaining all twelve account queues and their referenced receipts. The crawler exports per-session measurements, manifests, new/retry roles and verified backups. Cross-session and group aggregation belongs to the separate report repository: verify receipt/archive hashes, deduplicate papers and versions across checkpoints/final backups/retries, and generate the Book's statistics there. Interrupted cumulative-prefix measurements stay marked incomplete; do not sum checkpoint and final measurements of one run. Use the checkpoint ledger to locate real source corpus ZIPs for M2; session-report corpus stubs are insufficient.

## Permanent failure policy

Source HTTP 404/410, S2 not_found/404/410 and missing OAI records are excluded from automatic task retries. HTTP 429, 408, 5xx and transport timeouts remain retryable; unfamiliar errors stay visible for review. A source 404 does **not** prove a PDF-only submission. Only validated source payloads can produce `no_tex`, which keeps its empty version directory and receipt and is not counted as TeX success. Invalid scope IDs fail validation before any request rather than entering a malformed queue.

Decisions are per task. A paper with source 404 and S2 429 stays pending until the S2 task is resolved; the source 404 is not requested again after resume or restoration. A paper is quarantined only when every remaining unresolved task is permanent. `no_tex` is already a resolved source outcome, so references can still be recovered. Integrity failures always stay pending for repair. A completed operational paper can include verified `no_tex`; full-TeX coverage is reported separately.

Verified checkpoints/final backups retain the failure evidence before queue acknowledgement. Existing queues are migrated once per referenced report archive after checking its receipt hash, preserving completion history and assignments. Missing/corrupt evidence stops migration without deleting pending IDs. No Drive data is modified by merely upgrading local source; the new notebook applies migration on the next planned session.

“Permanent” is an automatic retry policy, not a claim that an upstream resource can never appear. For a deliberate recheck, use `RUN_MODE='resume'`, set `EXISTING_ROOT` to that saved corpus and `RETRY_PERMANENT_FAILURES=True`. Restore the actual corpus first if it is only on Drive; report-only stubs are insufficient. This option is rejected for automatic cold planning. Keep it false for normal sessions and do not delete queue/receipt files to force retries.
