# Carried transition ledgers and retirement callbacks

Phase 3 remains **OPEN**. The same two four-voter REMOVE carried INTENT/FINAL
originals now compose [export and floor authority](PHASE_3_CARRIED_TRANSITION_EXPORTS.md)
with continuous peer/future-retention revisions and complete observed retirement
callbacks. No native workload was rerun and no production code, workload,
resource limit or workflow changed.

## Continuous ledger derivation

[The retention reader](../../../scripts/v53/carried_transition_retention.py)
requires the complete original physical, lifecycle, attempted-network, export
and floor reduction. The peer ledger starts once from the independently derived
admitted prefix. In particular, FINAL's preparation already reconciles the peer
view at revision 1; a revision-0 bootstrap reset would lose that history.
All later snapshots are exact comparisons, never replacement seeds.

The peer chain binds actual floor observations, immutable captured source
ledgers, conservative selected-state merge and publication promotion. Every
revision must advance by one and name the exact preceding bytes. Every write,
force, candidate-parent force, rename and completion has its original owner and
bounded interval. Selection completion and initial reseals are fully consumed;
node 4's unchanged state is included even when it does not join a later selection.

The future chain independently starts at the derived empty ledger, records each
actual publication target before dispatch, matches remote acknowledgements to
the exact forced revision/digest, and clears only after publication promotion.
The complete chain must match installed, applied, published and closed bytes.
No snapshot resets, synthetic target acknowledgements or unconsumed writes are
accepted.

| Original | Peer writes | Future writes | Final peer revisions (nodes 1–4) | Final future revisions (nodes 1–4) |
| --- | ---: | ---: | --- | --- |
| INTENT | 40 | 22 | 15, 15, 10, 0 | 8, 8, 6, 0 |
| FINAL | 22 | 13 | 10, 10, 5, 1 | 5, 5, 3, 0 |

## Retirement authority and callbacks

[The retirement reader](../../../scripts/v53/carried_transition_retirement.py)
requires that complete retention result first. It derives each inactive inventory,
governing floor, retained endpoints, exact source authority, compacted journal
and final inventory. Image-copy versus image-borrow behavior comes from the
actual simultaneous image count under the existing seven-image limit, not from
a callback claiming which branch happened.

First-slot maintenance occurs after the exact current reaccept has completed
its durable return and before proof. The original entry and payload remain
unchanged; the new vote binds the current selector, promise, selection and ballot.
The pending vote stays byte exact through every projected retirement state. Its
frozen sources are not retired during that pending interval.

Later stable maintenance can retire an old source with an ACCEPT already covered
by the actual published floor. This explicit reader mode verifies the original
source binding, root, local owner, exact current floor cut and tail index at or
below that cut. An above-floor tail is refused. The existing default reader mode
continues to refuse accepted tails. This is qualification of the existing runtime
rule, not a new permission in runtime code.

| Original | Retired generations | Retired sources | Borrowed-image generations | Retirement callbacks | Physical image peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| INTENT | 13 | 8 | 9 | 779 | 7 |
| FINAL | 7 | 4 | 3 | 397 | 7 |

The replay consumes every generation/source retirement and journal-rotation
callback exactly once in derived order, with exact member deletion counts.
Extra fields, missing operations and events outside the original floor are refused.

## Negative qualification and retained evidence

Each original passes before 41 ledger negatives and 36 retirement negatives run:
**154 exact negative checks** across the two originals. Ledger mutations preserve
all files, wire and non-target observations. Retirement mutations additionally
must pass continuous retention replay before the expected retirement rejection.
Wrong failure reasons and accepted mutations cannot earn credit. Parallelism is
limited to independent disposable negative copies; original histories stay whole.

The [development receipt](phase3-evidence/carried-transition-retention.json)
binds both stages, original source/build/toolchain, current reader, original
inventories, portable optimized replay and tests. Original producer receipts and
failed-attempt accounting remain untouched. This is development replay of those
captured sources, not final-source cohort admission. Both stages produce identical
results after pack/unpack relocation under `python -O`, preserving all original
inventories and the source/build/toolchain bindings. All 2,479 V5.3 Python tests
pass; the 75 focused tests pass in normal and optimized mode. Historical ordinary
and interrupted REMOVE retirement replays also pass with the default helpers.

## Remaining scope

These results qualify continuous ledger revisions and complete **observed
retirement callbacks**. Derived transient inventories are predictions, not actual
interrupted-file captures. Exact transient retirement bytes and process-death
recovery still require their native observations. Dedicated source-bound
capture/admission and other membership/payload/process axes remain separate.
Public readiness and Phase 3 closure are not claimed. No hosted subset was added;
the nine existing entries still describe 460 planned whole histories.

The later [retirement prefix component](PHASE_3_CARRIED_TRANSITION_PREFIXES.md)
adds new writer-held byte captures. It does not upgrade these older callback-only
originals into transient-file observations.
