# V5.0 Phase 1 checklist

- **Status:** Accepted through protected PR #146 and exact-master CI `34930568130`
- **Production replication:** disabled
- **Paid cloud:** disabled

## Entry

- [x] Phase 0 merged through protected PR #145.
- [x] Exact-master commit is `105537c83921aaab8fc0d4cf911b043f1efac6e1`.
- [x] Exact-master CI run `34919817954` passed.
- [x] All active development coordinates moved to `5.0.0-SNAPSHOT`.
- [x] Exact published `4.4.0` core checksum remains pinned.

## Artifact and API fixtures

- [x] Optional `general-search-engine-replication` module is in the local reactor.
- [x] Core does not depend on replication.
- [x] Group/member/endpoint/configuration/bounds/role/state/status/failure declarations exist.
- [x] Replicated engine, configured-leader activation and offline bootstrap shapes exist.
- [x] Declaration-only build/storage operations reject without side effects.
- [x] Source-level V5 consumer and module contract tests compile.
- [x] Reflection inventory exactly freezes every top-level public replication type.
- [x] Full public/protected signatures, nested enums, record components and constant values are frozen.
- [x] V1 through V4 consumers continue compiling against the V5 core.
- [x] Exact V4.4 artifact comparison is added to the compatibility profile.

## Independent safety foundation

- [x] History model covers epoch promise, append, ACK, proof, apply and recovery floor.
- [x] No quorum cannot commit or advance application sequence.
- [x] Control entries do not advance application sequence; each application/bulk entry advances it once.
- [x] Apply is monotonic and requires local durable proof; a lost proof ACK cannot authorize truncation.
- [x] Epoch/incarnation fencing and invalid quorum rejection leave state unchanged.
- [x] Stale epoch, conflicting content and committed truncation fail closed.
- [x] Uncommitted suffix removal is distinguished from committed history.
- [x] Logical protocol fixture freezes message and rejection families.
- [x] Java 21 NIO transport dependency and bounded binary frame envelope have golden fixtures.
- [x] Stable force, quorum-ACK, proof, apply, publication and response barriers are frozen.
- [x] Bounded manifest/log/proof/snapshot fixtures have an independent inspector.
- [x] Deterministic delivery/drop/delay/duplicate/disconnect trace is serializable.
- [x] Serialized trace replay is exact and stable.
- [x] Fault execution drives the history model with distinct entry/proof force and ACK deliveries.
- [x] Seeded schedules compare transcripts and final model state after serialized replay.

## Process and evidence foundation

- [x] Three separate JVM workers run concurrently in isolated directories.
- [x] Crash uses an exact captured PID and real `SIGKILL`.
- [x] Configured leader restarts under a distinct fixture generation.
- [x] A classified storage-fault command terminates only its exact worker and restarts cleanly.
- [x] Checksummed structured evidence is independently validated.
- [x] Parent PID/exit/concurrency observations agree with checksummed raw worker receipts.
- [x] CI retains foundation artifacts and failed process workspaces with `always()` upload.
- [x] Harness workers open no product authority and no network listener.
- [x] Finite frame, append, queue, in-flight, retry, timeout, snapshot-chunk, log and staging bounds are tested.

## No-GCP lane

- [x] Fake profiles freeze experiment, failure-drill and canonical topology counts.
- [x] Each simulated measurement requires overlapping lifetimes of exactly three voters.
- [x] Canonical simulation executes three repetitions; each waits for preceding resource deletion.
- [x] Peak planning caps are 24 vCPU and 450 GiB disk.
- [x] Provisioning failure retains evidence and proves VM, disk, firewall and staging cleanup receipts.
- [x] Boot and data disks are tracked separately; running failure cleans all created resources.
- [x] Incomplete cleanup fails validation and prevents the next topology.
- [x] Semantic negative cases fail even when modified evidence has recomputed valid checksums.
- [x] Manual workflow hard-rejects non-master refs and restricts execution to `plan` and `fake`.
- [x] Workflow has no GCP authentication or resource-creation step.
- [x] Machine SKU, zone and exact image catalog availability were verified read-only and recorded.
- [x] Fresh capacity/pricing/IAM/quota/firewall/GCS and guest-runtime checks remain Phase 6 preflights.

## Exit

- [x] Full local reactor, model, process, fake-cloud and consumer gates pass.
- [x] Protected Phase 1 PR #146 accepts the foundation at `2e78bddd`.
- [x] Exact-master CI `34930568130` passed before Phase 2 begins.

This checklist records the accepted Phase 1 scope. Production storage work proceeds
under the [Phase 2 entry plan](PHASE_2_ENTRY_PLAN.md); paid cloud and baseline
registration remain outside both phases.
