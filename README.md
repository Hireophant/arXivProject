# arXiv Project — Milestone 1

Collect all versions of assigned arXiv papers, source text, paper metadata and
Semantic Scholar reference metadata. The shared notebook runs the implemented
pipeline, audits outputs, computes corpus statistics, measures resources and
exports an English-report data bundle. Collection always uses real services.

## Ownership

| Member | Module | Responsibility |
|---|---|---|
| Khánh | `src/crawling/discover.py` | Scope discovery, verified version history, metadata and submission dates |
| Khang | `src/crawling/download.py` | Explicit version downloads, safe extraction, text retention and source receipts |
| Nguyên | `src/crawling/references.py` | Semantic Scholar pagination, reference metadata and reference receipts |
| Danh | `src/crawling/pipeline.py`, `metrics.py` | Checkpoints/resume, orchestration, statistics, resources and report exports |

The shared types and callable contracts are in `src/crawling/__init__.py`.
Use one notebook: `src/notebooks/milestone1.ipynb`. The older milestone planning
documents describe development stages; follow the current notebook for execution.
No official assigned scope has been recorded in this integration work. The configuration contains four blank member assignments. No screenshot values
are treated as the official scope, and no default paper is collected.

## Local setup

From the project directory, using Miniconda or Anaconda:

```bash
conda env create -f environment.yml
conda activate arxiv-project
python -m jupyterlab
```

For an existing environment, skip creation. When the YAML changes:

```bash
conda env update -f environment.yml --prune
```

Open `src/notebooks/milestone1.ipynb` with the environment's Python kernel.
Python >= 3.11 is required. Direct dependency versions are pinned in
`environment.yml` and `src/requirements.txt`; this is not a full transitive lockfile.
The existing validation environment is not proof of a fresh pinned installation.

## Notebook workflow

The notebook contains 24 cells organized around the project rather than separate
member test runs:

1. Local/Colab source setup and optional installation.
2. Four blank assigned ranges, selected member, run mode, HTTP policy and output paths.
3. Actual machine, package versions and source revision.
4. One complete pipeline call using all real default dependencies.
5. Coverage, reference completeness and per-paper/per-version tables.
6. Output/receipt integrity audit and outstanding-task diagnostics.
7. Corpus outcome, paired size and processing-time figures.
8. End-to-end benchmark table and RAM/disk traces.
9. Per-run exports and downloadable report ZIP.
10. Interpretation, methods, manual verification and milestone handoff.

Default `ALLOW_NETWORK=False`; clone/install are also off. This default loads
setup and instructions without crawling. To collect, set `ALLOW_NETWORK=True`,
fill the selected member assignment and choose a run mode before Run All:

| RUN_MODE | Configuration | Behavior |
|---|---|---|
| `cold` | Fresh generated root; `SCOPE_PURPOSE` describes development or assigned scope | Download new data and measure the full pipeline |
| `resume` | `EXISTING_ROOT` points to saved manifest; selected range matches exactly | Recheck discovery and let file owners validate receipts before reuse |
| `analyze` | `EXISTING_ROOT` points to a completed run | Rebuild tables/figures/exports from stored measurements without network |

Fill `ASSIGNMENTS` with four rows, one per member. Each row has `member`,
`start_month`, `start_id`, `end_month`, `end_id`. Months use `YYYY-MM`; IDs are
numeric suffixes. Set `SELECTED_MEMBER` to choose which row this notebook runs.
All four range values are initially None; collection is blocked if the selected
row is incomplete. Both ends are included. Output roots are separated by member.

For a same-month row the notebook creates the unchanged range Scope. For a row
crossing months, set `MONTH_END_IDS` to the verified last ID for each month before
the final month. The notebook then builds an IDs Scope using the existing schema.
Missing month boundaries cause an error before any collection; they are never
guessed from a screenshot or an assumed monthly maximum. Analyze mode reads the
saved scope and does not require filling the four rows. Each run has a new run_id and its own report snapshot.
A cold collection is not automatically followed by a second resume call.
The group must collect and report all four assignments before claiming full coverage.

Interrupted runs preserve checkpoints and sampler errors. Resume their printed
root; do not delete prior data. When reading an older run_summary, ensure run_id
matches the manifest. Partial/failed collection still produces diagnostics; a
successful notebook execution does not imply complete corpus collection.

## Colab CPU benchmark

1. Commit/push the intended source revision to the shared repository, or upload
   the source directory together with the notebook. A GitHub clone uses the
   remote `master`, not uncommitted local edits.
