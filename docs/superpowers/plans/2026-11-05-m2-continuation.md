# M2 continuation implementation plan

**Goal:** Danh selected dataset + publication count per visit, automatic continuation
from Drive, pending retries, and deferral after four failed attempts.

**Chosen behavior (Danh, chat 05/11/2026):** retain preparation unchanged; one
writer per dataset. Read verified immutable backups to reconstruct progress.
An attempt counts only after its audit and required outputs are backed up. Retry
pending publications first, once per visit, then unseen publications. Four failed
attempts defer a publication for later review, preserving evidence. A publication
always includes every version. Source/config/code/review signature changes create
a new attempt history. Export-ready output is complete; partial/blocked/write
failures are pending. An interrupted unfinished publication remains eligible.

**Files:** `parsing/continuation.py` owns history and queue selection;
`pipeline.py` composes this in ordinary runs and backs up queue artifacts;
notebook selects prepared ZIP by dataset, stages locally and invokes the bounded
run. Existing contracts/schema and unbounded/benchmark behavior stay compatible.

- [x] Add failing tests for verified progress, retries 1–4, deferral, dedup across
  metadata snapshots, corruption, signature changes, and all-versions selection.
- [x] Implement replay/queue and integrate bounded runs; persist queue and later
  review list with the existing immutable backup protocol.
- [x] Simplify notebook input selection; test real staging and repeated pipeline
  visits, including notebook smoke. Update README and handoff documentation.
- [x] Run M2 + M1 regression, review diff, then commit/push as already requested.

**Validation boundary:** local filesystem emulates Drive storage, not Google
authorization or actual Colab performance. Missing raw and human review remain
pending. Queue completion is not M2 acceptance.

Validation: 311 unittest tests PASS, 0 fail/skip; final reviewer found no blocking issue. Existing staging-only tests exposed a gating regression; the stage condition was repaired while preserving their assertions. Preparation code/notebook diff is empty. Actual Drive/Colab and human acceptance remain pending.
