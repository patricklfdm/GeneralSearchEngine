# Bounded automatic election entry

Phase 3 remains **OPEN**. `MembershipRoundDriver.startAutomatic` now owns one
randomized election wait, then runs existing original-prefix discovery, fresh
activation, carried recovery and the new barrier under its original deadline.
The caller no longer sequences those steps. Continuous campaign ownership,
periodic scheduling and the complete restart/failover matrix remain required.

## Authority and cancellation

The wait uses the configured `AutomaticLeadershipPolicy` election interval.
Its jitter must stay within the inclusive bounds. It returns only revalidated
original discovery state, never a ballot, vote, lease or readiness. The following
campaign still performs its complete normal protocol.

Only a current voter may wait to campaign. Idle polls use the volatile fence and
authenticated heartbeat contact; they do not acquire the journal writer. A new
view/fence requires a full original-state check and another bounded wait inside
the same invocation. An accepted activated heartbeat arms from its original
arrival, not the later poll or reply time. Seeing that same contact again cannot
keep postponing the timer. Unactivated repeated pulses do not postpone it.

Before returning, the wait rechecks original storage, current membership and
fence, then looks for newly admitted contact. A heartbeat racing after this
decision does not provide exclusive ownership: ordinary competing-campaign and
ballot fencing rules still apply. Long-running activation progress needs its
own admitted progress semantics; this timer does not infer it from chatter.

Close and interruption wake idle waiting. The enclosing round owns/drains this
child with its existing resources. Closing in WAITING cannot proceed to a grant
or send. Full work-boundary checks may still wait for the writer; the idle-path
guarantee is not a promise to interrupt an active filesystem operation.

## Retained validation

The [receipt](phase3-evidence/election-wait.json) binds two immutable source
snapshots with identical production Java: the original eight-test execution and
one later close-integration test. The final test file contains all nine tests.

- Conditional original-storage tests cover delay, arrival age, overall deadline,
  repeated inactive pulses, busy-writer close, changed disk bytes and invalid
  jitter. The timer fixture uses 5/15/25/20 ms; it does not change frozen runtime
  timings or establish a failover SLA.
- A real TCP history runs automatic wait, STATUS discovery, fresh activation,
  BARRIER and DATA. Its default RPC and 180-second round bounds are unchanged.
  Existing independent physical/wire/lifecycle replay and eight exact negative
  mutations pass.
- A second native history closes WAITING. Original storage before/after matches;
  no request or new grant occurs. The new reader reconstructs initialization and
  checks the exact normal reopen force sequence, with six exact negatives.
- Sixteen focused Python tests pass. The first reader incorrectly expected no
  reopen events; that failed diagnostic is retained. The correction validates
  the real startup lifecycle and rejects missing, reordered or extra forces;
  neither original history was rewritten or rerun to remove those events.

No public API, persisted bytes, workflow, paid-cloud execution or time bound
changes. Rollback removes the private waiting child and automatic entry; the
explicit discovered/start paths and heartbeat components remain available.
