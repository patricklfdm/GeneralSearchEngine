# V5.0 Phase 1 checklist

- **Status:** Candidate implementation; protected-master acceptance pending
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
- [x] V1 through V4 consumers continue compiling against the V5 core.
- [x] Exact V4.4 artifact comparison is added to the compatibility profile.

## Independent safety foundation

- [x] History model covers epoch promise, append, ACK, proof, apply and recovery floor.
- [x] No quorum cannot commit or advance application sequence.
- [x] Stale epoch, conflicting content and committed truncation fail closed.
- [x] Uncommitted suffix removal is distinguished from committed history.
- [x] Logical protocol fixture freezes message and rejection families.
- [x] Stable force, quorum-ACK, proof, apply, publication and response barriers are frozen.
- [x] Bounded manifest/log/proof/snapshot fixtures have an independent inspector.
- [x] Deterministic delivery/drop/delay/duplicate/disconnect trace is serializable.
- [x] Serialized trace replay is exact and stable.

## Process and evidence foundation

- [x] Three separate JVM workers run concurrently in isolated directories.
- [x] Crash uses an exact captured PID and real `SIGKILL`.
- [x] Configured leader restarts under a distinct fixture generation.
- [x] A classified storage-fault command terminates only its exact worker and restarts cleanly.
- [x] Checksummed structured evidence is independently validated.
- [x] Harness workers open no product authority and no network listener.
- [x] Finite frame, append, queue, in-flight, retry, timeout, snapshot-chunk, log and staging bounds are tested.

## No-GCP lane

- [x] Fake profiles freeze experiment, failure-drill and canonical topology counts.
- [x] Each topology has exactly three concurrent voters.
- [x] Canonical topology repetitions are serial.
- [x] Peak planning caps are 24 vCPU and 450 GiB disk.
- [x] Provisioning failure retains evidence and proves VM, disk, firewall and staging cleanup receipts.
- [x] Manual workflow hard-rejects non-master refs and restricts execution to `plan` and `fake`.
- [x] Workflow has no GCP authentication or resource-creation step.
- [x] Machine/image/IAM/quota/firewall/GCS instructions remain Phase 6 preflights.

## Exit

- [x] Full local reactor, model, process, fake-cloud and consumer gates pass.
- [ ] Protected Phase 1 PR accepts the foundation.
- [ ] Exact-master CI passes before Phase 2 begins.

Paid cloud work, baseline registration and any production replication path remain
unauthorized by this checklist.