2. Upload/open the notebook in Colab and choose **Runtime → Change runtime type →
   Hardware accelerator: None**, as described in the
   [official Colab FAQ](https://research.google.com/colaboratory/faq.html).
3. Enable `ALLOW_NETWORK`, and enable `CLONE_REPOSITORY`/`INSTALL_DEPENDENCIES`
   only when needed. The setup can clone
   [the project repository](https://github.com/Hireophant/arXivProject) and install
   `src/requirements.txt`. Restart the runtime if installation requires it.
4. Fill the selected member's assigned range, choose `RUN_MODE='cold'`
   and `REQUIRE_COLAB_CPU=True`; Run All. Keep benchmark files on runtime-local
   disk under `/content/arxiv-data` and copy them out after measurement.
5. Review discovery issues, source/reference outcomes, integrity audit, sampling
   errors and the benchmark conditions table for that selected segment. Report failed/partial runs honestly.
6. Save the per-run report ZIP and the corpus separately before the VM is
   discarded. Use the Colab Files panel or optional `DOWNLOAD_REPORT_ZIP=True`
   for the report ZIP. Colab VMs are temporary; see the FAQ above.

An S2 key is optional. Set `S2_API_KEY` in the environment, or use Colab Secrets
and enable `READ_COLAB_SECRET`. Its value is never printed or exported. The
[Colab Secrets API](https://github.com/googlecolab/colabtools/blob/main/google/colab/userdata.py)
requires access to the named secret. Do not paste keys into notebook code/output.

## Measurements and interpretation

Wall time starts before discovery and includes service pacing, retries, downloads,
source processing, references/date lookup, checkpoints, initial result persistence
and sampler shutdown. Clone/install, analysis and ZIP creation are outside this
measurement. Final metric rewriting is bookkeeping. Per-paper time belongs to
this run and excludes global discovery; it is not accumulated over previous runs.

The sampler runs every 0.25 s and stops/joins in finally, including interruption.
RSS includes the kernel and unique descendants. Disk includes regular files under
the corpus root, including staging files, receipts and metrics, and excludes
symlinks. RAM mean is an arithmetic sample mean; peaks are observed and can miss
brief spikes. Resource errors are saved separately. Missing measurements remain
null; resource traces are only drawn when actual stored samples exist.

`no_tex` is a verified source outcome and counts toward processing coverage;
it is separate from successful TeX versions and full-source papers. Discovery
issues remain visible beside ratios based on discovered papers. Paired before/after
uncompressed bytes share a denominator; archive bytes are a separate measure.
References report job success, full-pagination counts, missing required fields
and completeness denominators. These statistics do not measure ML matching
accuracy or guarantee version-specific Semantic Scholar citation coverage.

## Output and reporting

Local output defaults to `data/milestone1/`, and Colab to `/content/arxiv-data/`:

```text
corpus/member-<number>/<run-folder>/
  manifest.json
  <paper>/metadata.json
  <paper>/sources/vN/...
  <paper>/sources/.vN.receipt.json
  <paper>/references.json
  <paper>/.references_receipt.json
  metrics/run_summary.json
  metrics/resource_samples.json
  metrics/resource_errors.json
reports/<run_id>/
  summary.json, benchmark.json, run_id.txt
  papers.csv, versions.csv, references.csv
  run_summary.json, manifest.json
  environment.json, configuration.json
  resource_samples.json, resource_errors.json   # when available
  integrity_audit.csv, outstanding_tasks.csv
  benchmark_checks.json, figures/, README.md
archives/report-<run_id>.zip
```

Reports are outside the measured corpus root. Snapshots preserve cold and resume
results separately. Analyze mode writes `analysis_environment.json` rather than
relabeling old measurements with the analysis machine's environment. Keep the
original report bundle with the corpus to retain collection metadata.

ZIP contains reports, not source corpus. Do not commit corpus, keys, archives or
embedded crawl output. Blank CSV values and JSON null indicate missing data.
Authors are JSON arrays in CSV. The separate English Jupyter Book must generate
its own tables/figures during build from saved JSON/CSV, without recrawling.

For manual checks, compare all metadata/version dates with arXiv; compare retained
text byte for byte with an independently retrieved versioned archive; compare
selected references and v1 dates with Semantic Scholar/arXiv. Receipt audits prove
local integrity, not independent agreement with the source. Use only disposable
copies to check altered-cache recovery. Concurrent writers to one root are unsupported.

## Evidence and remaining work

Historical development evidence is recorded in the notebook. A real local BERT
cold run collected v1/v2 and 35 retained references, with source/reference hashes
matching receipts. Its subsequent resume failed at discovery timeout. These
historical local figures are not a Colab or assigned-corpus benchmark.

The current 24-cell notebook completed in fresh kernels with network disabled,
with analysis of saved real data, and with a new cold BERT collection via real
services. The new local collection succeeded in 33.275875 s with 120 resource
samples and no sampling errors; metadata, both source versions and references
passed the integrity audit. Its tables/figures and report ZIP were generated and
the ZIP passed CRC verification. This is a local development run, not Colab.
Run artifacts: `data/milestone1/reports/4f33147f-1aae-424b-adab-c8bedc82299c/`.

The notebook is validated locally with Python 3.11.17, requests 2.34.2,
psutil 7.2.2, pandas 3.0.6, matplotlib 3.11.2, nbclient 0.11.0 and ipykernel 7.4.0.
Fresh installation of the pinned versions and hosted-Colab execution still need
verification. No Colab results are claimed before running there.

The group still needs the assigned corpus, complete manual comparisons, final
cold Colab CPU benchmark, a separate English Jupyter Book repository, build/publish
and link checks, and code/report-link submission through Moodle. Keep the corpus
for later milestones. Implementation alone does not complete Milestone 1.

Specification: [ARXIV_PROJECT_FULL.md](ARXIV_PROJECT_FULL.md).

Jupyter `.ipynb_checkpoints` directories have been removed and remain ignored by Git.
Crawler manifest checkpoints remain available for interruption/resume.
