# V4.4 to V5 architecture handoff

- **Status:** Final — published V4.x compatibility and failure-classification reference
- **Stable release:** GeneralSearchEngine `4.4.0`
- **Stable predecessor:** GeneralSearchEngine `4.3.0`

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
format, lifecycle, failure and resource families. Production change remains zero;
Phase 6 accepted the frozen implementation without reopening admission.

The V5 comparison reference binds signed tag `v4.4.0` to protected-master commit
`1052a0bc0d84cb0d4245b07f3ba1ff6dae651dda`, exact-master CI `34899198199`, the
`v4.4.0-final-durable-cloud` registration, and the exact six-JAR inventory in
`candidate-artifacts.sha256`. Release workflow `34900681485`, Central deployment
`8fc934f3-533f-4452-9b6e-7ffc01dfb6ad`, production deployment `6447226553`, GitHub
Release `388745840`, remote signatures/checksums and clean V3/V4 consumers all
completed successfully. These identities close the V4.x handoff rather than merely
describing a candidate.

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
