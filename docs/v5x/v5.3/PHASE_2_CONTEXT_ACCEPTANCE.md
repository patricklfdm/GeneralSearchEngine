# Context-backed acceptance and completion capacity

Phase 2 remains **OPEN**. This batch connects a private owner transition from the
old context-backed vote to the exact entry selected by the newer installed round.
It does not enable online membership, arbitrary context replacement or campaigning
while a fenced old context still exists.

## Exact transition

`acceptRetainedCurrent` reconstructs the original vote/generation using the
existing context and separately owned backing source. It requires the same parent,
exact ENTRY and payload bytes, an installed higher PROMISE/BASIS/SELECTED and the
same selected entry. It derives one successor ACCEPT under the installed ballot;
the ENTRY origin does not change. A complete, partial or renamed successor must
match these exact bytes. A foreign well-framed candidate is rejected.

The owner forces the successor file and parent before removing the redundant
context. Old phased objects remain in the original frozen backing source. Reopen
may finish only this exact successor and cleanup; it returns no voting ACK. An
explicit retry with no context must match the already installed successor before
it can finish floor cleanup and use the ordinary ACCEPT acknowledgement path.

## Completion space before ACK

An actual first integration attempt failed at the unchanged seven-image limit:
replay needs two scratch reservations plus the applied-end reservation. Reclaiming
the predecessor source alone left five occupied reservations, so immediately
reserving those three could not succeed. The failed log is retained.

The corrected order is:

1. Read-only validation of the existing floor-release plan and future publication
   ancestry/coverage, plus shared journal completion capacity.
2. Force the uniquely selected successor ACCEPT while keeping context and floor.
3. Remove context only after that successor is independently recoverable from its
   current generation and journal.
4. Release the now obsolete floor copies through the existing forced exact-inventory
   transaction; retain the current generation, selector and frozen backing source.
5. Reserve replay input/output, applied end and publication space; check fencing
   again before returning any ACK.

After predecessor reclamation this path ends at six APPLICATION reservations.
Extra shared reservations can prevent an ACK after durable conversion/cleanup;
no rollback erases the successor. Reopening and the exact original retry may
finish once capacity is available. No resource count/byte limit is increased.

## Qualification and limits

The retained matrix covers 26 first IOException cut types across vote creation,
prefix write, force/rename, context removal and floor release. Every case has a
second interrupted recovery at successor active-file force, then exact retry and
duplicate return. Additional owner tests cover changed original entry/payload,
missing/torn authority, a well-framed foreign successor, higher observations at
four handoff boundaries, and capacity refusal followed by retry.

The independent validator first replays original generation retirement and source
reclamation. It derives the successor from exact original bytes, models every
snapshot and force prefix, preserves the original ENTRY origin, and checks that
floor deletion follows forced successor/context withdrawal. Fourteen mutations
must fail for exact reasons; normal, `-O` and relocated replay must agree.

See [retained receipt index](phase2-evidence/context-acceptance.json). These are
actual local-owner exception tests, not process-death, power-loss or network
qualification. Historical bootstrap and remote observations remain conditional.
Later campaigns from a still-retained context, complete phased application and
publication, maximal resources and coordinated old/joint/new lifetime still need
their own integration evidence.
