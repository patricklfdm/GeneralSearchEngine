# V5.1 owned partitions and slow follower

**Status:** implementation candidate for the first full-preset extension batch.
This adds four locally qualified guest scenarios to the persistent SSH path. It
does not admit new paid presets or claim complete failure-drill qualification.

| Scenario | Fixed injection | Independent acceptance |
| --- | --- | --- |
| isolated-old-leader | Bidirectional old-leader request isolation for 15 seconds | Original minority write/read refusals; healthy-majority progress during isolation; durable higher-promise fencing and retained rejoin |
| asymmetric-requests | Old leader's `BEFORE_REQUEST_WRITE` edges for 15 seconds | Actual request drops with decoded old-leader sender; reverse-direction replies; progress and post-heal rejoin |
| asymmetric-responses | Old leader's `AFTER_RESPONSE_READ` edges for 15 seconds | Original target call, actual peer execution before lost replies, reverse traffic, conservative outcome and post-heal rejoin |
| slow-follower | Selected peer's ACCEPT/PROOF force delay, 1500 ms, enabled for 15 seconds | Original selected pair, matching begin/end force observations and durations, original lag observations, healthy progress and rejoin |

The first three cells retain their frozen 120-second limits; slow-follower keeps
180 seconds. The shared progress ceiling remains 60 seconds, with at most four
fresh write/read pairs and four final read attempts inside the 24-call cap.
Controllers and guests each retain their own monotonic intervals; cross-host
clock values are never compared. The 17-second guest watchdog releases a stuck
injection but makes the evidence invalid. It cannot replace the controller's
observed 15-second hold and original heal receipts.

## Closed guest actions

`guest_fault_network` derives all network rules from the configured case and a
member name. No request carries a duration, executable, path or arbitrary rule.
A durable injection claim precedes changing the fault file; uncertain responses
cannot rearm a fault. Slow-force injection can target only the receiving guest.
Read-only observation returns original selected-pair/force events. Ordinary public
calls retain their original consumed intent IDs and conservative outcomes.

Controller commands are serialized per guest, including receipt observation, so
the heal timer cannot collide with a status request at the guest's single command
executor. Different guests remain independent. Waiting consumes the original
deadline; a lost reply never authorizes resubmission. This also preserves disjoint
controller command intervals required by portable replay.

The controller reserves the affected guests' command slots at hold second 12.
Existing commands finish observing their original receipts; later polls wait on
their original deadlines. Once all slots are available, the controller waits until
hold second 15 and submits one heal per affected guest in parallel. Ordinary
admission resumes after those original heal observations finish. Unaffected guests
remain independent. Failure to reserve by second 15 fails the cell promptly;
shutdown and evidence collection remain available. No command is replayed and the
15-second hold, 17-second watchdog and all cell limits remain unchanged.

The asymmetric controller may use the old leader again only after the heal has
completed on every guest. Isolation must instead show surviving-majority progress
while the old leader remains disconnected. All three voters must subsequently
reach the proven floor, and the last public operation is a successful strong read.
Uncertain commands, cleanup failures, missing samples and late operations remain
failures, with their original evidence retained.

## Qualification and CI

The separate `owned-network-faults` scope runs four fresh groups on the real guest
service and persistent SSH transport. It reuses per-guest public EMPTY bootstrap,
once-only package delivery, native worker processes and complete binary collection.
The qualifier deliberately loses every original workload submission reply, then
observes the same durable command rather than resubmitting it.

```bash
python3.11 -m scripts.v51.guest_owned_qualification \
  target/v51-owned-network-faults --bundle target/v51-network-package \
  --source "$(git rev-parse HEAD)" --network-faults --allow-sudo-namespace
```

The package must first be produced by `cloud_bundle` from the exact checkout and
verified reactor build. `--fault-local` can replace `--allow-sudo-namespace` for
separate local paths, with that weaker filesystem boundary explicitly recorded.
Neither qualification mode writes a physical block device or accesses GCP.

`guest_fault_evidence` checks all original guest/controller receipts, JVM identities,
sealed configuration, actual authority/wire/force bytes, complete public history
and final durable floors. The network slice adds missing injection, reversed
direction, missing reverse traffic, missing fencing/force observations and early
release mutations to the existing proof/history/rejoin negatives. It requires
actual fault observations within each guest's hold and reverse traffic during the
asymmetric hold. An operation already reading the fault file may log after removal;
every such observation still needs the correct decoded direction or full force
duration. Moving all observations outside the hold is rejected. A partial case
list cannot close the four-cell aggregate; full remote qualification stays false.

