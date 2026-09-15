# GeneralSearchEngine V5.x roadmap

- **Status:** Phase 4 accepted; Phase 5 hardening candidate locally validated
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
exact-master CI `34930568130` passed. Phase 2 was accepted through protected PR #147 at `1895598`; exact-master CI
`34934537274` passed. Phase 3 was accepted through protected PR #148 at `911c9de`;
exact-master CI `34940262703` passed. Phase 4 was accepted through protected PR #149
at `a67e654`; exact-master CI `34950041552` passed. Phase 5 implements hardening under
its [entry plan](v5.0/PHASE_5_ENTRY_PLAN.md), [design](v5.0/PHASE_5_HARDENING.md),
[baseline](v5.0/PHASE_5_BASELINE.md) and [checklist](v5.0/PHASE_5_CHECKLIST.md).
Protected Phase 5 acceptance and exact-master CI precede subsequent work. Complete
public bootstrap/lifecycle admission is still required before public runtime/cloud
admission; Phase 5 does not by itself establish Phase 6 paid-run readiness.
