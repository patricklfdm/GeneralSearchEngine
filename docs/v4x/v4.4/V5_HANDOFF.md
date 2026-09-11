# V4.4 to V5 architecture handoff draft

- **Status:** Phase 5 draft; publication identities remain pending
- **Stable predecessor:** GeneralSearchEngine `4.3.0`
- **Candidate line:** `4.4.0-SNAPSHOT`

## Guarantees V5 must inherit

- immutable snapshots, lock-free readers, one authoritative writer and atomic bulk
  mutation visibility;
- V3.4 retrieval, ranking, pagination, highlighting and explanation semantics;
- force-before-success durable completion and indeterminate incomplete operations at
  crash;
- canonical fail-closed recovery, contiguous sequence authority, checksummed WAL and
  atomic checkpoint publication;
- checkpoint-consistent backup, independent structural inspection, absent-target
  restore and source-preserving offline migration;
- exact live/backup format meanings for `(1,0)`, `(1,1)` and `(1,2)`;
- reconstructible derived state that never becomes canonical authority; and
- bounded retention, plan-bound cleanup, exclusive ownership and deterministic
  continued operation after every successful recovery/restore/migration.

## Final V4.x comparison surface

V4.4 keeps the published Java API and persisted formats closed. It introduces no
`(1,3)`, implicit upgrade, repair, salvage, new ranking/retrieval behavior, new Maven
artifact or distributed authority. Its local matrix covers all ten frozen authority,
format, lifecycle, failure and resource families. Production change remains zero
unless later Phase 6 evidence contradicts the accepted admission record.

The V5 comparison reference must bind the eventual signed `v4.4.0` tag, exact
protected-master commit, exact-master CI, `v4.4.0-final-durable-cloud` registration,
six canonical unsigned/published JAR hashes, Central signatures/checksums and remote
consumer results. Those fields cannot be filled before Phases 6–8 and must not be
represented by this draft.

## Known limits retained by V4.4

- single node, single process owner and one authoritative writer;
- local block-device canonical storage; GCS is transport/evidence only;
- no replication, consensus, sharding, distributed query or network-partition
  guarantee;
- no live remote WAL, network-filesystem authority or cross-node durable cursor;
- no in-place migration, downgrade, history merge, heuristic repair or salvage;
- no physical power-loss/firmware claim beyond the explicit process/VM interruption
  and filesystem assumptions in the accepted evidence; and
- performance thresholds are exact-source release gates for the frozen environment,
  not portable user SLAs.

## Architecture deferred to V5

Replication topology, consensus, sharding, multi-writer coordination, remote durable
authority, vector/hybrid retrieval, new query semantics and any new storage format
require a new V5 Phase 0 decision. V5 may use V4.4 as a compatibility and failure-
classification oracle, but it may not silently reinterpret V4.x bytes or successful
completion guarantees.
