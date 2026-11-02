# Phase 3 — exact-source joining initialization process matrix

The [process capture](PHASE_3_JOINING_INITIALIZATION_PROCESS.md),
[physical/transport replay](PHASE_3_JOINING_PROCESS_COMPOSITION.md) and
[authority replay](PHASE_3_JOINING_PROCESS_AUTHORITY.md) now have one explicit
cohort entry: [`joining_process_matrix.py`](../../../scripts/v53/joining_process_matrix.py).
It requires all 360 declared whole histories. This implements admission and
replay orchestration; **final-source native execution and Phase 3 remain OPEN**.

## Exact set and indivisible execution

The catalogue is the Cartesian product of five ADD/REPLACE profiles, 36 original
initialization cuts and two termination modes:

| Axis | Required values |
| --- | --- |
| Profile | `3-ADD`, `4-ADD`, `3-REPLACE`, `4-REPLACE`, `5-REPLACE` |
| Record | SEED, PEERS, FUTURE, LEARNER, DONE |
| Cut within each record | CREATED, PREFIX_WRITTEN, WRITTEN, FORCED, CANDIDATE_PARENT_FORCED, RENAMED, PARENT_FORCED |
| Additional cut | `JOINING_RETENTION_BEFORE_RETURN` |
| Termination | `halt`, `kill` |

Each member is one original execution from bootstrap through initialization
death, recovery, native FINAL/BARRIER and cold reopen. The old majority remains
alive while the joining JVM is replaced. No boundary within this history may
be split into separate jobs, rerun, or reconstructed from successful fragments.
These process-loss experiments do not establish host power-loss behavior.

## Provenance and independent qualification

All members must have the same exact source, class inventories, portable
Java/Maven identity and reader manifest. Each reader must belong to the recorded
producer source. A later reader can diagnose an old original but cannot admit it
to the final-source cohort. The command must select exactly the declared native
method, profile and cut/mode. The original JUnit result must be one unretried,
unskipped success; producer collection status remains `PARTIAL`.

The gate checks every retained source and class file, execution receipt,
toolchain, JUnit and raw collection. It independently recollects process
observations and checks the original plan identity. Linked or escaping paths,
duplicate metadata keys, extra history directories, changed files and boolean
values impersonating counts reject admission. Missing/extra members, producer
aliases and duplicate original plans cannot fill the complete matrix.

Each member then executes three original-first readers:

1. Complete physical/transport/authority validation and all 130 authority
   negatives. Only the three original-backed absences documented in the
   authority reader may be `NOT_APPLICABLE`; exact case/status/reason must match.
2. Physical/transport validation and all 11 composition negatives. Its full
   original result must equal the authority reader's physical precondition.
3. Initialization transaction validation and all nine transaction negatives.

An unrelated original failure never counts as a successful negative. Partial
negative selections cannot qualify a member. Producers and reader hashes are
checked again after replay. A single qualified member does not claim the matrix.
Only the exact complete set can set `declaredJoiningProcessMatrixQualified`;
`allMembershipProfilesQualified`, `originalObservationCoverageComplete` and
`phase3Complete` remain false because other Phase 3 requirements are separate.

The standalone aggregate supports one to four member replay processes. Within
each member, authority negatives use one worker, so the aggregate does not
multiply that parallelism by three. Invalid provenance fails before replay;
after scheduling, a failed member is retained and the other members are still
checked exactly once. Final inventory checks also cover previously completed
members. It never executes or retries JVM workloads.

## Local commands and later hosted execution

Inspect the complete set without running a workload:

```bash
python3 -B -m scripts.v53.joining_process_matrix plan
```

After preparing and capturing the common final source, qualify one whole
producer using its reviewed cohort pins:

```bash
python3 -B -m scripts.v53.joining_process_matrix member /new/output/member \
  --producer /path/to/producer \
  --case 3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt \
  --source-sha256 "$SOURCE_SHA256" --build-sha256 "$BUILD_SHA256" \
  --toolchain-sha256 "$TOOLCHAIN_SHA256" --reader-sha256 "$READER_SHA256"
```

The `aggregate` command takes `--inputs /path/to/all-producers` instead of
`--producer`/`--case`, with the same four pins and optional `--workers 4`.
The directory must contain exactly the 360 case IDs emitted by `plan`, each
containing one complete producer. Output directories must be new; failures
retain `receipt.json` and completed negative results in `progress.jsonl`.
Both commands emit a heartbeat every minute, including original-first validation
before any negative completes.

This standalone aggregate rereads raw producers and is not a lightweight
receipt-only hosted aggregator. The next batch must prepare one immutable seed,
distribute whole cases, independently verify downloaded artifacts and bind the
complete aggregate to exact source/run/attempt evidence. Hosted grouping must
preserve every case and whole history. This batch adds no workflow or dispatch
and changes no Required job, release authority, workload parameter or time limit.

## Development evidence and remaining acceptance

The [development receipt](phase3-evidence/joining-process-matrix.json) records
provenance/orchestration tests, optimized-Python checks, the complete Python
regression suite and an actual historical-original rejection. Synthetic test
fixtures exercise all 360 scheduler keys and all 150 required negative slots;
they are deliberately invalid native histories and cannot certify execution.

The retained earlier SEED_PREFIX_WRITTEN/halt original is rejected because its
source lacks the current reader. Its bytes remain unchanged, and its earlier
diagnostic success is not upgraded to final-source acceptance. No new native
history, full 150-negative member, complete 360-member execution or hosted
campaign was run in this batch. Those executions, combined resource bounds and
the final frozen-requirement audit remain open.

Rollback removes this optional matrix entry and its tests/docs. The existing
producer, physical/authority readers, Java runtime and original evidence remain
unchanged.
