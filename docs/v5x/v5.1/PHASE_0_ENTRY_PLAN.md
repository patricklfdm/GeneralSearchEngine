# V5.1 Phase 0 entry plan: automated leadership

**Status:** PROPOSED, revision 0.1, 2026-09-19. Documentation and design review only.

**Review base:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

**Immediate published replication reference:** `5.0.0`, release commit
`e6afb5349c018fe163d4938d7637a4de8854d4ea`.

**Frozen search/storage reference:** published `4.4.0`.

**Design progress:** the user started this task on 2026-09-19. The
[contract candidate](PHASE_0_CONTRACT.md) supplies the six outputs below from
reviewed checkout `09d2bf247f004eb134eb81c59ee88005affafe92`, after planning PR #183.
D01-D12 were accepted through PR #184; [acceptance and Phase 1 authorization](PHASE_0_CHECKLIST.md)
are now recorded. The original base above records entry provenance.

Read the [accepted charter](../DEVELOPMENT_CHARTER.md),
[roadmap](../ROADMAP.md) and [proposed addendum](../NEXT_DEVELOPMENT_ADDENDUM.md).
This document is the task specification for producing Phase 0. It is not the
finished consensus contract and does not authorize Phase 1 or runtime changes.

## 1. Outcome

Produce a reviewable contract for one fixed three-voter replicated shard that can
select a new leader, preserve confirmed committed history, fence superseded leaders,
and automatically regain service after communication among a surviving majority
stabilizes under stated process, storage and scheduling assumptions.

Safety must not depend on accurate failure detection. Progress claims must explicitly
state their timing/communication assumptions; do not promise a universal election
completion time during arbitrary partitions or indefinitely delayed execution.

The user-visible acceptance example is a real three-JVM public consumer with ongoing
operations: kill the current leader, make no manual activation call, observe majority
recovery, verify all acknowledged writes, then rejoin the old leader without
conflicting committed history or an invalid strong read.

## 2. Current task boundary

Allowed work is source inspection, design, counterexample reasoning, documentation,
review of existing test/tooling contracts, and documentation-only validation. Do not
change Java/Python/shell production or test sources, Maven coordinates, dependencies,
workflow definitions, storage fixtures or release records in this planning PR.
No `5.1.0-SNAPSHOT` bump, cluster startup, fault execution, paid cloud run or release.

Do not create declaration-only API classes or a model harness yet; those belong to
Phase 1 after the Phase 0 contract and Phase 1 entry are separately accepted. Phase 0
must specify what those fixtures/harnesses will validate.

The proposed runtime scope excludes follower application reads, membership changes,
sharding, multi-writer reconciliation, hostile-network and Byzantine guarantees,
lease-based optimization as an unreviewed shortcut, and transparent mutation retry.
Preserve existing supported single-node and configured-leader usage.

## 3. Inspect before choosing the protocol

Start with [V5.0 public admission](../v5.0/PUBLIC_ADMISSION_CONTRACT.md),
[public runtime](../v5.0/PUBLIC_ADMISSION_RUNTIME.md),
[public API delta](../v5.0/PUBLIC_ADMISSION_API.md),
[public 1.1 format](../v5.0/PUBLIC_ADMISSION_FORMAT_1_1.md),
[recovery/failure contract](../v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md), and
[release reconciliation](../v5.0/RELEASE_CHECKLIST.md).
Distinguish historical internal 1.0 fixtures from admitted public 1.1 authority.

The inspected implementation surfaces include `ReplicatedSearchEngine`,
`PublicReplicaEngine`, `ReplicaNode`, `ReplicaStore`, `ReplicaEntry`, `ReplicaProof`,
`ReplicaSnapshot`, `ReplicaManifest`, `ReplicaWire`, `AdmissionNode`,
`ReplicationGroupConfig` and bootstrap/replacement operations in the replication
module. Confirm their current definitions; do not rely on this list as a full audit.

Map every configured-leader assumption in public role gates, vote/promise identity,
manifest/configuration digests, wire admission, recovery ancestry and commit proof.
For each, document whether it remains valid, needs an additive mode, or requires an
explicitly versioned migration. A persisted configured leader is not just a runtime
pointer that can be switched after a heartbeat timeout.

