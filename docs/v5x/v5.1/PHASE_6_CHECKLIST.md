# V5.1 Phase 6 checklist

**Status:** entry/model foundation accepted; runtime and its corrections merged
through PR #219 at `54e203eeca6c087b7ba03954d546c7682e8338f2`. Exact-master CI
`35920225478` passed all nineteen jobs and all 24 V5.1 verification steps, including
public bounds, resources and local performance. The [6A acceptance record](PHASE_6_LOCAL_ACCEPTANCE.md)
reconciles original evidence and downloaded replay. Its final review and the [6B cloud contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md)
were subsequently accepted through PR #222 as recorded below.
PR #220 merged these candidates at `717bed8f578019c71ffe3d739deaf067ec0fa8d2`.
Master CI `35927462738` passed the performance gate but failed Phase 5A's
[post-restart write assumption](PHASE_5_COMBINED_RECOVERY.md#post-pr-220-correction-a-recovered-read-does-not-lease-leadership).
PR #221 merged the recovery-write correction at `af68d8473f9998628e49189a2d8be658b8bfe116`.
Master CI `35932225694` then failed the
[per-round proof sampling boundary](PHASE_5_COMBINED_RECOVERY.md#post-pr-221-correction-confirm-proof-before-recording-a-drained-round)
and a [V5.0 retry fixture](../v5.0/PHASE_5_HARDENING.md#post-pr-221-follow-up-target-the-add-exchange).
PR #222 accepted both corrections at `33aa89bf8a6b4b0587fa6a127e481d73671a60ec`.
Exact-master CI `35937300754` passed all nineteen jobs and 24 V5.1 verification steps.
6A/6B are accepted. [6C1 remote control foundation](PHASE_6_REMOTE_FOUNDATION.md)
was accepted through PR #223, master `833da4947266b4edfbee2a0e6fe10055ed3be00c`;
exact-master CI `35942555519` passed all nineteen jobs and 25 V5.1 verification steps.
[6C2A rich JVM integration](PHASE_6_REMOTE_RICH.md) was accepted through PR #224,
master `28cd5edc0a63fd82a9c01dad028623acc529c9f2`, exact-master CI `35961961431`
(twenty jobs, 26 V5.1 gates). The [6C2B fault candidate](PHASE_6_REMOTE_FAULTS.md)
is the current review boundary; full 6C qualification remains open.
Governing documents: [entry plan](PHASE_6_ENTRY_PLAN.md),
[local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md).

- [x] Phase 5 accepted through PR #214, master `15c8c68011e37370dfcd31ee855f91247c3771d8`.
- [x] Exact-master docs CI `35830149418` and unchanged-runtime full CI `35826641489` distinguished.
- [x] Local corpus/control/mode semantics, counts, timing, resource/evidence bounds and independent validation specified.
- [x] Cloud E-row mapping, planning ceilings, operator sequence choices and fresh admission boundaries specified.
- [x] Protected entry/local-contract acceptance: PR #215, master `243434f6e1dc94422b57997b33eabb3cc1e8f64d`, docs CI `35831892351`.
- [x] 6A model candidate: closed machine-readable preset, independent rich decoder/projection and adversarial fixtures.
- [x] 6A model candidate: 90-call published V4.4 semantic execution, actual backup/checkpoint/reopen checks and three isolated core compilations.
- [x] Protected acceptance of the [model foundation](PHASE_6_MODEL_FOUNDATION.md): PR #216, master `bcac615aeef93dadcab6636162a86ce2156e5515`, exact-master full CI `35841378072`.
- [x] 6A implementation candidate: materialized plan/schema and isolated external published-control/candidate probes.
- [x] 6A local implementation: all three healthy modes and bounded concurrent failover/rejoin history pass.
- [x] PR #217 runtime implementation merged; exact-master CI `35889987294` passed all nineteen jobs.
- [x] Resource recovery follow-up: corrected-runtime resource/performance gates passed exact-master CI `35920225478`.
- [x] 6A runtime: physical/semantic/timing/resource negatives, relevant regressions and exact-source full CI pass at PR #219.
- [x] 6A review candidate: original downloaded performance evidence independently revalidated; receipt/source/member identities retained.
- [x] Protected acceptance of final 6A review and portable replay: PR #222, exact-master CI `35937300754`.
- [x] 6B candidate: trace-backed local calibration and synthetic full-slot encoding retained, with cloud execution explicitly absent.
- [x] 6B candidate: closed cloud plan, three rich tapes, fifteen cells, exact allocations, evidence ceilings and numerical completion criteria.
- [x] 6B: workload hash/calibration accepted through PR #222; full rich concurrency/remote schedule execution remains a 6C prerequisite.
- [x] 6C1 implementation candidate: durable command claims, fixed-arrival executor, disjoint time accounting and bounded binary evidence parts.
- [x] 6C1 local control qualification: real lost-response/duplicate/SIGKILL/cancel processes, complete synthetic tapes and independently checked collection.
- [x] 6C1 protected acceptance: PR #223, exact-master CI `35942555519`; control-only receipts do not qualify a GSE workload.
- [x] 6C2A implementation candidate: persistent JVM lanes, full frozen rich tapes, concurrent captured-cut oracle and portable binary replay.
- [x] 6C2A protected acceptance: PR #224, exact-master CI `35961961431`.
- [x] 6C2B fault implementation: twelve frozen public JVM schedules, bounded history/physical/resource validation and binary replay.
- [ ] 6C2B fault-document amendment and fault qualification protected acceptance.
- [ ] 6C2 full-size boundary: 512 actual slots, full basis/wire/transfer/re-proposal/pin and two-generation retention.
- [ ] 6C2: persistent JVM adapter, full rich concurrent cut validation, twelve fault cells and full-size retention qualification.
- [ ] 6C3: V5.1 runner, workflows, identities, remote adapter and same-path fake failures qualified.
- [ ] 6C: fresh configuration/IAM/image/quota/retention/cleanup readiness; exact-source full CI.
- [ ] 6D: priced complete-sequence request and fresh user confirmation; user-triggered paid execution only.
- [ ] 6D: experiment and failure-drill independently valid, with failures/costs retained.
- [ ] 6D: all three canonical repetitions valid on one admitted source/artifact/workload set.
- [ ] 6D: every member's raw evidence retained and cleanup/absence verified; no leftovers.
- [ ] 6E: independent set review and append-only baseline registration accepted.
- [ ] Full Phase 6 acceptance; only then a separate Phase 7 entry.

An entry merge does not check implementation or cloud boxes. The current
`scripts/v51/cloud_plan.py` is fake-control-plane-only. Existing V5.0 cloud evidence,
cleanup receipts, budget approvals and sequences do not satisfy V5.1 admission.
