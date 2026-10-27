# M2 Input Preparation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** A Colab notebook restores verified raw M1 papers from a Drive backup folder or downloaded ZIP into a separate Milestone2 folder, ready for later parsing.

**Architecture:** A dependency-free preparation package scans backup receipts, validates corpus archives, reconciles publication/version records and restores only source/metadata/reference artifacts. A thin notebook mounts Drive, configures paths, previews input, executes preparation and displays inventories. Source backups remain unchanged; errors/empty sources remain explicit.

**Tech Stack:** Python >= 3.11 standard library; Colab/IPython display for the notebook.

**Spec:** User request and `docs/milestone2/KE_HOACH_MILESTONE_2.md` A1/9.2; inspected archive `Milestone1-20261027T125453Z-1-001.zip` contains folder `Milestone1/`, checkpoints, session-report stubs and full backups, with M1 receipt schema 3.0.

## Global Constraints

- Preserve input bytes; no crawling, parsing, cleanup or dedup of article text in this step.
- Keep all expected versions, including verified no_tex and missing/failed sources.
- Accept one account or recursively grouped accounts; do not assume a source contains all four people.
- New output schema `m2-input-1.0`; retain M1 source receipts and publication record/download shapes.
- Never publish success for damaged backups, ambiguous source copies or missing expected versions.

## Review Focus

- Session-report corpus ZIPs contain manifests only; use them for coverage, never as successful source restores.
- A retry may supply only some versions; combine valid per-version copies without dropping the others.
- Identical retries must be idempotent; conflicting valid bytes for one version require visible review.
- ZIP traversal/links and output/source overlap must not write outside the destination or modify M1.
- Interrupted/corrupt output must be checked again on rerun rather than trusted from a marker.

### Task 1: Verified preparation engine

**Files:** Create `src/preparation/__init__.py`, `src/preparation/milestone2.py`, `tests/test_m2_preparation.py`.

**Interfaces:** `inspect_backups(source: Path) -> dict`; `prepare_corpus(source: Path, output: Path, *, progress=None) -> dict`. Folder or outer ZIP inputs; output has raw sources, manifest, inventory, provenance, backup audit and summary.

- [x] Write tests using genuine small nested ZIPs/receipts: stubs + retries, no_tex/missing, hash failures, conflicting copies, overlap/traversal, rerun repair.
- [x] Run `python -m unittest discover -s tests -p test_m2_preparation.py -v`, observe missing-feature failures.
- [x] Implement bounded ZIP reading, receipt/source validation, deterministic reconciliation, publication artifacts, run-in-progress/completion evidence.
- [x] Run the tests; fix implementation and validate a real supplied backup.

### Task 2: Notebook and usage

**Files:** Create `src/notebooks/milestone2_prepare.ipynb`, `docs/milestone2/HUONG_DAN_CHUAN_BI_INPUT.md`; update README and M2 plan links.

**Interfaces:** Calls Task 1 APIs; configure `SOURCE_PATH`, `MILESTONE2_DIR`, `DATASET_NAME`, `PROJECT_DIR`. Drive mount only on Colab; local ZIP is supported.

- [x] Create notebook with setup/config, preview, restore, inventory and next-step cells; no embedded parser or notebook outputs.
- [x] Execute notebook code cells against a fixture and the supplied ZIP with local paths; verify output/source hashes and inventory.
- [x] Run project tests where dependencies are available; record limitations accurately.

## Execution record

### Follow-up: preparationM2 and an explicit input handoff

User requested renaming the Drive output to preparationM2, reliable notebook-produced raw input and actionable owner instructions.

- [x] Rename notebook configuration to PREPARATION_DIR and default output preparationM2/raw_m1/<DATASET_NAME>; keep parsed output separate.
- [x] Add read-only validate_prepared_corpus and automatic saved-output verification, stable snapshot receipt and negative tests for damaged/stale/inconsistent artifacts.
- [x] Expand assignment P0 and all 16 owner tasks with input, method, deliverable and acceptance; sync README/guide/main plan.
- [x] Execute notebook against the supplied real ZIP at the new destination; run the full regression suite and review the changed input contract.

- Ruling: implement in the shared checkout using new files and narrow documentation edits; retain existing uncommitted changes and do not commit/push. User explicitly asked to code this notebook here.
- Ruling: the preparation helper uses only stdlib, so restoring data does not require crawler/network dependencies. Receipt rules follow the existing M1 schema; source is never fetched again.

- Task 1 complete: 14 focused tests pass, including nested ZIPs, corruption on duplicate reuse, failed-download provenance and no_tex rerun repair.
- Task 2 complete: all notebook cells executed through nbclient against the supplied ZIP. Final run: 1666 publications, 2189 expected versions, 2100 ready_tex, 82 empty_no_tex, 7 blocked; zero backup errors. Local execution only; Drive mount/write is exercised by the user on Colab.
- Full project regression: 55 tests passed. Test-only dependencies were installed under ignored data/validation/python-deps; no project dependency changes.
- Independent reviewer found two P2 issues, both reproduced with failing tests, fixed and confirmed resolved.
- Environment ruling: sandbox temp directory ACLs and missing existing dependencies initially prevented regression tests. Final suite and Jupyter kernel ran with normal temp permissions; preparation itself remains stdlib-only.

- Follow-up complete: preparationM2 default and PREPARATION_DIR are synchronized across notebook, tests and guides. P0 plus all 16 owner tasks specify methods and handoffs.
- Follow-up verification: 27 focused tests and 68 full-suite tests passed; the Jupyter notebook completed against the real supplied ZIP under data/validation/m2-revision/preparationM2. Saved input_valid=True, complete=False, 1666 publications / 2189 versions: 2100 ready_tex, 82 no_tex, 7 blocked, zero backup errors.
- Snapshot: d7db8153bb9111e26f61944e99edc8b3b43a50e8dcb78a07584b20844cf9d25a. Raw bytes remain unchanged; missing M1 versions remain visible.
- Review: provenance JSONL/evidence validation was reproduced, fixed and verified by reviewer. Identical source bytes with different download receipts now keep manifest/receipt evidence consistent.
- Runtime fixes: bounded retry for transient Windows file locks; per-pass ancestor checks; chunked bounded JSON reads. Tiny-file memory regression reproduced at ~256 MiB and now passes a <4 MiB test without removing the JSON size limit. Superseded slow test processes were stopped and the corrected notebook was executed to completion.
