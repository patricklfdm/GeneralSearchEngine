# Storage observations during joint queue pressure

The existing [queue-completion experiment](PHASE_3_QUEUE_COMPLETION.md) now
retains the disk state of the same node that owns the queue, at both
`SEVEN_SENDS_HELD` and `EIGHTH_SEND_REFUSED`. These are checkpoints inside one
uninterrupted REMOVE history. The experiment must still drain the pressure,
finish native FINAL/activation/BARRIER and close every owner.

This is a component observation, not simultaneous maximum-resource acceptance.
In particular, independently observed metadata, image and queue maxima are not
added together or represented as a shared peak.

## Independent checks

`queue-storage-captures/index.json` binds each snapshot to node 1, the original
network event index and the resource-observation sequence before and after the
copy. The fixture borrows existing file descriptors while copying owned files,
so reading evidence does not release the runtime's POSIX locks.

The reader first validates the complete original physical history and joint
authority. It then requires both snapshots, including directory membership and
every file byte, to equal `installed-2/node-1`. Producer hashes alone cannot
authorize another snapshot. Identical image contents in different locations
count as separate physical copies.

Storage reservations are derived from these original files using the existing
publication resource rules. Every trace transition during each copy must agree,
including intermediate transitions when the endpoint counters happen to match.
CONTROL and WAITER callbacks may change; they cannot hide storage growth. The
result retains physical bytes, physical application bytes, image copies,
metadata/staging reservations and the queued bytes at each exact checkpoint.
Existing queue replay independently checks the charged request/reply bytes.

Missing snapshots, foreign owners, shifted sequences, changed inventories and
incorrect reservations add five exact negative cases. A passing unmodified
original remains a prerequisite. Current sets are:

| Profile | Raw receipt | Exact negative cases |
| --- | --- | ---: |
| JSON queue | `gse-v53-queue-completion-v2` | 15 |
| Segmented queue | `gse-v53-segmented-queue-completion-v2` | 17 |
| Maximum image queue | `gse-v53-maximum-queue-completion-v2` | 20 |

The producer, verifier and cohort reader require the new observations. Old v1
originals remain intact and describe their historical source; they cannot be
relabelled as the current qualification. Small rehearsals keep their distinct
non-pressure outcome and cannot fill an admission slot.

## Execution limits

Production Java, queue and storage limits, request/barrier deadlines and the
continuous-history lifetime are unchanged. There is no history retry or split.
The two snapshots use the existing bounded original archive; pressure cannot
be completed by extending its deadline.

The [maximum-image entry](PHASE_3_MAXIMUM_QUEUE_ENTRY.md) still requires native
Linux and its published disk/memory checks. The operator has no qualifying
machine currently and will arrange one after development. This batch does not
dispatch a workflow or bypass the environment gate. Full maximum execution,
combined-resource coverage and final-source admission remain open.

## Development evidence

The [development index](phase3-evidence/queue-storage-pressure-development.json)
retains the first full-pressure failure: the native history reached BARRIER and
closed, but the new index used physical paths as protocol JSON object keys. Its
997-second execution remains FAIL; no missing receipt was reconstructed.

The correction records ordered `path`/`sha256` rows, preserving the protocol's
object-key restrictions. Two fast Java serialization regressions pass. A fresh
small-image continuous history passes in 329.1 seconds, followed by 6.21 seconds
of original-first physical/resource replay with an unchanged original inventory.
Both checkpoints show four physical images (83,468 bytes), 274,346 total physical
bytes, 35,820,334 reserved metadata bytes and 139,973 reserved staging bytes. Its
685,231-byte queue observation is a rehearsal, not aggregate-byte refusal.

The related Python suite passes 196 tests; 30 optimized checks and 19 contract
tests also pass (test groups overlap). The corrected full-pressure 17-negative
gate and maximum-image 20-negative gate have not executed. All five Phase 3
closure gaps remain open.
