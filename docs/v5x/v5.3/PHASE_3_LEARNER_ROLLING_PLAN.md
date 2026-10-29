# Next implementation — bounded rolling learner lifecycle

Status: **partially implemented; complete rolling lifecycle OPEN**. A21 reclaims
the initial source/backup, A22 enables current-head acquisition, and
[A23 inactive installation](PHASE_3_LEARNER_SLOT.md) implements the bounded slot-B
plan, source move, semantic backup and cold resume. B is still pending: migration,
new-head selection, covered slot-A retirement and alternate reuse remain required.
The first-successor installer continues to protect its immutable old plan.

## Reuse boundary

`MembershipGenerationFiles` belongs to the voting journal and its selector/floor
authority. A learner's copied GENERATION belongs to its original source voter.
Do not create a learner voting manifest or fabricate a Floor.Copy to reuse that
class. Share bounded file/ownership helpers where applicable, while preserving a
distinct nonvoting rolling owner and independent received-source verification.

Use exactly two fixed source slots and two fixed typed locations. The currently
retained successor/source and ready sidecar can serve as the first slot; a fixed
second pair belongs to one rolling owner. No per-revision directory allocation.
The original admission, A18 install metadata, A20 head and A21 retirement decision
remain immutable recovery roots until an explicit migration contract retires them.
Their old references must never be mistaken for the rolling active selection.

Only a real current typed owner may start a new transfer. Keep its GENERATION and
APPLICATION leases until the next complete source, semantic backup, exact receipt
and active-head selection have been forced. Received files use the same LEARNER
slot, then its existing atomic GENERATION claim; never occupy a third generation.
Keep the current terminal ancestry, rather than forcing future compacted sources
to retain every ancestor of the initial admission.

## Durable states to implement and test

1. Enter rolling mode from the exact reclaimed live typed head. Retain original
   source/backup ownership across migration; no close/reacquire budget gap.
2. Write one bounded original inactive-slot plan before moving received bytes.
   The plan binds current-head identity, terminal ancestor, slot/sequence, source
   peer, original generation, file identities, staging and destination paths.
   Partial original plans refuse unchanged; complete plans resume their own bytes.
3. Force the received source and both move parents, then decode and force the
   inactive typed backup and receipt. The current head stays usable and owned.
4. Force a candidate head binding the new source/receipt and exact covered old
   slot plan/typed members. Atomically select and force it before revoking old
   handles. A complete candidate alone never becomes the selected head.
5. The selected head can also carry exact old-slot deletion authority. This avoids
   a growing per-cycle retirement log. Preserve the covered old plan until its
   source and typed members are removed and their parents forced; remove that
   obsolete plan last. Unknown/replaced members refuse; only covered missing
   members are accepted during interrupted cleanup.
6. Reuse only the cleared inactive slot. A new complete plan must link the current
   selected head and next bounded sequence. Recovery must distinguish an old
   covered slot, a cleared slot and a new staged candidate without treating stale
   files as new originals. A new selection revokes earlier head capabilities.

Current-source verification must finish before any recovery deletion. Initial
operation/replica locks and the rolling owner protect the whole history. Keep
the old source's leases across interrupted deletion; release only after force.
Failure before a durable handoff cannot delete the still-current source.

## Metadata accounting for the remaining selection states

A21's 2,048 KiB sum is a simultaneous worst-case envelope, not the amount remaining
after completed retirement. At that boundary the old typed plan/candidate/receipt/
selection have been deleted. Active admission and retention require no redundant
candidates; the first-successor plan and head are active-only, and its typed plan
has no redundant candidate. Their remaining bounded metadata sum is 908 KiB:
596 KiB admission/replica plus 312 KiB successor selection/typed/head/retirement.

A23's pending B adds 576 KiB, for a 1,484 KiB bound. This leaves room inside the
original 2 MiB lease for the remaining rolling selection metadata. Verify the exact
simultaneous maxima of migration, candidate selection,
partial cleanup and slot reuse against actual permitted inventories before freezing
their sizes. Do not count freed bytes until the associated original deletion and
parent forcing are complete, or count the same backup as both borrowed and owned.
Retain the unchanged two-GENERATION and seven-APPLICATION global limits.

The implementation must be followed by a continuous native multi-revision history,
all five ADD/REPLACE shapes, cold reopen, partial-record and halt/SIGKILL cuts,
stale/foreign receipt and slot rejection, cancellation and matching INTENT. Final
hosted shards may split independent histories, never transfer/install/restart
segments of one original history. A standalone core/source smoke cannot close
this lifecycle or Phase 3.
