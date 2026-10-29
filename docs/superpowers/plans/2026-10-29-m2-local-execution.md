# M2 local execution plan

**Goal:** Preserve M1 backup preparation as a separate step, then stage verified prepared raw locally for M2 without changing parser contracts.

**Architecture:** preparationM2 remains the persistent raw input. Optional transport ZIP + checksum receipt is created after preparation; parser notebook stages this ZIP into a new local directory. Parser validates the local corpus once at run start. Parser business functions remain assigned prototypes.

**Tech stack:** Python >=3.11 stdlib, existing preparation validator, notebook JSON.

- [x] Add failing tests for prepared corpus packaging/staging, wrong hash, unsafe paths and existing destination protection.
- [x] Implement src/preparation/transport.py; preserve verified empty source directories and all raw artifacts. Atomic publication, no input mutation, no overwrite of local data.
- [x] Configure parser notebook for local raw/output and explicit staging; leave RUN_PARSER=False. Per user follow-up, remove optional bundle export from the preparation notebook and restore that notebook exactly to its prior committed version. Transport helpers remain separate from prepare.
- [x] Update plan, assignment/prompts and prototype guidance: once-per-run validation, bounded per-publication memory, indexed dedup/source maps, local checkpoints and verified batch Drive backups. Keep expected versions and fresh benchmark boundaries.
- [x] Run focused tests and preparation regression; execute notebook smoke with parser disabled and inspect code cells. Do not claim full parser/Colab performance verified.

## Verification

- Full offline suite: 94 tests, 81 passed and 13 intentionally skipped parser templates.
- Prepared transport: 7 tests, including notebook code-cell staging smoke and canonical-path alias regression.
- Real Danh2 local round trip: 1,666 papers / 2,189 versions, valid=True, snapshot d7db8153bb9111e26f61944e99edc8b3b43a50e8dcb78a07584b20844cf9d25a unchanged. ZIP 208,132,768 bytes; pack including validation 29.095 s, local stage 14.771 s, local read-back 14.281 s. These are local transport measurements, not Drive/Colab parser benchmarks.
- Independent review found and prompted fix for parent-path alias overlap; regression demonstrated RED then GREEN.
- Parser algorithms, output batch backup/restore and full M2 benchmarks remain owner implementation work.
