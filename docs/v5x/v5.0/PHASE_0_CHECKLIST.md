# V5.0 Phase 0 checklist

- **Status:** Accepted through protected master
- **Production Java changes:** none authorized

## Predecessor and scope

- [x] Published `v4.4.0` is the immutable behavior and failure oracle.
- [x] One dataset, one group and exactly three fixed voters are frozen.
- [x] V5.0 is configured-leader replication correctness, not complete HA.
- [x] Election/promotion, follower reads, membership change and sharding are deferred.
- [x] Crash/omission/corruption-detection and non-Byzantine assumptions are explicit.

## Identity and leadership

- [x] Immutable genesis manifest contents and digest are frozen.
- [x] Group, configuration and node identities are explicit and path/address independent.
- [x] V5.0 initial epoch and configured leader identity are frozen.
- [x] Every leader incarnation requires a greater quorum-persisted epoch.
- [x] Durable voter promises fence stale/different incarnations without clock leases.
- [x] Conflicting manifests or epoch promises fail closed.

## Log, commit and visibility

- [x] Replicated log, CommitIndex, AppliedIndex and ApplicationSequence are distinct.
- [x] Document, bulk and index-lifecycle operations share one deterministic order.
- [x] Atomic bulk remains one entry and one all-or-nothing apply.
- [x] Exact predecessor and digest-chain validation are required.
- [x] Same-entry retry is idempotent; same identity/different bytes fails closed.
- [x] Durable entry quorum is exactly two voters and counts only after force.
- [x] Durable commit proof is forced on two voters before Future success.
- [x] Commit → apply → immutable publication → Future success order is frozen.
- [x] Search exposes only AppliedIndex and no quorum cannot produce new success.
- [x] Client timeout/cancellation remains indeterminate.

## Storage and recovery

- [x] New outer `gse-replicated (1,0)` family is frozen.
- [x] Replicated log/proof is authority; V4 WAL is not a second authority.
- [x] Materialization and derived images remain reconstructible.
- [x] Logical history immutability is separated from safe physical compaction.
- [x] Quorum recovery-floor requirements prevent deletion of the last recovery source.
- [x] Leader restart requires new-epoch fencing and commit-proof reconciliation.
- [x] Follower incremental catch-up and snapshot-install rules are frozen.
- [x] Permanent same-NodeId disk reconstruction is distinguished from membership change.
- [x] A replaced disk cannot vote; leader-disk reconstruction requires both survivors.
- [x] Snapshot staging, verification, atomic install and anti-regression are frozen.
- [x] Arbitrary live-directory copy is unsupported.

## Bootstrap and compatibility

- [x] Bootstrap is offline plan/apply into three absent targets.
- [x] Empty and independently verified V4.4-backup sources are supported directions.
- [x] Bootstrap preserves the V4 source and partial targets never become authority.
- [x] Live in-place conversion and mixed-version replication are unsupported.
- [x] Replication is an additive optional artifact over unchanged core/processor behavior.
- [x] Embedded one-node-per-JVM deployment and no-daemon boundary are frozen.
- [x] Existing mutation, checkpoint, backup, close and currentSequence mappings are frozen.
- [x] Application backup and group-bound replica snapshot are distinct.

## Protocol, bounds and security

- [x] Logical protocol `gse-replication/1.0` message families are frozen.
- [x] Unknown major/mismatch/stale epoch/integrity/capacity failures reject before mutation.
- [x] Safety is independent of clocks, timeout and heartbeat.
- [x] Every queue/frame/batch/in-flight/retry/retention/staging resource is bounded.
- [x] Phase 1 must freeze exact numeric defaults before Phase 2 production storage.
- [x] Trusted-private-network/non-Byzantine security assumptions are explicit.
- [x] No TLS, Internet exposure or hostile-network security claim is implied.

## Harness and evidence

- [x] Independent history model and property schedules begin in Phase 1.
- [x] Structured trace and exact deterministic replay begin in Phase 1.
- [x] Separate-JVM crash/storage harness begins before production replication.
- [x] Fake-cloud and real durable cloud lanes are first-class Phase 1 infrastructure.
- [x] Every cloud topology contains three concurrent voters.
- [x] Current quota planning caps are 24 vCPU and 450 GiB provisioned disk per topology.
- [x] Serial canonical repetitions cannot substitute serial nodes within a topology.
- [x] WIF/IAM/GCS-prefix/quota/image/cost/cleanup preflights precede paid work.
- [x] Planned schema, suite, preset and baseline identities are distinct from V4.
- [x] Paid runs and baseline registration remain Phase 6 work.

## Phase 0 acceptance

- [x] No production Java or replication implementation is part of this candidate.
- [x] Critical decisions are represented under `docs/v5x/`, not only in root prompts.
- [x] Documentation/reference checks pass on the candidate branch.
- [x] Review confirms no unresolved P0 semantic blocker.
- [x] Protected PR #145 accepts the Phase 0 contract at `105537c83921aaab8fc0d4cf911b043f1efac6e1`.
- [x] Exact-master CI run `34919817954` passes before Phase 1 begins.

Phase 1 opened from that exact accepted boundary on `feat/v5.0-phase1-foundation`.
