# Phase 3 — original voter CURRENT opens

The preceding [SELECTED journal audit](PHASE_3_SELECTION_JOURNAL.md) retained a
disposable original REPLACE copy without node 1's first `CURRENT_FILES_FORCED`.
The complete reader accepted it. Native bytes and execution were unchanged;
this was a missing observation requirement, not a demonstrated runtime fsync bug.

## Native boundary and independent inputs

`MembershipCurrentGeneration` validates its original manifest and members, then
emits `CURRENT_VALIDATED`, `CURRENT_FILES_FORCED`, `CURRENT_GENERATION_FORCED`,
`CURRENT_SELECTOR_FORCED`, and `CURRENT_DIRECTORY_FORCED`, in that order.
`MembershipGrantJournal.openRetainingFuturePeers` opens this generation before
resealing its initialized retention ledgers. The original network driver opens
all old voters before constructing its protocol endpoints.

`initial_current_evidence` requires this exact first per-node block before the
first learner/peer retention reseal. It uses the original model's voter set after
the physical precondition has validated the before-network bytes. It does not
derive a smaller voter set from whichever callbacks remain in an altered trace.
Every old voter is included, even one that later receives no PREPARE or SELECTED.

Each row must have only its original node and event. Missing, duplicate, reordered,
unknown, extra-field or scoped callbacks fail. Removing the entire initial block
also fails. A later installation's matching five callbacks cannot replace the
missing startup evidence. All initial opens must finish before the first observed
network, allocation or capture operation. Per-node startup blocks may interleave;
the validator does not impose a fictitious total order between different nodes.

The shared check runs after existing checks in ADD/REPLACE and REMOVE network
readers. The process reader uses the independently verified shared trace and
exact parent/child projections. Its initial parent opens are distinct from the
later interrupted and resumed child's opens; the existing process recovery
reader continues to own those later lifetimes. Existing result shapes and
rejection ordering are preserved.

## Verification

Eight focused regressions cover original sizes 3/4/5, unused minority voters,
interleaved opens, premature protocol activity, malformed or absent rows, and
every new mutation. Twenty-four original observation negatives remove or corrupt
the first or last original voter's startup. Each disposable mutation must retain
all physical files and exact rejection reasons. For process evidence, the parent
projection and shared trace change together; all child observations remain exact.

The [receipt](phase3-evidence/initial-current.json) records actual original-first
replays, negative results, immutable reader source, original inventories, Python
tests and relocated archive replay. This is historical native evidence replayed
by the current reader; it does not claim new native executions at this source.

Measured validation: all 1,775 Python tests passed. The complete retained REPLACE,
4-REMOVE, 5-REMOVE and SIGKILL/reopen compositions passed; each rejected all 24
new startup mutations (96 exact rejections). The historical ADD replay also passed.
The actual previously accepted omission now fails the complete corrected REPLACE
composition with `initial current complete original open`.

The 40,075,891-byte archive retains 27,265 files and
5,161 directories. All five extracted histories replayed with
optimized Python and produced exactly the same results. Original inventories and
frozen reader source stayed unchanged. Earlier 405-negative full matrices belong
to the preceding journal batch; this batch ran its 96 focused startup negatives,
not another complete run of those older matrices.

## Remaining work and rollback

This closes the reproduced successful initial-open omission. It does not qualify
every CURRENT callback elsewhere in a continuous history, arbitrary interrupted
opens or the full final-source profile/process cohort. Complete observed-family
ownership, combined resource qualification and the frozen S/N mapping remain
open; Phase 3 stays open.

The change is limited to Python evidence checks, tests and documentation. It does
not change Java, persisted formats, POMs, workflows, resource limits or cloud
execution. Rollback reverts this increment while preserving its original audit
and exact affected scope.

The [whole-history CURRENT ownership follow-up](PHASE_3_CURRENT_OWNERSHIP.md)
now accounts for the other original intervals and rejects unbound callbacks.
