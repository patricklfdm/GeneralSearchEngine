# V5.1 Phase 4D: public fencing and mutation fault matrix

**Status:** accepted through [PR #195](https://github.com/patricklfdm/GeneralSearchEngine/pull/195)
at `da9f3e9fe957e61c0fe45cf041431a5c4c74cd79`, with exact-master
[CI 35570118695](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35570118695).
All six jobs passed; public runtime, qualification, faults and rejoin steps actually
executed, including the checkpoint follow-up. [Batch E](PHASE_4_PUBLIC_RECOVERY.md)
extends recovery/lifecycle evidence; complete Phase 4 acceptance remains open.

## Public process boundary

Run `scripts/verify-v51-phase4-public-faults.sh --skip-build` after packaging current
sources. The complete gate contains 19 cases, each with three simultaneous public
JVM voters and a retained-directory restart in a fourth process. The external
consumer compiles against candidate JARs outside implementation packages. Bootstrap,
start, mutations, strong reads and close all use the public API.

A separate observer owns network fault injection and precise pauses/crashes. It can
drop real outbound requests/responses, pause an application observation point, halt
a worker or let the controller SIGKILL it. It cannot call private activation,
initialize voters, mutate authority files or force a ballot on the engine's behalf.
Election and higher promises are produced by the running protocol.

## Three partition and read-fence cases

| Case | Schedule and expected public result |
| --- | --- |
| Isolated old leader | Split the old leader from both peers; the surviving majority elects and acknowledges a tagged atomic bulk. Later old-leader reads fail and the subsequent mutation is NOT_SUBMITTED. Heal and reopen the retained old node; the acknowledged application survives. |
| Promise before capture | Pause after a read's NO_OP publication but before its current-ballot/cut check. Partition, let the other majority write, briefly heal to deliver higher-ballot traffic, observe an actual forced higher promise, isolate again and release the pause. The read returns STALE_EPOCH without invoking its query callback. |
| Promise after capture | Pause after the validated view is captured. Repeat the majority write and forced higher-promise crossing. The pending read completes with its earlier captured documents; its invocation overlaps the later write. A new old-leader read still fails. |

The fixture freezes a 60-second operation deadline through public bootstrap, while
keeping heartbeat/election/transport settings unchanged. This gives the controller
time to exercise the ballot boundary explicitly; it is not a production default or
performance claim. A cached LEADER_READY hint alone is not treated as proof of a
currently reachable quorum. Actual strong-read outcomes and decoded force records
establish the safety property.

The runtime emits an observation-only validation record under the protocol monitor,
then exposes the pausable capture event after releasing it. The physical oracle
checks the validation record against the latest local forced promise at that point.
A later promise may legally precede the pausable observation or the view's release;
moving it before validation must fail the independent check. A separate crossing
check requires the higher forced promise strictly
inside the pause interval; removing that record must invalidate the evidence.

Capture also rechecks cancellation, close and the finite deadline after acquiring
the protocol monitor. Waiting for that monitor can outlive the initial check. A
Java regression pauses before capture until the public deadline expires, releases
the pause and proves that the query callback is never invoked; a following mutation
drains the same application worker successfully.

## Sixteen public mutation interruption cases

Each boundary below runs once with `Runtime.halt(71)` and once with SIGKILL:

1. Before local ACCEPT write.
2. After local ACCEPT force.
3. After receiving the remote ACCEPT receipt.
4. Before local PROOF write.
5. After local PROOF force.
6. After receiving the remote PROOF receipt.
7. Before application publication.
8. After application publication, before client completion.

The observer records forces before exposing their corresponding post-force cut.
After arming a crash, other observed paths in that JVM cannot race past the cut
while the controller delivers SIGKILL. A read pause remains cooperative and permits
the control thread to process a higher promise. These observer gates are test-only.

Every interrupted mutation stays pending in the controller history. No uncertain
operation is retried. The independent cut audit binds the interrupted payload to
its actual entry, receipts, proof and publication. Once a remote ACCEPT receipt
establishes the entry quorum, the tagged value must survive failover, even if its
original proof or response was absent. Before quorum, inclusion is checked as an
allowed uncertain outcome rather than falsely counted as an acknowledged success.

Each crash retains its requested/observed boundary, PID, generation and exit code,
plus a verified exact-file inventory/archive before reopening. Source inventories,
candidate JAR hashes, controller intervals, complete wire/force traces, per-case
receipts and failures are always retained by CI. The inherited bounded history and
chosen-prefix oracles both run; stale/partial/reordered results and missing evidence
must still fail their negative checks.

## Scope and remaining Phase 4 work

This batch extends E03/E05/E09/E10 with public process evidence. It preserves the
existing bounded model, storage inspector and internal runtime coverage without
relabeling them as public execution. [Batch E](PHASE_4_PUBLIC_RECOVERY.md) takes up
imported genesis failover, missing/copied authority, cancellation/close schedules
and cursor behavior across rebuild. Remaining partition/selection/exhaustion/mixed-mode
mapping in E01–E12 and full protected Phase 4 acceptance remain separate work.

The production changes are package-private observation points, the capture-time
cancellation/deadline recheck and the checkpoint idempotency follow-up below. Public
API descriptors, authority formats, configured 1.1 behavior, versions, dependencies
and paid-cloud settings are unchanged.

## Local validation

Base `6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4` plus this batch, 2026-09-20:

- Targeted reactor package passed 16 tests: 12 public-runtime regressions, including
  the new expired-capture callback test, and four internal-runtime regressions.
  This is a targeted package/test result, not a full-reactor claim.
- Final fault matrix:
  `target/v51-public-faults/run.JGuWO6/evidence/receipt.json` — all 19 cases and
  250 controller-recorded client calls passed both independent oracles. Every case
  retained four voter process instances. Exact mutation-stage audits, crossing-promise
  negatives and the allowed delayed-capture-observation fixture passed.
- Existing qualification:
  `target/v51-public-qualification/run.URdRUq/evidence/receipt.json` — all six
  read/response crashes, their independent negative checks and the separate
  published V4.4 rich-query/backup comparison passed on the final JARs.
- Foundation:
  `target/v51-foundation/run.fOZC9B/evidence/receipt.json` — all 64 Python tests,
  external consumers, API checks and published V5.0 compatibility passed.
- CI YAML/retention entry, shell/Python syntax, V5 documentation contract,
  changed Markdown links/anchors/fences and whitespace checks passed.

Original fault-matrix replication JAR SHA-256:
`0f3426cf8bcde213b5b75c12c4aa369fb9826ee68749d04fa04cb07238c40064`.
Exploratory receipts retain their original source/JAR identities; the receipts
above qualify the original fault-matrix candidate. The initial driver incorrectly waited
for an isolated node's cached role hint to change without issuing a read. The final
case instead verifies the actual fresh-barrier rejection, as the contract requires.

Receipts retain the source inventory at execution time. This summary is written
after execution. The acceptance update above records the later exact-master CI.

## Checkpoint CI follow-up

Source `93f7eaa02f00b24a9273c2ef137c682fce7a98cb` plus this follow-up, 2026-09-20:

The public checkpoint capacity check allowed reuse of an identical retained cut,
but execution unconditionally rotated to the inactive generation. If that directory
still held an older cut, the storage guard rejected the operation with
`inactive generation requires durable floor cleanup` and quarantined the voter.
Checkpoint now uses the same idempotent proven-snapshot installation as background
recovery. An identical cut leaves both generations and the selector untouched;
a newer cut still needs capacity and the existing two-source retirement authority.

Two Java regressions deliberately seed both generation slots, then exercise the
public checkpoint and reopen paths on a single running voter. Both reproduced the
original integrity failure before the fix. They now verify repeated identical-cut
success, unchanged retained bytes, classified capacity rejection for a newer cut,
and successful advancement only after durable floor cleanup. These are focused
storage-seeded regressions, separate from the public fault matrix above.

The first process rerun also exposed legitimate capacity pressure immediately after
backup advanced the proven prefix. The driver now records checkpoint attempts and
waits at most 30 seconds, retrying only `CAPACITY_EXCEEDED` / `NOT_APPLICABLE`.
It requires actual checkpoint success and fails immediately on integrity/storage
errors, other classifications or a missing response. Mutations and backup remain
single calls. Five Python regressions enforce that boundary and the total deadline.

Validation:

- Targeted reactor package: 46 Java tests passed across checkpoint, public/internal
  runtime, recovery storage and recovery exchange.
- V5.1 Python discovery: 69 tests passed, including the five new driver regressions.
- Public runtime gate:
  `target/v51-public-runtime/run.jcTKiy/evidence/receipt.json` — four JVM process
  instances, nine chosen entries/publications, three writes, three fresh reads,
  seven rejected negatives and the published V4.4 backup comparison passed.
- Rejoin gate:
  `target/v51-rejoin/run.gld2LB/evidence/receipt.json` — five JVM process instances,
  retained restart/second failover and independently verified floor/retirement
  evidence passed. Its source inventory precedes the driver-only follow-up.
- The intermediate capacity-pressure failure remains at
  `target/v51-public-runtime/run.YlaUrF/evidence/receipt.json`.

Follow-up replication JAR SHA-256:
`2300c45c8f2bb5596d96ffe6479254b50a7fd2f87df81a3ba592c67898c2db4f`.
The earlier full fault-matrix, qualification and foundation receipts retain their
original JAR identities. This is targeted follow-up validation; the acceptance
update above records the subsequent protected merge and exact-master CI.

## Post-crash concurrent service CI follow-up

PR #213 [CI 35822480859](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35822480859)
failed in `kill-accept_before_write`, after the old leader (node 1) was killed and
the surviving node 2 exposed `LEADER_READY`. Raw records show the node 2/node 3
activation at epoch 6 and index 9, then a local ACCEPT for the next public bulk.
The first post-crash concurrent write returned `INDETERMINATE` / `QUORUM_UNAVAILABLE`
in about 328 ms; the peer did not observe its ACCEPT. There was no intervening
higher promise. Background source transfer and heartbeat responses arrived after
the rejection. The original trace lacks per-reservation accounting, so it does not
prove the exact local transport contention path. It does establish that the driver
incorrectly required four immediate successes from a cached role hint during recovery.

The shared public-qualification driver now requires a complete successful four-call
wave within at most **three fresh waves** after the crash. It reselects the observed
leader before each wave and generates new, unique bulk keys for every mutation.
All four calls are submitted before collecting any response; every result, including
partial success, rejection and uncertainty, remains in the same client history and
in `recoveryWaves`. The stopped leader remains absent until all four calls in one
wave actually succeed. Neither the interrupted write nor an indeterminate wave
mutation is replayed; no full scenario is retried into a PASS.

Only classified availability results can lead to another fresh wave: reads must
be `NOT_APPLICABLE`; mutations must be `NOT_SUBMITTED`, or `INDETERMINATE` with
`QUORUM_UNAVAILABLE`, `STALE_EPOCH` or `DEADLINE_EXCEEDED`. Proven pre-submission
and read refusals also allow `NOT_LEADER` / `NOT_READY`. Missing responses, malformed
outcomes, storage/integrity failures, explicit capacity errors, closed handles and
unknown errors fail. Persistent unavailability fails after the third wave.

This permits at most 22 attempted application calls per crash case, inside the
unchanged 24-call / 100000-state oracle limit. Both independent oracles still check
every attempted mutation and read, including eventual inclusion of uncertain values,
no effect from `NOT_SUBMITTED`, exact read barriers and preservation of acknowledged
bulks. Initial healthy traffic and the final retained-restart read remain strict.
The sixteen mutation boundaries and the three fencing cases remain unchanged;
production runtime, transport limits, deadlines and retries are unchanged.

Ten driver regressions cover the observed CI response sequence, fresh payloads,
complete concurrent submission/collection, leader reselection, three-wave exhaustion,
strict failure classifications, missing responses and independent history rejection
of lost acknowledged data. Both affected gate scripts run those tests.
The downloaded original failing evidence is retained under
`target/v51-fault-wave/ci-evidence/run.Uas3B4/evidence/kill-accept_before_write`.

Local validation of this follow-up on `5c896b966e7ac0e31de2081eaeb25ff571ced720`
plus the driver changes:

- Complete 19-case fault matrix passed at
  `target/v51-public-faults/run.LTzXvR/evidence`, including the failing SIGKILL boundary.
- All six qualification crash cases and the V4.4 semantic/backup comparison passed
  at `target/v51-public-qualification/run.AWaevq/evidence`.
- All 267 V5.1 Python tests and 19 CI classifier/topology tests passed. Both complete
  gates recorded source inventories matching the final driver and test scripts.
- A separate three-JVM pressure probe held actual per-peer transport reservations.
  Its first wave returned `INDETERMINATE`, `NOT_APPLICABLE`, `NOT_SUBMITTED`,
  `NOT_APPLICABLE`; its second fresh wave returned four successes. All 13 calls,
  raw response bindings, unique mutation keys and balanced transport accounting
  passed the bounded client-history/resource checks. This probe has no retained
  restart, so it is not credited as a four-process physical qualification; that
  independent oracle passed in both complete gates above. The original probe's
  incomplete-manifest and four-process-prerequisite validation errors are retained
  alongside the correctly scoped validation of the same unmodified history.

Summary and logs: `target/v51-fault-wave/validation-summary.json`, `faults.log`,
`qualification.log`, `python-tests.log`, `ci-tests.log`, and
`pressure-probe-final-validation.log`. Protected PR/master acceptance remains pending.
