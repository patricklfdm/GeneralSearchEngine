# V5.2 Phase 6L full M01 controller

**Status:** controller and local integration validation passed. Complete
physical M01 admission, M02–M04 schedules and the machine execution freeze remain
open. There is no formal measurement result or newly enabled execution CLI here.

## Exact preparation and offered work

The separate M01 preparation profile binds one of the five existing modes and a
repetition in 1–3. It uses the same copied artifacts, independently compiled public
consumers, observer, real V4.4 seed and source/build binding as the short gate. It
does not acquire the short gate's three-update setup or three-second marker profile.
The two preparation profiles are mutually exclusive.

The controller selects the one observed ready leader, makes exactly one initial
strong read and confirms sequence one on the declared read/write targets. Read
targeting remains the initial leader for strong modes and the highest-ordinal
initial follower for stale/minimum. Minimum carries the original setup token.
No business update runs during preparation.

All 1,980 original requests run on the unchanged 180-second clock: 60 seconds
warmup and 120 seconds measurement. The three asynchronous marks occur at zero,
60 and 180 seconds on all three consumers. Updates and reads keep their frozen
targets even if an operation fails or leadership changes. Neither completed
operations nor control markers pace the next original due time.

Activation and initial-publication observation each use the existing 40-second
integration bound. Original futures share one drain after dispatch; the original
35-second value was revised to 125 seconds in [Phase 6V](PHASE_6_M01_DRAIN.md)
to account for queued synchronous consumers. There is no fresh drain deadline per
operation, cancellation or business retry. The current value is bound by the
[complete execution freeze](PHASE_6_MACHINE_COHORT.md).

## Failure retention and qualification boundary

The controller saves the dispatch receipt before draining, then saves every
observed response and the undispatched suffix. Setup/dispatch/validation errors
retain a failed controller receipt and the last scenario stage. The process owner
attempts to stop every started consumer, saves all histories and process identities,
and records close errors separately without replacing an earlier execution error.

A completed controller returns `OBSERVED`, never qualified PASS. Its separate
execution receipt records stopped processes. Physical quorum/force/publication,
actual query results, ownership, resource windows, complete-set admission and
portable negatives must all pass before a measurement can be accepted. No short
smoke or virtual-clock run can substitute for the full measured history.

## Validation

Seven deterministic tests cover all 15 mode/repetition combinations with the
complete program and original unresolved futures. They also cover a retained
business rejection, partial dispatch, partial marker failure, invalid setup,
activation failure, invalid/mixed profiles, and simultaneous execution/close
failures. Their virtual consumers establish controller behavior only.

Real-artifact preparation passed against both published V5.1 and the candidate,
without starting a measured window. Both unchanged short gates passed original
and relocated physical/query/lifecycle/resource replay: 22 reads, six updates and
76 negative rejections. All 145 V5.2 Python tests passed, along with CI inventory,
documentation contract, changed local links, shell syntax and whitespace checks.
No new reactor or hosted qualification is claimed. Logs, bindings and summaries
are retained at `target/v52-m01-controller`.
Continue under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md);
formal M01–M04 runs still follow the complete machine freeze.
