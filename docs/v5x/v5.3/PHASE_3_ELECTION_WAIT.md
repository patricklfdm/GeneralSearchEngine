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

Only a current voter may wait to campaign. Idle polls use the volatile fence,
authenticated heartbeat contact and completed activation milestones; they do not acquire the journal writer. A new
view/fence requires a full original-state check and another bounded wait inside
the same invocation. An accepted activated heartbeat arms from its original
arrival, not the later poll or reply time. Seeing that same contact again cannot
keep postponing the timer. Unactivated repeated pulses do not postpone it.

Before returning, the wait rechecks original storage, current membership and
fence, then looks for newly admitted contact. A heartbeat racing after this
decision does not provide exclusive ownership: ordinary competing-campaign and
ballot fencing rules still apply. The two admitted activation milestones below
provide bounded progress hints; unfinished transfers do not postpone the timer.

Close and interruption wake idle waiting. The enclosing round owns/drains this
child with its existing resources. Closing in WAITING cannot proceed to a grant
or send. Full work-boundary checks may still wait for the writer; the idle-path
guarantee is not a promise to interrupt an active filesystem operation.

## Admitted activation milestones

An incoming endpoint records `GRANTED` only after the original promise exchange,
local grant/basis validation, required maintenance and successful response checks
finish. It records `INSTALLED` only after selected original sources are verified,
installation completes and the response passes the same final checks. Progress
advances monotonically at most twice per existing campaign scope; an exact duplicate
or a fresh trace for the same completed stage cannot renew its time. Serving a
local outgoing campaign alone does not count as incoming progress.

The hint binds root, view and ballot to its original scope and completion time.
It is volatile, contains no payload/image, and has constant per-scope space.
Abandonment, scope expiry, replacement, a changed fence/view or endpoint close
makes it unavailable. Recreating the endpoint cannot recover it from a durable
grant. Polling only checks the existing volatile fence and scope; it neither
acquires the journal writer nor changes stored authority.

The wait consumes heartbeat and milestone observations independently and arms
from the latest original time. A delayed older heartbeat cannot move the arm
backwards. Repeated polls do not draw fresh jitter or reset the arm. The existing
parent lifetime, incoming campaign deadline and all resource/retry limits remain
unchanged. Neither milestone grants READY, a vote, a lease or exclusive election
ownership. Failed controls, incomplete source transfers, STATUS and inactive
heartbeats do not manufacture milestones.

This is deliberately a completion boundary, not a transfer-byte progress policy.
A long-running transfer can still overlap another candidate's election timeout;
ordinary ballot fencing must settle that race. Ungated competing-candidate and
process-restart qualification, the eventual storage/listener owner and the full
Phase 3 matrix remain open.

## Retained validation

The [milestone receipt](phase3-evidence/activation-milestones.json) binds the
current increment to two immutable source snapshots with identical production
Java: 38 tests, followed by one added delayed-heartbeat regression. All 39 pass,
without skips. Ten new component checks cover once-only grant/install completion,
unfinished and corrupt sources, capacity rejection, revocation, nonblocking
observation, endpoint recreation, original overall deadline, both activity orders
and a delayed older heartbeat after an already consumed milestone.

The same source passes existing native TCP activation at 3/4/5 voters, automatic
wait/discovery/BARRIER/DATA and WAITING-close. Independent original-storage/wire
replay accepts those five histories and rejects all 24 existing mutations; ten
focused Python checks pass. Java assertions establish the volatile scheduling
semantics, while the readers verify the original authority, storage, exchanges and
close behavior. The initial failed execution is retained: four new-fixture errors
assumed a zero incoming start, and fourteen existing fixtures could not bind
loopback under the sandbox. The corrected fixture retains the actual first
deadline; permitted local TCP execution leaves production timing unchanged.

The source, reports, raw histories, inventories and analysis tools are retained in
`target/v53-activation-progress/qualification.tar.gz`; its exact byte hash and
member count are in the receipt. No JAR or compiled class is needed in that
archive. Current qualification is local and scoped, not protected or complete
Phase 3 acceptance.

The earlier [election-entry receipt](phase3-evidence/election-wait.json) binds two immutable source
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
The milestone increment can instead be rolled back alone by removing the
endpoint progress cell and its consumption in the wait, restoring heartbeat-only
timing without changing any durable format or campaign authority check.
