# V5.1 Phase 6C2: public 512-slot runtime integration

**Status:** implementation candidate on PR #228's accepted runtime. Local
qualification is recorded below; protected acceptance remains open. The
[component gate](PHASE_6_FULL_SIZE.md), [rich workload gates](PHASE_6_REMOTE_RICH.md)
and [twelve fault cells](PHASE_6_REMOTE_FAULTS.md) remain required.

## Execution boundary

Three separate owned JVMs open the public automatic engine using the frozen
64-document, seed-17 published V4.4 backup. Public update, strong search,
checkpoint, start and close APIs drive the schedule. Package-level hooks only
observe actual force/wire/publication events or inject declared faults; they do
not select ballots, append entries, install snapshots or return manufactured
public responses. Candidate and published controls retain isolated classpaths.

Updates cycle keys 1–64 and increment the revision once per 64-document round,
remaining in the frozen revision-0–9 rich corpus.

1. Public updates advance the actual proven log to slot 480. Halt the leader
   after receiving the remote ACCEPT acknowledgement for slot 481, before it
   consumes that acknowledgement. The disconnected update remains uncertain in
   the history. Automatic election must retain and re-propose the same chosen
   entry at a higher acceptance ballot; no application retry is submitted.
2. Restart that voter at its original sealed path. Capture a public read near
   the limit and hold its application view while isolating its node. The other
   two voters must elect, read and update through the public API. Heal the
   partition, observe the higher promise, then release the held read. Its answer
   must still equal its original captured prefix. After release, the node must recover the newer prefix by automatic rejoin or
   reactivation; either role is valid.
3. Advance to slot 500 and inspect the current leader's durably selected pair.
   Verify that its public status still reports the same READY epoch and cut, then
   stop the third voter outside that pair. Advance to 511 and perform the final
   public read at slot 512. Checkpoint, restart the retained follower, and require
   a complete production snapshot transfer and convergence of all durable cuts
   to exactly 512. Actual observations must also include two distinct retained
   generations near the limit.
4. Stop the final leader. The remaining voters perform a real campaign with a
   complete 512-slot basis. Halt at `PROMISE_QUORUM`, after production selection
   has durably chosen the pair and before installation/activation starts.
   Independently verify the selected prefix, downloaded basis and elapsed time.

A fresh activation at a fully occupied log would append slot 513. The terminal
halt is therefore an intentional boundary: this gate does not claim successful
new leadership after 512 slots. Recovery with actual public service is tested
near the limit, and complete-prefix selection/transfer is tested at the limit.

The application executor owns a captured public view. Reconstruction queued on
that executor can finish only after the read releases it. An initial development
schedule incorrectly waited for rejoin before releasing that view; its retained
failure demonstrated the queue ordering. The corrected schedule verifies fencing
and newer majority progress while held, then public recovery after release. The separate
component gate still verifies disk reclamation while its application view is
held. These checks do not add a concurrent-public-install guarantee.

## Independent acceptance

The oracle projects rich state from original forced acceptance bytes and checks
proofs, exact remote owners/receipts, selected bases, publication and sealed
retained authority using the existing physical validator. Every public operation
is bound to its original process, invocation and result. The follower stop is
bound to its owned process lifetime, the leader's original selection event and
its slot-500 publication/proof; stopping either selected voter is rejected.
Each successful read
requires its own post-invocation NO_OP, validated capture, unchanged release and
exact projected answer. The deliberately disconnected write is the only operation
allowed without a result. Known conservative recovery-read refusals stay in the
history; at most four fresh read attempts are allowed per recovery step. Mutations
are never retried. The complete history remains within the frozen eight auxiliary
read slots and 64 activation slots, and no accepted entry may exceed slot 512.

The full snapshot exchange must have contiguous 4096-byte chunks, exact image and
install acknowledgement, an observed receiver installation and at most 9600 ms
from offer to the final acknowledgement. A second conservative bound starts at
the preceding sender-side authority status probe, before image preparation and
transfer admission, and must also fit 9600 ms. Terminal PREPARE, including its complete
remote basis download, must finish within the existing 1200 ms exchange deadline.
The public runtime uses the original 1200/3600/6000/9600 ms leadership policy,
1-MiB frames, 64-MiB replica/staging limits and the frozen JVM/application bounds.
None of the rich tapes, cloud cells, rates, operation counts or workload hash changes.

Evidence retains process identities, compressed bounded observations, all public
attempts, actual final stores, loaded JARs and compiled adapter/source inventories.
Collection enforces existing member/total/part limits. Relocated inspection first
verifies the complete inventory and preserves original sealed paths; copied voters
are never opened. Positive replay precedes every negative qualification. Exact
rejection reasons are checked for changed public answers/cuts, premature replies,
invented crash success, missing generations/selection, late PREPARE, unowned reads,
changed process identity, changed mutation requests and a late complete snapshot
transfer.

Receipts identify `local-public-full-size-runtime`, `paidCloud=false` and
`fullRemoteQualification=false`. This finite local gate does not authorize cloud
execution, qualify provider lifecycle or establish a failover/throughput SLA.
Full 6C2 acceptance still requires protected CI; 6C3 runner/admission/provider
qualification remains the next mainline task.

