# Phase 3 — continuous REMOVE ballot forces across process death

Status: allocator reservation and promise-force composition is qualified for the
retained v2 `4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill` member. This extends
[original retirement recovery](PHASE_3_REMOVE_PROCESS_RETIREMENT.md). The other
native members, complete observation coverage and seven-profile/frozen acceptance
mapping remain OPEN. Phase 3 is not closed.

## Continuous original authority

The complete original physical, attempted-network, temporal-export, floor,
retention and retirement prerequisites run first. The allocator and highest
promised counter are seeded once from the independently derived admitted prelude,
not copied from an installed or reopened snapshot. In this history, node 1 enters
the network cut with allocator counter two and the other nodes with counter one.
These values differ from the revision-zero retention ledgers.

Each reservation must contain the exact original create/write/force/rename and
parent-directory force sequence. It consumes `max(reserved, observed) + 1` without
exceeding the original counter bound. Every proposer grant has exactly one unused
reservation after its previous open/current force boundary and before capture;
no extra or unbound reservation can disappear from replay. The ballot uses the
original proposer's storage identity.

Each selected voter's original frozen basis binds its promise write and force to
the corresponding capture/return interval. The three callbacks have exact owner,
shape and order and cannot be reused. Unknown or unbound promise callbacks are
also rejected. Remote promises advance the observation fence, not that voter's
local allocator. All subsequent installed, interrupted, reopened, applied,
published and closed snapshots compare the evolving state. None resets it.

| Result | This original member |
| --- | ---: |
| Completed reservations / local grants | 4 / 4 |
| Forced original promises | 11 |
| Allocator snapshot comparisons | 71 |
| Highest-promise comparisons | 71 |
| Final reserved counters, nodes 1–4 | 6 / 1 / 1 / 1 |
| Final observed promises, nodes 1–4 | 6 / 6 / 5 / 2 |

The allocator chain digest records original reservation boundaries, preceding
counter and observed fence. The surrounding raw-input inventory binds the
complete promises, sources, physical files and process observations.

## Qualification and scope

```bash
python3 -B -m scripts.v53.remove_process_ballot ORIGINAL_V2_PROCESS_ROOT \
  --qualify --workers 4
```

The [receipt](phase3-evidence/remove-process-ballot.json) binds frozen reader and
original producer provenance. Eighteen negatives exercise missing/reordered
forces, incomplete/duplicate writes, forged owners or fields, reservation outside
its original grant interval, extra/unbound reservations and missing, duplicated,
unknown or unbound promises. They preserve physical files, wire/failure bytes,
directories and all non-ballot observations. Continuous retention and retirement
still replay successfully on each copy before the ballot reader must reject the
exact intended fault.

The unmodified full prerequisite runs first. Mutated full network activation is
not counted as the target rejection: its promise checks overlap this reader.
Original and extracted optimized-Python qualification must match exactly and
leave every input hash unchanged. Ten focused tests cover continuity across
reopen, force boundaries, identity, one consumed reservation per grant and
rejection isolation. The complete V5.3 Python test result is retained in the
receipt, separately from the original native experiment. All 1,694 tests pass.
A direct comparison also confirms that all 1,392 Java/POM source files match
the original producer, with none added or missing.

`ballotForceCompositionQualified=true` refers to this member and layer.
`completeObservedCompositionQualified`, `originalObservationCoverageComplete`
and `phase3Complete` remain false. Earlier nested receipts retain their original
scope flags. No native history was rerun; no Java, POM, workflow or paid-cloud
behavior changed. Rollback removes this reader, tests and documentation only.
