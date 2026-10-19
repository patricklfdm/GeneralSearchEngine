# V5.2 Phase 1 entry: declarations and independent read foundation

**Status:** authorized after PR #335; implementation and validation recorded in
[Phase 1 foundation](PHASE_1_FOUNDATION.md). Protected full acceptance pending.
**Prerequisite:** protected acceptance of the complete [Phase 0](PHASE_0_CONTRACT.md),
recorded exact-master CI with actual scope, then the user's Phase 1 instruction.
The previous entry-plan merge is not acceptance of this new contract.

## One coherent foundation batch

1. Reconcile the accepted design/source and record acceptance in the
   [checklist](PHASE_0_CHECKLIST.md). Preserve published V5.1/V5.0/V4.4 identities.
   Open active reactor/consumer coordinates together at `5.2.0-SNAPSHOT`, using
   the repository's existing alignment checks. Do not edit published release pins.
2. Add the six [new public types and one default method](API_FORMAT_AND_COMPATIBILITY.md).
   Pure constructors and token encode/decode may execute; explicit GSE runtime
   `read` stays disabled with UnsupportedOperationException before side effects.
   Old startup/reads/writes remain enabled with their existing gates. No follower
   path is enabled merely because the method compiles.
3. Freeze exact positive 112-byte token fixtures and independent encoder/decoder
   expectations, including reserved/version/checksum/identity/index negatives.
   Prove no GSER/GSRP/catalog change. Do not introduce a persistent token registry.
4. Implement the independent read-state model, bounded schedule exploration and
   deliberate N01–N16 checker negatives from [evidence](TESTING_AND_EVIDENCE.md).
   Separate logical authority assumptions from later physical process validation.
   Report incomplete exploration as incomplete; never silently shrink bounds.
5. Add an external V5.2 consumer scaffold for all seven view methods, three policies,
   option failures, token bytes and default rejection on a third-party implementation.
   Include negative compilation for paging/mutation on the scoped view. At this stage
   these are declaration/disabled-capability checks, not executed follower reads.
6. Map S01–S30 to future deterministic hooks/public process fixtures using existing
   V5.1 worker/inventory/physical-replay patterns. Establish evidence schema and
   source/process/attempt/relocation validation. Use synthetic fixtures only with
   explicit foundation labels; do not relabel them runtime qualification.
7. Register a bounded no-GCP foundation verifier in the existing CI registry,
   generated inventory and planner tests. Reuse shared build artifacts when their
   source/JDK/build identity matches. Update dependency/artifact contracts and any
   exact full-job consumers coherently; keep Required and older suites intact.
8. Run appropriate constructor/byte/model/consumer checks and the required build,
   compatibility and contract checks. Record exact changed artifact identities,
   failures and pending hosted acceptance in a Phase 1 receipt/checklist.

Suggested file ownership (new paths are proposed, not present yet):

| Area | Planned change |
| --- | --- |
| `general-search-engine-replication/src/main/java/.../replication/` | Six declaration/value files and default method in AutomaticReplicatedSearchEngine; no runtime override |
| Replication Java tests | Token/option bounds, exact declarations, external implementer/default rejection, no-side-effect disabled path |
| `scripts/v52/` and `docs/v5x/v5.2/` | Independent model, byte fixtures, source-bound evidence/negative contract and foundation receipt |
| `compatibility/v52-style-consumer/` | New isolated consumer fixture; preserve all six old consumers |
| Active POM/version checks | Aligned 5.2.0-SNAPSHOT and new consumer inclusion; historical pins unchanged |
| CI registry/workflow/planner consumers | One integrated foundation gate and retained artifacts; update exact dependency contract, not ad hoc workflow-only job additions |

Actual file names and registry placement must be verified at implementation time.
If source inspection contradicts the read/pin/resource design, first document the
counterexample and amend that decision. Do not silently enable a weaker policy.

## Phase 1 exit and later boundaries

- Exact public inventory, token layout and option/error behavior pass independent
  positive/negative fixtures and external compile/default-implementation checks.
- Model covers all declared bounds/invariants with explicit counts; failures and
  incomplete explorations remain visible. Model evidence is not production proof.
- Full source-bound compatibility/regression checks preserve published behavior;
  all new runtime paths remain disabled. The foundation gate has a protected exact
  source result and retained artifacts before cloud admission. The operator's
  [local batching instruction](LOCAL_DEVELOPMENT_SEQUENCE.md) defers intermediate
  hosted acceptance while locally verified Phase 2 work proceeds.
- Phase 2 implements the application capture/waiter kernel; Phase 3 enables the
  public policies. Phases 4/5 own the full fault/resource and combined-hardening
  matrix. Later measurement/release entries need their own frozen plans.

Phase 1 does not authorize new replication records/messages, a different election
algorithm, membership work, in-place migration, paid infrastructure, cloud execution
or publication. No new IAM/environment provisioning is needed for this foundation.
The later [local batching instruction](LOCAL_DEVELOPMENT_SEQUENCE.md) authorizes
local commits; push/PR and paid triggers remain operator-owned.
