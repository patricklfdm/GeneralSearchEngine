# V5.1 Phase 5 checklist

**Status:** Batch A accepted at master `04d12316bd6971ac477cfcb08c5073b2252ecf2a`,
exact-master CI `35818964327` (all 19 jobs passed). Batch B accepted through PR #213,
master `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`, exact-master CI `35826641489`
(all 19 jobs and 23 V5.1 verification steps passed). [Batch C reconciliation](PHASE_5_ACCEPTANCE.md)
is complete for review; full Phase 5 protected acceptance awaits this review's merge.

- [x] Phase 4 accepted through PR #208, master
  `b0d586f32b01f59aadfa940d7f778a8a2b5ea078`, exact-master CI `35802660895`.
- [x] User entered `test/v5.1-phase5-hardening` and the [Batch A plan](PHASE_5_ENTRY_PLAN.md).
- [x] Three rounds each of combined partition/held-ACK/crash and retained whole-group restart.
- [x] Independent process/archive binding, chosen-prefix and public outcome checks.
- [x] Bounded history/resource accounting and evidence-negative mutations.
- [x] Regression-backed correction for private rebuild exceeding the engine batch limit.
- [x] CI gate and always-retained evidence in the public lifecycle lane.
- [x] Final-source local gates and [validation record](PHASE_5_COMBINED_RECOVERY.md#local-validation).
- [x] Protected Batch A acceptance and exact-master CI `35818964327` after PRs #209–#212.
- [x] Batch B: freeze and execute four corruption/recovery/pressure and cancellation/close combinations.
- [x] Batch B: physical/history/process/archive/resource checks and 60 rejected evidence variants.
- [x] Batch B: final implementation local qualification, shared consumer regression and required CI gate.
- [x] Protected Batch B acceptance: PR #213, exact-master CI `35826641489`.
- [x] Batch C: reconcile seven combined-fault cases plus supporting public/internal resource evidence.
- [x] Batch C: independently replay source/JAR/physical/history/archive/accounting checks and rejection variants.
- [x] Batch C: document resource ceilings, defect disposition, claim limits and Phase 6 design handoff.
- [ ] Protected acceptance of this Batch C review, completing Phase 5 within its recorded scope.
- [ ] Separate Phase 6 entry decision; no paid-cloud execution authorized by this batch.
