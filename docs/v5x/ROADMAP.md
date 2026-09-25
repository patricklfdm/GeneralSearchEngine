# GeneralSearchEngine V5.x roadmap

- **Status:** V5.0 published and reconciled; V5.1 Phase 3 accepted; Phase 4 accepted; Phase 5 accepted; Phase 6A/6B accepted; Phase 6C remote foundation; V5.2–V5.4 planned
- **Search/storage reference:** published `4.4.0`
- **V5.1 replication reference:** published `5.0.0`
- **Later-minor planning:** PROPOSED revision 0.1, 2026-09-19; V5.1 acceptance and phase scope are recorded below

## Version sequence

| Version | Boundary | Completion question |
| --- | --- | --- |
| 5.0 — published | Configured-leader replication | Accepted through Phases 0–8; see the [release record](v5.0/RELEASE_CHECKLIST.md). |
| 5.1 | Automated leadership | Can a quorum safely fence an old leader and restore write availability? |
| 5.2 | Replica reads | Can followers serve only the consistency they explicitly prove? |
| 5.3 | Cluster operations | Can membership and maintenance change without violating committed history? |
| 5.4 | Final hardening | Is the replicated single-shard line a stable future architecture reference? |

## Next entry and proposal status

The user has started [V5.1 Phase 0](v5.1/PHASE_0_ENTRY_PLAN.md), limited to contract
and evidence design. The [contract candidate](v5.1/PHASE_0_CONTRACT.md) supplies the
six planned documents; [protected acceptance](v5.1/PHASE_0_CHECKLIST.md) is
recorded for PR #184. The user authorized the [Phase 1 foundation](v5.1/PHASE_1_FOUNDATION.md);
it was accepted in PR #185 with exact-master CI `35491646610`. The user has entered
[Phase 2 storage](v5.1/PHASE_2_ENTRY_PLAN.md); Batch A was accepted in PR #186 with exact-master CI
`35495493715`. [Batch B recovery](v5.1/PHASE_2_RECOVERY.md) was accepted in PR #187
with exact-master CI `35503107173`. The user has entered [Phase 3](v5.1/PHASE_3_ENTRY_PLAN.md);
its transition kernel was accepted in PR #188 with CI `35507802486`. The
[runtime batch](v5.1/PHASE_3_RUNTIME.md) was accepted in PR #189 with CI `35527143425`.
[Phase 3C](v5.1/PHASE_3_REJOIN.md) was accepted in PR #191 with exact-master CI `35542143840`.
[Phase 4A](v5.1/PHASE_4_BOOTSTRAP.md) is accepted in PR #192 (master
`fce35d955e0b6b973014959e23fc38eb95dd2745`, CI `35547603482`).
[Phase 4B](v5.1/PHASE_4_PUBLIC_RUNTIME.md) is accepted through PR #193 (master
`6ca9418ae14bb3434e3ee2aa8dcc6ba2cd7e45b6`, exact-master CI `35554352587`).
[Phase 4C](v5.1/PHASE_4_PUBLIC_QUALIFICATION.md) is accepted through PR #194 (master
`6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4`, exact-master CI `35560692475`).
[Phase 4D](v5.1/PHASE_4_PUBLIC_FAULTS.md) is accepted through PR #195 (master
`da9f3e9fe957e61c0fe45cf041431a5c4c74cd79`, exact-master CI `35570118695`).
[Phase 4E](v5.1/PHASE_4_PUBLIC_RECOVERY.md) is accepted through PR #196 (master
`15eb04054f28ecb52b896eedb79775c257736e00`, exact-master CI `35579584390`).
[Phase 4F](v5.1/PHASE_4_PUBLIC_PROTOCOL.md) is accepted through PR #197 (master
`764cbf4a41bd6afc79e39cb3f97e612a3d66d39d`, exact-master CI `35591386329`).
[Phase 4G](v5.1/PHASE_4_PUBLIC_RECLAMATION.md) is accepted through PR #198 (master
`4833bddf08b95a9cd28d63ee0b1c78e2e3de16dc`, exact-master CI `35664882661`).
[Phase 4H](v5.1/PHASE_4_PUBLIC_BOUNDS.md) is accepted through PR #199 at
`fdf9482781e04727e20326fa0e32bcd281242f04` (exact-master CI `35688926607`).
[Phase 4I](v5.1/PHASE_4_PUBLIC_PROMISES.md) is accepted through PR #200 at
`6a781ac33945016645961ec1c6564d8975cd82fd` (exact-master CI `35693468905`).
[Phase 4J](v5.1/PHASE_4_PUBLIC_CANDIDATES.md) is accepted through PR #201 at
`04106a0c2e88010c2c14c43ad485bc3113ed1d05` (exact-master CI `35698045261`).
[Phase 4K](v5.1/PHASE_4_PUBLIC_PRESSURE.md) is accepted through PR #202 at
`3bb84b250800c7871745450491e56b6821195d1d` (exact-master CI `35705020751`).
[Phase 4L](v5.1/PHASE_4_RESOURCE_LIMITS.md) is accepted through PR #203 at
`a5595f8efad34ec96a3f6e883e5c9c9491004279` (exact-master CI `35712922357`).
[Phase 4M](v5.1/PHASE_4_BACKPRESSURE.md) is accepted through PR #204 / #205
at `39332feb71f877d3cbd976631e8a26a9cf2f607c` (exact-master CI `35753082195`).
[Phase 4N](v5.1/PHASE_4_PUBLIC_SELECTION.md) is accepted through PR #206
at `3f5b0b25b6484bf6ddc062dd25527bee0ddaedb4` (exact-master CI `35779031221`).
[Phase 4O](v5.1/PHASE_4_LIFECYCLE_HARDENING.md) is accepted through PR #207,
master `1a043615ec4a8de5b7f110d999c5f7268e5e165c` (exact-master CI `35794875603`).
[Phase 4P and full Phase 4](v5.1/PHASE_4_FINAL_COVERAGE.md) are accepted through
PR #208, master `b0d586f32b01f59aadfa940d7f778a8a2b5ea078` (exact-master CI `35802660895`).
[Phase 5A](v5.1/PHASE_5_COMBINED_RECOVERY.md) is accepted at master
`04d12316bd6971ac477cfcb08c5073b2252ecf2a` (exact-master CI `35818964327`, all 19 jobs passed).
[Phase 5B](v5.1/PHASE_5_COMBINED_LIFECYCLE.md) is accepted through PR #213 at
`fc1feca4dee6ee346e45d3afb22c4df9b9e0d945` (exact-master CI `35826641489`, all 19 jobs passed).
[Full Phase 5](v5.1/PHASE_5_ACCEPTANCE.md) is accepted through PR #214 at
`15c8c68011e37370dfcd31ee855f91247c3771d8` (docs-only master CI `35830149418`;
unchanged-runtime full CI `35826641489`). The [Phase 6 entry](v5.1/PHASE_6_ENTRY_PLAN.md)
is accepted through PR #215 at `243434f6e1dc94422b57997b33eabb3cc1e8f64d`
(docs-only master CI `35831892351`). The [rich model foundation](v5.1/PHASE_6_MODEL_FOUNDATION.md)
was accepted through PR #216 (master `bcac615aeef93dadcab6636162a86ce2156e5515`,
full CI `35841378072`). The [local runtime candidate](v5.1/PHASE_6_LOCAL_PERFORMANCE.md)
and corrections passed full master CI `35920225478` through PR #219. The
[6A review](v5.1/PHASE_6_LOCAL_ACCEPTANCE.md) reconciles original measurements;
the [6B cloud workload contract](v5.1/PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) adds a
closed fifteen-cell plan and trace-backed local calibration. Both are accepted
through PR #222 at `33aa89bf8a6b4b0587fa6a127e481d73671a60ec`, full master CI
`35937300754`. The [6C1 remote foundation](v5.1/PHASE_6_REMOTE_FOUNDATION.md) was accepted through
PR #223, exact-master CI `35942555519` (nineteen jobs, 25 V5.1 gates).
[6C2A rich JVM integration](v5.1/PHASE_6_REMOTE_RICH.md)
was accepted through PR #224, exact-master CI `35961961431` (twenty jobs,
26 V5.1 gates). [6C2B fault workloads](v5.1/PHASE_6_REMOTE_FAULTS.md) and the two
approved document-size exceptions were accepted through PR #225, exact-master CI
`35989431966` (all 21 jobs). PR #227 closed rich CI sharding, exact-master CI
`36064320654` (all 26 jobs). The [512-slot component gate](v5.1/PHASE_6_FULL_SIZE.md)
was accepted through PR #228, exact-master CI `36072038218`. The
[public runtime integration](v5.1/PHASE_6_FULL_SIZE_RUNTIME.md) was accepted through
PR #229, master `57622552e02addfae991642786e1a87a0633fb43`, exact-master CI
`36094121631` (27 successful jobs), closing 6C2. The
[6C3A cloud control candidate](v5.1/PHASE_6_CLOUD_CONTROL.md) starts the owned
runner and no-GCP failure qualification. Actual provider/remote integration,
configuration and cloud work remain open in the
[checklist](v5.1/PHASE_6_CHECKLIST.md).
The [next-development addendum](NEXT_DEVELOPMENT_ADDENDUM.md) is a proposed scope
refinement, not a replacement for the accepted [charter](DEVELOPMENT_CHARTER.md).
No implementation, version bump, paid run or release is authorized by these files.

