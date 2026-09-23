# V5.1 Phase 6 checklist

**Status:** entry accepted through PR #215; rich model foundation accepted through
PR #216. The [local runtime](PHASE_6_LOCAL_PERFORMANCE.md) merged through PR #217,
master `e3efda820beef9efcd6f6f06e8af71006c3b85ce`, with exact-master full CI
`35889987294`. The [resource recovery follow-up](PHASE_4_RESOURCE_LIMITS.md#recovery-scheduling-after-the-phase-6a-resource-rerun)
changes the runtime again; full 6A protected acceptance and cloud qualification
remain pending on the corrected artifact.
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
- [ ] Resource recovery follow-up: deterministic alternate-peer regression, unchanged public resource gate and corrected-source protected CI accepted.
- [ ] 6A: physical/semantic/timing/resource negatives, relevant regressions and exact-source full CI pass.
- [ ] 6B: local calibration retained; complete cloud loads, timings, counts, bytes and numerical criteria frozen through review.
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
