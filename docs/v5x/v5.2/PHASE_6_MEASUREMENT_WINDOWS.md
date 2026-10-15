# V5.2 Phase 6J full offered-window accounting

**Status:** local validation passed. The full M01 window ledger is implemented;
the full execution entry, resource-window binding, M02–M04 schedules and complete
machine execution freeze remain pending. No formal measured history ran here.

## Share successful cut validation without hiding failures

`measurement_reads.validate` contains the existing per-process publication/capture,
fresh strong barrier, token/generation, released view, callback and actual V4.4
query-result checks. Both the strict short smoke and the later measured path use
that implementation. It consumes the complete business-call ledger but creates
query cuts/timings only for successful reads. Failed calls remain in the separately
validated [complete lifecycle ledger](PHASE_6_MEASUREMENT_HISTORY.md).

The short smoke still requires all 14 business calls to succeed. The shared helper
does not relax that qualification or turn a historically failed smoke into PASS.
It also does not independently prove authority: general physical replay, the
[forced-generation profile](PHASE_6_MEASUREMENT_PUBLICATION.md), chosen application
projection and complete lifecycle validation remain required.

## Account for the complete original M01 program

`measurement_window.validate` requires the exact 1,980-call offered program over
180 seconds, with no shortened observation or missing response. It preserves the
60-second warmup / 120-second measurement split, all 600/1,200 reads, all 60/120
updates and each original due time. The read target is the original leader for
strong modes and the highest-ordinal original follower for stale/minimum. Updates
keep the original leader. Minimum reads carry the unchanged initial strong token.

Exactly one separately labelled successful setup read may precede the program.
Any extra business call, hidden setup call, retry or substituted target rejects.
Repetition is an integer in 1–3. This helper does not by itself prove that all three
repetitions or five modes exist; complete-set admission is separate.

Window statistics group calls by their original offered window, not the window
where their response happened to arrive. Late responses are retained and counted
explicitly. All outcomes contribute to offer delay, submit duration, due-to-response,
offer-to-response, API duration and client-queue latency distributions. Percentiles
use nearest rank; empty distributions have null values, never fabricated zeroes.
The original per-call timing samples remain available in history and offered-load
evidence. Controller and worker clock differences are never subtracted.

Nonvacuity requires at least one successful read of each of the five query families
and one successful update in each window. Every rejection is still reported. These
are coverage requirements, not an availability, speedup or latency SLA; the complete
machine plan must bind them before execution. Fatal or undeclared failures are
handled by the lifecycle validator, and chosen/rejected mutation effects by the
independent projector.

## Validation boundaries

Seven deterministic window tests exercise all five modes using a virtual clock and
the full original call list. They cover failure-tail retention, late completion,
missing successful coverage, hidden retries, retargeting, changed tokens and
shortened/changed windows. They are accounting tests, not measured performance.

The shared successful-cut component is checked against all ten existing original
and relocated `run.IlyS4r` inputs, requiring complete returned results and every
negative result to remain equal. The retained failed `run.MgK7WG` control is also
replayed: its three actual successful reads match the real V4.4 query control; its
eight QUORUM_UNAVAILABLE rejections do not become query cuts or success timings.
The original qualification stays FAIL.

All 132 V5.2 Python tests pass. Ten unchanged original/relocated physical and
query replays preserve every complete result, including all 190 negative checks;
replay took 167.706 seconds. CI inventory, documentation contract, changed
local links, shell syntax and whitespace checks pass. No fresh reactor, hosted CI
or measured performance result is claimed.

Local logs, exact replay results and original failures remain at
`target/v52-measurement-window`. Next finish resource-window observations and the
full execution/fault entry, then freeze the exact machine plan before formal runs
under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
