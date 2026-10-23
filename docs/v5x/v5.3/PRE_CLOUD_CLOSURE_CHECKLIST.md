# V5.3 local pre-cloud completion audit

Status: **OPEN**, future roadmap. The active operator goal is continuous local
development through Phase 2 closure, with a local commit after each validated
batch and unified operator acceptance afterwards. This document retains the
later pre-cloud obligations; it does not authorize automatically continuing into
Phases 3–6 after that goal is complete.

| Required stage | Current authoritative state / required completion evidence |
| --- | --- |
| Phase 0 contract | [Local closure audit](PHASE_0_CLOSURE_AUDIT.md); retain exact protocol/API/format/resource/acceptance contracts |
| Phase 1 foundations | [Local closure audit](PHASE_1_CLOSURE_AUDIT.md); later storage/runtime evidence must replace conditional fixture assumptions |
| Phase 2 storage | [Closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) remains OPEN: complete durable recovery, adoption, phased votes/application, floors, retirement, rotation and offline initialization |
| Phase 3 protocol | Required: real learner lifecycle, selected activation, joint transition/finalization, authority discovery, bounded retries and adversarial deterministic/network/process qualification |
| Phase 4 public operations | Required: enabled APIs for add/remove/replace and queryable identities, actual inherited read semantics, operation/result retirement, same-version maintenance and compatibility |
| Phase 5 hardening | Required: combined election/read/reconfiguration/restart/resource cases with independent original physical/history validation, exact negatives and preserved failures; frozen S/N inventory mapped requirement by requirement |
| Phase 6 local workload | Required: frozen executable workloads, complete prescribed histories/repetitions/controls, resource and causal measurements, portable original-first replay and no measurement retry relabeling |
| Released predecessor integration | Required: verify actual V5.2 release/tag/artifacts and changes since the branch base; integrate semantically without changing the separate experiment's checkout or evidence |
| Unified local acceptance | Required: current complete compatibility, build/reproducibility, public runtime, recovery, fault and evidence gates, all relevant frozen inventories and documentation aligned with the final source |
| Cloud preparation | Required: source-bound plan, runner/credential/cleanup/retention safety, soft experiment time/cost budgets as authorized, explicit paid-run boundary and operator instructions; cloud execution itself is outside this goal |
| Completion decision | Required: inspect final code, tests, artifacts and docs for every row; local passes cannot be called protected CI, production release or cloud evidence |

The implementation order and integration rules remain in the
[local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md). Later stages must be
expanded into concrete entry/closure checklists against the frozen
[acceptance register](ACCEPTANCE_REGISTER.md) and [machine plan](acceptance-plan.json)
before their implementation. A component test, dummy runtime, omitted scenario or
weakened oracle cannot replace a stage. Unavailable external release evidence must
be recorded honestly while independent implementation work continues.

Work and commits stay on `feat/v53-cluster-operations`, with no push/PR/tag/cloud
dispatch under this authorization. Protected acceptance requiring a remote push
and actual paid runs remain separate operator-controlled actions; their pending
status must remain visible at the final local handoff.
