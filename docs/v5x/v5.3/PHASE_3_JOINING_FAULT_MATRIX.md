# Phase 3 — complete joining source-reply fault matrix

This gate requires three complete original `3-ADD` histories: one initial learner
SOURCE_OFFER loss, one CHUNK loss and one TRANSFER_COMMIT loss. Each continues on
its own original filesystem through joining ownership, automatic FINAL, the
new-stable barrier and cold reopen. It extends
[the first complete fault history](PHASE_3_JOINING_SOURCE_FAULTS.md), not the frozen
scope of Phase 3 or the number of required membership profiles.

## One producer source, independent histories

The source snapshot and build manifest are caller-pinned SHA-256 values. Every
member must retain those exact sources, compiled classes, toolchain, full JUnit
method, selected reply kind and successful execution/collection receipts. Native
collection remains `PARTIAL`; a collection label is not acceptance.

`joining_history_run --source-from <earlier-producer>` copies only the earlier
immutable source manifest's verified files. It preserves executable modes and
rejects changed bytes, duplicate keys, linked parents, traversal, invalid hashes,
excessive files/bytes and an output inside the earlier producer. It never copies
that producer's generated classes, runtime files, snapshots or prior outcome.
Maven builds again in the new workspace. The exact resulting build must match at
aggregation. The current repository can continue developing its reader without
silently changing the already executed producer.

The local cohort deliberately reuses the earlier SOURCE_OFFER execution, then
executes the other two complete histories from its same frozen source snapshot.
This is not a failed-attempt retry or a splice between stages. The producer is
identified by its full source manifest, including the then-uncommitted test
instrumentation; its recorded base commit alone is not that source identity.
The launch controller and final reader are separately retained.

```bash
# SOURCE_OFFER is an existing complete producer; use fresh destinations below.
python3 -B -u -m scripts.v53.joining_history_run target/joining-chunk \
  --fault CHUNK --source-from /path/to/offer-producer --maven /opt/maven/bin/mvn
python3 -B -u -m scripts.v53.joining_history_run target/joining-commit \
  --fault TRANSFER_COMMIT --source-from /path/to/offer-producer --maven /opt/maven/bin/mvn

python3 -B -m scripts.v53.joining_fault_matrix \
  --offer /path/to/offer-producer --chunk target/joining-chunk --commit target/joining-commit \
  --source-sha256 <pinned-source-manifest-sha256> --build-sha256 <pinned-build-manifest-sha256>
```

The two new runs may execute concurrently in independent workspaces. The driver
emits progress every minute and never retries a failed history. Reusing a source
does not renew any running protocol deadline. Keep each complete member on one
runner; no initial/INTENT/FINAL/cold stage may be distributed across runners.
The same source/build/attempt principles remain required for later hosted jobs.

## Aggregate authority and portability

`scripts.v53.joining_fault_matrix` requires the exact three-member set, distinct
producer directories and original execution plans. It rejects failed/skipped or
shortened test methods, changed process exits, extra native history directories,
incorrect fault selectors, missing original files, changed generated classes and
mixed toolchains. Bounded regular source, metadata, raw and build files are read
from the retained copy. Recorded original paths are never opened for replay.

For each member, the aggregate runs the full original physical/network/export/
control/maintenance/peer-ledger reader before checking the fault and all fourteen
exact evidence negatives. All 42 case/reason results must match. Every source,
build, receipt and raw inventory is rechecked after replay and again before the
whole aggregate returns, including an earlier member while later members run.
Prior PASS summaries cannot substitute for this work.

The archive keeps each member's source/build/raw layout, the final reader,
manifests and execution logs. A per-member hash inventory is checked during
extraction before aggregate replay. The local aggregate is performed from that
relocated archive, so portability is tested with all three original histories and
their negative checks, without rerunning native measurements.

See [the source-bound receipt](phase3-evidence/joining-fault-matrix.json) for the
actual execution, aggregate and archive results. All three original histories and
42 negative checks passed from the relocated archive, with 327 joining Python
tests passing locally. CHUNK and TRANSFER_COMMIT each reached stable index 11 and
cold reopen in one execution; their JUnit durations were 895.914 and 907.380
seconds. SOURCE_OFFER was reused from the earlier successful producer, without
rerunning its native workload. All three source/build/toolchain manifests match,
and all 705 protected production/workflow/POM/frozen inputs remain unchanged.

This is one membership profile
and one precisely declared initial reply loss per history. Other joining faults,
voting/publication losses, expiry/cancellation, whole joining process deaths, all
seven membership profiles and frozen S/N-family mapping remain required.
`phase3Complete` and `allMembershipProfilesQualified` remain false. No production
Java, frozen parameters, POM, workflow or paid-cloud behavior changes in this batch.