V5.0 publication closes V5.0, not the entire V5 line. V6 may proceed as
[architecture research](../v6x/ARCHITECTURE_PREVIEW.md), while production work remains
on V5.x. The proposed V6 implementation prerequisite is a mature V5.4 handoff;
changing that gate requires an explicit reviewed decision.

## Proposed minor-release acceptance boundaries

| Minor | Required refinement before implementation | Public acceptance example |
| --- | --- | --- |
| V5.1 | Election and durable history reconciliation; old-leader fencing; compatible operating modes; safe leader-read admission; client outcome rules | Kill the current leader without manual activation, restore service on a surviving majority, preserve acknowledged history, and safely rejoin the old leader. |
| V5.2 | Strong leader, stale-allowed and history-bound at-least-index policies; publication-aware waits; bounded pins/cursors | A lagging replica waits or rejects exactly as requested and never disguises stale or uncommitted state as a stronger read. |
| V5.3 | Safe membership protocol; non-voting catch-up; serialized transitions; restartable operation identities | Add/remove/replace a member through interruptions without conflicting authority or unsafe cleanup. |
| V5.4 | Combined faults; longer runs; capacity/load sweeps; complete metadata/resource bounds; stable public group contract | Repeated elections, replica reads and maintenance coexist inside a measured supported operating envelope. |

