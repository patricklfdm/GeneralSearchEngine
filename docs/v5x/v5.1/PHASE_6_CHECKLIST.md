# V5.1 Phase 6 checklist

**Status:** entry/model foundation accepted; runtime and its corrections merged
through PR #219 at `54e203eeca6c087b7ba03954d546c7682e8338f2`. Exact-master CI
`35920225478` passed all nineteen jobs and all 24 V5.1 verification steps, including
public bounds, resources and local performance. The [6A acceptance record](PHASE_6_LOCAL_ACCEPTANCE.md)
reconciles original evidence and downloaded replay. Its final protected review and
the [6B cloud contract candidate](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) are pending.
PR #220 merged these candidates at `717bed8f578019c71ffe3d739deaf067ec0fa8d2`.
Master CI `35927462738` passed the performance gate but failed Phase 5A's
[post-restart write assumption](PHASE_5_COMBINED_RECOVERY.md#post-pr-220-correction-a-recovered-read-does-not-lease-leadership).
Accept the corrected driver and exact-source full CI before proceeding to 6C.
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
- [x] 6A local candidate: all three healthy modes and bounded concurrent failover/rejoin history pass; protected acceptance remains pending.
- [x] PR #217 runtime implementation merged; exact-master CI `35889987294` passed all nineteen jobs.
- [x] Resource recovery follow-up: corrected-runtime resource/performance gates passed exact-master CI `35920225478`.
- [x] 6A runtime: physical/semantic/timing/resource negatives, relevant regressions and exact-source full CI pass at PR #219.
- [x] 6A review candidate: original downloaded performance evidence independently revalidated; receipt/source/member identities retained.
- [ ] Protected acceptance of the final 6A review and portable evidence replay correction.
- [x] 6B candidate: trace-backed local calibration and synthetic full-slot encoding retained, with cloud execution explicitly absent.
- [x] 6B candidate: closed cloud plan, three rich tapes, fifteen cells, exact allocations, evidence ceilings and numerical completion criteria.
- [ ] 6B: protected acceptance of the workload hash and calibration; full rich concurrency/remote schedule execution remains a 6C prerequisite.
- [ ] 6C: V5.1 runner, workflows, identities, remote adapter and same-path fake failures qualified.
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
