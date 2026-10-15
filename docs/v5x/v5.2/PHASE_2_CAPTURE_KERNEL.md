# V5.2 Phase 2: application capture and bounded requests

**Status:** Phase 2A locally verified; runtime admission/waiter integration pending.
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

## Remaining Phase 2 work

- Bounded waiter ownership sharing P permits and reserving R=min(64,P-1).
- One coalesced read dispatch with eligible FIFO and application-task fairness.
- Strict single deadlines, cancellation races, state-change rejection and safe close.
- Atomic protocol-state/application capture, fresh strong barrier binding and
  deterministic wakeup/publication/fencing tests with original failure evidence.
