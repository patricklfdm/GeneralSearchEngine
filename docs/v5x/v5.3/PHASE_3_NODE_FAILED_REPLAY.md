# Phase 3 — replay a failed post-publication client without accepting it

The retained ACCEPT_RENAMED/halt diagnostic capture now has physical, lifecycle,
child-transcript and complete network replay. Its experiment result remains
**FAIL**, its second JVM exits 1 and successful native admission still rejects
the missing terminal close. This work does not fix the runtime exception or
close Phase 3.

## Original maintenance authority

The physical reader retains its independently derived before/after grant states.
The network reader uses those states to explain an unselected, lagging node's
post-grant retirement. It cannot obtain expected source bytes from the received
offer or treat a status hint as a governing copy.

In the retained ballot-4 transition, node 3 cannot borrow every image in node 1's
newer capsule. The original runtime first completes a packet-only probe, then
fetches a complete prefix and generation. Replay requires both transfers and
their deliveries before the governing floor. The packet-only probe provides no
application copy by itself. Exact root, identity, view, covering ancestry and
both governing majorities remain required.

The reader derives floor acquisition, source retirement, journal rotation and
floor release from the original member inventories. All 82 callbacks must occur
in order after the fresh grant and before its actual PROMISE response. Image,
member and deletion counts are derived from bytes. The complete released state
must equal the physical projection. This path permits neither generation
retirement nor a changed retention ledger; those additional paths need their own
original-backed model.

All 775 requests, 761 responses and 14 silent attempts in the retained failed
history are classified. Its 26 heartbeat samples establish observed contact
only. They supply no grant, vote or successful client response.

## Failure remains failure

`scripts.v53.node_failed_evidence` is a separate diagnostic entry point. It
requires the original producer's FAIL status, `producerPassed=false`, the first
process's exact interruption and lock observations, the second process's exit 1,
the retained exception and the exact absent-close lifecycle. Child messages
still match the corresponding lifetime's original events and snapshots.

Its output is always `status=FAIL`, even when `diagnosticReplay=PASS`; its CLI
exits 2. It cannot replace `node_current_evidence.validate`, which still requires
a successful terminal lifecycle, empty stderr and clean drain. No close,
successful client response or process drain is synthesized.

To inspect the retained original, point `ORIGINAL` at the captured run directory
containing `history/` and `process/`, and write the result outside that directory:

```bash
python3 -m scripts.v53.node_failed_evidence "$ORIGINAL" --negatives \
  --output target/v53-node-failed-diagnostic.json
```

Exit 2 is the preserved failed experiment result. Other exceptions or missing
diagnostic output mean the evidence did not pass diagnostic replay. The negative
driver validates the unchanged original first, mutates temporary copies only and
requires all 14 exact rejection reasons. It rejects missing floor/member/source
forces, reordered or duplicate deletion, missing probe/complete copies, invented
close/clean exit/producer success and a missing final child event.

## Validation and remaining work

The [receipt](phase3-evidence/node-failed-replay.json) records the new diagnostic
result, original inventories, Python tests and historical replays. The previously
qualified PROOF/SIGKILL history and seven legacy histories retain their exact
results and negative vectors. No new JVM experiment, Maven build, cloud run or
workflow dispatch is part of this batch. Production Java, POMs, workflow and
frozen timing/resource bounds are unchanged.

The original exception occurs in the endpoint's combined expired/ended/closed
guard after the last `ROUND_SLOT_COMPLETE`. Consistent storage and network
evidence does not identify which guard condition fired or explain the latency.
That runtime investigation, the remaining rename combinations, final-source
profile/process cohorts and frozen acceptance coverage remain open. Rollback
removes the additional diagnostic reader and grant-retirement callback; existing
successful admission requirements and the original failed artifacts remain.
