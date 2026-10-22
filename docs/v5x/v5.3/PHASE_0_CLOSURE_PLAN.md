# V5.3 Phase 0 closure worklist

Operator instruction: continue until Phase 0 closes, commit intermediate batches
locally and continue. Work stays on `feat/v53-cluster-operations`, without push,
PR, tag, publication or cloud dispatch. Starting source: `acba545`.

The local contract/design exit is distinct from later protected acceptance and
runtime qualification. The operator deferred unified acceptance and integration
until after V5.2 publication. Do not invent a protected CI/merge record or require
changing the running V5.2 source to complete this local design work.

## Required work and evidence

| Work | Owning decisions | Exit evidence |
| --- | --- | --- |
| Queryable operation identity, revision, cancellation, terminal retirement and identity reservations | D01/D05/D09 | Exact state machine; crash, duplicate, old-ID, stale revision and capacity counterexamples |
| Removed-node reads, same-version rolling maintenance and cleanup boundary | D07 | Explicit capture/state matrix and revalidation counterexamples |
| Learner readiness before INTENT; global grants and steady-state rounds across changes | D02/D03/D04 | Integrated schedules with no pre-admitted learner, higher fences, lost replies and incomplete transitions |
| Incremental authority capsules, full descriptors, recovery/floor and resource lifetime | D01/D06/D09 | Bound-preserving extension and refusal cases; separate complete metadata and application byte obligations |
| Exact Java declarations, reason/outcome classes and storage/wire catalogs | D08 | Concrete API inventory, layouts, independent byte fixtures and mismatch/corruption negatives |
| Frozen workload and acceptance register | D10 | Numbered scenarios, controls, repetitions, measurements, physical/public/evidence negatives; future executions explicitly pending |
| Contract and phase handoff | All | PHASE_0_CONTRACT, MEMBERSHIP_PROTOCOL, API_FORMAT_AND_COMPATIBILITY, PHASE_0_CHECKLIST, PHASE_1_ENTRY_PLAN and updated evidence plan |
| Closure audit | All | Source/hash-bound local report mapping every D01–D10 row and deliverable to actual evidence; no unresolved semantic decision disguised as implementation work |

Implementation qualification (real disk/wire faults, public consumers, performance,
cloud and release) belongs to later phases. Phase 0 must nevertheless decide what
those implementations mean and exactly how their acceptance will be tested.
Finite models do not prove all schedules or actual filesystem behavior.

## Intermediate commits

Append actual commits/evidence as work completes. A counterexample reopens its
owning decision. Preserve earlier failed/invalidated research outputs and explain
why a replacement result supersedes them.

- Entry: existing six model batches through `acba545`, 135 local tests. Contracts
  are not frozen yet; outstanding work is listed above and in the entry plan.
- Operation/maintenance batch: 160 tests, 308 replayed reducer schedules; see
  [decisions](OPERATION_AND_MAINTENANCE.md) and [receipt](operation-research.json).
  Next: certify these commands through the transition/global-promise model.
- Certified integration: 172 tests, 126 recovery schedules and 21 portable
  histories; see [candidate](INTEGRATED_PROTOCOL_RESEARCH.md) and
  [receipt](integrated-research.json). Steady-state rounds, bounded metadata,
  formats/resources and the final contract register remain.

- Stable round/catalog batch: fixed-source sequential round extension and complete
  metadata capsules now have directed counterexamples and 49 portable histories.
  See [decisions](STEADY_ROUNDS_AND_CATALOG.md) and [receipt](continuity-research.json).
  Exact formats/resources, acceptance register and final contract audit remain.
