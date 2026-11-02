# Joining initialization across process death

The opt-in capture now keeps one real ADD/REPLACE history running while a fresh
joining JVM dies during initialization. A second JVM reopens the same original
joined roots; the old majority remains alive. After recovery, that same history
continues through native FINAL, the new-view BARRIER and stable cold reopen.
Collection and transaction replay remain `PARTIAL`; the additional composition
readers are linked below. Complete negative qualification, the final-source
cohort and Phase 3 are still **OPEN**.

The subsequent [process composition reader](PHASE_3_JOINING_PROCESS_COMPOSITION.md)
now binds this transaction to the original full physical history, observed
transport and durable ACKs. Complete export/control authority and continuous
ledgers are subsequently implemented by the
[authority reader](PHASE_3_JOINING_PROCESS_AUTHORITY.md); final-source admission
and the complete process catalogue remain pending.

## Original execution

`V53JoiningIntentExportTest#joiningRetentionResumesAfterNativeProcessDeathThenCompletesFinal`
is enabled only by an explicit `v53.joining.process` property. It reuses the
existing typed learner, publication, placement and old-majority preparation
path. The worker receives a bounded canonical specification of the original
plan, paths and proposer. This specification grants no runtime authority.

The child acquires the actual joined ownership locks and obtains initialization
material from the live old proposer over TCP. The parent observes the exact
selected callback, verifies the child's exclusive lock, then allows
`Runtime.halt(73)` or issues SIGKILL. It retains the interrupted original files.
The recovery JVM requires the original decision, including a partial candidate;
it cannot fall back to a fresh joining installation. An incomplete seed must be
completed from actual original sources. A complete decision recovers its
derived ledgers through the existing native recovery path. The old proposer
must observe initialization over TCP before the recovery child closes.

Both PIDs, exit codes, live/released locks, resource drain and complete stdout
are retained. A shared, bounded process trace orders parent and child
observations without forcing protocol storage or manufacturing authority. The
reader preserves bytes verbatim and rejects incomplete final lines. An exited
reader or malformed output fails promptly rather than waiting for the full
fixture budget. The fixture's existing time and resource limits are unchanged.

The first development attempt reached its actual prefix-write halt and then
failed during recovery endpoint construction: the native-use guard also blocked
read-only acquisition of the missing seed bytes. The runtime correction keeps
all original ownership, inventory, pending-prefix and unused-joined-owner checks
in the discovery/prefix read path. Native activation, PREPARE, voting scratch,
maintenance copies and readiness still require completed initialization. Read
guards neither set the initialization-in-progress flag nor waive native checks.
Targeted regressions cover empty/partial candidates, changed bytes/inodes,
missing original decisions, read admission and refusal of native uses.

Five files have seven initial write boundaries each: `CREATED`,
`PREFIX_WRITTEN`, `WRITTEN`, `FORCED`, `CANDIDATE_PARENT_FORCED`, `RENAMED`
and `PARENT_FORCED`. Together with `JOINING_RETENTION_BEFORE_RETURN`, this
declares 36 cut points. The catalogue crosses both death modes with `3-ADD`,
`4-ADD`, `3-REPLACE`, `4-REPLACE` and `5-REPLACE`: 360 whole-history cases.
Declaring this catalogue does not mean it has executed or passed.

## Independent transaction replay

`scripts.v53.joining_initialization_process_evidence` derives the seed and
revision-zero ledgers from retained old-majority grant/source packets and
endpoint ancestry. It reconstructs decision and completion bytes using recorded
original inode identities, never the inode of a downloaded copy.

A finite state model derives the exact interrupted prefix and cold completion
sequence. Replayed bytes, original file keys, force/rename callbacks and
unrelated custody must agree across before-process, interrupted, resumed-active
and resumed-closed snapshots. Complete seed candidates, active decisions and
already completed transactions have distinct recovery paths. This checks only
the initialization transaction; preceding bootstrap/native authority, complete
network causality and subsequent FINAL/BARRIER must still be composed by the
whole-history process reader before qualification.
Nine original-first evidence mutations cover prefix bytes, inode replacement,
missing/reordered callbacks, foreign owners, changed initial ledgers/custody and
premature readiness and a substituted recovered cut. An unrelated original or mutation failure cannot count as
an expected rejection. The receipt distinguishes synthetic checks from actual
replay of retained native evidence.

For one fresh local capture with the pinned Java/Maven and offline dependencies:

```bash
python3 -B -u -m scripts.v53.joining_process_run \
  target/v53-joining-process-local/seed-prefix-halt \
  --maven /opt/maven/bin/mvn \
  --case 3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt
```

The output must not already exist. The runner captures an immutable source,
toolchain, exact JUnit command and generated classes. It emits minute progress,
executes once and retains failures. A skipped method or retried/flaky JUnit
result cannot count as success. The final-source hosted execution will shard
whole cases only; death, recovery and continuation must not be split or stitched.
This batch adds no workflow and changes no existing Required jobs.

## Verification

The [development receipt](phase3-evidence/joining-initialization-process.json)
records actual focused results and both original native development attempts.
The corrected `3-ADD / SEED_PREFIX_WRITTEN / halt` history completed FINAL,
BARRIER and stable cold reopen. Independent replay checked its two initial
callbacks, 34 recovery callbacks and exact original transaction bytes. All nine
semantic negatives were rejected for their expected reasons; originals remained
unchanged. Packing and unpacking the retained raw history produced the same
transaction result at a new location.

The permitted local TCP suite passed 105 tests, followed by the strengthened
higher-ballot refusal regression. The earlier sandbox socket-denial logs remain
retained. Python passed 2082 tests before the final negative-driver/type checks;
the final 30 focused tests passed under both normal and optimized Python. The
native producer predates the final read-only discovery-scan adjustment and some
reader/test additions; source hashes and the exact runtime difference are
recorded. Its success is development evidence, not a final-source cohort.

The complete catalogue, downloaded original replay and full network/process
composition are not accepted by these development checks. No paid cloud run,
release change belongs to this batch. The production correction is confined to
read-only recovery admission; the native initialization format, voting checks,
force order and workload parameters are unchanged.