## 4. Blocking decision register

At entry, all rows below started **OPEN**. Recommended postures remain design
inputs. The [candidate decision register](PHASE_0_CONTRACT.md#scope-decisions) now
supplies the resolutions subsequently accepted through PR #184. Phase 0
cannot be closed while a safety, compatibility, API or evidence blocker remains
unresolved.

| ID | Required decision | Recommended posture and required analysis |
| --- | --- | --- |
| D01 | Protocol lineage and safety argument | Extend/reconcile the V5.0 authority model; show how election, entry quorum, proof quorum and recovery interact. A named consensus algorithm alone is not an argument. |
| D02 | Durable election state | Define epoch/term, voted-for or equivalent promise, leader identity and incarnation. Specify persistence ordering, crash cuts, duplicate requests and stale messages. |
| D03 | Candidate eligibility and log recovery | Derive admissibility from recoverable committed history, not maximum index alone; address unproven tails, proof-only knowledge and snapshot-covered entries. |
| D04 | Public startup and activation | Specify automatic-mode lifecycle, when start completes, when service is ready, rejoin and close races; preserve configured-mode semantics explicitly. |
| D05 | Leader-read contract | Select a reviewed quorum/read-barrier path for strong reads, including current-epoch authority and applied/published cut. Define legacy and historical-view behavior separately. |
| D06 | Routing and client outcomes | Define leader hints, role errors, before-dispatch rejection, possible-dispatch failure, deadlines and cancellation. No automatic replay of indeterminate mutations by default. |
| D07 | Compatibility and format transition | Separate source/binary API, wire, storage, bootstrap and operating-mode compatibility; choose actual format/version strategy and a supported upgrade procedure. |
| D08 | Loss and replacement assumptions | Distinguish process restart with retained disk from disk loss; specify recovery eligibility and prevent loss of stable vote state from reintroducing an unsafe voter. |
| D09 | Resource and timing bounds | Freeze finite configuration ranges, defaults, queues, retained metadata, transport limits, election retries and operation deadlines; state which are tunable versus persisted identity. |
| D10 | Observability and public evidence | Define protocol events, local monotonic timestamps, leader/read readiness, independently inspectable durable state and external consumer behavior. |
| D11 | Evidence and acceptance | Define model invariants, deterministic schedules, process-crash cuts, compatibility tests, load measures and exact source/result binding before implementation. |
| D12 | Scope and phase authorization | Document exclusions, Phase 1 deliverables, stop conditions and explicit approval records; do not use proposal acceptance as blanket implementation authority. |

If D01 cannot reconcile an assumption with published guarantees, document the exact
counterexample and propose a reviewed format/mode transition. Do not weaken V5.0
semantics, conceal the incompatibility, or silently replace its protocol.

## 5. Required protocol reasoning

### 5.1 Distinguish durable and visible states

Specify at least these different observations: locally appended entry, quorum-durable
entry, proof constructed, proof durable under the required quorum rule, recovered
committed prefix, locally applied prefix, and publicly published view. Include
acknowledged and indeterminate client operations in the same reasoning.

Give a state-transition table with actor, precondition, message, required durable
write, success response, failure response and post-crash recovery rule. Include
candidate eligibility, vote persistence, activation, higher-epoch observation,
step-down, replication and rejoin. Define the commit/linearization points precisely.

### 5.2 Required safety obligations

The eventual contract must explain why acknowledged mutations remain in all future
valid committed histories; why conflicting commands cannot both commit at the same
logical position; and why only permitted committed state is published. Epoch and
voting state must survive allowed crashes before acknowledgments depending on that
state are issued. Older incarnations must not regain write authority by restarting.

A newly elected leader must reconcile required committed state before serving new
application work. The design must explicitly handle an old leader with a minority,
an entry whose response was lost, a commit proof not yet applied everywhere, and
an unproven suffix spanning a leadership change. Define whether/how such a suffix
is retained, adopted, resolved or truncated; copying stock log-truncation rules is
not sufficient for this proof-ledger design.

Snapshots must carry enough admitted authority for the new voting/recovery rules.
Compaction cannot erase the only evidence needed for a safe later election. A
replacement with a lost disk must not be counted as a fully valid voter merely
because it has the same configured endpoint or node name.

### 5.3 Leader reads are a V5.1 blocker

Define a concrete ordering from authority confirmation to selection and publication
of the readable committed cut, with race analysis for concurrent election and writes.
A cached leader hint, local role, past successful heartbeat or diagnostic timestamp
cannot substitute for that argument. Specify the treatment of already-started reads
and explicitly pinned historical views across step-down.

V5.1 need not expose follower reads, but its automatic mode cannot postpone strong
leader-read admission to V5.2. Unsupported strong-read requests reject; they do not
fall back to an older view. Use [etcd's read guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/)
as a terminology comparison only, not a proof of GSE's implementation.

### 5.4 Compatibility is multidimensional

Produce separate matrices for API compatibility, operating modes, on-disk formats,
wire versions and upgrade/recovery paths. A compatible method signature does not
prove safe mixed-version replication. Preserve V5.0's explicit configured activation
path in its supported mode, or identify and review a different compatibility plan.

Recommended initial deployment boundary: homogeneous automatic-mode groups; no
implicit in-place V5.0 authority conversion and no mixed-version rolling upgrade.
Specify a supported offline transition or clearly require a new explicitly bootstrapped
group if that is the accepted choice. Do not claim a whole-group stop alone makes
old bytes readable or permits safe downgrade after new-format writes.

## 6. Evidence contract to design before Phase 1

| ID | Scenario family | Required observable result |
| --- | --- | --- |
| E01 | Stable startup, leader crash, majority recovery | No manual activation; valid authority, preserved acknowledged history, measured service restoration |
| E02 | Concurrent candidates and split votes | No conflicting committed authority; eventual progress only under stated stable conditions |
| E03 | Isolated old leader, delayed higher-epoch messages | Minority cannot commit; no invalid strong reads; rejoin obeys the newer authority |
| E04 | Vote/epoch persistence crash cuts | Restart cannot issue a contradictory vote/promise or resurrect an invalid incarnation |
| E05 | Entry/proof/publication/response crash cuts | Acknowledged history retained; ambiguous client results stay indeterminate unless proven otherwise |
| E06 | Lagging candidate and unproven longer tail | Eligibility follows the accepted history rule, not raw index size |
| E07 | Snapshot transfer, installation and compaction during elections | Preserved election/recovery authority; incomplete transfer never becomes a readable committed view |
| E08 | Old leader restart, disk loss and repeated failover | Correct distinction between restart and replacement; no unsafe reconstructed voter |
| E09 | Strong-read barrier, concurrent write, step-down races | Reads meet the selected contract or fail explicitly; no hidden stale downgrade |
| E10 | Client hints, deadlines, lost replies and cancellation | No unreviewed replay; no false success; bounded retained in-flight work |
| E11 | No quorum, delayed network, slow disk and capacity pressure | Safety preserved; finite resource behavior and classified failures |
| E12 | API/format/mode mismatch and full public consumer | Published compatibility checked; unsupported combinations reject before authority mutation |

The independent model must not call production decoders or infer correctness only
from matching implementation-produced status fields. Plan negative examples that
prove the checker can reject conflicting history, fabricated proof, stale authority
and invalid read success. Distinguish a bounded model exploration from a formal
proof covering all executions.

Fault evidence should retain operation identities, process generations, exit causes,
raw messages where appropriate, pre-reopen authority, timing origins and hashes.
Public tests must compile outside implementation packages and use supported APIs.
Internal hooks may choose crash points, but may not initialize authority or perform
unavailable public operations on the consumer's behalf.

For failover latency, define detection, election, activation, first durable write,
first strong read and end-to-end client outage as separate measurements. Do not
subtract clocks on separate hosts as if synchronized. Freeze numerical goals and
calibration procedure before canonical execution, including offered/completed load,
error outcomes, queueing and recovery work. Reuse the cloud framework, not the old
baseline identity; authorization and quota evidence must be renewed for paid work.

## 7. Concrete Phase 0 deliverables

Create a small coherent document set under `docs/v5x/v5.1/`. These six outputs
were delivered as review candidates and subsequently accepted through PR #184:

| Candidate document | Required contents |
| --- | --- |
| [PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md) | Goal, non-goals, assumptions, D01-D12 decisions, authority hierarchy, compatibility and approval boundary |
| [LEADERSHIP_AND_RECOVERY.md](LEADERSHIP_AND_RECOVERY.md) | State machine, durable transitions, protocol pseudocode, safety arguments and counterexamples |
| [API_FORMAT_AND_COMPATIBILITY.md](API_FORMAT_AND_COMPATIBILITY.md) | Exact proposed API declarations, error/outcome table, mode/wire/storage matrices, format strategy and operator transition |
| [TESTING_AND_EVIDENCE.md](TESTING_AND_EVIDENCE.md) | E01-E12 expansion, independent-model contract, crash points, public consumers, metrics and cloud preflight design |
| [PHASE_0_CHECKLIST.md](PHASE_0_CHECKLIST.md) | Evidence-linked review items, open blockers, reviewed source and actual acceptance identity |
| [PHASE_1_ENTRY_PLAN.md](PHASE_1_ENTRY_PLAN.md) | Declaration/model/network/crash foundation scope; explicit prohibition on early production leadership |

Link each D decision to its document section and each safety/API requirement to one
or more E cases. Every externally visible method should have lifecycle, role,
threading, ordering, timeout, cancellation and error behavior before implementation.
Identify exact format family/version and unknown-version rejection before Phase 1
byte fixtures. Do not select concrete APIs or numeric defaults merely to fill a table.

## 8. Proposed execution sequence after this task

| Phase | Proposed boundary; each requires its own reviewed entry |
| --- | --- |
| 0 | Contract and evidence design only |
| 1 | Version opening, declaration fixtures, independent model, deterministic network, separate-process and fake-cloud foundations |
| 2 | Durable election/epoch state and independently inspected recovery foundations |
| 3 | Automatic leadership and committed-history reconciliation |
| 4 | Complete public admission, safe leader reads, rejoin and client outcome handling |
| 5 | Combined deterministic faults, crash cuts, lifecycle and resource hardening |
| 6 | Controlled performance and separately authorized concurrent cloud evidence |
| 7 | Compatibility, independent consumers, candidate artifacts and reproducibility |
| 8 | Separately authorized signed publication and post-publication reconciliation |

These phases are directional until the new contract accepts their exact boundaries.
Do not defer public bootstrap/lifecycle contracts until after internal implementation.
Public enablement must be accepted before end-user performance or cloud claims.

## 9. Original exit checklist and stop point

The completed source/decision/validation and protected acceptance records now live in
[PHASE_0_CHECKLIST.md](PHASE_0_CHECKLIST.md); the requirements below preserve the entry checklist.

- [ ] Current source and governing documents reviewed; differences from this base recorded.
- [ ] D01-D12 resolved with rationale; incompatible alternatives and counterexamples retained.
- [ ] Complete automatic-mode state machine and V5.0 authority reconciliation reviewed.
- [ ] Strong-read admission and legacy mode compatibility explicitly specified.
- [ ] E01-E12 mapped to independent evidence and public consumers.
- [ ] Exact proposed API/format decisions and finite resource bounds reviewed.
- [ ] Required local links, whitespace and existing documentation gates pass.
- [ ] Changed files remain documentation only; no version/dependency/workflow change.
- [ ] Protected review acceptance and exact-master CI recorded only after they actually occur.
- [ ] Phase 1 remains stopped until separately authorized.

A green documentation gate proves only the checks it actually ran. It does not
validate the consensus design or execute new Java tests. Report skipped jobs as
skipped. Finish Phase 0 with a decision summary and unresolved blockers, not a claim
that automatic failover is implemented or experimentally proven.