## Commands and CI

```bash
scripts/verify-v51-phase6-full-size-runtime.sh
# With a fresh reactor package:
scripts/verify-v51-phase6-full-size-runtime.sh --skip-build
python3 -m scripts.v51.full_size_runtime_evidence PATH_TO_RAW_EVIDENCE
```

The required `v51-full-size-runtime` job runs this complete gate in parallel with
`v51-reclamation`, which retains the component gate. Both restore the same verified
build; no Maven build is added. The runtime job always uploads
`target/v51-full-size-runtime` and its build provenance for fourteen days.
[PR #229 CI 36078101942](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36078101942)
passed before the split, measuring this command at 17m46s. The
[CI split record](../../CI_V51_LANES.md#reclamation-and-full-size-runtime-split)
describes the new scheduling; revised-source CI and master acceptance remain open.
The local process schedule has a 600-second control backstop; the complete command
has a 1200-second backstop including compilation and independent portable replay.
These are local qualification budgets, not amended production/cloud deadlines.

## Local validation record

The owned execution at `target/v51-full-size-runtime/fifth` passed all 512 slots,
independent positive validation, eleven exact evidence negatives and portable
positive/negative replay of six binary collection parts. The five owned process
lifetimes covered 311.090 seconds; every process was reaped. It recorded 502
mutations, six public read barriers, four remaining activation NO_OP slots, and
final application sequence 506 on the exact 512-slot projection. The chosen slot
481 was re-proposed without replaying the public update; the held read used cut
485. All three final durable prefixes were exactly 512.

The complete image was 182452 bytes. Its observed offer/ACK span was 0.779 seconds;
the additional earlier-probe deadline check also passed. The terminal full-basis
PREPARE took 0.770 seconds and the entire observed terminal campaign took 0.822
seconds. Largest final retained authority was 2074168 bytes. These are local
observations, not changed limits or an SLA.

All 460 V5.1 Python tests and 23 CI topology tests passed, including ten new
boundary tests. YAML, 129 shell blocks, the documentation contract and changed
local links were checked. The final oracle separately replayed the unchanged
binary collection, including its conservative transfer-start check. Supplementary
replay receipts and validator hashes are retained under
`target/v51-full-size-runtime`. Production Java/POM files are unchanged; no full
Maven reactor or paid cloud execution was repeated in this batch. Protected CI
must still build/test the candidate and run the new required gate.

Development workspaces remain retained. Besides the held-view ordering correction,
the controller initially required the released node to remain a follower, although
reactivation is legal. An independent replay also rejected per-call increasing
revisions outside the frozen corpus; revisions now increase per 64-document
round, with all 511 possible updates checked. The invalid/cancelled runs do not
contribute to the successful receipt.


## Slot-500 follower-stop correction

[PR CI 36082534323](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36082534323/job/107908819094)
failed after reaching slot 500. The retained original selection at epoch 13 paired
leader node-3 with node-1. The controller chose the first non-leader by node order,
stopped node-1, then immediately required the next update to succeed. That update
returned `INDETERMINATE / QUORUM_UNAVAILABLE`. The trace retains node-1's actual
slot-500 ACCEPT/PROOF acknowledgements, its clean close, and the failed next call.
This was an invalid assumption that either follower could be removed without
interrupting the selected pair.

The controller now observes the existing selection and stops the remaining third
voter. It never changes the production selection or retries the mutation. The
independent validator ties this choice to the original selection, public slot-500
proof and owned stop lifetime. Stale epochs, changed leadership/cuts and invalid
pairs fail the controller before it injects the stop. All later writes, the full
512-slot transfer, terminal selection and existing eleven evidence negatives
remain required under the original limits.

The same run's [Compatibility failure](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36082534323/job/107907411928)
occurred while Maven Central returned HTTP 403 for the enforcer plugin POM, before
API comparison. Compatibility commands and checks remain unchanged. Local failure
diagnosis and validation are retained under `target/v51-full-size-ci-fix/`; corrected
source still requires protected CI and master acceptance.


Correction validation passed all 464 V5.1 Python tests, including fourteen full-size
unit tests. Replacing the new choice with the original ordinal rule fails four
assertions across the possible selected pairs. The complete gate at
`target/v51-full-size-runtime/run.YA7Iti/evidence` passed its independent validator,
eleven exact negatives, six-part collection and relocated positive/negative replay.
The observed pair was again node-3/node-1, and node-2 was stopped. All five processes
were reaped after a 422.302-second owned execution; 502 updates, six read barriers,
slot-481 reproposal and all three durable cuts at 512 passed. Full transfer took
0.934 seconds and terminal PREPARE took 0.851 seconds under the original limits.

The unchanged Compatibility API command also passed in an isolated checkout of
`e62252b97ccfb639e76ea9dbb40803060554aa25` with a fresh Maven repository: 549 Java
tests and thirteen published API comparisons, in 1m24s. These local results do not
establish recovery of GitHub's download path or replace corrected-source CI.
