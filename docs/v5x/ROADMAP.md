# GeneralSearchEngine V5.x roadmap

- **Status:** V5.0 published and reconciled; V5.1–V5.4 remain planned
- **Reference:** published `4.4.0`

## Version sequence

| Version | Boundary | Completion question |
| --- | --- | --- |
| 5.0 — published | Configured-leader replication | Accepted through Phases 0–8; see the [release record](v5.0/RELEASE_CHECKLIST.md). |
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
was accepted in PR #154 with exact-master CI `35020203126`. [Step C public runtime](v5.0/PUBLIC_ADMISSION_RUNTIME.md)
was accepted through [PR #155](https://github.com/patricklfdm/GeneralSearchEngine/pull/155)
at `836137aba672c010d0c7e3fc07bc194359543d9f`, with
[exact-master CI 35031124266](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35031124266)
passing all admission and Phase 1–5 gates.

The [Phase 6 entry plan](v5.0/PHASE_6_ENTRY_PLAN.md) was accepted in PR #156,
with exact-master documentation CI `35039318340` passing.
[6A local performance](v5.0/PHASE_6_LOCAL_PERFORMANCE.md) was accepted in PR #157,
with exact-master CI `35043760510` passing.
[6B cloud runner and preflight](v5.0/PHASE_6_CLOUD_RUNNER.md) was accepted in PR #158,
with exact-master CI `35051728286` passing. The
[full cloud workload plan](v5.0/PHASE_6_CLOUD_WORKLOAD_PLAN.md) was accepted in PR #159
with exact-master documentation CI `35053778177` passing.
[Cloud workload and evidence](v5.0/PHASE_6_CLOUD_WORKLOAD.md) were accepted in PR #160
with exact-master full CI `35058372449`.
[Runner preset qualification](v5.0/PHASE_6_RUNNER_PRESETS.md) was accepted through
PR #161/#162 and exact-master CI `35069706211`.
[Remote workload execution and evidence](v5.0/PHASE_6_REMOTE_WORKLOAD.md) was
accepted through PR #163. The measured source `340df06148bc7d5a25a29a55c3ee928c9472dd09`
passed full CI `35384694759`, three canonical repetitions, experiment and failure-drill.
The [6D review](v5.0/PHASE_6_CANONICAL_REVIEW.md) and independent complete-set validation
are complete. Registration PR #179 and telemetry correction PR #180 passed
exact-master CI `35421934224`, closing [Phase 6](v5.0/PHASE_6_CHECKLIST.md).
[Phase 7](v5.0/PHASE_7_CHECKLIST.md) merged through PR #181 as
`e6afb5349c018fe163d4938d7637a4de8854d4ea`; exact-master CI `35427118768` passed.
[Phase 8](v5.0/RELEASE_CHECKLIST.md) published signed tag `v5.0.0` in workflow
`35428718030`, with three Central artifacts, nine canonical JARs and independent
V1–V5 consumer verification. Later minor versions remain separate planned work.
