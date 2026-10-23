# Phase 2: typed coordinator with compact admission

Status: locally qualified private coordinator; Phase 2 remains **OPEN**.

The private coordinator now selects the admitted transaction profile. Actual
captured application configuration, per-target codecs, original source and the
retained projection are rechecked before PREPARING and COMMITTING. It publishes
all compact admission files after the original COMMITTED decision and before any
local seal. `readInitialResult` selects that exact inventory.

Planning and both typed decision checks reserve **original completion bytes + one
compact admission per target + the existing retained projection** together. The
new `verifyAdmitted` entry adds these bytes to the read-only recheck. The original
component entry and its historical byte profile remain separate; no resource or
operation limit is increased. Tests distinguish a budget that fits the original
profile from the admitted total, accept the exact total and reject one byte less.
The latter refusal leaves existing original plans and all targets unchanged.

## Evidence

The six EMPTY/verified-backup × 3/4/5 profiles still retain one random history and
one projection across plan reopen and PREPARED recovery. Each resulting target
then crosses the actual admitted store entry, reserves a counter and produces a
fresh local grant. All 24 owners release their reservations after closing.

The independent replay explicitly selects `--admitted` and a version-2 coordinator
receipt. It derives the added bytes and exact inventory from original inputs;
16 negative variants include missing/foreign compact admission. The old default
reader still accepts the unchanged version-1 retained evidence with its exact
14 negatives. Both profiles run normally, with Python assertions disabled, and
from relocated copies. New and historical profiles must not be interchanged.

The coordinator, read-only recheck and typed revalidation suites are covered.
Actual outcomes and source/build provenance are in the
[evidence index](phase2-evidence/bootstrap-admitted-coordinator.json). The initial
physical snapshots precede the additional grant/open assertions; those assertions
are Java observations, not a separate independent replay of coordinator-to-store
runtime progress. The previous [store evidence](PHASE_2_BOOTSTRAP_STORE_ADMISSION.md)
independently replays that store's real grant/reopen bytes.

## Remaining boundary

This is private offline orchestration, not public runtime activation. Existing
`readInitialResult`/transaction resume still require initial mutable target state.
General result inspection and recovery after an already sealed node has made
legitimate progress need a separate immutable-authority path, without restoring
initial counters/logs or opening a second descriptor to a live `replica.lock`.
All-size typed coordinator halt/SIGKILL, partial-group progress recovery, maximal
lifetime and the complete physical audit remain pending. The full Phase 2 goal
and V5.2 integration are unchanged; no workflow, cloud, POM or frozen catalog edit.
