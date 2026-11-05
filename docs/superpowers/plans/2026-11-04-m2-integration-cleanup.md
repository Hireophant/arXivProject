# M2 integration and cleanup plan

**Goal:** Make the assembled M2 checkout reproducible through its notebook, with real stage integration and an evidence-based cleanup.

**Architecture:** Keep the existing prepared-input, owner API, contracts and working-output schemas. Verify the implementation already merged into master; fix demonstrated integration defects in the owning module. Keep unit-test doubles for unavailable services and fault injection, and add a separate unmocked notebook/read-back check.

**Tech stack:** Python >=3.11, stdlib parser/preparation, existing pinned notebook and measurement dependencies.

**Spec:** Danh's integration request in this chat; `PHAN_CONG_MILESTONE_2_4_NGUOI.md` sections 12 and 15, and plan section 10.0.

## Constraints

- Initial checkout: clean master `d6b2de8`. Included owner commits: Danh `12c0df7`, Khánh `8ed8f93`, Nguyên `56139d5`, Khang `bf8309e` and `74a7fd4`.
- Final handoff messages and human approvals are not inferred from commit messages; missing handoffs remain pending.
- No automatic commit/push, remote PR merge, destructive clean, or deletion of corpus, outputs, decisions, evidence, useful fixtures or real tests.
- Preserve schemas and public signatures; no parallel workers or unmeasured performance claims.
- Book is a separate checkout: audit its M2 placeholders; do not mix its Git changes into this code checkout.

## Tasks

- [x] Audit owner diffs/public docstrings, dependencies, notebook, markers and references to potential cleanup targets.
- [x] Run the baseline regression suite, then exercise actual load/gather/tree/extract/unify/normalize/assemble/finalize/export/metrics APIs on prepared input.
- [x] Add an unmocked notebook smoke/read-back test covering two versions, citations, content dedup, preserved occurrences and resume; preserve fault-injection tests.
- [x] Fix only reproduced integration failures, first adding a failing regression test. Preserve unsupported-content diagnostics and raw bytes.
- [x] Remove proven obsolete source scaffolding/messages and update shared README/notebook once. Delete files/adapters only if replacement and zero live callers are established.
- [x] Run M2 plus M1 regression, notebook execution, saved-output read-back and a limited real-source integration probe; record scope and code hashes.
- [x] Review diff, cleanup inventory and limitations. Request human raw/output review by owner; leave Colab/Pages and absent shard evidence pending.

## Review focus

- Scientific prose adjacent to nested lists must remain covered without false structure failures.
- Unsupported math macros must retain explicit diagnostics instead of silently claiming normalized success.
- No-TeX and blocked versions must survive orchestration/metrics with their original meaning.
- Notebook smoke must run real owner functions; default notebook execution must remain harmless without configured input.
- Resume and read-back must verify current signatures and artifacts rather than trust prior success markers.

## Evidence

Run logs and generated output stay under `data/milestone2-dev/integration/`. Handoff status, deleted-file reasons and outstanding human checks will be listed in the final response.

- User confirmed the listed commits are the final handoffs; human checks remain pending.
- Baseline 262/262; final 264/264 (223 M2, 41 M1), zero skipped. Final suite also passed in the pinned Python 3.11 conda environment.
- Real notebook: 3 papers, all 8 versions retained, status partial (4 partial, 4 failed), no published papers. Review source-specific list/macros and bibliography identities before accepting whole-corpus results.
- Ruling: preserve useful unit doubles and two import roots; no tracked temporary artifacts/unused adapters were demonstrated, so no file deletion is warranted.
- Ruling: preserve strict rejection of unsupported real cases; this cleanup is not permission to auto-approve bibliography identity or weaken D3.
- Independent code review found no blocker; detailed handoff is in `docs/milestone2/TICH_HOP_M2_20261104.md`. No commits/pushes in this turn.

## Follow-up: supplied preparation ZIP

- User supplied the actual Drive download ZIP and explicitly approved D3 exact-content fast-path plus per-validation citation caching after measured profiling.
- Inner transport checksum and all staged source receipts validated: 1,666 papers / 2,189 versions. User confirmed no alternate backup for 7 blocked source versions; retain them as blocked.
- Fixed supported list labels/spacing, math alias declaration context, parent/leaf consistency, comment gaps in arguments and unique include-parent document root. Unknown labels/styles, ambiguous roots and C3 decisions remain errors.
- Kept sharing-lock retry inside parsing only, preserving atomic/immutable publication; preparation restored unchanged per user request. No M1 business changes or automatic identity approvals.
- Isolated optimization comparison on five real papers: complete parsed payload hashes identical; local18.90s ->9.06s, no whole-corpus or Colab speed claim.
- Final regression: 294 passed, zero failed/skipped in Python3.11 with pinned dependencies. Earlier Windows sharing errors in M1 tests were recorded; final suite passed without M1 source changes.
- Latest handoff: `docs/milestone2/KIEM_TRA_PREPARATION_M2_20261104.md`. Corpus acceptance, source recovery, human review, official Colab benchmark and Book/Pages are still not signed complete.
