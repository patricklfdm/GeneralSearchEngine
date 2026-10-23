# Original-round process recovery

Status: private local process qualification. [Storage closure](PHASE_2_CLOSURE_CHECKLIST.md)
and public runtime remain **OPEN**. This extends [same-round storage](PHASE_2_ROUND_STORAGE.md)
with actual child-JVM halt/SIGKILL; no production Java change is required by this batch.

## One original request across interruptions

The retained seed starts from the earlier conditional bootstrap, then actual
separate local owners certify and publish DATA at slot 1 and BARRIER at slot 2.
They retain the same original selected cut 0, ballot 20 and original BASIS/source
bytes. All three owners also retain the actual slot-3 DATA votes and applied ends.
Each case privately copies the settled slot-2 local owner and resumes the exact
original third-slot request. Copies are offline test inputs, not additional live
voters or network ownership evidence.

The child uses only the 36 exact phase/end observations present in the original
three-node physical snapshots. It creates no replacement historical fixture.
Its application replay and original covering publication use the normal storage
owner; after selector publication, reopen only retires the covered staging.
Neither recovery nor a completed receipt grants READY or restores callbacks.

| First halt / SIGKILL | Second interruption during recovery (halt) |
| --- | --- |
| ACCEPT prefix written | ACCEPT candidate forced |
| PROOF prefix written | PROOF candidate forced |
| CERTIFICATE prefix written | CERTIFICATE candidate forced |
| Ancestor ACK prefix written | Ancestor ACK forced |
| Round coverage member written | Round coverage member forced |
| Round coverage member forced | Generation directory forced |
| Selector renamed | Covered-vote candidate forced |
| Selector publication completed | Covered-end member deleted |
| Covered-end member deleted | Covered-vote prefix written |
| Covered-vote prefix written | Covered-vote candidate forced |
| Covered-vote renamed | Empty active-vote file re-forced on reopen |

Each of the 22 cases uses four fresh JVMs: first interruption, interrupted recovery,
completion and a duplicate reopen. The parent checks the actual halt/SIGKILL exit
codes. The duplicate leaves the settled bytes unchanged. Old generation and
source authority survive; governing-floor retirement is a separate operation.

## Independent replay

[The source/build and raw-evidence index](phase2-evidence/round-process.json)
records the execution and replay results. The Python driver:

1. Validates the unchanged original seed and its first two real publications.
2. Derives the third-slot generation from original votes, local applied ends,
   first/latest proof records and exact ancestor ACKs before examining candidates.
3. Binds every supplied observation to those original local records; unused or
   invented observations cannot count as ownership.
4. Simulates every pending phase prefix, recovery rewrite and force boundary,
   application/end prefix, generation member, selector switch and covered deletion.
5. Compares exact event order and complete physical snapshots after both crashes,
   completion and duplicate reopen, including preservation of old authority.
6. Validates the original before thirteen evidence-negative mutations and repeats
   the replay after relocation and with Python assertions disabled.

The earlier 39-publication storage replay still runs its original complete
comparison and eleven negatives. Factoring its candidate projection for this
process driver does not make final-state verification optional in that gate.

The initial Java process run passed, but independent replay rejected its test
inputs because the general historical fixture also supplied unrelated conditional
observations. The producer now retains only physically referenced observations;
the complete process matrix was executed again. The original run and rejection
remain retained. No production limit, vote rule or oracle was relaxed.

## Limits and next work

These are three-voter small-image cases at slot 3, with one extra ancestor and
original first/latest phased proofs. They do not establish maximal payload or
metadata admission, power-loss durability, distributed activation or a public
failover guarantee. Actual carried-first-entry, membership-boundary/cross-view
lifetimes, bootstrap and torn PROMISE recovery remain storage obligations.
