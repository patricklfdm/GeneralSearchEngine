# V5.1 Phase 5 checklist

**Status:** Batch A implemented and locally qualified; protected acceptance pending. Full Phase 5
acceptance remains open.

- [x] Phase 4 accepted through PR #208, master
  `b0d586f32b01f59aadfa940d7f778a8a2b5ea078`, exact-master CI `35802660895`.
- [x] User entered `test/v5.1-phase5-hardening` and the [Batch A plan](PHASE_5_ENTRY_PLAN.md).
- [x] Three rounds each of combined partition/held-ACK/crash and retained whole-group restart.
- [x] Independent process/archive binding, chosen-prefix and public outcome checks.
- [x] Bounded history/resource accounting and evidence-negative mutations.
- [x] Regression-backed correction for private rebuild exceeding the engine batch limit.
- [x] CI gate and always-retained evidence in the public lifecycle lane.
- [x] Final-source local gates and [validation record](PHASE_5_COMBINED_RECOVERY.md#local-validation).
- [ ] Protected Batch A acceptance and exact-master CI.
- [ ] Batch B: freeze and execute broader corruption/recovery/pressure and cancellation/close combinations.
- [ ] Batch C: reconcile complete Phase 5 evidence, resource bounds and protected acceptance.
- [ ] Separate Phase 6 entry decision; no paid-cloud execution authorized by this batch.
