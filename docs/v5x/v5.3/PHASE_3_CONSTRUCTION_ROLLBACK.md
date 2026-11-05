# Phase 3 conditional constructor rollback

This qualifies seven failed-construction paths in the existing implementation;
it does not change runtime code. The [development evidence index](phase3-evidence/construction-rollback.json)
binds the test inputs, original observations and independent replay reports.
Phase 3 remains OPEN.

## Executed failures

| Component | Failure | Expected temporary ownership |
| --- | --- | --- |
| Learner checkpoint listener | Real endpoint already bound | One 32768-byte CONTROL reservation, released before `BindException` returns |
| Learner head listener | Real endpoint already bound | One 32768-byte CONTROL reservation, released before `BindException` returns |
| Both listeners | All 256 CONTROL slots already held | No new reservation |
| Source transfer service | Guard throws before reservation | No new reservation |
| Source transfer service | Original deadline expires immediately after reservation | One 32768-byte CONTROL reservation, released before failure returns |
| Source transfer service | All 256 CONTROL slots already held | No new reservation |

The three Java tests cover these seven cases. A real socket holds each listener
port during bind failure. After the blocker or capacity pressure is removed,
the same retained owner successfully serves a correlated request through the
real TCP listener. The source-service test likewise opens a new service on the
same journal owner and checks an actual source offer. Its controlled clock
crosses the existing deadline at the constructor's second clock read; no runtime
deadline or resource bound is changed.

The observed listener resource budgets include their original storage owners.
The source-service test observes a separate service CONTROL budget, compares
the journal owner's usage after successful reuse, and records original file
hashes. That separate budget is not evidence for every journal-owner allocation.

## Independent checks

```bash
python3 -m scripts.v53.construction_rollback_evidence RAW
python3 -m scripts.v53.construction_rollback_negatives RAW
```

Each collection contains only the canonical `resources.json` and `history.json`.
The reader derives resource usage from the complete transition stream and binds
constructor entry and observed exception return to original sequence numbers.
During that interval, original reservations must remain continuously owned;
matching entry and exit counters cannot excuse release followed by reacquisition.
Temporary reservations must have the exact component role and extent, and must
be released before the observed failure return. Capacity rejection requires all
256 original CONTROL slots. Original file observations must be unchanged.

All three original collections pass. Fourteen mutations per collection reject
at their declared obligation: failed original, missing case, wrong exception,
empty message, stale usage, boolean sequence, premature failure return, missing
temporary allocation, wrong role, wrong extent, original ownership gap,
insufficient capacity pressure, changed files and incomplete observation.
The original is validated before mutation, and its inventory remains unchanged.
Twelve reader tests also cover negative sequence numbers, reordered boundaries,
portable replay and invalid inventories.

These readers qualify failed-constructor accounting only. Successful service
reuse is checked by Java, not independently qualified by these two-file records.
File hash observations do not establish native physical custody or lock lifetime.
Other constructor/export/task paths, replacement and recovery guards, combined
resource maxima and final-source native/hosted qualification remain open. The
12 Phase 3 requirements, 544 planned hosted histories and later-phase 3310-case
plan are unchanged.
