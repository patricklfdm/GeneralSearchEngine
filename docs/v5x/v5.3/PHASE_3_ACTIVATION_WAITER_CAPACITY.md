# Phase 3: activation reply waiter admission

Status: runtime correction and regression entry added; Phase 3 remains OPEN.

Activation previously counted reply callers only in a local integer. Exact
duplicate PREPARE requests shared their original control, but each duplicate
could wait without a shared WAITER reservation or an inherited pending-call
check. The transport connection cap is a separate bound and cannot establish
the frozen 64-waiter limit for these handlers.

Every admitted activation control reply caller now reserves a zero-byte WAITER
from the existing shared pool. Its observation name binds the original request
digest and a unique allocation nonce. The endpoint also checks its inherited
`maxPendingClientOperations` bound. Admission happens before control creation or
dispatch, including when a completed control already holds the response.
Capacity refusal returns the existing correlated `REJECT/CAPACITY_EXCEEDED`.
The original task, deadline and cached result are not replaced by that refusal.

Higher PREPARE validation and volatile fencing still precede this admission.
A valid higher ballot therefore fences the old campaign even if other owners
occupy every shared waiter. Refusal does not force a promise or fetch a source.
Different in-flight controls retain their existing single-control rejection.

The caller releases its own lease on success, interruption, control failure,
timeout or cancellation. Reservation/dispatch failure releases it before
propagating the original exception. Caller drain cannot report completion
before that release. Interrupting a duplicate does not cancel the shared task
or release another caller's waiter. Existing CONTROL and descendant slot/voting
charges remain separate reservations in the same pool.

## Validation and limits

Six regressions fail on the original implementation. They use real original
bootstrap/journal/transfer owners and block the first reverse source exchange;
the original three-frame exchange is released to finish under its original
deadline. The cases cover:

- Two-caller inherited capacity and the 64-caller shared bound; excess exact
  duplicates are refused before dispatch, all admitted replies remain equal,
  and the completed reply is reused without another source fetch.
- Exhaustion by other shared owners, including an authentic higher PREPARE;
  the journal file inventory stays unchanged and the old campaign is fenced.
- Interruption of one duplicate, replacement admission and continued completion
  of the original control.
- CONTROL exhaustion after waiter admission, release on that original failure,
  and successful later admission after capacity is freed.
- Endpoint close cancelling the blocked control and draining all waiter leases.

The [development receipt](phase3-evidence/activation-waiter-capacity.json) records
the original failures, corrected-source Java results and any native replay
actually completed. Adjacent tests preserve caller/scratch drain and early
higher-ballot fencing. A fresh native two-slot smoke checks composition with
existing socket, source, voting, slot and publication evidence readers.

This is an admission and release correction. The new request-bound labels do
not by themselves establish independent whole-runtime waiter lifetime coverage.
The original bounded callback fixtures do not qualify every native saturation
schedule, simultaneous physical maximum, final-source hosted cohort or Phase 3
closure. No quota, deadline, retry count, wire/storage format, workflow or paid
cloud behavior is changed.