The independent required CI job `V5.1 owned network faults (no GCP)` restores this
run's exact build artifact, constructs its own package and runs all four cells in
isolated mount views. It retains original evidence on success or failure and runs
in parallel with the existing owned experiment. All previous gates remain intact;
docs-only routing and the stable `Required` check include the new lane.

### Local validation

`target/v51-owned-network-final/qualification/receipt.json` records all four
cells passing complete physical/history replay, with 33 public calls, 45 rejected
evidence mutations, twelve guest services and 225 original submission replies
deliberately lost and recovered by observation. All processes were reaped and the
modeled lease released, with no cleanup errors. Cell execution times were
50.779 / 38.804 / 37.334 / 32.859 seconds in the table's order.

This host used `--fault-local`: real SSH/JVMs and separate local directories,
modeled provider/volumes, no independent mount-view claim. Protected CI must still
qualify its isolated-mount path. The 236 related Python tests passed, including
serialization, unchanged deadlines, failure release and unchanged native scope.
The original successful native archive was independently replayed again with the
shared validators; its four cells and 42 negative results still match exactly.

The first development attempt remains at
`target/v51-owned-network-dev/qualification-1`. Its response-loss scenario
overlapped heal/status submissions at one guest, and the observer correctly refused
to replay a command whose lost BUSY reply left no durable claim. The per-guest
admission above corrects that controller error. The same attempt's negative
checks exposed a missing decoded-direction check for bidirectional isolation;
the validator now checks every drop's sender, recipient and barrier.

The initial complete reactor passed 917 tests with four existing skips. A refreshed
build later failed one unchanged `V50ReadyTest` COMMIT_PROOF case; its complete
15-test suite passed one isolated rerun. Original failure XML/logs remain under
`target/v51-owned-network-final/failed-build-reports` and `maven.log`. This does
not establish the timing failure's cause or a runtime fix. Protected-source CI
remains required for the combined batch.

### Post-merge correction: reserve the heal before its deadline

PR #305 merged at `03e361c12265516ddabb43c5660f6ad0c68d9fd9`. Both attempts of
master CI `37738421960` failed this lane, although the PR's second attempt passed.
All four cells executed and cleaned up; independent replay rejected the guest
hold/watchdog evidence. In attempt 1, asymmetric-request node 3 and
asymmetric-response node 1 reached their watchdogs. Attempt 2 repeated the latter.

The controller requested heal after 15 seconds, then waited 0.761–1.162 seconds
behind an in-flight status observation. The heal command itself took another
1.156–1.336 seconds. Guest holds reached 17.0007–17.0023 seconds with
`watchdog=true`. Original archives and measured intervals are retained under
`target/v51-network-ci-review`; no failed receipt is reclassified as passing.

Early reservation removes that command-queue delay from the release path while
preserving the original command/receipt serialization and independent watchdog.
Regression tests cover an in-flight observation, a waiting poll, unrelated guests,
partial reservation timeout, cancelled holds, uncertain heal results, original
deadlines and the 12/15-second schedule. Errors now include the failing case,
node, observed hold and watchdog flag, and the CI qualifier reports nested workload
validation errors alongside controller errors.

The correction's local build, four-cell qualification and regression receipts are
retained under `target/v51-network-heal-admission`. Corrected-source protected CI
is still required. Reservation cannot eliminate arbitrary host/SSH stalls: a late
release or watchdog intervention must still fail independent replay. The original
native experiment and the remaining preset implementation boundary are unchanged.

## Next boundary

The original three experiment fault cells and native four-cell preset are
unchanged. New network cases are rejected by the native guest configuration and
native owned-services factory until the larger preset's timing and admission are
reviewed. This local slice cannot upgrade an experiment lease or receipt.

Next implement interrupted-transfer, entry-chosen, proof-quorum, group-restart and
minority-capacity, then qualify the full twelve-cell guest aggregate. Canonical
healthy/concurrent schedules, repetition placement and the final same-source
five-member native set remain governed by the
[preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).
