# Phase 3 — exact-source ordinary membership profile matrix

Status: the seven-member collection/replay interface is implemented. Its synthetic
provenance tests are not a native cohort. Long whole-history execution is deferred
to [hosted acceptance](PHASE_3_PROFILE_HOSTED.md), whose orchestration is now
implemented; no workflow has been dispatched. Phase 3 remains OPEN.

## Scope and indivisible histories

The order and exact set are checked against frozen `acceptance-plan.json`:
`3-ADD`, `4-ADD`, `4-REMOVE`, `5-REMOVE`, `3-REPLACE`, `4-REPLACE`, `5-REPLACE`.
Each member retains its own bootstrap, complete original membership transition,
FINAL, publication and cold recovery. Only whole independent histories may run
concurrently. Prefix-only, special same-view and process-crash histories cannot
substitute for an ordinary member.

The ADD/REPLACE collector must execute `--complete`. It now saves the raw file
inventory before its semantic replay and checks it again afterwards. REMOVE
requires `--retirement-captures`: the transient retirement observations are
collected during that same original execution, never reconstructed by a later
reader. Earlier failed producers remain failed even if a corrected diagnostic
reader subsequently accepts their preserved history.

## Provenance and replay

`profile_matrix` binds each producer to the same supplied source, compiled build,
toolchain and reader hashes. It verifies every recorded source file and all three
class inventories, exact Maven command, successful execution record, exact one
JUnit method with no retry/flaky results, original inventory, semantic replay
receipt and exact negative cases. REMOVE also requires its successful captured
prefix replay and independently recollects the original sidecar's owner,
callback, event/result hash and object bindings.

The reader manifest includes every V5.3 Python module, the V4.3 format dependency,
format catalogue and frozen acceptance plan. Its files must match the recorded
producer source, so an old producer plus a new diagnostic reader cannot qualify
as the final-source cohort. A new collector option, `--portable-toolchain`, uses
the existing [hosted tool identity](PHASE_3_REMOVE_PROCESS_HOSTED.md): actual tool
versions and binary hashes determine the comparable pin; original host-specific
diagnostics remain retained. Default legacy toolchain recording remains supported.

Producer receipts are prerequisites. Every member is independently replayed with
[joining profile ballot composition](PHASE_3_PROFILE_BALLOTS.md) or
[ordinary REMOVE ballot composition](PHASE_3_REMOVE_BALLOTS.md), including the
full preceding physical/network/export/retention chain. REMOVE includes actual
captured retirement prefixes. Then every declared ballot negative must return
its exact status and reason. Only adoption cases whose target is absent in the
validated original may be `NOT_APPLICABLE`; no blanket ADD/REPLACE exception is
inferred from the profile name.

The joining negatives preserve physical/wire/other observations; REMOVE negatives
also replay continuous retention and retirement. As in those existing readers,
mutated full prerequisite chains are not claimed. This gate does not rerun every
earlier layer's negative suite or establish complete original-observation coverage.

The aggregate requires exactly seven distinct producer paths and original plan
identities. It rechecks each producer after replay, then all seven and the reader
again before acceptance. Missing, extra, failed, aliased, copied, changed or mixed
members cannot pass. Failures remain in results while other submitted members
finish. No measurement or JVM execution is automatically retried.

## Commands

Inspect the frozen catalogue and current reader hash:

```bash
python3 -B -m scripts.v53.profile_matrix plan > PLAN.json
```

For a later authorized native cohort, freeze one recorded source and use it for
all members. Representative collector commands are:

```bash
python3 -B -m scripts.v53.joining_profile_run NEW_3_ADD_PRODUCER \
  --profile 3-ADD --complete --portable-toolchain --maven /opt/maven/bin/mvn \
  --source-from PINNED_SOURCE_PRODUCER
python3 -B -m scripts.v53.remove_profile_run NEW_4_REMOVE_PRODUCER \
  --profile 4-REMOVE --retirement-captures --portable-toolchain \
  --maven /opt/maven/bin/mvn --source-from PINNED_SOURCE_PRODUCER
```

Pin source/build manifest SHA-256, the toolchain identity pin, and the reader
manifest SHA-256 from that cohort. Complete producer directories retain source,
classes, tools, reports, logs, raw history and sidecars. For aggregate input,
the seven directory names are the lowercase profile IDs printed by `plan`.

```bash
python3 -B -m scripts.v53.profile_matrix member NEW_MEMBER_CHECK \
  --producer ORIGINAL_PRODUCER --profile 3-ADD \
  --source-sha256 SOURCE_SHA256 --build-sha256 BUILD_SHA256 \
  --toolchain-sha256 TOOLCHAIN_SHA256 --reader-sha256 READER_SHA256
python3 -B -m scripts.v53.profile_matrix aggregate NEW_AGGREGATE \
  --inputs EXACT_SEVEN_PRODUCER_DIRECTORIES --workers 4 \
  --source-sha256 SOURCE_SHA256 --build-sha256 BUILD_SHA256 \
  --toolchain-sha256 TOOLCHAIN_SHA256 --reader-sha256 READER_SHA256
```

These verification commands never execute a JVM. Aggregate workers are bounded
from one to four, with one negative worker per member. Aggregate progress is
printed at completion and on sixty-second polling intervals while replay is
pending; it is also retained in `progress.jsonl`. Output directories are exclusive;
failure receipts are preserved. The collector's native command still reports
minute progress and retains its existing fixture bounds.

## Evidence and remaining work

The [implementation receipt](phase3-evidence/profile-matrix.json) records tests
and retained-result checks. Synthetic successful matrices test orchestration and
provenance guards only. Historical result compatibility checks inspect existing
reader output; they are not new physical replays or new native executions.

Measured validation: all 1,931 V5.3 Python tests pass, including 23 new matrix
and collector regressions; those 23 also pass with Python assertions disabled.
Four retained ADD/REPLACE/REMOVE result contracts match. Three historical
producers are correctly refused (one older reader source; two retained failures).
No original history was rerun or modified. The initial synthetic metadata fixture
errors and the premature missing-receipt link check remain in the audit logs.

A complete successful cohort may set
`declaredMembershipProfileMatrixQualified=true` for the stated implemented
composition. It must retain `phase3Complete=false`,
`originalObservationCoverageComplete=false` and `processDeathQualified=false`.
The exact-source hosted seven-profile run, process/fault cohorts, combined bounds
and frozen S/N mapping remain in the
[deferred acceptance plan](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback removes the new matrix adapter and its tests; collectors can revert the
optional tool recording and inventory additions without changing runtime Java,
persisted formats, POMs, Required checks or workload parameters. Preserve all
original histories and failure evidence. No paid cloud work belongs to this batch.