Strong leader-read safety under automatic leadership is a V5.1 obligation, even
though public follower reads are V5.2 work. Preserve legacy V5.0 configured-mode
behavior explicitly; do not relabel its quorum-loss readable view as linearizable.

Learner catch-up does not replace a safe voting-configuration transition. Rolling
restart does not establish mixed-version rolling upgrade. Minimum-index reads do
not by themselves establish global freshness. All later minor scopes remain
proposed until their own Phase 0 is accepted.

## Evidence and reference progression

Published V4.4 remains the inherited search/storage oracle. V5.1 additionally pins
published V5.0 as its immediate replication reference; later minors pin their
immediate published predecessor and preserve the earlier guarantees.

The V5.0 cloud baseline records 49 scenario executions at controlled offered load,
not 49 distinct fault types, maximum throughput, automatic failover or sharding.
Each new boundary requires separately identified evidence, independently validated
results and explicit source/artifact identity. Do not relabel the measured V5.0
snapshot source as a later release commit.

Retain the established contract, independent-foundation, implementation, public
admission, fault-hardening, evidence and publication gates. Before paid work, renew
quota, cost, cleanup, source and authorization checks. A documentation-only CI pass
must not be reported as a fresh full-runtime or consensus validation.

The V5.0 section below preserves the accepted historical gates and records.

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
