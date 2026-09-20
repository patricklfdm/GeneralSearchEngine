# V5.1 Phase 0 contract candidate: automatic leadership

**Status:** Phase 0 design accepted through PR #184; revision 0.1, 2026-09-19.
Phase 1 subsequently authorized; automatic runtime remains a later-phase obligation.

**Acceptance update:** protected PR [#184](https://github.com/patricklfdm/GeneralSearchEngine/pull/184)
accepted this Phase 0 design at `31b70d08b509ac75037a8eb6386780affc353ed9`.
[Exact-master CI 35487644896](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35487644896)
passed the documentation lane; reactor/compatibility/packaging jobs were skipped.
Original candidate wording below records the reviewed design, not runtime evidence.
The user subsequently authorized Phase 1; see its [foundation record](PHASE_1_FOUNDATION.md).

**Reviewed checkout:** `09d2bf247f004eb134eb81c59ee88005affafe92`.
Relative to the entry plan's `066a04602f7116a0386c645ddfcf4c2e3d41312a` base, this
checkout adds only the nine planning Markdown files/updates integrated by PR #183.
The V5.0 production sources and accepted contracts are unchanged.

**References:** published V5.0 at `e6afb5349c018fe163d4938d7637a4de8854d4ea` for
replication compatibility; published V4.4 for inherited search/storage semantics.
The V5.0 measured source `340df06148bc7d5a25a29a55c3ee928c9472dd09` remains a
separate historical evidence identity.

## Authority and deliverables

The [accepted V5 charter](../DEVELOPMENT_CHARTER.md) governs. This candidate supplies
the six outputs requested by the [entry plan](PHASE_0_ENTRY_PLAN.md); it does not
amend the published configured-leader contract by changing that contract's files.

- [Leadership and recovery](LEADERSHIP_AND_RECOVERY.md): transitions, recovery
  selection, read ordering, safety reasoning and counterexamples.
- [API, format and compatibility](API_FORMAT_AND_COMPATIBILITY.md): complete
  proposed additive surface, operating modes, finite bounds and format decisions.
- [Testing and evidence](TESTING_AND_EVIDENCE.md): independent foundation and E01-E12.
- [Phase 0 checklist](PHASE_0_CHECKLIST.md): current review and acceptance state.
- [Phase 1 entry plan](PHASE_1_ENTRY_PLAN.md): declarations and independent foundations.

Decisions below were accepted through protected PR #184 as design selections with
rationale, not as experimental proof. The original entry register records the initial
OPEN state; this table records the reviewed resolutions. A counterexample that defeats a selection reopens that decision.

## Goal and assumptions

One embedded Java replica per JVM, one shard, exactly three fixed voter identities,
any two intact voters forming a quorum. In automatic mode, eligible survivors can
elect, recover, admit leader writes/strong reads and rejoin without an application
calling an activation method. Keep one ordered application writer and deterministic
whole-operation publication, including bulk and index lifecycle operations.

Safety tolerates delay, duplication, loss, reordering, process suspension and restart.
It assumes trusted non-Byzantine peers, stable acknowledged storage, exclusive local
ownership, no disk-image rollback/cloning, collision-resistant content hashes and
deterministic cooperative codecs/application callbacks. Checksums are not signatures.
The existing private-network boundary applies; no Internet/TLS/authentication claim.

Progress additionally requires an intact communicating majority, sufficient remaining
resource bounds, finite storage/callback execution and a period in which one candidate
can finish recovery without perpetual higher-ballot interference. Randomized timers
encourage that period; they do not prove that a process is dead. There is no universal
failover-time promise, and neither force nor arbitrary Java callbacks have a hard
wall-clock interruption guarantee.

## Scope decisions

| ID | Candidate decision and rationale | Owning specification / evidence |
| --- | --- | --- |
| D01 | Extend the durable-promise, ordered-entry, entry-quorum, proof-quorum and publication pipeline with prepare/accept recovery. In automatic mode a quorum-accepted value is protected even before proof distribution, preventing a delayed valid proof from resurrecting a conflicting branch. Retain the V5.0 pipeline as the configured-mode restriction. | [Protocol lineage](LEADERSHIP_AND_RECOVERY.md#protocol-lineage), E02/E05/E06 |
| D02 | Unique proposer-ranked epochs and forced promises bind candidate and incarnation; a higher promise fences every older accept/proof request. Restart never reuses an election epoch. | [Election](LEADERSHIP_AND_RECOVERY.md#election-and-frozen-recovery-basis), E02/E04 |
| D03 | Select the greatest mutually consistent proven prefix from a frozen promise quorum, then preserve its highest-ballot accepted next value. Neither longest log nor proof absence alone authorizes tail deletion. | [Recovery](LEADERSHIP_AND_RECOVERY.md#recovering-the-prefix-and-the-next-slot), E05/E06/E07 |
| D04 | New automatic factory/configuration/interface; build is side-effect free, start completes local admission, election and rejoin run autonomously, application readiness follows a fresh activation NO_OP. Old start/explicit activation retain their meanings. | [Lifecycle](API_FORMAT_AND_COMPATIBILITY.md#lifecycle-and-method-contracts), E01/E08/E12 |
| D05 | Each automatic application read uses its own newly committed NO_OP and captures the corresponding local immutable view. No leases, cached readiness shortcut, historical-view API or follower reads. This deliberately pays two durability rounds for a simple first read contract. | [Strong reads](LEADERSHIP_AND_RECOVERY.md#strong-read-ordering), E03/E09 |
| D06 | No forwarding or transparent mutation replay. New structured errors distinguish proven NOT_SUBMITTED from INDETERMINATE; cancellation/lost replies remain conservative. Leader hints are local observations. | [Outcomes](API_FORMAT_AND_COMPATIBILITY.md#client-outcomes-and-reentrancy), E05/E10 |
| D07 | Keep configured storage/wire 1.1 and every published descriptor/constant; automatic mode uses explicit 1.2 and a new sealed group. Re-proposal adds an acceptance ballot around immutable entry identity; no mixed-mode/version group or in-place conversion. | [Compatibility](API_FORMAT_AND_COMPATIBILITY.md#compatibility-and-operator-transition), E12 |
| D08 | Automatic recovery covers retained-disk restart and lag. A missing/corrupt/rolled-back voter disk cannot be reinitialized under the old identity. Automatic same-group disk replacement is outside V5.1; use a reviewed new-group backup transition. Existing configured-mode replacement remains supported. | [Loss](LEADERSHIP_AND_RECOVERY.md#restart-disk-loss-and-rejoin), E08 |
| D09 | Reuse existing resource ceilings, serialize consensus slots, reserve bounded control capacity and bind new timing policy to the existing request timeout. Keep explicit ancestry/promise exhaustion; no indefinite-operation or capacity expansion claim. | [Bounds](API_FORMAT_AND_COMPATIBILITY.md#resource-and-timing-bounds), E04/E07/E11 |
| D10 | Local status separates role, readiness, promise, proven/applied positions and observed leader. Evidence has process generations, slot/value/ballot identities and local monotonic timing; no cross-host clock subtraction. | [Observability](TESTING_AND_EVIDENCE.md#observable-history-and-timing), E01/E09/E10 |
| D11 | Independent model and byte inspectors, deterministic network, process-crash scaffold, external consumers and no-GCP planning precede production. Old V5.0 evidence remains immutable and is not automatic-election evidence. | [Evidence](TESTING_AND_EVIDENCE.md), E01-E12 |
| D12 | Phase 0 is documentation; Phase 1 is separately authorized declarations/model/network/crash foundation. No implementation, version bump, cloud run, publication or fabricated acceptance in this batch. | [Next entry](PHASE_1_ENTRY_PLAN.md), [checklist](PHASE_0_CHECKLIST.md) |

## Preserved guarantees and intentional new-mode costs

Successful application mutations still require exact entry bytes forced on a quorum,
their receipt-bound proof forced on a quorum, ordered apply and local publication
before the Future succeeds. Control entries advance LogIndex but not application
sequence or document/index visibility. A mutation without a successful response can
still take effect; automatic recovery does not promise abort or exactly-once replay.

The automatic selection rule may preserve an entry that V5.0's configured recovery
would have discarded when no proof was observed. Such an operation was indeterminate
to its client. This stronger internal preservation rule belongs only to newly
bootstrapped automatic groups; it does not reinterpret published 1.1 bytes.

Configured leaders retain their documented quorum-loss readable view. Automatic
leaders must obtain a new barrier for each strong read and reject without quorum.
The barrier adds log/proof traffic and consumes finite ancestry space, even for a
read-only workload. This cost must appear in performance results and resource docs.

Core/processor dependencies, V4 formats 1.0/1.1/1.2, query truth, bulk atomicity,
ranking, highlighting and current-snapshot cursor semantics remain inherited.
The automatic façade must override all inherited application overloads so defaults
cannot bypass leader admission or split a bulk call into multiple replicated units.

## Explicit exclusions and review priorities

No follower application reads, dynamic membership, automatic same-group disk
replacement, rolling upgrade, V5.0 in-place conversion, transparent write retry,
deduplication service, new client/server daemon, sharding, vector retrieval or V6 code.
Offline bootstrap and cleanup are complete public obligations, not internal-only
shortcuts deferred until cloud testing.

Review must concentrate on D01/D03's accepted-tail rule and preservation of the
charter's protocol lineage, D05's barrier/view race, D07's exact API/format inventory,
and D08's intentionally narrower automatic disk-loss boundary. The selected design
has written safety arguments and falsifying schedules. Phase 0 executed no model,
runtime or paid experiment. Subsequent independent foundation evidence and its limits
are recorded separately; production acceptance remains a later gate.
