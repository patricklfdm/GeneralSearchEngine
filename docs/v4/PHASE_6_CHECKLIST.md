# V4.0 Phase 6 checklist

**Status:** all Phase 6 acceptance work is complete; the protected evidence merge and
its exact-master CI form the Phase 7 entry boundary

## Entry and invariants

- [x] Phase 5 merged through protected PR #82 at
  `c9a8b4725f3c44bced40764d1a9b3e9a4eb37b51`.
- [x] Exact-master Phase 5 CI run `33597658600` completed successfully.
- [x] Add no supported public API or storage-format `1.0` change.
- [x] Preserve force-before-publication, Future completion, authority, corruption,
  terminal failure and conservative-cleanup semantics.
- [x] Keep published V1–V3.4 and current-source in-memory behavior frozen.

## Local measurements

- [x] Separate in-memory and durable single/bulk JMH completion cells.
- [x] Preserve p50/p95/p99/max rather than reporting throughput alone.
- [x] Expose actual force groups through package-private benchmark instrumentation.
- [x] Measure checkpoint elapsed time, CPU, retained bytes and temporary peak.
- [x] Measure WAL-only, checkpoint-only and checkpoint-plus-WAL open stages.
- [x] Record document/index rebuild, WAL unit and byte identities.
- [x] Run a bounded mixed reader/writer/checkpoint long-run cell.
- [x] Preload every operational corpus in audited batches within the engine atomic
  mutation bound.
- [x] Require identical in-memory/durable logical checksums.
- [x] Reject incomplete or internally contradictory performance evidence.

## Independent cloud family

- [x] Keep suite `v4.0-durable-single-node-suite-v1` and preset
  `v4.0-durable-single-node-v1` separate from all V3 modes and registries.
- [x] Require exact protected-master source, Standard `c3d-standard-30`, pinned image,
  ext4 persistent data disk, fixed identities and bounded runtime.
- [x] Make experiment one member and canonical exactly three comparable members.
- [x] Schedule canonical members serially while preserving fresh VM/disk isolation.
- [x] Require GCS retention for canonical and failure-drill evidence.
- [x] Aggregate and checksum member identities before canonical eligibility.
- [x] Provide append-only registration for `v4.0.0-durable-cloud` only.
- [x] Validate dry-run and fake-cloud paths without GCP access.

## Preserved-disk failure drill

- [x] Use a data disk with auto-delete disabled rather than the writer boot disk.
- [x] Hard-halt after durable WAL force and before Future completion.
- [x] Delete the writer VM while retaining the data disk.
- [x] Attach the same disk to a separate replacement recovery VM.
- [x] Independently inspect the durable prefix before production recovery.
- [x] Recover, continue/reopen, retain checksummed evidence and delete every resource.

## Remaining acceptance

- [x] Full clean reactor, compatibility, release artifact and JMH gates pass.
- [x] Protected Phase 6 implementation PR #83 and exact-master CI run `33604967584`
  pass.
- [x] One paid experiment on the exact accepted source passes and is reviewed.
- [x] One paid preserved-disk failure drill passes with cleanup receipt.
- [x] Three comparable canonical members pass on one exact final source.
- [x] Register the reviewed set as `v4.0.0-durable-cloud`.

Phase 7 may prepare the release candidate only after required Phase 6 evidence is
reviewed. Performance results cannot weaken durability semantics.
