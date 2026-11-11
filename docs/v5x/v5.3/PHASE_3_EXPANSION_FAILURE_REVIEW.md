# Phase 3 expanded hosted run failure review

Status: corrections under local validation; final-source qualification and
Phase 3 remain **OPEN**. Initial observation: 2026-11-10 UTC; Joining completion
and follow-up inspection: 2026-11-11 UTC.

## Frozen execution and retained failures

The twelve runs below used source
`5217a5569ee457f29e01dbfee8d0ae95ee7d15de`, attempt 1. Local corrections after
that source cannot change their conclusions. The earlier profiles and
required-four runs (`42699337007`, `42699339465`) passed, but do not qualify
these twelve expansion families.

| Family | Run | Observed result and failure scope |
| --- | --- | --- |
| Joining reply loss | [42716178511](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716178511) | All three originals passed; all three independent replays failed. |
| Remove processes | [42716178420](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716178420) | Success, 106 jobs. |
| Node renames | [42716178254](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716178254) | All four originals failed; request/activation deadlines and a duplicate snapshot after another campaign need further diagnosis. |
| Joining processes | [42716178947](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716178947) | Completed: 119 original groups passed, group 047 lost runner communication. Replay: 59 groups passed, 60 retained failed receipts, group 047 lacked originals. Aggregate correctly failed. |
| Learner histories | [42716179123](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716179123) | Alternating-slot original failed; retained cancellation passed. |
| Transfer histories | [42716179974](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716179974) | Success, six jobs. |
| Round histories | [42716180030](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716180030) | Slot-accept original failed; six other originals passed. |
| Carried DATA histories | [42716180961](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716180961) | Three of twelve originals failed. |
| Carried transition histories | [42716180316](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716180316) | All sixteen originals passed; eleven independent replays failed. |
| Automatic histories | [42716179899](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716179899) | Competition and restart originals failed; reply-revocation original passed but its replay failed. |
| Joint floor processes | [42716180666](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716180666) | All 32 originals passed; nine independent replays failed. |
| Capacity completion | [42716181225](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716181225) | Success, three jobs. |

Joining group 047 has an annotation that the runner stopped communicating.
That annotation alone does not distinguish runner infrastructure failure from
resource exhaustion or a process problem. Its original remains failed. No
running group was cancelled, restarted or superseded during this review.

## Confirmed corrections

* Retention negatives check the declared peer event shape before generic
  transaction reduction, so a mutation is rejected at its intended boundary.
  Exact negative reasons remain required; an unrelated exception is not credit.
* Joining reply-loss and joint-floor producers enable existing per-connection
  transport capture, including the joint-floor child JVM. Reply-loss negative
  catalogues explicitly distinguish legacy, terminal and connection capture.
  Old missing observations are not reconstructed or granted passing status.
* The service-close revocation fixture now closes from outside the active
  handler, observes actual revocation and waits for drain. A handler's rejected
  self-close is no longer mistaken for a successful revocation.
* Learner renewal assertions use the actual donor's completed PREPARE cut.
  Independent physical replay includes renewal campaigns, their BARRIER slots,
  retained ancestry and all sixteen publication slots. A fixed index increment
  omitted the existing reconciliation behavior.
* Carried transition replay derives the selected floor cohort and nonvoting
  departing ends. It models the existing conditional local floor pin without
  adding a checkpoint endorsement or increasing the seven-copy limit.
* Network replay accounts for identical late/lost ACKs only when an identical
  response was actually delivered in the same phase. Unselected grants require
  original journal/capture evidence. Unanswered PREPARE and checkpoint lookups
  must match their original authority and interval and add no quorum credit.
* Maintenance discovery may return a physically derived stale cut that was
  correctly declined. It remains a discovery observation, not a retained copy.
  Export replay includes real unselected frozen grants and validates every
  source's separate complete retirement interval.
* Automatic restart capture preserves the primary failure and attaches any
  later evidence-save error instead of masking it with a missing events file.

These edits affect test fixtures and offline evidence readers. The later Joining
follow-up also removes both matrix `max-parallel: 8` settings as requested;
job count, dependencies and coverage stay the same. Production Java, request
deadlines, history budgets, frozen capacity limits and measurement retry policy
are unchanged.

## Verification and its limits

Local evidence and full logs are retained under ignored
`target/v53-hosted-fixes-5217a556/`. The associated diagnostic artifact downloads
and the earlier paginated API snapshots remain intact. The machine-readable
`validation-summary.json` in that directory indexes individual checks and logs.

Three unchanged hosted originals passed their complete original replay chains
with the corrected readers: artifact `13719213195` (INTENT accept halt),
`13720886303` (INTENT proof kill), and `13723095596` (INTENT application kill).
The first two include storage/prefix/ownership replay; the third includes its
application transient chain. This is diagnostic replay of the old bytes, not
admission of a new source-bound cohort. The complete mutation suites for those
originals have not all been rerun.

The real 48-case reply-lifetime matrix passed, followed by independent replay
and all 44 exact evidence negatives. A fresh automatic higher-ballot restart
passed within its unchanged budget, and its physical, network and lifecycle
replay passed. That single success does not establish the historical deadline
failure's cause. Fourteen focused Java checks also passed.

