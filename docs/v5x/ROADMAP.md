# GeneralSearchEngine V5.x roadmap

- **Status:** Phase 1 accepted; Phase 2 storage candidate locally validated
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
`34919817954` passed. Phase 1 merged through protected PR #146 as `2e78bddd`;
exact-master CI `34930568130` passed. Phase 2 adds production local storage and
independent crash/format inspection; protected acceptance remains pending. Its
[entry plan](v5.0/PHASE_2_ENTRY_PLAN.md), [format](v5.0/PHASE_2_STORAGE_FORMAT.md),
[baseline](v5.0/PHASE_2_BASELINE.md) and [checklist](v5.0/PHASE_2_CHECKLIST.md) record
that boundary. Phase 3 quorum/apply work starts after Phase 2 exact-master CI passes.
