# Phase 3 — complete observed REMOVE retirement transactions

This extends [continuous REMOVE retention](PHASE_3_REMOVE_RETENTION.md) on the
same two original TCP histories. It checks complete observed generation/source
retirement transactions, not just the existence of a force before return. The
[receipt](phase3-evidence/remove-retirement.json) pins the original source/build,
separately frozen reader, inventories, diagnostics and portable results. No Java,
workflow, resource cap or native experiment changes are made.

## Derivation and observed order

The complete physical, attempted-network, export/floor and continuous-retention
precondition runs first. For every acquired governing floor, the reader derives
the exact inactive generation and its original members from the preceding owned
inventory. Original manifest membership, current selector, ancestry coverage,
settled pending state and conservative retained endpoints remain required.

Retirement cannot choose an image policy from its own callback log. Each physical
image owns a separate reservation, including equal bytes in distinct generation,
source and complete-floor files. The reader derives whether another physical
backup fits the frozen seven-image capacity. Otherwise it binds the exact old
image to the local governing FLOOR copy and derives the borrowing record from
the original owner, selector, floor, generation and image bytes.

The existing transaction projection derives every proposal, manifest, member and
image write/force; saved source and authority force; original-file deletion;
saved-file deletion; marker clearing and final return. Both inactive slots `a`
and `b` are supported, preserving the active slot. Source retirement derives the
old frozen PROMISE/BASIS/capsule, complete file set, conservative coverage and
compacted journal. Journal rotation must be written, forced and renamed before
any source file is deleted. Every observed callback must belong to exactly one
derived transaction inside its still-live FLOOR interval.

| Original | Generation retirements | Source retirements | Borrowed / copied generations | Original generation members deleted | Callbacks |
| --- | --- | --- | --- | --- | --- |
| `4-REMOVE` | 13 | 8 | 6 / 7 | 102 | 761 |
| `5-REMOVE` | 15 | 9 | 9 / 6 | 117 | 876 |

Both profiles reach a derived physical image peak of seven. The complete
post-transaction projection must preserve every other member. The original
physical reader separately compares the subsequent retained native inventories.

## Qualification and remaining evidence

Each history has 36 targeted callback negatives: omitted proposal/member/image
or borrowed-image force, incomplete deletion, journal rotation omission/order,
saved-file deletion before original deletion, duplicate deletion, forged event
fields and an unbound callback. All non-event files, wire bytes, directory sets
and non-retirement event order must remain unchanged. Each mutation still passes
the preceding continuous-retention replay, then fails the new transaction reader
for its exact expected reason. An unrelated earlier failure cannot count as a
new rejection. The full unmodified prerequisite runs before these mutations;
mutated full physical prerequisites are not presented as rerun qualification.

The shared generation transaction helper retains its default slot and the shared
source-decision helper retains its default coverage derivation. Tests exercise
both borrowed slots and every interrupted model state, explicit empty coverage
rejection, exact default compatibility and unchanged active generation bytes.
Model-state recovery tests do not stand in for fresh native process failures.

The formal original replays passed in 175.156 seconds (`4-REMOVE`) and 230.043
seconds (`5-REMOVE`), with 72 exact negative results in total. All 1,595 V5.3
Python tests passed, including 13 new tests; the focused compatibility suites
passed 35 tests. Replay of the retained historical ADD source-retirement evidence
also matches its previous receipt exactly, preserving the shared helper's
default behavior. That historical regression remains separate from the two
REMOVE originals and is not a new native execution.

The sealed archive contains 20,178 files and 2,658 directories (41,578,052
compressed bytes). Every extracted member hash and directory is checked.
Relocated `python3 -O -B` qualification passed in 170.852 and 225.137 seconds,
with exact positive/negative result equality and unchanged source/original
inventories. This repeats the same 72 negatives; it is not another 72 distinct
cases or another native history.

The two original histories do **not** contain intermediate retirement-file
captures. Complete callback validation therefore leaves
`transientRetirementBytesQualified=false` and `processDeathQualified=false`.
Subsequent process-fault qualification must collect and compare actual interrupted
proposal/authority/borrowed-image/journal bytes and recovered inventories. Missing
captures cannot be reconstructed into claimed observations or supplied by a
final snapshot. Current-source seven-profile execution, composition with the
existing automatic election lifecycle, and frozen acceptance mapping also remain
open; Phase 3 stays OPEN. The automatic owner, election wait, heartbeats and bounded
fresh-campaign handling already exist; this receipt does not qualify their
composition with these REMOVE histories.

## Reproduction and rollback

```bash
python3 -B -m scripts.v53.remove_retirement_evidence ORIGINAL \
  --profile 4-REMOVE --qualify --workers 2
```

Use `5-REMOVE` for the other complete original. Only independent negative copies
run concurrently. Portable qualification repeats from the sealed extraction with
`python3 -O -B` and exact positive/negative result equality. Rollback removes this
reader, tests and receipt and restores the helper defaults; persisted formats and
production behavior are unaffected.
