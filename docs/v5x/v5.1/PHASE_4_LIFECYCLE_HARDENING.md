# V5.1 Phase 4O: pinned recovery, partial I/O and repeated timeouts

**Status:** local qualification passed; protected Batch O and complete Phase 4
acceptance remain open. Batch N was accepted through PR #206 at
`3f5b0b25b6484bf6ddc062dd25527bee0ddaedb4`, exact-master CI `35779031221`.

## Scope and execution layers

The gate `scripts/verify-v51-phase4-lifecycle-hardening.sh --skip-build` executes
five public three-JVM/TCP scenarios. Public consumers compile separately against
the packaged core/replication JARs and use public bootstrap, startup, atomic bulks,
strong reads and close. They do not initialize retained authority or activate a
leader. The controller never replays an uncertain mutation or repairs a failed disk.

The fixture seals four pending public operations, a 1200-ms request timeout,
9600-ms operation deadline and 4096-byte transfer chunks. Node 3 has the existing
long-election fixture policy while voting and recovering normally. All waits and
faults are bounded; failed runs retain their evidence.

This batch adds internal observation events `RECONSTRUCT_QUEUED`,
`RECONSTRUCT_BEGIN` and `RECONSTRUCT_END` to the existing runtime event sink.
They identify the same reconstruction request, prefix and application sequence;
the existing single application worker and reconstruction algorithm are unchanged.
The production replication JAR therefore changes, but no public API, format,
deadline, capacity, dependency or authority rule changes.

Two test-only mechanisms supply additional observations/faults:

- The existing `maximumWriteBytes` / `*_WRITE_CHUNK` storage hooks restrict one
  journal append to a real 64-byte channel write, observe exact before/after bytes,
  and throw `IOException`. No controller-side truncation simulates this failure.
- A separate observer reads queue/executor/semaphore counters by reflection. It
  never invokes internal queue methods or changes their contents. The public
  workload still provides every submitted operation. Counter samples are bounded
  observations, not a proof of all possible scheduling or unbounded endurance.

## Five public schedules

| Case | Required behavior and evidence |
| --- | --- |
| `pinned-rebuild` | Hold a real query callback after capture. Isolate its leader; the surviving majority acknowledges another atomic bulk. Heal and observe a newer durable rejoin snapshot on the held node. Stop the replacement leader so the original voter naturally queues reconstruction for another campaign. The old callback must return its original complete view; reconstruction must begin only after view release. The rebuilt original voter must then serve the new prefix. |
| `partial-leader-accept` | Fail the old leader's ACCEPT append after exactly 64 bytes. The in-flight public mutation reports INDETERMINATE; later writes/reads on that handle are rejected for storage failure. The surviving majority recovers without this unchosen value. |
| `partial-follower-proof` | Fail the selected peer's PROOF append after exactly 64 bytes. The leader's complete proof and the entry quorum already exist. The uncertain client mutation is not replayed; the surviving majority must recover its exact complete bulk. Bind the partial bytes to the actual incoming proof and leader force. |
| `queued-timeouts` | Hold one cooperative query and submit three waves of three distinct poisoned bulks. Each wave fills the other three public slots, expires at the sealed deadline as NOT_SUBMITTED, and drains queued work/timers while the query remains held. Arguments must never be evaluated. All nine expired calls remain in the history. |
| `exchange-timeouts` | Keep the original two-voter write quorum available while holding node 3's replies to three successive real `AUTHORITY_STATUS_PROBE` exchanges. Each source reservation must remain live through the request deadline and then release. Require fresh public write/read service after each round. |

Every case requires later successful public write/read service, a healthy retained
restart and another strong read. Transport admission/release events are independently
balanced through public close, with existing per-peer, byte and inbound limits.
The timeout cases check fresh bounded queue samples rather than inferring cleanup
from a final PASS flag.

## Damaged authority remains damaged

Each partial-write case archives the closed, damaged authority directory. Two fresh
public startup processes must reject it as FAILED / NOT_APPLICABLE with an integrity
or storage reason. Exact inventories before and after both attempts must match the
archive; no tail repair, truncation or same-group re-enrollment is allowed.

The independent retained-authority inspector continues to reject this directory.
The shared physical oracle accepts at most one explicitly identified quarantined
voter only after verifying its observed 64-byte incomplete append to the active
journal, complete pre-failure frame prefix, exact unchanged file and expected torn
journal rejection. Its result names that voter as QUARANTINED; it does not report
it as a valid recovered member. Both healthy authorities still undergo their full
inspection. All three original process traces still participate in force/quorum,
chosen-history and read-view validation. Existing gates keep strict all-voter
inspection unless they explicitly supply this precise fault witness.

## Oracles and limits

The read/rebuild oracle checks same-process ordering: callback hold, newer snapshot
installation, queued reconstruction, callback/view release, reconstruction begin
and end. It binds the old read bytes and the new majority write to independently
decoded images. It rejects borrowed process/work identities and early replacement.

The timeout oracle binds actual invocation/failure events, sealed deadlines,
queue/admission samples, unique calls and balanced transport reservations. Samples
read concurrently changing queues individually; they are not presented as an atomic
snapshot of the entire runtime. These are finite three-wave/three-round witnesses,
not OS exhaustion, arbitrary blocked-control schedules or an endurance proof.

