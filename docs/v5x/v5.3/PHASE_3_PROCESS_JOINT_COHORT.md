# Phase 3 joint-floor process cohort admission

The [native process producer](PHASE_3_NATIVE_PROCESS_JOINT_FLOOR.md) now has a
local source-bound component gate in `scripts.v53.process_joint_cohort`.
Its 32 members are the four original copy ordinals, four writer callbacks and
halt/SIGKILL modes. Each member includes the entire 5-REPLACE history through
original-directory recovery, FINAL and the stable BARRIER. The gate does not
split a death from its recovery or combine successful fragments across attempts.

This is a component admission implementation, not an executed final-source
cohort or Phase 3 closure. The subsequent
[hosted adapter](PHASE_3_PROCESS_JOINT_HOSTED.md) adds these 32 local entries to
the scheduling inventory: twelve hosted subsets, **544 planned histories**.
No hosted execution is implied by either entry.

## Common provenance and original-first replay

Every member must have the same externally pinned source, compiled classes,
portable toolchain and current reader. The gate checks all recorded source files,
the three compiled directories, the exact Maven case argument, one exact
unretried passing JUnit method and both successful execution/collection receipts.
It independently recollects the retained raw inventory. Linked files or generated
parents, extra raw runs, a different capture directory, stale collectors, missing
members and duplicated original plans refuse. Host paths/kernel diagnostics may
differ; the portable Java/Maven/Python identity must match.

Only the v2 producer with its original scratch recovery sidecar can enter.
Historical v1 remains replayable by its own reader, but cannot fill this cohort.
An old native original replayed with a new validator remains development evidence:
the validator's hash must belong to the producer source for admission.

The complete unmodified physical, network, export, maintenance and four continuous
ledger derivations run before any negative suite. Process-boundary, composition
and scratch suites then independently check their original prerequisites. Each
suite's original result must match the corresponding complete derivation.
All original bytes and source/build bindings are checked again after replay.
No false declaration or successful summary substitutes for those checks.

## Fixed negative vectors

| Interrupted copy | Original abandoned receivers | Process | Composition | Scratch | Total per member |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 12 | 16 | 21 | 49 |
| 2 | 2 | 12 | 16 | 21 | 49 |
| 3 | 1 | 12 | 16 | 21 | 49 |
| 4, local | 0 | 12 | 16 | 18 | 46 |

The complete declared vector has **1,544 exact rejection results**. Selection
uses the requested copy ordinal before mutation, never an observed error or a
missing file. Original replay must prove exactly the declared receiver count.
Each remote receiver has handed off before the fourth local copy; that scope
cannot provide receiver-payload, early-file-deletion or omitted-discard negatives.
Its remaining ownership, force, baseline, authority and writer checks still run.
This is not permission to omit a negative from an early-copy original.

Exact suite/case/stage/reason equality rejects reordered, missing, duplicated or
relabeled results. An unrelated error is a failure. In local aggregation a failed
member is retained and the remaining member checks finish; the aggregate stays
FAIL. No member or failed workload is automatically retried.

## Operator entry

Inspect the immutable case catalogue without running a workload:

```bash
python3 -B -m scripts.v53.process_joint_cohort plan
```

Capture a complete member in a new destination:

```bash
python3 -B -m scripts.v53.process_joint_cohort capture \
  target/v53-joint-process/operator-001 \
  --case 1,FLOOR_COPY_CREATED,kill --maven /opt/maven/bin/mvn
```

Use `--source-from <recorded-producer>` for subsequent members of the same
source. This copies immutable source, not a prior run's generated state.
Changing the source or reader requires a new cohort. Retain failed producers.

The `member` and `aggregate` commands require `--source-sha256`,
`--build-sha256`, `--toolchain-sha256` and `--reader-sha256`. These identify,
respectively, the exact recorded `source.json`, exact `build.json`, portable
`process_toolchain.pin(toolchain.json)` and `reader_manifest()['sha256']`.
They are admission inputs, not values inferred from whichever member passes.

```bash
python3 -B -m scripts.v53.process_joint_cohort member <new-output> \
  --producer <original-producer> --case 1,FLOOR_COPY_CREATED,kill \
  --source-sha256 <source> --build-sha256 <build> \
  --toolchain-sha256 <portable-tools> --reader-sha256 <reader>

python3 -B -m scripts.v53.process_joint_cohort aggregate <new-output> \
  --inputs <complete-32-producer-directories> --workers 2 \
  --source-sha256 <source> --build-sha256 <build> \
  --toolchain-sha256 <portable-tools> --reader-sha256 <reader>
```

The inputs directory contains exactly one directory named by each comma-separated
case. Replay workers are bounded to 1–4; each worker keeps a whole history intact.
The CLI emits a minute heartbeat and retains its terminal receipt even on failure.
No command dispatches GitHub Actions, pushes code or launches paid cloud resources.

## Development validation

All 2,767 V5.3 Python tests passed. The 77 focused and qualification-plan tests
also passed with Python assertions disabled. Synthetic orchestration fixtures
check complete 32-member aggregation, one failed member while others finish,
case-specific vectors, original-first ordering, source/build/toolchain drift,
retries, linked paths, repeated plans and changed inputs. These fixtures test
admission behavior; they are not native executions of the declared matrix.

A direct CLI check retains a FAIL receipt for invalid pins and refuses to
overwrite that receipt. The earlier real `1,FLOOR_COPY_CREATED,kill` producer is
correctly refused as a current-reader cohort member, because the new reader did
not belong to its recorded source. Its unchanged bytes are separately useful
for development replay. `phase3-evidence/process-joint-cohort.json` records
validation provenance and keeps that distinction explicit.

## Remaining work

Only a passing complete matrix can set
`declaredJointFloorProcessHistoriesQualified=true`. Both individual results and
aggregate keep `processDeathQualified`, `combinedPeakResourcesQualified`,
`allMembershipProfilesQualified`, `powerLossQualified` and `phase3Complete` false.
These wider flags include obligations outside this single profile/cut catalogue.

All 32 executions on one final source, remaining native
negative axes, transient acquisition/application-publication resource intervals,
torn-file cases and the simultaneous physical maximum remain open. The complete
3,310-row public correctness matrix remains owned by Phase 5. Development checks
and a replay of an earlier original cannot fill any unexecuted final-source slot.
