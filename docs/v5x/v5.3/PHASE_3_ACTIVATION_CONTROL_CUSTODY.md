# Phase 3: retired activation control custody

Status: runtime correction and regression entry added; Phase 3 remains OPEN.

An activation control may finish before its original response callers finish
their final guards. A different request could then replace that completed
control and release its CONTROL reservation immediately. The old callers still
referenced the request, future and response, so those retained bytes were no
longer charged to the shared queue budget. The earlier caller-drain and waiter
admission fixes did not establish this cached-control custody.

Two regressions reproduce the original under-accounting with one and two
delayed callers. They hold the existing final clock guard after real PREPARE
work completes, admit another correlated PREPARE with a different trace, and
compare actual CONTROL counts and queued bytes. Original bootstrap, journal,
transfer and response bytes remain in use; no synthetic quota changes or
replacement protocol implementation supplies the result.

Each control now counts its admitted response callers under the existing
registry. Removing a cached control marks it retired. Its original reservation
is released only when the worker has finished and its last caller has exited.
Callers retain the retired task through their existing bounded references; no
separate retired-task queue or unbounded lookup is introduced. Their WAITER
reservations and the original CONTROL/queued-byte limits still constrain
admission. If additional retained bytes leave insufficient capacity, ordinary
reservation failure applies before new work can run.

The caller releases its WAITER and then retired control custody before leaving
the endpoint caller drain; both releases share the original registry. The
[independent resource reader](PHASE_3_ACTIVATION_CONTROL_RESOURCES.md) checks that
conservative ordering against original reply boundaries. A dispatch rejection marks the never-started
task finished before retiring it. An active cancelled worker retains its bytes
until it finishes, even if every response caller has already returned. Closing
or abandoning a scope does not turn live references into free capacity.

## Evidence and remaining scope

The [development receipt](phase3-evidence/activation-control-custody.json) records
the two original failures, corrected-source tests and native replay actually
performed. A third regression closes the endpoint while an old retired reply
is still held: close must fail its existing drain bound and retain the scratch
lock, the cancelled caller must release precisely its original request/reply
bytes, and a later close must complete without leaked reservations.

Adjacent waiter, close, activation progress, endpoint and scratch recovery
tests preserve fencing, original deadlines and callback cleanup. The existing
native two-slot entry and its original-first physical/resource readers check
composition with transport, source, voting, slot and publication accounting.

This correction does not add request/response observation authority for every
activation allocation. Independent activation CONTROL/WAITER content and
lifetime coverage remains to be connected to original requests and physical
publications. Complete resource peaks, failure schedules, precise Phase 3
coverage and the final-source hosted cohort remain OPEN. Frozen quotas, retry
counts, time limits, wire/storage formats and workflow behavior are unchanged.
