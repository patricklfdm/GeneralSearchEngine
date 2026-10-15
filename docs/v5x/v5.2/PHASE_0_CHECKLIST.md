# V5.2 Phase 0 review checklist

**Status:** accepted through PR #335; docs-scope exact-master CI recorded below.
**Reviewed checkout:** `fd5bf155994887a5d5adc114000afc9e770960ae`, after entry PR #334.
**Design instruction:** user “下一批”, 2026-10-15, for the documentation-only contract.

## Delivered design

- [x] Read governing charter/addendum and actual published automatic/configured
  public, runtime, application, bootstrap and frame definitions.
- [x] Produce [D01–D10 selections](PHASE_0_CONTRACT.md), including narrower explicit
  paging scope, no authenticated-token claim and unchanged old methods.
- [x] Define [capture/lifecycle/resource rules](READ_AUTHORITY_AND_LIFECYCLE.md),
  including no worker/pin while waiting and cooperative active callback limits.
- [x] Define [six new types, default method, 112-byte encoding and errors](API_FORMAT_AND_COMPATIBILITY.md).
- [x] Map [E01–E09, S01–S30, N01–N16 and M01–M04](TESTING_AND_EVIDENCE.md) to concrete
  public/model/physical evidence; none is claimed executed in this phase.
- [x] Produce the bounded, guarded [Phase 1 entry](PHASE_1_ENTRY_PLAN.md).

These checks mean documents/source review exist. They do not mean runtime tests,
formal proof, hosted acceptance, cloud execution or publication occurred.

## Decision review and acceptance

| Decision | Owning review | State |
| --- | --- | --- |
| D01 | Explicit automatic-only surface; preserve default strong/configured behavior | Accepted in PR #335 |
| D02 | Runtime token issuance after confirmed work; trusted-client lower bound | Accepted in PR #335 |
| D03 | Verified publication, serialized callback and strong overlap boundary | Accepted in PR #335 |
| D04 | Wait/deadline/cancellation ownership and no fallback | Accepted in PR #335 |
| D05 | History/manifest lifetime, restart/compaction/new-group behavior | Accepted in PR #335 |
| D06 | Scoped/thread-bound views; explicit paging excluded; old paging unchanged | Accepted in PR #335 |
| D07 | R=min(64,P-1), one active view, no wait-owned publication work | Accepted in PR #335 |
| D08 | Exact additive descriptors/token bytes; unchanged authority formats | Accepted in PR #335 |
| D09 | Independent physical/history oracle and meaningful negatives | Accepted in PR #335 |
| D10 | Phase gates and pre-measurement freeze, no recycled cloud acceptance | Accepted in PR #335 |

- [x] Contract accepted through PR #335; no subsequent design amendment in Phase 1.
- [x] Record accepted PR, exact master commit and exact CI attempt/scope.
- [x] Confirm documentation checks separately from future compiled/runtime evidence.
- [x] Obtain subsequent Phase 1 instruction before version/declaration/model changes.

No unresolved design choice is delegated to runtime code as an implicit default.
Future counterexamples can reopen a row. Numeric measurement inputs still requiring
the Phase 6 machine-plan freeze are explicitly identified; they are not Phase 1
API decisions. Retained Tiered CI/Nightly observations are separate ongoing work.

## Phase 0 validation and acceptance identity

| Item | Current record |
| --- | --- |
| Entry plan acceptance | PR #334, master `fd5bf155994887a5d5adc114000afc9e770960ae` |
| Immediate published reference | v5.1.0 at `516fe1efb54ef0787f38209108f322f258f71696` |
| Current core/replication production and V5.1 consumer | PASS: no diff between reviewed HEAD and v5.1.0 for these paths; unchanged by the Phase 0 batch |
| Local document verification | PASS: 12 Markdown files, 1,015 local links and 47 heading anchors; fences/whitespace, D/E/S/N/M registers, six-type inventory and contiguous 112-byte layout checked |
| Inherited checks | PASS: generated CI inventory, V5.0 Phase 0 contract and V5.1 document contract (114 documents / 860 links); these do not accept V5.2 behavior |
| Local actual-diff planner replay | PASS for PR and master push: docs, two planned meta jobs, 36 suite placeholders skipped; Required used simulated job results, not hosted executions |
| Contract acceptance PR/master/CI | PR #335; exact-master CI 38710485375 attempt 1, docs scope |
| Model / byte fixtures / public runtime evidence | Not executed; owning Phase 1 and later gates |
| Phase 1 authorization | User switched to feat/v52-phase1-foundation after merge |

The original Phase 0 batch changed only Markdown planning/navigation. No source/test/POM/workflow,
policy, frozen hash, toolchain, published release record or cloud ledger is changed.
The local report must list actual checks and their results; a simulated planner
receipt is not hosted CI. No Maven/cluster/cloud rerun is needed to review this
documentation-only diff. Preserve previous failures and raw evidence. The checker,
changed-file/hash inventory, planner inputs/logs and local receipt are retained in
`target/v52-phase0-contract/`.

## Protected acceptance recorded at Phase 1 entry

PR #335 merged as `9e1aeb282135802ff8886c4585351ce42a7908b0`. Exact-master
CI `38710485375` attempt 1 succeeded: Change scope and Required passed; all 36
suite placeholders were deliberately skipped in docs scope. This accepts the
contract only. The user switched to `feat/v52-phase1-foundation` on 2026-10-15
to proceed with [Phase 1](PHASE_1_FOUNDATION.md); protected full acceptance of
that implementation remains pending.
