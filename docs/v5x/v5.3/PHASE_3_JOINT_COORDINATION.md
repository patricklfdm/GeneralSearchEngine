# Coordinating a JOINT continuation

Phase 3 remains **OPEN**. `MembershipJointContinuation` connects the existing
old-majority preparation, remote completion observation and normal round driver
under one serialized internal owner. It does not expose a public runtime or
choose when a node should campaign.

## Sequence and authority

The actual old voter reads its original JOINT context and derives the joining
identity from new-minus-old membership. ADD/REPLACE has one new identity; REMOVE
has none. Stable and foreign owners are refused. For a new identity, the owner
prepares the old majority and retains its published routing hint while waiting
for the joining endpoint to complete native initialization.

`MembershipCompletionWait` polls only a valid initial absence returned by the
existing completion probe. Poll spacing uses the existing request timeout.
Malformed/correlated-transfer failure, capacity/fencing/closure, or exhausted
transport retries propagate immediately. There is no retry of a failed campaign,
new ballot during waiting, union of hints, or promotion of an observation into a
vote. The joining process remains independently responsible for initialization.

After positive observation, close/drain the preparation before constructing a
normal `MembershipRoundDriver`. That driver still performs actual selection,
installation, governing majorities, FINAL, stable activation and fresh BARRIER.
A member can fail after observation; ordinary activation must still succeed.
Removed proposers are not exempt from new-view membership checks.

Preparation, waiting, cleanup and activation share one original local start and
budget. The new round `start(originalStarted)` overload preserves that lifetime;
existing direct `start()` starts its own lifetime. Readiness and subsequent
submissions retain the same guarded owner. Time expiry after a positive probe or
after cleanup prevents handoff. No timeout or cancellation creates readiness.

The coordinator reserves 4096 bytes of existing CONTROL capacity under a unique
owner key. Existing child reservations stay in force. Close revokes new calls,
cancels/drains children and waits for the owning call before returning its charge.
A failed cleanup keeps child references for another cleanup attempt.

## Validation and limitations

Final component results and immutable source/archive hashes are recorded in
[`phase3-evidence/joint-coordination.json`](phase3-evidence/joint-coordination.json).
The focused tests cover all seven profile-derived joining identities, stable or
foreign refusal, original deadline expiry before writes, cancellation/drain,
absence-only polling, failure propagation and deadline expiry during cleanup.
Positive scheduling probes are synthetic and confer no native authority.

The first run executed 23 tests: 22 passed and the existing native stable
round test failed after 122 seconds with `membership exchange deadline`. Its
original trace contains installation, the completed first BARRIER, readiness,
and the second DATA slot begin. The failed request is a node-1 to node-2 PUBLISH;
the original trace also retains node-2 publication-force/ACK events, but no
successful second PUBLISH exchange. It has no completed second publication
snapshot or round PASS receipt. Late endpoint-closed failures occur during
cleanup. The retained data does not establish the underlying latency cause.
This failure is not converted to a pass, and no timeout/retry bound is increased.
It remains a required final-source native validation item.

The original increment compiled the complete joining TCP history without running it.
The later [native qualification](PHASE_3_NATIVE_JOINING_QUALIFICATION.md) exposed
a scratch-parent defect after initialization/cold reopen. Preparation and normal
activation now reuse the caller's same OUTGOING scope only after draining the
previous owner; the exact marker/lock continues to enforce identity and exclusion.
The correction has 40 focused passing tests; full corrected history is pending.

At the original increment, Its retaining
cold continuation now calls this coordinator instead of constructing the normal
round directly. This adds a fresh preparation and completion probe for an
already initialized member; it does not yet exercise concurrent early-start
joining discovery. Whole-history independent physical replay, all actual
profiles and alternative majorities, process death, maximum combined resources,
removed-proposer takeover and autonomous election/adoption remain required.
Long histories stay in the [hosted acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
No workflows, POMs, public API, frozen limits or V5.2 cloud execution changed.
