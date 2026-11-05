# Phase 3 retained-owner failed listener close

The [listener drain predicate](PHASE_3_NATIVE_CONTROL_CLOSE.md) now gates retained
owner storage release and pending-listener drain before voter handoff. The
[development index](phase3-evidence/pending-listener-drain.json) records exact
inputs and results. Phase 3 remains OPEN.

## Failure and correction

`MembershipTransport.close()` in an I/O callback cancels its transport without
waiting for that same worker. The checkpoint/head endpoint correctly reports
`closed() == false` while the callback is live, but `MembershipLearnerDisposition`
previously released retained storage immediately after the endpoint close call
returned. Both checkpoint and head regressions reproduce this: close returned
normally and metadata reservations fell to the pre-retention baseline while the
original callback was still held.

The disposition now requires each owned listener's completed-drain predicate
after closing it. An undrained callback close throws an `IOException` before
retained children or storage leases are released. The owner is already revoked;
an external caller may retry the same owner, finish the drain, and release its
original reservations. Interrupted external close retains storage and preserves
the interrupt flag. Voter handoff uses the same listener check. Existing transport
timeouts, durable formats, voting rules and resource bounds are unchanged.

## Scoped evidence

The new four-case TCP component test holds a real response callback and exercises
checkpoint/head listeners with callback cancellation and interrupted external
close. It captures the genuine pre-retention resource sequence, each close-call
boundary, and file hash observations before failure, after failure and after
successful retry. The resource journal is complete through fixture cleanup.
Original failed tests and raw traces are retained separately from corrected runs.

```bash
python3 -m scripts.v53.pending_drain_evidence RAW
python3 -m scripts.v53.pending_drain_negatives RAW
```

Independent replay reconstructs every resource change. It requires continuous
original storage ownership through failed close, continuous pre-retention leases
through successful retry, release-only storage cleanup, and the exact original
baseline at return. It rejects release/reacquire gaps even when checkpoint totals
are correct. It also checks the exact exception/interrupt outcome, retained file
hash continuity and final complete zero accounting. The negative driver first
validates the unchanged original; each mutation must fail its specific obligation.

This is conditional retained-owner lifecycle evidence. Recorded file hashes are
not an independent replay of native authority. Results explicitly leave
`physicalStorageQualified`, `wholeRuntimeResourcesQualified` and `phase3Complete`
false. A successful retry here does not qualify constructor rollback, every
enclosing store/owner cleanup path, or full native joining/custody histories.

## Remaining work

Enclosing store cleanup still needs its own failure/drain propagation audit:
best-effort child cleanup and one-shot close guards cannot by themselves establish
safe parent release or retry. Failed construction, remaining export/task/control
owners, combined maxima/headroom and final-source required-four/joining hosted
qualification remain separate obligations. The frozen 544 planned Phase 3 hosted
histories and later-phase 3310-case plan are unchanged.
