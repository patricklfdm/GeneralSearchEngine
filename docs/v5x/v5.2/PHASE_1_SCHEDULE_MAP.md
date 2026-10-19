# Phase 1 mapping to later runtime schedules

All S01–S30 retain their full definitions and variants in [the evidence contract](TESTING_AND_EVIDENCE.md).
This map names future hook/fixture responsibilities. Proposed hook names are not runtime implementations.
Only S02 default/disabled checks execute now; the S01 old signature/consumer subset compiles and runs separately.

| Schedule | Future fixture / deterministic boundary | Current status |
| --- | --- | --- |
| S01 | old public API consumers / compatibility | Declaration/compatibility subset; runtime variants pending |
| S02 | external old implementation / stopped handle | Default/disabled checks executed; no runtime reads |
| S03 | read capture / public search oracle | Planned runtime evidence |
| S04 | read capture / public search oracle | Planned runtime evidence |
| S05 | ACCEPT/proof before application publication | Planned runtime evidence |
| S06 | ACCEPT/proof before application publication | Planned runtime evidence |
| S07 | read capture / public search oracle | Planned runtime evidence |
| S08 | wait registration / publication / deadline | Planned runtime evidence |
| S09 | wait registration / publication / deadline | Planned runtime evidence |
| S10 | wait registration / publication / deadline | Planned runtime evidence |
| S11 | wait registration / publication / deadline | Planned runtime evidence |
| S12 | wait registration / publication / deadline | Planned runtime evidence |
| S13 | identity decode / restart / snapshot import | Planned runtime evidence |
| S14 | identity decode / restart / snapshot import | Planned runtime evidence |
| S15 | identity decode / restart / snapshot import | Planned runtime evidence |
| S16 | identity decode / restart / snapshot import | Planned runtime evidence |
| S17 | promise / capture / generation replace | Planned runtime evidence |
| S18 | promise / capture / generation replace | Planned runtime evidence |
| S19 | promise / capture / generation replace | Planned runtime evidence |
| S20 | promise / capture / generation replace | Planned runtime evidence |
| S21 | promise / capture / generation replace | Planned runtime evidence |
| S22 | old paging / scoped-view compile-negative | Declaration/compatibility subset; runtime variants pending |
| S23 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S24 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S25 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S26 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S27 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S28 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S29 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |
| S30 | permit admission / cancellation / callback release / dispatch | Planned runtime evidence |

S14/S18/S20/S25/S26 additionally require separate-process halt and controller SIGKILL as specified.
Extend the existing V5.1 public worker/history/inventory and physical replay patterns; do not use
inspectLocal or manufactured success records to satisfy public calls. Model/Synthetic N01–N16 results
qualify only the independent foundation checker. M01–M04 remain unexecuted and require a Phase 6 freeze.
