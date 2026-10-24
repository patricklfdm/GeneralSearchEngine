# Protected capture and backing retirement across process death

Phase 2 remains **OPEN**. This local gate combines
[protected capture](PHASE_2_CONTEXT_CAPTURE.md) and
[intermediate source retirement](PHASE_2_CONTEXT_BACKING_RETIREMENT.md) under fresh
process owners. It adds no runtime Java behavior, resource limit or public API.

## Execution contract

The initial local owner has installed selection 21, original pending certificate
20 and forced context backing 22. Each case starts from that validated snapshot
and uses three separate JVMs:

1. Capture 23 and retire covered backing 22, stopping at one declared cut by
   `Runtime.halt(73)` or an externally delivered SIGKILL.
2. Reopen, complete any exact pending source/BASIS recovery, then halt while
   re-sealing the backing source, before a new context write or returned grant.
3. Reopen again, finish the exact transaction, explicitly obtain grant 23, then
   capture 24 and retire 23. Check the unchanged original vote and steady image
   reservations; close the owner and verify all reservations are released.

There are 50 first boundaries, each tested with both termination modes: 34
capture/rebind boundaries, the second context source-member force, 14 source
retirement/rotation boundaries and the second source-file deletion. The full set
uses 300 worker JVMs plus 50 external live-lock probes. Workers run sequentially.
No file snapshot reads a live lock descriptor.

An empty retirement-intent file cannot supply a complete original deletion
request. The resumed caller must complete that original request before replaying
a grant. An initial driver attempted the reverse order and was correctly refused;
its failed run remains retained. The corrected driver obeys the existing storage
contract instead of relaxing that guard.

## Evidence and limits

The source/build-bound index is
[context-capture-process.json](phase2-evidence/context-capture-process.json).
The independent validator reconstructs the original reference, captures 22/23/24,
context bytes, exact deletion inventories and journal pruning. It compares all
first/second/recovered/final snapshots and complete worker force/return traces.
Both interrupted workers must terminate at their declared boundaries; recovery
never fabricates a returned grant. Only explicit requests after open may return.

Original-first negative and relocated replay check missing or changed evidence,
pinned authority, force order, premature/wrong replies, resource claims, truncated
traces and execution scope. Normal and Python `-O` results must match.

Peak and steady APPLICATION reservations remain seven and six, including one
empty future-publication reservation. These are small actual payloads, not maximal
byte qualification. Historical bootstrap/quorum observations are still conditional
fixtures. Process termination does not simulate power loss. Later selected-slot
reuse, governing-floor replacement, maximal coordinated old/joint/new lifetime,
public runtime and Phase 2 closure remain separate obligations.
