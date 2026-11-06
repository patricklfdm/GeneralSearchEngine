# Hosted native carried transition qualification

Phase 3 remains **OPEN**. The [workflow](../../../.github/workflows/v53-carried-transition-histories.yml)
and [adapter](../../../scripts/v53/carried_transition_history_hosted.py) prepare
the [fourteen-history cohort](PHASE_3_CARRIED_TRANSITION_COHORT.md) for isolated execution
and independent downloaded replay. This implementation batch does not dispatch it.

## Execution graph

One preparation freezes the exact source, compiled classes, toolchain, reader
and offline Maven dependencies. Fourteen execution jobs each run one complete native
history exactly once. Each ordinary original and its retirement sidecar travel
together; each process original contains all seven or nine capture families internally.
Their continuous ownership, revision and publication history is never split
between jobs.

Fourteen verifier jobs download those complete originals and the same seed, validate
their provenance, then run the applicable original-first readers: 301 exact checks for each
ordinary history and 210 capture/owner checks for each ACCEPT/PROOF process history and 268 for each
application-ACK process history. Preparation, execution and verification return
`PARTIAL`. Component acceptance requires all fourteen execution jobs and all fourteen verifier
jobs to succeed, all 3,354 negative results, exact input inventories and distinct
original plans, archives and producer receipts.

Every artifact name and manifest binds the workflow, source, run, attempt, role
and case. The aggregate checks the seed archive and all source/build/toolchain/
reader pins again. Missing, skipped, cancelled or failed workflow stages block
acceptance. A successful receipt from another attempt cannot substitute.
Verifier artifacts remain separated on download; no directory merging is used.

Both matrices use `fail-fast: false` and at most two concurrent jobs. Failed
originals and diagnostic receipts are retained for 90 days. There is no native
retry, mutable shared Maven cache, shortened workload or protocol-budget change.
Commands retain the once-per-minute heartbeat and per-stage progress output.

## Authority and use

Only manual dispatch or push to `experiment/v53-carried-transition-histories`
triggers this entry. Jobs check out the exact workflow source without persisting
credentials. The existing pinned setup supplies Java 21.0.12, Python 3.11 and
Maven 3.9.11. Action revisions are pinned. Permissions are contents-read only;
there are no cloud credentials or paid-cloud/release operations.

After separately authorizing publication and execution on the desired source:

```bash
gh workflow run v53-carried-transition-histories.yml \
  --ref experiment/v53-carried-transition-histories
```

Existing Required CI and all other subset workflows are unchanged. The source
inventory now has **twelve optional subsets and 564 planned whole histories**.
These are scheduling counts, not successful final-source executions or covered
rows in the frozen S matrix. Final Phase 3 admission across subsets remains open.

## Verification and rollback

The synthetic orchestration tests exercise one capture per case, downloaded
replay, failed-original retention, wrong source/attempt/tools/role, changed
classes/dependencies, sidecar corruption, shortened negative vectors, duplicate
plans and incomplete aggregates. They test orchestration, not native acceptance.
The native capture/readers already have their separate development evidence;
neither historical evidence nor these synthetic tests fills final-source slots.

Historical two-history implementation checks passed: 2525 V5.3 Python tests, 59 focused tests in
normal and optimized Python, four declared workflow jobs and five checked shell
blocks. The [development receipt](phase3-evidence/carried-transition-cohort.json)
also records 602 exact negative replays over unchanged older native originals.
This validates the reader composition, not execution of this hosted workflow.
That earlier implementation dispatched no workflow and produced no new native
original. Current development execution is recorded separately in the
[capture cohort notes](PHASE_3_CARRIED_CAPTURE_COHORT.md).

For the current expansion, rollback restores the previous ten-case adapter,
receipt versions, tests and catalogue bindings together. Retain every original;
no production rollback is needed.
