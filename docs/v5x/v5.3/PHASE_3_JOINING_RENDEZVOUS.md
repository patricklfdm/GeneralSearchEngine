# Joining initialization before preparation publication

Phase 3 remains **OPEN**. `MembershipJoiningEndpoint.initialize()` now owns a
`MembershipJoiningPreparationRendezvous` instead of requiring its single discovery
pass to find an already-published old preparation. Explicitly supplied hints and
explicit proposer entry points retain their existing behavior.

## Bounded discovery and waiting

The original new member, JOINT cut and local fence are fixed before waiting. A
scan uses the existing exact request/transfer parser and visits known old
identities in order. The first valid complete hint is returned unchanged; it
cannot grant a ballot or authorize native initialization by itself.

If a scan finds no hint, only identities that returned a correlated **initial**
`NOT_READY` remain eligible for another scan. Each subsequent scan uses this
shrinking set. A route exhausting its original identical IO/deadline attempts is
excluded for the lifetime of this rendezvous. This allows an explicitly absent
reachable proposer to become ready while an offline minority remains excluded,
without multiplying failed-network retries. A temporarily excluded route becoming
the only prepared proposer is a possible availability limitation; there is no
silent reset of its retry budget.

If no absent routes remain, propagate the unavailable failure. Fatal transport
categories, unknown I/O, malformed/foreign data, and a rejection after transfer
starts propagate immediately. Nothing observes a remote promise, allocates an
old campaign, merges different hints or replays a client mutation.

The shared wait helper spaces scans with the existing request timeout. All scans,
waiting and subsequent native initialization inherit the endpoint's original
local start/budget. Deadline, cut/fence and cancellation checks remain active.
Close cancels the current read and drains its task before releasing rendezvous
metadata. The rendezvous retains 64 KiB of existing CONTROL capacity, alongside
unchanged per-pass and initializer reservations; the receiving hint stays charged
through the admitted force transaction.

The original one-pass `find()` remains available. Its internal scan result now
also reports exact absent identities, so waiting does not reinterpret generic
exceptions as permission to retry.

## Validation boundary

Source snapshots, exact executed/selected test inventories and archive hashes
are recorded in [`phase3-evidence/joining-rendezvous.json`](phase3-evidence/joining-rendezvous.json).
The first exploratory selection requested a nonexistent
`V53JoiningInitializationTest`: its 23 actual tests passed, but the launcher
correctly rejected the incomplete selection. It is retained as incomplete
qualification, not claimed as a green selected suite. The final selection uses
the actual endpoint and initialization-task classes: **46 tests passed in
69.931 seconds**, with zero failures or skips; all main/test sources compiled.

New tests use conditional original files and actual hint-serving handlers, with
controlled initial absence and unavailable replies. They exercise delayed hint
visibility, one-time exhausted route exclusion, all-unavailable/fatal refusal,
original expiry/guard failure, cancellation while waiting or reading, unchanged
original files and returned resource accounting. They do not establish the
positive native initializer's force behavior.

The existing complete native TCP history compiles against the managed entry but
still starts initialization after preparation. A new whole native history must
exercise concurrent early startup, waiting, exact source acquisition, forced
initialization, completion observation, FINAL/BARRIER and cold reopen before
this ordering is accepted. Preserve original first-failure histories and replay
physical evidence independently before negative mutations. The preceding batch's
native stable second-DATA publication timeout remains open, with no widened RPC
or owner budget. No POM, workflow, release or V5.2 cloud work changed.
