# Phase 3: activation endpoint caller drain

Status: implementation and regression entry added; Phase 3 remains OPEN.

The activation endpoint previously waited for its control/expiry executors, but
did not wait for all synchronous calls that could still use the original journal
and incoming scratch. A completed PREPARE worker could leave its reply caller
inside the final guard; direct discovery and local campaign registration also
ran outside those executors. Closing the endpoint could report success and
release `scope.lock` before those admitted calls returned.

Four deterministic regressions fail against the original implementation. Three
hold a real direct request, control reply caller or local registration inside
the existing injectable clock and observe that `close()` incorrectly succeeds.
The fourth holds an actual file channel in the control callback and observes
that the timeout path interrupts that callback. These are original runtime
failures, not malformed evidence mutations.

## Closing behavior

Incoming calls and local registration, installed-state checks, maintenance and
joining-preparation publication now enter a small endpoint-lifetime counter.
Admission and revocation are serialized by a separate lock. This lock does not
hold journal, control-registry or caller callbacks, preserving higher-ballot
observation before waiting for an earlier control's registry. Callers always
release their count on return or exception.

`close()` revokes admission and cancels the pending response immediately. It
shuts down both executors cooperatively and closes the original child scopes.
It then waits for both executors and every admitted caller under one existing
request-timeout window. Timeout or interruption remains a failure and retains
scratch ownership. A later external close must finish that same drain before
releasing the lock. No `shutdownNow()` interrupts the control or expiry callback
while it may own original I/O.

A close invoked from an admitted caller, control worker or expiry callback
revokes the endpoint, then explicitly refuses to claim its own completed drain.
It retains ownership for a later external close. Closing a scope does not renew
its original grant deadline or create permission to reopen service.

The change does not add resource capacity, retries, wire/storage formats,
workload histories or publication authority. The lifetime counter establishes
drain, not a new WAITER quota or complete CONTROL-resource qualification.

## Evidence and remaining scope

The regression entry covers direct/control/local-registration timeout, original
channel survival after timeout, interrupted caller drain, self-close from all
three callback roles, and higher-ballot fencing while the original control
registry is held. Real scope-lock reacquisition is tested before and after
successful external drain. Adjacent activation, slot-close, scratch recovery and
progress regressions exercise existing ownership and callback composition.

The [development receipt](phase3-evidence/activation-close-drain.json) retains
original failing reports, corrected-source results, input hashes and any native
smoke/independent replay actually executed. The first adjacent attempt's TCP
case was denied loopback access by the execution sandbox; that environmental
error is retained separately from the four reproduced runtime failures.

The local gates establish this closure behavior. They do not qualify the full
544-history hosted cohort, combined physical maximum, all callback schedules or
Phase 3 completion. Exact coverage and final-source execution remain OPEN.
