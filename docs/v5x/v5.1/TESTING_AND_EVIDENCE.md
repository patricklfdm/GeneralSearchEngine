# V5.1 testing and evidence candidate

**Status:** Phase 0 evidence design accepted through PR #184; revision 0.1.
Phase 0 produced no V5.1 model, runtime or cloud results; later evidence is recorded separately.
**Reviewed source:** `09d2bf247f004eb134eb81c59ee88005affafe92`.

**Acceptance update:** protected PR [#184](https://github.com/patricklfdm/GeneralSearchEngine/pull/184)
accepted this Phase 0 design at `31b70d08b509ac75037a8eb6386780affc353ed9`.
[Exact-master CI 35487644896](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35487644896)
passed the documentation lane; reactor/compatibility/packaging jobs were skipped.
Original candidate wording below records the reviewed design, not runtime evidence.
The user subsequently authorized Phase 1; see its [foundation record](PHASE_1_FOUNDATION.md).
Phase 2's real storage/recovery evidence is recorded in [its acceptance record](PHASE_2_RECOVERY.md).
[Phase 3](PHASE_3_CHECKLIST.md) is accepted through PR #191 with real concurrent
JVM/TCP/rejoin evidence. [Phase 4A](PHASE_4_BOOTSTRAP.md) enables the public offline
bootstrap/cleanup subset. [Phase 4B](PHASE_4_PUBLIC_RUNTIME.md) implements the
public lifecycle/strong-read façade and initial public JVM evidence and is accepted
through PR #193 (exact-master CI `35554352587`). [Phase 4C](PHASE_4_PUBLIC_QUALIFICATION.md)
adds concurrent histories, read/response crashes and rich V4.4 comparisons. Its
coverage table distinguishes these cases from the remaining full public matrix below.
Phase 4C is accepted through PR #194, exact-master CI `35560692475`.
[Phase 4D](PHASE_4_PUBLIC_FAULTS.md) adds public old-leader isolation, read fencing
and mutation-stage interruptions, accepted through PR #195, exact-master CI
`35570118695`. [Phase 4E](PHASE_4_PUBLIC_RECOVERY.md) adds imported failover,
missing/copied authority rejection, cancellation/close and cursor reconstruction.
Phase 4E is accepted through PR #196, exact-master CI `35579584390`.
[Phase 4F](PHASE_4_PUBLIC_PROTOCOL.md) adds competing campaigns, asymmetric faults,
minority-tail selection and basis/snapshot interruption, accepted through PR #197,
exact-master CI `35591386329`. [Phase 4G](PHASE_4_PUBLIC_RECLAMATION.md) adds
two-source floor publication, interrupted physical retirement and retained restart.
Phase 4G is accepted through PR #198, exact-master CI `35664882661`.
[Phase 4H](PHASE_4_PUBLIC_BOUNDS.md) adds public admission capacity, application
bounds, no-quorum startup and incompatible configuration/mode/wire rejection.
Phase 4H is accepted through PR #199, exact-master CI `35688926607`.
[Phase 4I](PHASE_4_PUBLIC_PROMISES.md) adds twelve public peer-promise write/force,
frozen-basis and reply interruption cases with independent retained-journal checks.
Phase 4I is accepted through PR #200, exact-master CI `35693468905`.
[Phase 4J](PHASE_4_PUBLIC_CANDIDATES.md) adds fourteen candidate-side promise,
frozen-basis and PREPARE request/response interruption cases with fresh retained
campaign checks. These supplement E04; resource exhaustion remains open.
Phase 4J is accepted through PR #201, exact-master CI `35698045261`.
[Phase 4K](PHASE_4_PUBLIC_PRESSURE.md) adds five transport saturation/slow-force
scenarios, reservation release accounting, conservative uncertain outcomes and
public recovery without write replay. These supplement E10/E11; internal runtime
mailbox saturation and snapshot/promise/ancestry exhaustion remain open.
These batches do not close unrelated E rows.

## Independent foundation before production

Phase 1 must supply an independent logical model, independent byte/schema inspector,
immutable fixtures, deterministic message scheduler, separate-process crash protocol,
external public consumer source and no-GCP cloud planner. None may import production
decoders or use implementation status equality as its sole correctness oracle.
The model must implement the written selection rules independently, not copy Java
control flow. It must preserve all failed seeds/traces and make its assumptions visible.

Proposed new identities, distinct from every V5.0 family:

- Evidence schema: `gse-v51-leadership-evidence-v1`.
- Deterministic/process suite: `v5.1-automatic-leadership-suite-v1`.
- Later cloud preset: `v5.1-automatic-leadership-v1`.
- Eventual append-only baseline: `v5.1.0-automatic-leadership-cloud`.

These names reserve new evidence scope; no baseline is registered by this document.

## Model invariants and falsification

The independent state includes each voter's forced promise, last accepted ballot
and value per retained slot, proof-backed prefix, durable generation/snapshot,
publication cut and process generation. Volatile queues, responses, callbacks,
frozen basis pins and client outcomes are separate. A forced receipt must be backed
by an earlier durable event in the same process/disk generation, not by a hash that
the checker can recompute without evidence of a force.

| Invariant | Required failure witness |
| --- | --- |
| I01 promise monotonicity and unique ballot binding | One eligible disk grants conflicting identities for one epoch or accepts below a forced promise |
| I02 one chosen value per slot | Two quorum receipt sets choose different immutable values at the same slot |
| I03 preserved acknowledged history | Any later admitted prefix omits/changes a successfully acknowledged mutation |
| I04 ordered proof-backed publication | Application publishes an unproven value, skips a slot, splits an atomic bulk or advances application sequence for NO_OP |
| I05 safe prepare selection | Candidate ignores a highest-ballot accepted value, mixes frozen bases or changes a same-ballot retry |
| I06 strong-read ordering | A read invoked after an acknowledged write returns an older incompatible cut, or uses a barrier before its own invocation |
| I07 ownership and recovery completeness | Reinitialization, generation switch or cleanup forgets a required promise/accepted value/proof or permits two owners |
| I08 finite accounting | Repeated timeout/cancel/campaign/transfer leaks timers, basis pins, queued bytes, tasks or authority beyond declared bounds |

Start with three voters, a small finite document/key domain, two concurrent
candidates, at least three epochs and three slots. Exhaustively enumerate the
declared bounded scheduler state space and retain its exact bounds/counts. Add
seeded longer traces separately; bounded exploration is not a proof for arbitrary
executions. Include entry-origin epoch differing from acceptance epoch, a carried
application value followed by activation NO_OP, and a compacted prefix.

Mandatory negative checker fixtures deliberately introduce each I01-I08 violation.
The gate must fail when a receipt force is removed, a quorum voter is duplicated,
the selected accepted value is changed, a basis hash is swapped, a read barrier is
reused, a read invocation is moved after step-down, a bulk is partially published,
or a retained promise is rolled back. Mutating only a final PASS/status field is
not a meaningful negative test.

## Scenario matrix

Every row requires deterministic model traces first, relevant independent physical
fixtures, and later real implementation/public-process evidence. Phase 1 scaffold
success is never reported as completion of the implementation column.

| ID | Required schedules and inspected data | Public/physical acceptance | Decisions / invariants |
| --- | --- | --- | --- |
| E01 | Empty and imported-genesis startup; no quorum at start; leader crash with two retained disks; fresh activation NO_OP | Three concurrent public JVMs regain service without manual activation; full acknowledged oracle survives | D04/D10, I03/I04 |
| E02 | Simultaneous candidates, split grants, duplicate PREPARE, higher epoch during ACCEPT/PROOF; repeated eventual stable period | No conflicting chosen value; progress only after stated quorum/timing conditions; exact ballot owner survives retries | D01/D02, I01/I02/I05 |
| E03 | Old leader isolated before read invocation; new majority acknowledges a write; delayed heartbeat/proof/reply; asymmetric partition | Old leader rejects new strong reads/writes, later rejoins through recovery; no stale-success downgrade | D01/D05, I02/I06 |
| E04 | Crash before/after promise write, force, basis capture, ACK; crash after selecting an epoch before peer replies; epoch/promise-count exhaustion | Independent pre-reopen inspection; no forgotten grant, reused incarnation/ballot, wraparound or silent reset | D02/D09, I01/I07/I08 |
| E05 | Local entry force, entry-quorum formation, proof construction/force/quorum, apply/publication and response loss | Success set preserved; entry-chosen/proof-unknown values survive selection; NOT_SUBMITTED leaves no effect; uncertain results remain uncertain | D01/D03/D06, I02/I03/I04 |
| E06 | Minority longer tail, lagging candidate, different acceptance/origin epochs, hidden proof, all chosen quorum intersections, changed same-ballot retry | Prefix and next value derive from frozen quorum rules; exact bytes carried; recovery cannot choose by index alone | D03, I02/I05 |
| E07 | Basis download changes epoch; snapshot chunk/install/select/floor/deletion cuts; accepted next value beyond snapshot; pinned read during rebuild | Old complete authority survives interruptions; neither accepted tail nor root promise lost; bounded pins/materializations | D03/D09, I05/I07/I08 |
| E08 | Old leader retained-disk restart; one/two lost disks; copied/stale seal; missing promise/acceptance; repeated failover | Retained-disk rejoin automatic; missing authority quarantined; no same-group disk re-enrollment; new-group transition preserves verified cut | D04/D08, I01/I03/I07 |
| E09 | Every application read overload; concurrent writes/elections; barrier before/after higher promise; pin before/after step-down; cursor across NO_OP versus mutation/rebuild | Exact barrier/view relation; legal overlapping read accepted; stale later read rejected; original query/ranking/page truth | D05/D10, I04/I06 |
| E10 | Role hints race with dispatch; queued deadline; partial write error; lost response; cancellation before/after authority; close/start/read and callback reentrancy | Structured outcomes are conservative; no hidden replay; accepted work eventually releases its accounted capacity; close retains ownership while needed | D04/D06/D09, I03/I07/I08 |
| E11 | Zero/one reachable peer, slow force, long callback, full payload/control queues, tiny bounds, snapshot/promise/ancestry exhaustion | Control remains bounded/admitted; unsafe cleanup never makes space; no-quorum and capacity errors carry correct outcomes | D09, I01/I07/I08 |
| E12 | 1.0/1.1/1.2 wire/disk mismatches, mode/manifest/schema mismatch, configured/API compatibility, absent-target bootstrap and ambiguous cleanup | External V1-V5.0 consumers unchanged; new automatic consumer covers full lifecycle; wrong mode/version rejects before authority mutation | D07/D11/D12, I04/I07 |

## Process and public-consumer requirements

The public consumer compiles outside implementation packages against built core and
replication JARs. It uses public automatic bootstrap, start, application, checkpoint,
backup and close. The controller can kill JVMs and inject deterministic transport
faults; it cannot initialize authority, call private activation, mark a voter READY
or repair storage on the consumer's behalf. Nodes run concurrently; serial stand-ins
do not establish quorum/failover behavior.

Required scenario: bootstrap three nodes, continuously submit tagged atomic operations
and strong reads, kill the current leader, route later attempts using local leader
hints while retrying only confirmed NOT_SUBMITTED calls, observe a surviving majority
recover, then restart the old retained-disk node. Check every success and every
permitted indeterminate inclusion against the independent history. Do not replay an
indeterminate mutation to manufacture a successful count.

Physical barriers include promise force/ACK, frozen basis publication/chunk completion,
selected-next force, ACCEPT write/force/ACK, PROOF write/force/ACK, application publish,
read view capture/release, client response, snapshot force/select/floor/delete and
bootstrap decision/seal delivery. Exercise both worker-owned abrupt halt and
controller-owned SIGKILL; record PID, process generation, requested cut and exit code.
Archive exact files before reopening so recovery cannot erase the failure evidence.

V4.4 is the separate search/backup oracle, including ordered documents, atomic bulk,
index lifecycle, query/ranking, highlight, explain and paging semantics. Published
V5.0 is additionally the configured replication/API behavior control. Their code
sources and JAR hashes must be recorded independently. A current-source engine
calling itself the baseline is not a published control.

## Observable history and timing

Each record binds source tree/dirty diff, candidate/control artifact hashes, run,
node/disk/process generation, group/manifest, local event sequence, operation ID,
ballot/proposer/incarnation, slot/value/proof/basis identity and local monotonic time.
Keep raw relevant messages and before/after authority inventories plus final hashes.
Wall-clock timestamps are for navigation only.

The controller records client invocation and completion intervals on one monotonic
clock. Worker clocks measure local durations; correlate events across machines by
message/operation identity and causal order, never by subtracting their nanoTime.
Per-call evidence distinguishes NOT_SUBMITTED, INDETERMINATE, validation failure,
success and timeout/cancellation with missing outcome. Report all attempted calls.

| Measurement | Exact boundary |
| --- | --- |
| Detection | Local last qualifying heartbeat/progress observation to local campaign start |
| Election | Campaign start to its complete frozen promise quorum |
| Recovery/activation | Promise quorum to local publication of the fresh activation NO_OP |
| First durable write | Controller fault event to first post-fault mutation success response |
| First strong read | Controller fault event to first post-fault read success with its fresh barrier/cut |
| Client outage | Controller last pre-fault success to first qualifying post-fault success, reported separately for reads/writes |

Use a bounded linearizability checker for small concurrent operation histories,
including pending/indeterminate invocations and overlapping reads. Larger load runs
use the independently reconstructed chosen-prefix and query-cut oracle; do not label
that a complete exhaustive linearizability search. Include the two-oracle agreement
on small histories and negatives that each checker rejects.

## Performance, cloud and claim limits

Strong automatic reads deliberately add one NO_OP entry/proof round and consume
ancestry. Measure them separately from V5.0 configured local reads. Report total
offered/completed rates, read/write outcome counts, barrier latency, force counts,
queue time, pinned-view waits, election/recovery time and retained/pinned bytes.
Do not hide rejected/time-out calls from the latency outcome account.

Phase 1 calibrates bounded local schedules and fake control-plane overhead. Numerical
performance goals, corpus/seed, run durations, rate sweeps, repetitions, fault schedule
and cost envelope must be frozen in a later accepted Phase 6 entry before canonical
execution. The timing defaults in the API document are configuration choices, not
those future acceptance thresholds. No guessed throughput/failover SLA is filled in
as a Phase 0 success criterion.

Future paid work requires renewed quota/IAM/image/source/cleanup/retention/cost
preflight and explicit user triggering/authorization. Keep exact lease/ownership/ID
checks and safe scheduled/manual cleanup behavior. Do not reuse an old sequence,
budget allocation, V5.0 source-bound evidence or a past quota observation as current
authorization. Use three simultaneous voter VMs for quorum evidence; physical
scaling and cross-region claims remain outside this phase.

Each E row must have deterministic and public-process coverage before corresponding
production behavior is accepted. A later cloud plan explicitly maps its selected
cells back to E01-E12; it need not redundantly run every byte-corruption fixture in
paid infrastructure. Full member/set validation, failure retention and an actual
complete cleanup receipt precede any append-only baseline registration.

## Validation performed for this candidate

This batch performs documentation checks only: inherited V5 contract gate, whitespace,
all changed/new Markdown links and anchors, fences, identity/decision/evidence mapping,
public inventory uniqueness and preservation of accepted V5.0 documents. Existing
change-classifier tests can run as tooling checks. It does not instantiate the new
model, compile proposed Java declarations, start clusters, execute faults or claim
consensus, consumer, performance, cloud or publication success.
