# Actual automatic-owner lifecycle observations

Phase 3 remains **OPEN**. Final `READY`/`RESTARTING` diagnostics alone do not
prove when a session was abandoned, drained or replaced. The private automatic
owner now has an optional observer for actual start, round, readiness, typed
loss, restart, session-close/open, terminal failure, close and drain boundaries.
Existing constructors use `NONE`; there is no public callback or new decision
source. Retry counts, original deadlines, queue behavior and client mutation
replay rules are unchanged.

Observations carry the state, round number, pending count, original start and
typed loss or barrier digest at that boundary. They use the existing owner
monitor. The observer does not supply clocks or protocol results. I/O/runtime
observer failure is retained separately, stops further observation and is
reported by the test producer after node drain; it invalidates collection without
retrying or changing an admitted operation. A failed observer does not release
protocol resources early or invent successful drain.

The test-only `V53AutomaticLifecycleCapture` writes `automatic-lifecycle.json`
after all nodes close. Under the existing shared trace monitor it records the
original event index, monotonic time and per-owner ordinal. It does not insert,
renumber or reconstruct protocol events. At most 256 observations are retained;
output uses `CREATE_NEW`. The producer checks retained observation failures, so
truncation or a failed write cannot qualify as complete evidence.

`scripts.v53.automatic_lifecycle` requires exact shape, counters, ordinals,
node inventory and original event/time anchors. Its state reader checks old
session close before replacement, the unchanged original start, finite round
count and terminal drain. READY must bind an actual prior local
`ROUND_BEFORE_READY` PUBLISH_ACK; a state string or final diagnostic cannot replace
that callback. Original resource-drain receipts and empty execution/close
failure files remain required. Existing histories without this attachment retain
their earlier scope and cannot be admitted by the new lifecycle gate.

## Retained execution and remaining integration

One predeclared native three-owner execution, using an immutable source copy,
passed without retries in 98.334 seconds. It produced 24 lifecycle observations:
node-1 lost with `HIGHER_BALLOT`, closed its old session and began round two with
the original start; node-3 published the ready barrier and DATA; all three owners
drained. Twelve mutations of the lifecycle attachment require exact rejection
reasons while preserving all protocol events, wires and physical files. Portable
optimized replay passes. Seven Java observation tests cover successful restart,
observer failure at ten boundaries, terminal round exhaustion, non-replayed DATA,
close before start, bounded trace capture and retained node observation failure.

The **complete integrated history remains unqualified**. On this new schedule
node-1 loses before its local grant is created. There are only two captured
grants, rather than the four in the previous retained history, and no preinstall
source-retirement transaction. The preceding physical prefix passes, but
`competing_campaign_maintenance` currently refuses the first-install boundary
when no preceding floor transaction exists. This refusal and its original
artifact are retained; there is no rerun to obtain the older schedule.

Next, derive the no-retirement branch from its actual prefix and account for the
abandoned pre-grant discovery/attempt, then compose the new observations with
physical/network/export replay. Typed LOSS collection is not independent proof
of its cause. Full lifecycle/recovery, expiry/close faults and final-source
cohort admission stay open. The [development receipt](phase3-evidence/automatic-lifecycle.json)
distinguishes source-bound native execution, lifecycle collection, legacy replay
and the rejected integration attempt. No hosted or cloud run was dispatched.

```bash
python3 -B -m scripts.v53.automatic_lifecycle "$RAW" --qualify
```
