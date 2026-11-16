# Remaining ordinary families: original failure review

Reviewed 2026-11-16 UTC against development base `659377b3`. The selected failed
originals remain [node-renames 43123631252](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123631252)
and [learner-histories 43123639693](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123639693),
attempt 1, source `defd80d258845a4965fb1a51d9073f5cd8c8a409`.
They are failures, not scheduling outages or accepted evidence. This correction
does not close Phase 3 or replace the final-source cohort requirement.

## Findings from original bytes

Downloaded five diagnostic archives and three complete original archives.
Unmodified ZIPs, unpacked inputs and their SHA-256 inventory are retained at
`target/v53-remaining-families-20261116/`. Original Maven/JUnit output identifies:

* Both ACCEPT rename cases exhausted the 180-second original service deadline
  during the second leader lifetime. The SIGKILL case reached carried DATA,
  recovery BARRIER and retention-reconciliation BARRIER, then failed in the final
  DATA slot. Observation-pipe timing was much smaller than the service interval.
* Both PROOF rename cases failed with `FileAlreadyExistsException: applied-3`.
  The SIGKILL original shows another installed campaign retrying index 3 before
  publication, causing the test observer to reuse its index-only directory name.
  It does not establish a duplicated committed DATA operation.
* Alternating learner slots reached revisions 4, 5 and 6, then exhausted the
  shared 900-second round deadline in `MembershipGenerationMaintenance.run` /
  `MembershipSourcePull.fetchGeneration`, entered by retention reconciliation
  before the next PREPARE. The exception alone does not prove a transport outage.

The original shared code does substantial exact-copy verification, filesystem
identity checking, generation retirement and physical observation. A local
Temurin 21.0.12 diagnostic run records JFR and thread dumps separately. Those
WSL observations are not hosted performance measurements, nor evidence that
production recovery is fast enough. No native-checking shortcut is introduced.

## Narrow correction

The node observer now preserves repeated APPLIED/PUBLISHED observations as
`applied-3-repeat-2` etc. It never overwrites or skips an earlier physical copy.
The independent reader still requires the declared complete trajectory; an extra
snapshot/campaign cannot receive a PASS merely because capture now succeeds.
A deterministic hook regression covers repeated observations, and a Python
negative verifies rejection of an added snapshot.

The complete rename qualification uses the already established control exchange
profile: 30-second request timeout and its derived automatic leadership policy.
This also means an initial 90–150-second election wait. Each leader service has
one finite 600-second budget covering election, recovery, reconciliation and
the client call; automatic retries keep the original start. Parent wait margins
follow that declared profile. The exact producer budget in the physical reader
changes with it. Other process cuts retain their 180-second/default profile.

Only the six-revision alternating learner fixture increases its round budget
from 900 to 3,600 seconds. The round retains its original start through all six
revisions, cleanup and CANCEL; it is not recreated per cycle. Each separate
learner transfer still has its own original finite pull deadline, as before.
The fixture and independent reader require the new exact budget. Three-revision
fixtures and the retained-cancellation experiment keep their existing budgets.

These are **qualification configuration changes**, not fixes to production
timing defaults or a recovery SLA. They give the expanded instrumented histories
room to complete while preserving six revisions, exact original ownership,
negative tests and no original-run retry. No runtime Java, wire format, resource
capacity, retry count, Required workflow or paid experiment changes.

## Verification and remaining gates

All 4,743 V5.3 Python tests pass, including rejecting a changed declared budget,
missing cycle, unrelated invalid original and extra snapshot. Sixteen Java
observation/diagnostic tests pass under the pinned Temurin toolchain in a
separate build directory. The new read-only large-host probe and its tests also
pass; this WSL host remains correctly BLOCKED for large admission.

The local original 900-second learner diagnostic failed at 905.046 seconds with
`slot driver original deadline` (revision 5); JFR instrumentation and WSL make
this a diagnostic observation, not a comparable hosted benchmark. Its originals
are retained. The corrected local proof-rename/SIGKILL history passed in
440.059 seconds. Its independent replay passed all three campaigns, five
published slots and all 34 exact evidence negatives. The snapshot regression
also fails against the original hook implementation and passes after correction.
The two new-source hosted family runs remain required before calling these
families resolved.
Increasing a fixture budget alone cannot establish that result. Any newly
observed extra campaign or integrity failure remains a new retained failure,
not an excuse for an automatic original rerun.

Large-runner deployment and the four default-branch registration entries remain
unexecuted; see [the prepared GCP runbook](PHASE_3_GCP_RUNNER_RUNBOOK.md).

## November 16 corrected-source results and learner replay

Both follow-ups use `b7b378a61ca188919bb12ed04ecf7fe46f629f80`, attempt 1.
[Node renames 43803439569](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43803439569)
passes all four originals, four independent replays and the aggregate (ten jobs
including preparation). No further rename run is selected for this reader fix.
[Learner histories 43803439571](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43803439571)
passes both original executions and retained-cancellation replay, but alternating
replay rejects `learner cycles native failures`; its aggregate also fails.

The unchanged alternating ZIP, SHA-256
`337b537fedbe1cf5cffec9b50031594f2b0ea9c3798538954adfa698ceb5adf0`,
contains all six revisions. Its 48 failures are 16 distinct
`FUTURE_RETENTION_INTENT` requests to `node-3`, each attempted three times.
That voter remains at its original bootstrap promise and does not install the
two-voter campaign. The fence's equality guard raises
`higher ballot observed; fresh campaign required`: this shared error text does
not prove the receiver observed a strictly higher ballot. Original node-three
files stay unchanged throughout the independently reconstructed history.

The existing native-dispatch and retained-cancellation readers already classify
such bounded nonselected-voter refusals. The six-revision reader's unconditional
empty-failure-list requirement was inconsistent with this fixture and protocol.
The correction is Python-only. It derives all sixteen original recording
intents and selected-peer ACKs from the physical replay, binds wire root/view,
ballot, identities, trace, sequence, certificate, endpoints, ledger revision and
digest, and requires matching response events. Each refused request must hash
to the exact same recording with recipient `node-3` and sequence 3. Only the
existing exception type/message, that voter and kind, and at most three attempts
per request (48 total) are admitted. Refusals never count as acknowledgements.
Other errors, forged requests, changed ACKs and extra retries remain failures.

The old reader reproduces the failure on the retained original. The repaired
reader replays the same unchanged bytes successfully: six revisions, 186 learner
exchanges and 25 physical snapshots. Seven focused regression tests cover
refusal binding, successful recording evidence, finite retries and foreign
authority. Five additional original-evidence mutations raise the alternating
negative count to 17 and the complete pair to 79. All 17 mutations of the retained
original are rejected for their exact expected reasons; all 68 focused Python
reader/cohort/hosted tests pass. Validation and original ZIP
are retained under `target/v53-retention-readiness-fix/` and
`target/v53-action-review-b7b378a6/`.

The complete two-history workflow will run on the new source/reader identity;
its exact-attempt aggregate cannot reuse the previous cancellation receipt.
This local retained-original replay is not a new hosted PASS. No production
Java, timing/resource limit, workload, retry policy or workflow is changed, and
large/paid execution remains unstarted.
