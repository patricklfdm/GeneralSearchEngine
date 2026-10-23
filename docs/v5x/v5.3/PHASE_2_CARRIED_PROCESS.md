# Carried-vote maintenance process recovery

Status: private storage qualification; Phase 2 remains **OPEN**. This gate
extends [carried publication](PHASE_2_CARRIED_PUBLICATION.md) from same-JVM I/O
injection to repeatedly interrupted child JVMs. It qualifies the handoff and
maintenance before the new ballot publishes its carried first entry.

## Original request and crash matrix

A fresh three-node seed first publishes actual DATA, accepts another DATA under
the old ballot on all three voters, and freezes a new selected set. The seed also
retains a clean reference completion through new acceptance, authorized
maintenance, DATA publication, a subsequent BARRIER and fresh PREPARE. Actual
votes and applied-end ACKs are retained independently of the final snapshots.
Its 39 observations come only from those original physical records; unrelated
historical fixture observations are excluded.

Each child starts from the same exact prepared originals. It installs the frozen
new generation, reaccepts the original ENTRY/payload under the new ballot, and
finishes floor, old-generation, old-source and journal maintenance. The request
does not choose a different ballot, source set or entry after an interruption.
Children open private copies of input owners; retained original seed evidence is
not reopened or resealed in place.

Eleven pairs of cuts run in both `Runtime.halt` and external SIGKILL modes:

| First interruption | Second interruption during recovery |
| --- | --- |
| Installation manifest force | Generation directory force |
| Selector rename | Original active ACCEPT force |
| New ACCEPT prefix write | Complete candidate force |
| New ACCEPT rename | Full governing-floor copies force |
| Floor proposal force | Floor authority force |
| Floor authority force | Retirement authority force |
| Old-generation file deletion | Retirement authority reseal |
| Old-source retirement force | Journal rotation force |
| Old-source file deletion | Original source-retirement force |
| Floor relinquishment | Release authority force |
| Floor authority removal | Final release marker removal |

The second interruption always uses a fresh child with halt. Two further children
finish and repeat the exact operation. Thus the full matrix contains 22 cases and
88 child JVMs. SIGKILL is delivered only after the cut handshake. Original,
first-crash, second-crash and final file snapshots and process logs are retained.
The final node must match the independently projected clean reclaimed state,
still owning the original entry with a new-ballot ACCEPT. It has two actual image
files and six reserved application image slots; no pending maintenance remains.

## Evidence and limits

The [source/build index](phase2-evidence/carried-process.json) records the final
qualification and earlier development output. Independent replay validates the
seed's original application/voting history before deriving installation and
maintenance. It checks phase write/force order, exact partial candidates,
selector switching, governing authority before deletion and complete physical
inventories after both interruptions and final reopen. Negative mutation and
portable/optimized replay must use the same original-first validation.

Historical bootstrap is still conditional, the application images are small,
and the process model assumes the existing filesystem force contract. Process
death leaves the OS cache alive and is not physical power-loss qualification.
The worker is a private storage driver, not network activation or public READY.
Maximal storage lifetime, configuration-boundary histories and complete offline
provisioning remain requirements in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
