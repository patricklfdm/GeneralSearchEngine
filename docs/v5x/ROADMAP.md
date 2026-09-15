# GeneralSearchEngine V5.x roadmap

- **Status:** Phase 5 and public-admission contract accepted; Step A accepted; Step B offline authority under review
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
- no Phase 6 end-user runtime/cloud lane before complete public bootstrap/lifecycle
  admission and its real three-JVM public-consumer gate;
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
at `a67e654`; exact-master CI `34950041552` passed. Phase 5 was accepted through
[PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150) at `4a8fd3d`;
[exact-master CI 34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066)
passed. Its [baseline](v5.0/PHASE_5_BASELINE.md) and
[checklist](v5.0/PHASE_5_CHECKLIST.md) record the completed hardening boundary.

PR #151 accepted the [public-admission contract amendment](v5.0/PUBLIC_ADMISSION_CONTRACT.md),
with an explicit [API delta](v5.0/PUBLIC_ADMISSION_API.md). The
[entry plan](v5.0/PUBLIC_ADMISSION_ENTRY_PLAN.md) splits implementation into reviewed
declarations/byte fixtures, offline bootstrap/recovery operations and the complete
public runtime. These are completion gates between Phase 5 and Phase 6; the amendment
does not itself enable the public builder or establish paid-run readiness.
[Step A declarations and independent 1.1 bytes](v5.0/PUBLIC_ADMISSION_FOUNDATION.md) were accepted in PR #153
and exact-master CI `35006998165`. [Step B offline authority](v5.0/PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md)
is under review; Step C public runtime is next after its protected merge and master CI.
