# V5.2 measurement failure corrections — 2026-10-16

Full M01–M04 acceptance remains open. These repairs preserve failed evidence and
require a fresh source/build/contract freeze before another qualifying cohort.

## Collected failures

Hosted source `e962348d0181e6f6c500aa6940227444d7cc0566`,
[run 38875654052, attempt 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38875654052):

| Original failure | Evidence and correction |
| --- | --- |
| `candidate-explicit-strong-r1`: incomplete idle ledger | The consumer recorded `CLIENT_IDLE` with one settling read and 63 free permits. The original submitted barrier released that ownership about 34 ms later. Wait for real admission/read ownership to drain after all response callbacks, then record idle. A 20-second observer bound fails on leaks; no business operation is retried. |
| `candidate-explicit-strong-r3`: missing measured-window query coverage | A public write spent most of its deadline in the ordered queue, then was submitted and proven. Public timeout cancelled the underlying protocol future, abandoning leadership at 32.652 seconds. Subsequent reads to the frozen leader failed. Preserve the caller's timeout classification while the already-submitted write/legacy read barrier settles under its original runtime deadline. Do not retarget the workload or hide failed calls. |
| `m02-above-5000`: missing successful query coverage | The selected voting pair was nodes 1/2, but the controller routed all 30 waits to passive node 3. That voter caught up through snapshot recovery and correctly returned `NOT_READY` to every uncaptured waiter. Freeze the actual selected voting follower for M02, verified against retained selected-basis bytes; preserve all calls, wait times, release delay and success coverage. |

The three corresponding downloaded replay jobs rejected incomplete producer
receipts (`hosted producer receipt identity/completion`). Those are downstream
failures, not three additional replay defects. Partial producer evidence must
continue to be rejected.

Local freeze `a40c5108aa9463a4f526bd3547b09518a2d49d83`, run
`run-20261016T074242Z-3935902`, stopped at `candidate-legacy-strong-r3`:

- The unchanged positive history was valid, but the M01 negative driver required
  a `SELECTOR_BEFORE_ACK` event. A healthy history can complete without installing
  a snapshot, so that target is not guaranteed.
- Replace this M01 negative with removal of a mandatory read capture. Actual
  snapshot/generation validation is unchanged, and M02/M04 retain their missing
  generation-byte negatives. M01 case counts remain 14/18/19 by mode; all 439
  cohort negatives still require exact case/status/reason equality.
- Replaying this original local history with the corrected validator passes all
  14 negatives in 344.447 seconds. This is diagnostic replay of the old artifact,
  not qualification of the new runtime or a new source cohort.

## Contract boundaries

M01 keeps its initial leader/follower targets, 60-second warmup, 120-second
measurement and 10 reads/1 update per second. The M02 program already names a
`selected-follower`; the controller now binds that selection to the actual voting
pair instead of choosing the highest ordinal passive follower. Its new profile
and exact negative definitions require a new execution freeze.

Public deadlines and result classification remain unchanged. A timed-out submitted
write stays `INDETERMINATE`; it is not called successful or retried. The runtime's
single-submission permit and protocol deadline continue to bound the outstanding
operation. Queue cancellation before submission still removes the queued call.
The same rule applies to a submitted legacy strong-read NO_OP; no read callback is
started after the public barrier wait has timed out.

Consumer shutdown observes ownership for at most 20 seconds, then uses the existing
bounded close policy. Process-exit observation allows 55 seconds for those phases.
Both bounds are part of the next machine/hosted contract. Neither extends any
measured request deadline or offered window.

## Verification and next run

- A new real TCP public regression fails on the original mutation implementation:
  the leader becomes `UNAVAILABLE` after the client deadline. The repaired write
  and legacy-read cases both preserve the original epoch and publish the proven
  operation, followed by another successful public write.
- Related public runtime/read/lifecycle tests pass: 29 tests, no failures/errors.
- Controller tests cover selection excluding the highest ordinal follower, bad
  masks, missing or forged selection evidence, and unchanged original call counts.
- Consumer shutdown probes cover late barrier release, leaked permits, partial
  diagnostic counters and interruption, against both published and candidate APIs.
- Fresh M02 above-floor 1000 ms and 5000 ms histories each pass all 30 original
  waiters, four updates, independent physical replay and all 15 exact negatives.
- A fresh complete candidate explicit-strong M01 repetition 3 passes its original
  180-second workload, physical/public/query/resource validation and all 18
  negatives. Capacity/deadline outcomes remain in the original ledger; PASS does
  not mean every offered call succeeded or establish a performance SLA.
- All 261 experiment-worktree V5.2 Python tests, 292 adapter tests and 22 local
  acceptance-tool tests pass. Shutdown probes pass 14 checks against each of the
  two API families. These targeted results do not substitute for a new complete
  28-history source/build-bound cohort.
- The pending pre-cloud suite in the separate adapter worktree is derived again
  from the corrected M02 target and M01 negatives. Its exact digest changes; old
  local freezes, histories, selections and receipts are not rewritten.

Raw GitHub logs, artifact metadata, original failures, local diagnostic replay and
fresh targeted qualification are retained under the experiment worktree's
`target/v52-hosted-repair/`. Old cohort receipts and histories are unchanged.
