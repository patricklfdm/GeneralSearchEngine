# V5.3 Phase 0 local exit checklist

Status: **audit pending**. All checked results below must be grounded in the final
source-bound closure receipt before status changes to locally closed.

| Requirement | Contract and required local evidence |
| --- | --- |
| D01 identity/history | API contract; membership/ballot/admission/operation identity and token-boundary counterexamples |
| D02 partial transition authority | Membership protocol; arithmetic, chosen-slot cross-view rejection and integrated accepted SEAL/INTENT/FINAL recovery |
| D03 ballots/selection/rounds | Activation/steady references; durable allocation, immutable bases, proposer-inclusive sources, late fence/callback negatives |
| D04 learner | Admission + integrated histories; image/receipt force precedes INTENT-derived eligibility; source provenance/identity negatives |
| D05 operations | Operation + integrated histories; exact duplicates, accepted SEAL vs CANCEL, revision, retirement and exhaustion |
| D06 recovery/retention | Recovery/admission/catalog models; owned tail, selector/floor/retirement and complete metadata/descriptor negatives |
| D07 reads/maintenance | Operation tests; known-removal/drain/capture matrix, fresh surviving-majority challenge, explicit no distributed maintenance lock |
| D08 exact API/bytes | API signatures, 24/21 catalog, 45 portable independent syntax fixtures and parser/context/corruption negatives |
| D09 lifetime/resources | Resource formula, operation/capsule capacity tests, 10,000-step reducer size check; no unlimited-history claim |
| D10 later acceptance | S01–S10/N01–N24/C01–C08/M01–M12 and source/attempt/indivisible-history rules, soft experiment budgets, protected/runtime gates still pending |
| Required deliverables | Contract, protocol, API/format, resource limits, acceptance plan/register, checklist and Phase 1 entry all exist and link correctly |
| Coherent final local checks | Entire V5.3 unit suite and declared research matrices run against the same final script bytes; originals and negative fixtures replay |
| Scope/provenance | Changes only isolated V5.3 docs/scripts; original production Java/POM/workflows and V5.2 tree unchanged from branch base; local commit only |

The audit must compare actual current file hashes with each final receipt, retain
failures and unique evidence directories, and list exclusions. Earlier dirty-source
receipts remain historical; a later commit hash is not silently substituted.

## Explicitly pending after local Phase 0 closure

- Published V5.2 tag/artifact pin and integration of later predecessor fixes.
- Protected CI/review and unified acceptance deferred by the operator.
- Java declarations/implementation, complete same-round/compacted-source composition,
  real force/transport/process tests, public consumer and independent physical replay.
- Frozen local/paid-cloud measurements, actual costs/timing, release/reproducibility.

Those are later phase gates, not unresolved choices about the Phase 0 semantics.
A counterexample or contradictory format decision reopens its owning D row.
