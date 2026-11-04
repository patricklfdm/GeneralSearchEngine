# Carried transition retirement byte observations

Phase 3 remains **OPEN**. This component extends
[continuous ledger and retirement replay](PHASE_3_CARRIED_TRANSITION_RETENTION.md)
with actual writer-held file observations. It does not infer these observations
from the older callback-only histories.

## Producer and binding

`V53CarriedTransitionDriverTest` can enable the existing retirement collector
before the first native campaign with `-Dv53.carried.retirement.captures=true`.
The complete carried INTENT or FINAL history remains indivisible, with its
existing workload, request observations, limits and final stable barrier.
Every retirement callback copies the files while the original writer owns them.
Repeated bytes are content-addressed in a sibling sidecar; original files and
events remain unchanged. The collection finishes only after the history closes
and every observed retirement transaction returns.

The carried collection uses `gse-v53-carried-retirement-capture-v1` and binds the
exact kind, `events.json` and `carried-transition-result.json`. Individual capture
rows reuse the existing REMOVE metadata format. The ordinary REMOVE collection
schema, result-file binding and profile allowlist are unchanged. The carried
reader cannot accept a REMOVE sidecar or alias INTENT and FINAL.

## Independent comparison

[The prefix reader](../../../scripts/v53/carried_transition_prefixes.py) first
requires complete physical/lifecycle, attempted-network, export/floor, continuous
peer/future-ledger and retirement-callback replay of the original. It then derives
each expected transient state from that authority, never from captured claims.
Every original callback has exactly one capture with the same node, kind and
event index. The complete physical inventory must match, including empty
directories, forced source journals, partial borrowed-image bindings, retirement
proposals, deletion progress and final cleanup.

The current reaccept in the first campaign is especially important: its pending
vote remains byte exact during generation retirement. Clearing it in a captured
prefix is rejected. Later source retirement remains authorized by the actual
published floor; capturing files does not grant additional retirement authority.

The collection reader bounds file counts, total bytes, object identities and
original owners, refuses links and extra/unreferenced objects, and binds both
original result and events. Nineteen exact sidecar negatives cover those bindings,
partial writes, early/late deletion and journal rotation, leftovers and pending
vote loss. The unchanged full original must pass before any negative earns credit.

## Qualification status

Two fresh originals ran once each against one frozen development source,
compiled build, toolchain and reader. INTENT took 343.266 seconds; FINAL took
300.366 seconds. Each complete original passed all prerequisite reductions before
the 19 prefix mutations. No workload retry or budget change was used.

| Original | Captured prefixes | Retired generations | Retired sources | Borrowed-image generations | Stored sidecar bytes, excluding header |
| --- | ---: | ---: | ---: | ---: | ---: |
| INTENT | 779 | 13 | 8 | 9 | 9,307,199 |
| FINAL | 397 | 7 | 4 | 3 | 4,944,423 |

Both original/sidecar pairs also pass after packing, unpacking and replay under
`python -O`, with identical positive results and all 38 exact negative outcomes.
All 2,484 V5.3 Python tests pass; the 26 focused tests pass in normal and optimized
mode, and all four Java collector tests pass. The unchanged ordinary REMOVE
collection decoder also accepts its retained 761-prefix original sidecar. This
compatibility check concerns collection only and does not rewrite that producer's
historical failed replay receipt.

The [development receipt](phase3-evidence/carried-transition-prefixes.json)
retains producer/source/build/toolchain identities, original and sidecar
inventories, complete results and portable replay hashes. These are new byte
observations; older callback-only receipts remain unchanged. The captured source
differs from the final documentation and one collector-test exception expectation.
The actual reader bytes belong to the captured source. This remains component qualification;
dedicated source/build/toolchain/reader cohort admission, other membership
profiles and carried process-death histories remain open. The hosted inventory
still contains nine entries and 460 planned whole histories. No public readiness,
process-death qualification or Phase 3 closure is claimed.