The existing independent client-history and physical chosen-prefix/captured-view
oracles remain enabled. Counterexamples remove overlap/reconstruction, queue samples,
release accounting, partial I/O or retained restarts, and corrupt final projections.
Unit witnesses reject full records mislabeled as partial writes, repaired/changed
tails, wrong journal paths/kinds, resource leaks and reordered reconstruction.

## CI and remaining Phase 4 work

The gate runs in `v51-public-lifecycle` after the existing backpressure gate and
always uploads `target/v51-lifecycle-hardening` as
`v51-lifecycle-hardening-${{ github.sha }}` for fourteen days. Existing required
lanes, verification steps, docs-only routing and paid-cloud workflows are preserved.

The [current evidence map](PHASE_4_EVIDENCE_STATUS.md) still requires final E01–E12
method/schedule reconciliation, including delayed-heartbeat and compatibility
coverage, review of internal/public evidence boundaries, and protected Phase 4
acceptance on the final source. This batch does not authorize Phase 5 or cloud runs.

## Local validation

Base: `3f5b0b25b6484bf6ddc062dd25527bee0ddaedb4` plus this batch.

- Complete five-case gate passed at
  `target/v51-lifecycle-hardening/run.bBw18a/evidence/receipt.json`: 69 public calls,
  20 runtime process identities, four additional rejected public startups and
  all 54 evidence-negative variants rejected. The complete local gate took about
  173 seconds, including consumer/observer compilation and independent checks.
- Complete shared-oracle/observer regression: all six Batch N cases passed at
  `target/v51-public-selection/run.oVO83v/evidence/receipt.json`; Batch M's two
  internal fixtures and four public scenarios passed at
  `target/v51-backpressure/run.JwbYdy/internal/receipt.json` and
  `target/v51-backpressure/run.JwbYdy/public/receipt.json`.
- Targeted reactor package passed all 34 `V51AutomaticRuntimeTest`,
  `V51PublicRuntimeTest`, `V51AutomaticStoreTest` and `V51AutomaticRejoinTest` tests:
  `target/v51-lifecycle-hardening/build.log`. This is targeted local validation;
  protected CI retains each lane's full reactor tests.
- Complete independent foundation passed at
  `target/v51-foundation/run.1vJ0kN/evidence/receipt.json`, including version alignment,
  the V5.0 contract, the 38-document V5.1 contract and all 214 V5.1 Python tests.
  Eleven new tests exercise overlap, resource counters and precise torn-tail rejection.
- All 25 CI/toolchain tests passed. The local static review checks YAML, 105 shell
  blocks, 34 unique artifact names, unchanged prior steps/job settings/triggers,
  local links, the historical 87-step migration map, Python compilation, shell
  syntax and whitespace. Evidence index: `target/v51-lifecycle-hardening/validation-summary.json`.

Candidate JAR SHA-256:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `92dc8035babcde58fd65e78ed01a9cab75b654eff60794dec9bb259e6aa6ad95`.

Exploratory failed receipts remain under `target/v51-lifecycle-hardening/probe-1`.
The final matrix uses the actual `AUTHORITY_STATUS_PROBE` message and the completed
independent oracle. It retains the damaged disks and conservative outcomes instead
of repairing authority or relaxing timeouts. Execution-time source inventories
precede this final documentation record. Protected Batch O and full Phase 4
acceptance remain pending.

## CI regression follow-up: V5.0 isolation prerequisite

CI run [35785207300](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35785207300/job/106940284845)
failed in the recovery/workload lane's prerequisite Maven tests, at
`V50ReadyTest.incrementalCatchupReplaysOnlyTheMissingTailOfAPublishedPrefix`.
The fixture waited for node-3's published prefix before isolating it, but had not
established that node-2 could provide the surviving write quorum. Seed completion
requires only one remote voter; a missed APPEND or COMMIT_PROOF can leave the
other voter behind until explicit recovery.

The fixture now calls the existing catch-up path for node-2 and checks its READY
state and exact log/commit/applied prefix before isolating node-3. Two added
schedules lose one APPEND or COMMIT_PROOF exchange, including its retry, and
require an actually lagging survivor. Without the prerequisite fix, both reproduce
`no valid remote voter for APPEND`; all three original schedules pass. This proves
the fixture defect, although the original CI log did not retain node-2's reason
and cannot identify the precise exchange it lost.

The original ten-entry recovery, three bounded batches, replay-count limits,
private-publication checks, duplicate recovery and subsequent quorum write remain
asserted. Failures attach all three pre-close states and the latest rejection for
each peer/message pair. This follow-up changes the test fixture and this record;
production code, request deadlines, resource bounds and write retries are preserved.
The deliberately failing regression reports and log remain under
`target/ci-investigation-35785207300/before-fix-reports` and
`target/ci-investigation-35785207300/reproduce-before-fix.log`.

Follow-up validation: the full `./mvnw -B -ntp -f reactor/pom.xml package` passed
(853 tests, 4 skipped, no failures/errors), including all 13 `V50ReadyTest`
cases. Log: `target/ci-investigation-35785207300/reactor-after-fix.log`;
summary: `target/ci-investigation-35785207300/validation-summary.json`.
Both production JAR hashes remain identical to the candidate values above.
The 38-document contract and whitespace checks passed. Updated-source protected
CI remains pending.
