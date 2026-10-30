# Serialized original floor reads

Phase 3 remains **OPEN**. This batch reduces repeated validation work in native
maintenance; it does not alter floor authority, physical ownership, force order,
quorums, exchange limits or the continuous native acceptance history.

## One bounded read scope

Reconstructing a retained floor authenticates every original generation, packet,
image, promise, selection and ancestry binding. Previously each stored-copy
callback additionally rechecked the same original journal and the entire floor
tree, on both sides of each copy's pure semantic decode.

Only when the native history owner already holds its journal monitor may one
private `OriginalRead` scope share those full physical inspections. Before the
scope begins, floor files and the original base owner are checked. After every
copy and the complete governing floor have been decoded and validated, both
physical checks run again before returning. Intermediate callbacks retain their
exact floor record, original packet, root, manifest and reference bindings.

The scope is tied to this floor, thread and held journal monitor. Its `finally`
revokes it on success or exception; each stored-copy capability also expires
after its own decode. No caller callback, network exchange, force, write,
deletion or asynchronous work executes within it. Constructors without the
journal monitor and the supplied-verifier mode retain the previous per-callback
physical checks. The returned copies still validate their complete original
bytes on subsequent use. Nothing is cached between calls.

## Source exchange checks

An outgoing source exchange previously ran the complete guard twice around
pure retry-attempt bookkeeping. It now performs that bookkeeping, then checks
the complete guard inside the existing synchronized send boundary. That check
still follows the clock supplier and precedes `link.exchange`. Reply consumption
and retryable failures retain their full checks. Request bytes, three-attempt
bound, original deadline, resource leases and cancellation are unchanged.

## Safety and remaining acceptance

Focused coverage includes valid floor reads followed by corrupt journal, floor,
generation, packet and image bytes; same-byte inode replacement; higher-ballot
fencing; and journal corruption after the release authority's parent force.
The last case must fail before relinquishing the floor, preserve the corrupted
original for diagnosis, and leave its writer failed even after test restoration.
External-verifier establishment/release and transfer loss, cancellation,
correlation and fencing checks remain required.

The [source-bound receipt](phase3-evidence/floor-read-validation.json) retains
all snapshots, logs, physical files and transport diagnostics. Twenty-two
existing floor establishment/release tests passed on the initial implementation.
One new test initially expected the wrong exception type: the damaged journal
correctly raised `ReplicationException(CONFLICTING_HISTORY)` after the force
callback. Its assertion was corrected, and that failed report remains retained.
Both new tests and all 14 source-exchange tests passed on the final implementation.
The only production difference between these focused snapshots is the separate
source-exchange check change; the floor implementation is identical. Twenty-two
Python tests and independent three-size source replay with 13 negatives passed.

The unchanged five-to-four native producer now **PASSes in this execution**:
the removed owner adopts FINAL 7 without voting, and the stale survivor adopts,
installs the selected cohort, publishes BARRIER 8 and DATA 9, and verifies that
nodes 1, 2 and 4 share the final cut. Runner elapsed was 347.698 seconds. Barrier
ACCEPT replies took about 12.1 seconds from first send; DATA ACCEPT took about
14.0 seconds. Both needed all three existing attempts, so timing margin remains
small and a single success does not establish reliable availability or a timing
root-cause fix. Unselected node 3 rejected retention and source operations; these
remain in the original trace and require explicit independent service replay.

Original-first replay derives seven preparation slots, both adoptions and 54
snapshots, rejecting all 11 exact negative mutations. It still returns PARTIAL:
it does not independently qualify the new selection, subsequent maintenance,
BARRIER 8 or DATA 9. The complete Java producer result and that deliberately
limited independent result are separate evidence, not interchangeable gates.

The prior [image-validation history](phase3-evidence/image-validation.json)
failed at the first BARRIER ACCEPT. This read-scope optimization does not by
itself prove a timing improvement, native availability, complete post-adoption
physical replay or Phase 3 closure. Whole-history evidence must keep every
failure, without restarting individual cells or substituting a successful retry.

Rollback removes `OriginalRead`, restores each `RetainedCopy.check()` physical
inspection and restores the redundant pre-bookkeeping source check. There is
no persistent format, wire kind, public API, POM, workflow or paid-cloud change.
