# V5.3 Phase 0 contract — controlled membership

**Status: LOCALLY CLOSED — 2026-10-21.**
[Closure audit](PHASE_0_CLOSURE_AUDIT.md) records the exact source and scope.
Scope: new homogeneous automatic membership groups; one serialized add/remove/
replace operation, learner catch-up and same-version maintenance. Stable voters
3–5, peak union six. Existing fixed configured/automatic modes and V5.2 release/
cloud source remain untouched. No mixed-version upgrade or forced minority repair.

## Resolved decisions

| Decision | Frozen choice / owning specification |
| --- | --- |
| D01 | Immutable group/history/genesis root; separate configuration generation; fresh node/storage/endpoint for replacement; no identity recycling; same-root token v1 continuity, new-group transfer resets compatibility — [API/compatibility](API_FORMAT_AND_COMPATIBILITY.md) |
| D02 | Old-majority INTENT, joint-majority FINAL, new-majority stable service; forced predecessor determines each slot; distinct ACCEPT and PROOF quorums — [protocol](MEMBERSHIP_PROTOCOL.md) |
| D03 | Root-wide ordered ballots, durable allocation/grants, immutable proposer-inclusive source set; highest accepted tail after longest proven prefix; current-ballot activation; stable-only round reuse — [protocol](MEMBERSHIP_PROTOCOL.md), [rounds](STEADY_ROUNDS_AND_CATALOG.md) |
| D04 | Reservation/prepared revision → verified learner image/receipt → SEAL → old-certified INTENT; learner votes only after locally forced matching INTENT; exclusive durable identity assumption — [operation lifecycle](OPERATION_AND_MAINTENANCE.md), [integration](INTEGRATED_PROTOCOL_RESEARCH.md) |
| D05 | Root+monotonic number and exact payload; certified queryable progress; timeout detaches, CANCEL only before SEAL; contiguous terminal retirement retains watermark/tombstones — [API](API_FORMAT_AND_COMPATIBILITY.md), [operation lifecycle](OPERATION_AND_MAINTENANCE.md) |
| D06 | New endorsed stable ranges plus complete membership certificates/full descriptors; full catalog/application binding, forced selector, current-view floor, exact owned tails and resumable retirement — [rounds/catalog](STEADY_ROUNDS_AND_CATALOG.md), [protocol](MEMBERSHIP_PROTOCOL.md) |
| D07 | Known removal/drain refuses new captures; already captured reads finish exact cut; explicitly stale/minimum semantics on unaware isolated nodes; operator-serialized same-version maintenance, no remote stop/delete authority — [API](API_FORMAT_AND_COMPATIBILITY.md) |
| D08 | Additive new factory/interface/config and 1.3 disk/wire family; unchanged legacy entry points/token bytes; exact declarations, catalog and 45 independent syntax fixtures — [API](API_FORMAT_AND_COMPATIBILITY.md), [catalog](format-catalog.json) |
| D09 | One transition/learner, bounded permanent identities/results/revisions/counters, 769 capsule items, 32 MiB complete capsule, 384 MiB peak metadata reservation, inherited application/log bounds — [resources](RESOURCE_AND_LIFETIME_LIMITS.md) |
| D10 | S01–S10, N01–N24, C01–C08 and M01–M12; original+independent physical/public/read validation, three canonical repetitions, one cohort, soft experiment budgets and explicit paid authorization — [acceptance register](ACCEPTANCE_REGISTER.md) |

## Authority matrix

| Local proven phase | Voting authority | Service / next action |
| --- | --- | --- |
| Stable, no operation | Current stable majority | Fresh activation then DATA/CONTROL/strong barriers; explicit local reads retain their policy |
| RESERVED/PREPARING/READY | Old stable majority | DATA allowed; learner non-voting; reprepare if application cut changes |
| SEALED before INTENT | Old stable majority | No DATA; recover/commit exact INTENT; cancellation refused |
| INTENT locally forced (JOINT) | Majority of both old and new sets | Only matching FINAL; new learner eligible only with matching forced image/catalog/receipt |
| FINAL locally forced | New stable majority | Fresh new-stable activation before service; query terminal result |
| Known removed / local draining | None for new local service/votes | Diagnostics and exact recovery/close obligations only; preserve owned evidence |

Query diagnostics and observed timeouts are never authority. Every public success
binds actual proven/applied state; every phase failure preserves conservative
NOT_SUBMITTED/INDETERMINATE distinction. Library deadlines/storage limits remain
finite even though experiment time/cost budgets are soft.

## Contract precedence and limits

This contract, MEMBERSHIP_PROTOCOL, API_FORMAT_AND_COMPATIBILITY,
RESOURCE_AND_LIFETIME_LIMITS, format-catalog and acceptance-plan supersede candidate
choices marked open in historical research notes. Those notes/receipts remain as
source-bound evidence and limitations, not retroactively rewritten success claims.
The protocol and API specify semantics; the machine catalogs specify exact bytes,
limits and frozen measurement numbers. A disagreement is a blocker to implementation
and must be resolved in a reviewed local contract amendment, never by silent fallback.

Phase 0 closure means design obligations and bounded counterexamples are ready for
implementation. It is not production consensus acceptance, a formal proof of all
schedules, real storage/network qualification, published predecessor pin, protected
CI or permission to enable a cloud/release path. Pending implementation gates are
explicit in [Phase 1 entry](PHASE_1_ENTRY_PLAN.md).
