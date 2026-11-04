# Hosted joint-floor process qualification

Phase 3 remains **OPEN**. The [workflow](../../../.github/workflows/v53-joint-floor-process.yml)
and [adapter](../../../scripts/v53/process_joint_hosted.py) prepare the
[32-history local cohort](PHASE_3_PROCESS_JOINT_COHORT.md) for isolated native
execution and independent downloaded replay. This implementation does not
dispatch the workflow or qualify any unexecuted final-source history.

## Whole-history execution graph

One preparation freezes source, reference classes, portable Java/Maven/Python
identity, the reader and offline Maven dependencies. Each of the 32 execution
jobs starts from that recorded source and executes its exact JUnit case once.
The replica/application roots, original plan, interrupted scratch, same-directory
recovery, common event/wire history and retirement captures stay together.
Death, recovery, FINAL and the stable BARRIER are never split across jobs.

Each verifier downloads the complete original and the same seed, verifies its
source/build/toolchain and inventory, and runs original-first physical, network,
export, maintenance and four-ledger replay. Its process/composition/scratch
negatives must match the declared cut-specific vector: 49 for each remote-copy
cut, 46 for each fourth local-copy cut, **1,544 results across all 32 members**.
The empty late-copy vector cannot replace any remote-copy vector. Original
receiver counts still have to match the declared cut before mutation starts.

The aggregate requires all execution and verifier jobs to succeed and exactly
one verifier artifact per case. Every artifact name and manifest binds workflow,
source SHA, run ID, attempt, role and case. The seed archive and all four common
pins are checked again. Original plans, raw archives and producer receipts must
be distinct; an artifact from a successful earlier attempt cannot fill a gap.
Verifier downloads preserve their separate directories.

Prepare, execution and verification receipts are PARTIAL. Only the complete
aggregate can grant `declaredJointFloorProcessHistoriesQualified=true`; wider
process-death, resource-maximum, all-profile, power-loss and Phase 3 flags stay
false. The source inventory contains **12 optional subsets and 544 planned whole
histories** after this entry. Those are scheduling counts, not passes or covered
rows in the frozen S matrix.

## Failure retention and operator use

Both matrices set `fail-fast: false` and allow at most six concurrent jobs.
Failed originals, producer diagnostics, verifier failures and aggregate receipts
remain available for 90 days. A native failure is never retried, and failure
while packaging cannot hide the original execution failure. An incomplete or
failed stage prevents aggregate acceptance even if some receipts are successful.
Commands keep minute heartbeats; summaries show the exact source/run/attempt,
case, expected negative count and bounded acceptance scope.

Only manual dispatch or push to `experiment/v53-joint-floor-process` triggers
the workflow. Its jobs check out the exact workflow SHA with read-only contents
permission and no persisted credential. The existing pinned setup supplies
Java 21.0.12, Python 3.11 and the checksum-pinned Maven 3.9.11 wrapper. Reference
classes are checked against independently built members. No mutable shared cache,
cloud identity, paid experiment, Required gate or release behavior is introduced.

After separately authorizing publication and execution on the intended source:

```bash
gh workflow run v53-joint-floor-process.yml \
  --ref experiment/v53-joint-floor-process
```

Rerunning selected jobs in a new attempt does not meet this cohort's contract:
the seed, all originals and all verifiers must belong to the same attempt.
Retain the failed attempt and start a complete new attempt when appropriate.
The workflow's hosted-runner job limit does not reset or extend any native
protocol deadline. It does not add measurement or operation retries.

## Verification boundary and rollback

Synthetic tests cover the complete prepare/download/execute/replay/aggregate
path, exact case IDs and vectors, original failure retention, wrong pins or
attempts, altered archives/classes/dependencies, duplicate plans and missing
members. These test orchestration and do not count as native matrix execution.
The previous native originals and replay evidence remain scoped to their
original source; they are not silently relabeled as this hosted source.

Local validation passed all 2,788 V5.3 Python tests, 39 focused tests and 76
focused/shared tests with Python assertions disabled. YAML parsing, five shell
blocks, 66 declared jobs and 99 expanded artifact names were checked; actionlint
was not installed. The existing workflows were unchanged. A retained real v2
producer (150,853,367 bytes, 13,771 files) was archived and unpacked with exact
source/raw-byte preservation and unchanged focused process/scratch replay.
This portability check did not execute another native history or admit the
historical source into a current-source cohort. The development receipt is
`phase3-evidence/process-joint-hosted.json`.

Final-source execution, the remaining transient resource and fault axes, and
phase-wide admission remain required. Rollback removes this optional workflow,
adapter and scheduling references while retaining the local cohort gate and
all original evidence. No production rollback is needed.
