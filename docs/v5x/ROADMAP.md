# GeneralSearchEngine V5.x roadmap

- **Status:** Phase 0 accepted; Phase 1 candidate locally validated
- **Reference:** published `4.4.0`

## Version sequence

| Version | Boundary | Completion question |
| --- | --- | --- |
| 5.0 | Configured-leader replication | Can one fixed three-voter group commit, recover and catch up without ambiguity? |
| 5.1 | Automated leadership | Can a quorum safely fence an old leader and restore write availability? |
| 5.2 | Replica reads | Can followers serve only the consistency they explicitly prove? |
| 5.3 | Cluster operations | Can membership and maintenance change without violating committed history? |
| 5.4 | Final hardening | Is the replicated single-shard line a stable future architecture reference? |

## V5.0 gates

V5.0 follows Phases 0 through 8 from the development charter. Every phase starts
from a successful exact-master CI boundary and ends through protected review.

The hard gates are:

- no production path before the Phase 0 authority and failure contract is accepted;
- no production path before Phase 1 has an independent model, deterministic network
  harness, separate-process crash harness, fake-cloud workflow and exact bounds;
- no successful application Future without durable entry quorum, durable commit proof,
  ordered application and leader snapshot publication;
- no paid cloud work before exact-source local, fake-cloud, IAM, quota, cleanup and
  cost preflights pass;
- no canonical evidence from serial stand-ins: the three voters must run concurrently;
- no baseline registration before independent member and set validation; and
- no release claim before signed publication and post-publication reconciliation.

Phase 0 merged through protected PR #145 as `105537c8`; exact-master CI run
`34919817954` passed. The locally validated Phase 1 candidate opens the declaration-only
replication artifact, independent history/transport/format models, three-JVM
process/storage crash scaffold and no-GCP workflow. Protected-master acceptance is
pending; its records are under [`v5.0/`](v5.0/).
