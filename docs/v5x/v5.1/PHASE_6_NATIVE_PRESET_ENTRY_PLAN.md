# V5.1 native full-preset entry plan

**Status:** implementation plan after the
[first successful native experiment](PHASE_6_NATIVE_EXPERIMENT_ACCEPTANCE.md).
The [owned network-fault batch](PHASE_6_OWNED_NETWORK_FAULTS.md) now implements
the first four missing guest scenarios in an offline scope. The
[complete owned failure drill](PHASE_6_OWNED_FAILURE_DRILL.md) adds the remaining
five and a source-bound twelve-cell offline aggregate accepted by PR #308 / master
CI `37837221623`. The [canonical tape batch](PHASE_6_OWNED_CANONICAL_TAPES.md) adds
all five full rich tapes, accepted through PR #309 / CI `37863567136`. The
[complete canonical aggregate](PHASE_6_OWNED_CANONICAL_AGGREGATE.md) adds
control rotation, shared seed and fifteen-cell replay, accepted through PR #310 /
CI `37887342685` attempt 2. The [native admission and execution integration](PHASE_6_NATIVE_PRESET_REVIEW.md)
now connects the reviewed allocation, exact request/session, owned algorithms, independent replay
and workflow selection. Corrected-source protected CI and actual paid qualification
remain pending. This document retains the implementation plan and acceptance boundary.

## Original gap and current candidate

The accepted native experiment initially ran four cells. This candidate adds
v3 requests for all five members, complete native failure-drill/canonical service
composition, source-bound guest sessions, independent replay and matching Action
choices. Legacy experiment records retain their original meaning. The extensions
are implemented but require protected CI and paid acceptance; an offline result
cannot establish native performance.

The existing `remote_faults` local controller has all twelve fault scenarios and
independent physical/history replay. Its direct JVM/filesystem controls are
references for the guest implementation, not evidence of native SSH execution.
The existing rich-workload shards similarly qualify local execution/replay only.

| Surface | Native experiment accepted | Required extension |
| --- | --- | --- |
| healthy, three published/candidate modes | 90 calls per mode | canonical 260 calls per mode; preserve ABBA windows and original scheduling |
| rich automatic concurrency | absent | read-heavy 120 calls and sustained 180 calls; guest-clock bursts and timing evidence |
| existing fault cells | leader-loss, maintenance, no-quorum | reuse exact scenario/history semantics in larger presets |
| partition and lag | offline guest accepted; native integration candidate | qualify isolated-old-leader, asymmetric-requests, asymmetric-responses, slow-follower through the independent CI lane |
| crash and transfer | offline guest accepted; native integration candidate | interrupted-transfer, entry-chosen, proof-quorum, group-restart |
| resource bound | offline guest accepted; native integration candidate | minority-capacity with the sealed bounded voter and real refusal |
| healthy control placement | experiment placement | rotate the control host through nodes 1/2/3 by repetition; automatic leader remains observed, never forced |
| independent aggregate | four cells | all twelve failure-drill cells; all fifteen canonical cells; complete source-bound five-member set |

Keep the [frozen workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), including
4100/20004-byte encoded document bounds for interrupted-transfer/minority-capacity,
history and trace limits, once-only mutations, and explicit unknown outcomes.
Neither an observer retry nor a replacement topology may become a workload retry.

## Implementation batches

1. **Extend the authenticated guest fault service and controller.** Implement
   bounded typed actions for the nine missing cells, preserving the existing
   command claims, retained process identities and original monotonic deadlines.
   The [partition/lag slice](PHASE_6_OWNED_NETWORK_FAULTS.md) is implemented, with crash/transfer and capacity in the
   [complete-drill batch](PHASE_6_OWNED_FAILURE_DRILL.md). Reuse
   the actual worker fault hooks; retain observed drops, force delays, exact
   durable cuts and partial transfer receipts. Do not expose arbitrary guest
   commands or manufacture damaged authority files.
2. **Qualify a complete owned failure drill locally.** Run all twelve cells
   through the real persistent guest transport on loopback SSH, with independent
   physical/history replay and the same negative evidence mutations. Collect
   every original failure. Full acceptance requires all cells in one bound set;
   individual shards may report only partial qualification.
3. **Extend the canonical owned workload.** Add full healthy windows, rich
   read-heavy/sustained guest execution and repetition-bound control placement.
   Qualify all fifteen cells, collection budgets and portable aggregate replay;
   reuse one immutable seed while retaining distinct group identities. The five
   individual tapes are accepted. Host rotation and shared-seed aggregation are
   accepted through all three protected repetitions. Native complete-preset
   acceptance remains open.
4. **Review the native preset admission and time allocation.** The
   [review implementation](PHASE_6_NATIVE_PRESET_REVIEW.md) supplies proposed clocks
   and rejects stale/mixed/over-budget remaining sequences without admitting a run. Carry a closed
   preset selection through request, package/configuration, lease, price,
   workflow, summary and independent validators. Add same-path fake failures
   for mixed presets/repetitions, duplicate commands, missing cells, expired
   approvals, provider failures, retention and cleanup. Protected CI must pass
   before any new native preset becomes dispatchable.
5. **Run the formal paid set on one final source.** Prepare fresh prices and
   exact requests, obtain the user's confirmations, then let the user trigger
   experiment, failure-drill and three canonical repetitions. The operator-authorized
   [any-order mode](PHASE_6_NATIVE_DRILL_RECOVERY.md#operator-authorized-member-order-amendment)
   allows any member to start or run next; complete-set and failed-canonical rules
   still apply. Keep all failed
   attempts and charges. Finish independent set review, cleanup/absence checks
   and append-only baseline registration before closing Phase 6.

Related cells should share a reviewable batch where practical. Commit/push/PR
execution and paid workflow triggers remain with the user. Manual cleanup is a
valid readiness path; waiting for GitHub's scheduled delivery is not a prerequisite.

## Time-budget decision before native admission

The frozen generic preparation/validation ceilings are 600 seconds each. This
successful native experiment spent 1432.606 seconds preparing and 1278.858 seconds
validating/retaining even the reduced four-cell workload. The full native presets
therefore need an explicit reviewed allocation before use. Do not silently apply
the experiment-only four-hour lease to them, or spend one cell's unused budget
on another.

First measure the additional local guest paths and inspect the native control
round-trip counts. Prefer safe savings in repeated read-only setup checks,
independent downloads and evidence validation. Preserve measured window duration,
request counts/rates, fault holds, conservative outcomes and failure thresholds.
Then propose preset-specific preparation, per-cell control, collection, retention,
cleanup and lease ceilings together with price coverage and cumulative headroom.
Any amendment must update the machine plan and independent evidence contract in
the same batch. The USD 200 ledger ceiling remains in force; reassess a fresh
complete-sequence quote instead of assuming current headroom is sufficient.

The offline archive review introduced with this plan is limited to experiment.
Its local `PASS` cannot enable a preset, prove current IAM/cleanup readiness, or
replace the new source's protected CI and exact-request admission.