The final related Python suite passed **1,910 tests** in 41.205 seconds.
Two new regression checks were executed against both HEAD and the working tree:
the old selected-voter checkpoint model and old retention rejection ordering
both fail, while the corrected versions pass. Related Python suites and focused
mutation tests cover the added acceptance paths and reject fabricated authority,
missing delivery, wrong intervals, selected-peer misuse and extra attempts.

The failed learner original agrees with the corrected reducer through all eight
available applied/published slots and four installations, then still fails for
its genuinely absent third-acquisition snapshot. A new complete six-cycle
original is required. No missing stage was filled in.

## Remaining diagnosis and rerun boundary

Several original failures remain open: node renames, slot-accept, carried DATA
process cuts and automatic competition. A controlled local carried-slot run
also encountered a request deadline (13 of its 14 selected tests passed).
Observed file/force capture overhead is a lead, not proof of a runtime defect
or a GitHub scheduling fault. Do not classify all of these as harmless flakes
or automatically retry client mutations.

The Joining matrix is now finished and all 60 failed replay receipts are
retained; the follow-up below records their classification. Qualify the
corrected source with fresh originals where capture changed, and rerun the
affected independent replay and exact-negative suites. Keep every old failure
and source/attempt binding. No new hosted run or push was performed as part of
this local repair batch; its passing checks are not a Phase 3 completion claim.

## Completed Joining matrix follow-up

The paginated snapshot contains all 242 jobs and 479 artifacts for attempt 1.
There are 357 completed original histories, 182 passing individual replays
(177 in green groups plus five in partially failing groups), 175 failed
individual replays, and three histories without a retained original from group
047. Do not turn the latter into test failures with an invented assertion.

| Failure in retained receipts | Histories |
| --- | ---: |
| `joining failure missing caller terminal` | 157 |
| `joining failure receiver lifetime` | 7 |
| `joining failure unqualified response delivery` | 1 |
| `joining network ambiguous overlapping retry` | 2 |
| `joining continuation exact inventory: applied-10: node-5` | 5 |
| `joining continuation exact inventory: applied-10: node-6` | 3 |

All 60 failed verifier artifacts were downloaded and six original histories
from five group bundles were inspected. Downloaded archive digests were checked
against the API, and selected raw bundle hashes against their manifests. The
six representative original errors reproduce locally; no producer is rerun to
replace an inconvenient historical outcome.

The legacy producer omitted connection capture. The Joining producer now turns
on the existing connection collector and propagates its setting to each child
JVM. Exact negative catalogues distinguish the two formats. Existing legacy
evidence remains subject to its original rules; missing connection identities
are not synthesized. A real TCP test covers delayed handler completion and
delayed response delivery, and independent replay passes both originals plus
eight exact negative mutations. Six child launches check property propagation
for enabled/disabled capture across halt, kill and resume commands.

The inventory failures expose a missing unselected-grant maintenance path in
the offline model. Post-grant maintenance can finish after the selected cohort
is installed. Remote original generation copies can straddle that installation.
The correction derives both possible generations, binds the choice to original
delivered bytes before floor reservation, and applies retirement only after its
complete observed force/rotation/delete sequence and before the snapshot marker.
Final snapshot and peer-ledger bytes remain exact comparison targets; they do
not supply replacement authority. Complete transport/export/floor qualification
is still required by the enclosing gate.

The unchanged `4-ADD,JOINING_RETENTION_SEED_WRITTEN,halt` and
`5-REPLACE,JOINING_RETENTION_SEED_FORCED,kill` originals now pass the complete
physical derivation through cut 11 (35 and 42 owner snapshot comparisons).
Their enclosing authority checks still reject missing caller terminals in
legacy transport observations. These are two repaired physical diagnostic
replays, not two fully qualified historical members. The focused Python suite
passed 141 tests; the broader Joining regression suite passed 992 tests. The
15 focused Java checks and the separate real TCP test passed. YAML, five shell
blocks, documentation contracts and whitespace checks passed.

One fresh local `4-ADD,JOINING_RETENTION_SEED_WRITTEN,halt` original passed
without retry in approximately 18m52s, including real child death/recovery,
FINAL, BARRIER and cold reopen. Its complete original physical, connection,
export/control, maintenance, peer/future/learner ledger and ballot replay
passed. The actual resume child retained connection metadata on all three
received requests and replies. Removing one original child response was
rejected with the exact connection-format reason. Raw history:
`general-search-engine-replication/target/v53-native-dispatch/run-28d1faab-6332-4441-b43a-1a8a0592d0e2`;
receipts: `fresh-authority.json` and `fresh-child-response-negative.json` in the
diagnostic directory below. This is one local diagnostic original, not the
360-member source-bound hosted cohort or its full 150-slot negative catalogue.

Working evidence and focused validation logs:
`target/v53-joining-review-20261111/`. Corrected-source hosted originals and
complete negative qualification remain pending. Removing the matrix cap affects
future runs only and does not override GitHub runner/account capacity.
