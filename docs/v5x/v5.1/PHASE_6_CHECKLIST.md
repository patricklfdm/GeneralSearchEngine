# V5.1 Phase 6 checklist

**Status:** entry design candidate; implementation, cloud qualification and performance
results remain pending. Governing documents: [entry plan](PHASE_6_ENTRY_PLAN.md),
[local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md).

- [x] Phase 5 accepted through PR #214, master `15c8c68011e37370dfcd31ee855f91247c3771d8`.
- [x] Exact-master docs CI `35830149418` and unchanged-runtime full CI `35826641489` distinguished.
- [x] Local corpus/control/mode semantics, counts, timing, resource/evidence bounds and independent validation specified.
- [x] Cloud E-row mapping, planning ceilings, operator sequence choices and fresh admission boundaries specified.
- [ ] Protected acceptance of this entry and local contract.
- [ ] 6A: materialized plan/schema and isolated external published-control/candidate probes.
- [ ] 6A: full local healthy modes and bounded concurrent failover/rejoin history pass.
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
