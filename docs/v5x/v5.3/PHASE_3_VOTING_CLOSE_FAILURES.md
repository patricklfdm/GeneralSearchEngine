# Phase 3: voting shutdown and original cleanup failures

Status: scoped lifecycle correction; Phase 3 remains OPEN.

Four deterministic regressions on the previous implementation exposed:

1. A transfer-service close timeout skipped writer shutdown and its drain.
2. A completed writer allowed close to return while an admitted caller still
   owned its voting WAITER.
3. Session cleanup replaced the original transfer IOException with a secondary
   export-close exception.
4. An export whose session constructor failed could lose its failed-close state;
   a subsequent service close then reported success.

## Ownership and shutdown

Voting shutdown now revokes the endpoint and executor first, cancels completion,
attempts every outgoing pull and incoming transfer cleanup, and still drains the
writer and admitted reply callers if a child fails. It uses `shutdown`, without
interrupting a writer in durable I/O. Writer and caller drain share the existing
request-timeout window; campaign time, retry limits and resource maxima do not
change. Timeout/interruption remains failure, and a later close must finish the
retained drain before reporting success.

WAITER reservation and caller admission are atomic with revocation. The try-with-
resources release occurs before decrementing the caller count. A writer or
admitted handler cannot declare its own drain complete: it revokes immediately,
then fails explicitly so an external closer can complete cleanup. Multiple
failures are preserved in a per-close exception chain without repeatedly adding
new failures to a child's cached exception. The first failure message remains
visible, and interruption remains set on the calling thread.

The transfer entry keeps an export until a source-session constructor actually
returns and takes ownership. If constructor/scope validation or later handling
fails, the original error remains primary and cleanup errors are suppressed.
A failed original export close is retained and not called again implicitly.
The bounded trace and parent metadata stay owned; repeated close cannot turn
that failure into successful cleanup. Other entries still get their cleanup
attempt, using the existing shared-service drain.

## Verification

Tests use the existing real installed native group, original TCP links, durable
ACCEPT, injectable clock and resource observations. They do not replace the
writer executor or transfer service. A short test-only close bound makes a held
transfer and writer timeout deterministic. Another gate holds the actual caller
after the durable writer completed; both normal and interrupted close must wait
for its WAITER release. Writer/handler self-close is rejected, and an external
close releases their remaining control resources.

Two original joining-preparation exports conditionally fail during constructor
reference acquisition or an admitted session check. Their wrappers close the
actual export then report a cleanup failure. The original IOException stays
primary, repeated close stays failed and the wrapper closes exactly once.
These are conditional error-path regressions, not storage/process-crash evidence.

A durable ACCEPT legitimately retains application buffers until journal owner
close. Assertions distinguish those original durable allocations from endpoint
CONTROL/WAITER; the fixture separately closes each original owner and requires
its complete resource budget to reach zero.

Results, failed-original reports, corrected-source tests and fresh native
physical/resource replay are recorded in the
[development receipt](phase3-evidence/voting-close-failures.json). Local evidence
is under `target/v53-voting-close-failures/`.

No public API, wire/storage format, POM, workflow, frozen timing or resource limit
changes. Whole-runtime physical maxima, all failure histories, the final-source
hosted cohort and Phase 3 closure remain OPEN. No hosted or paid-cloud execution
is claimed.
