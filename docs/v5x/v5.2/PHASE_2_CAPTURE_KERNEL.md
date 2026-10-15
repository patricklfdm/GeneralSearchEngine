# V5.2 Phase 2: application capture and bounded requests

**Status:** Phase 2A/2B implemented locally; runtime waiter integration pending.
Development follows the [authorized local sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
The public explicit read method remains the disabled Phase 1 default. No hosted
acceptance or public follower-read qualification is claimed.

## 2A: publication identity and scoped view

`AutomaticApplication` now retains the manifest validated during opening and
captures its group/history/embedded digest together with the current published
index, application sequence and process-local materialization generation. Private
staging/reconstruction does not change that cut. A control-only publication moves
the log position without replacing the live materialization or advancing sequence.

The internal view exposes exactly the seven declared methods. It checks the
callback thread and active lifetime before touching the core engine, drops the
engine reference on every callback exit, preserves callback throwables and allows
nullable return values. A cut must still match before its callback begins. The
runtime must call capture and callback in one application-worker turn, with state
validation under the protocol monitor and callback execution outside it; that
connection and bounded dispatch are the next part of Phase 2.

Local verification used actual store ACCEPT/PROOF records and application rebuilds:
unpublished accepted/proven/reconstructed data remains invisible; publication
changes documents and sequence; NO_OP advances index only. Every escaped and
cross-thread view method rejects before query validation. All three identity
components are compared, with no narrowing of a supplied long index.

- Four application-cut regressions plus six token/API checks: 10 passed.
- Existing real-socket automatic runtime suite: six passed, including election,
  retained recovery, business rejection, transport contention and cooperative close.
- Logs: `target/v52-capture-kernel/application-tests.log` and
  `target/v52-capture-kernel/inherited-runtime-tests.log`.
- Local Ubuntu JDK 21; pinned hosted toolchain qualification remains deferred.

This is an internal kernel result, not completion of S01–S30 or the physical
three-process oracle. No authority/wire records, token format, core query semantics
or published fixture hashes changed.

## 2B: bounded ownership and application scheduling

The application executor still has one worker and four ordinary queued tasks.
It adds one coalesced explicit-read turn without consuming those ordinary slots.
When both queues have work it alternates the two classes; within the ordinary
queue it preserves existing FIFO. Shutdown drains already admitted work and
never interrupts a cooperative callback during normal close.

The request kernel accepts at most R=min(64,P-1) reads and shares the existing P
admission permits. Behind waiters queue no application work. Publication and
registration use the same monitor and registration rechecks eligibility. Ready
requests are FIFO; unsatisfied older requests do not block ready reads. The
actual capture rechecks the cut and strict deadline, independent of readiness
hints. One deadline alarm is cancelled at capture or terminal rejection.

Cancellation cannot release a captured callback's permit. Completion handlers
execute outside the protocol monitor, and both callback work and cancellation
handlers must return before ownership is released. Timed-out/cancelled strong
requests also retain accounting until their outstanding fresh-barrier work
settles. This kernel does not create or retry a barrier itself.

Deterministic tests cover all 64 occupied waiters, the reserved legacy slot,
eligible FIFO, registration/publication ordering, deadline equality, zero wait,
state rejection, cancellation before/after capture, active-close cooperation,
completion-handler reentrancy, barrier ownership, original callback failures and
typed dispatch refusal. These use an explicit clock and scheduler; they do not
claim to be public process evidence. The first test compile failed due to a
generic type inference in a test; that original log is retained. Corrected checks
are recorded under `target/v52-capture-kernel/queue-tests-3.log`.

The application-worker change also passed 23 tests comprising three deterministic
worker tests, six original internal runtime tests and fourteen public runtime
tests (`worker-tests.log`). Public `read` is still disabled. The queue will be
bound to verified runtime state/publication in 2C before public enablement.

## Remaining Phase 2 work

- Atomic protocol-state/application capture, fresh strong barrier binding and
  deterministic wakeup/publication/fencing tests with original failure evidence.
- Integrate the kernel with real publication/state transitions and runtime close;
  preserve the disabled public default until Phase 3.
