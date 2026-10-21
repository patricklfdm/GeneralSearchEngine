# V5.3 Phase 0 entry — membership authority

**Status:** local research and design entry; Phase 0 contract not frozen.
**Reviewed source:** `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`.
**Predecessor:** V5.2 development source, not a published V5.2 release.

## Outcome

Allow an operator to add, remove or replace a voter through a serialized,
recoverable operation, preserving committed search history and explicit read
semantics. A joining replica first catches up as a non-voter. Losing a majority
does not authorize editing membership files or discarding promises to recover
availability. Same-version rolling restart is separate from mixed-version upgrade.

## What the current source actually assumes

Java paths below are under
`general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/`.

| Actual surface | Current assumption | V5.3 obligation |
| --- | --- | --- |
| `AutomaticReplicationGroupConfig.java` | Exactly three members; local node must be a voter; list order determines proposer rank | Separate immutable group/history from mutable, proven membership and learner identity |
| `AutomaticRecords.java` (`context`, `semantics`) | Proposer rank uses `(epoch-2) % 3`; exactly two SELECTED bases and two FLOOR sources; manifest has three distinct nodes/endpoints | New reviewed ballot, selection and floor rules; count changes alone are insufficient |
| `AutomaticRecordCatalog.java`, `AutomaticRecords.java` | GSER 1.2 decoding and bounded record catalog; proofs bind manifest, voter, ballot, index and entry digest | Specify explicit version and configuration-bound certificate bytes; do not reinterpret old records |
| `AutomaticProtocol.java` (`beginCampaign`, response handling, `commit`) | One frozen local basis plus one peer fixes selection; `quorumPeer` carries ACCEPT/PROOF acknowledgements | Generalize election/recovery selection and both durable phases, not just write acknowledgement count |
| `AutomaticRecovery.java`, `AutomaticStore.java` | Selected bases, accepted/proven tails, floors and snapshots reconstruct one fixed manifest history | Recover partial transitions across ballots and compaction without inventing membership from a status sample |
| `AutomaticWire.java`, `AutomaticWireCatalog.java` | Peer/manifest-bound frames and replies, fixed catalog limits | Admit learner transfer traffic without granting voting authority; bind membership era and reject stale frames |
| `AutomaticRuntime.java`, `AutomaticRejoin.java` | Peer ownership and recovery routes derive from the opened manifest/configuration | Serialize live route additions/removals with protocol state and outstanding exchanges |
| `AutomaticReplicatedSearchEngine.java`, `PublicAutomaticEngine.java` | Public lifecycle, strong default reads, explicit policies; no membership API | Additive bounded operation surface with queryable outcomes; preserve existing read/mutation contracts |
| `ReplicaReadToken.java`, `AutomaticReadCut.java` | Token binds group/history and immutable manifest digest; no membership epoch field | Decide stable root identity versus transition certificate identity; never accept a wrong-history token to ease migration |
| `AutomaticBootstrap.java`, `AutomaticAdmission.java` | Genesis and public bootstrap receipts bind fixed authority | Define new-group V5.3 bootstrap, learner admission and exact supported migration before touching disk formats |
| V5.0 `ReplicationReplacementPlan` and storage operations | Same-NodeId replacement in a configured fixed manifest | This is not online automatic membership replacement; keep the capability boundary explicit |
| V5.2 CI/shared build/cloud consumers | Exact source, original attempt, frozen workload and finite inventories | Reuse infrastructure after design; no copied V5.2 result may qualify new membership behavior |

Some historical `AutomaticFoundation` comments still describe disabled Phase 1
runtime. Follow the live public implementation and its tests, not that comment,
when identifying capabilities inherited from V5.2.

## Blocking decisions

The initial choices in [membership design](MEMBERSHIP_DESIGN.md) are proposals.
Every row needs a concrete specification and executable counterexamples before
production changes; an arithmetic quorum test closes only part of D02.

| ID | Required decision / completion |
| --- | --- |
| D01 | Group/history, genesis root, configuration generation/digest and endpoint/incarnation identity; token continuity and new-group transfer |
| D02 | Joint transition protocol, including which configuration governs each partially accepted log entry, election, activation, ACCEPT and PROOF |
| D03 | Configuration-aware ballot total order and generalized frozen-basis selection; committed-prefix preservation across competing transitions |
| D04 | Learner admission, catch-up certificate and replacement fencing; old and new disks cannot both vote as the same incarnation |
| D05 | Stable operation identity, exact payload binding, duplicate/query behavior, client timeout/cancel semantics, bounded terminal-history retirement |
| D06 | Durable transition records, snapshot/compaction chain, crash prefixes, recovery from partial proofs and old configuration replicas |
| D07 | Removed leader/node behavior for strong and stale reads, maintenance/rolling restart, explicit data cleanup permission |
| D08 | Exact public signatures/reasons, byte families/versions/limits, compatibility consumers and migration restrictions |
| D09 | Finite storage, voter/learner/transfer/queue/tombstone bounds and overflow handling, including peak old/new union |
| D10 | Deterministic schedules, real public consumers, independent physical checker, performance and cloud workload freeze |

## Research progress on blocking decisions

The [durable ballot/handoff batch](BALLOT_AND_HANDOFF_RESEARCH.md) narrows D01/D03
with explicit identity/ballot proposals and tests one-slot persistent recovery.
D02/D06 now have a retained cross-view fork counterexample and an explicit list of
handoff obligations. These are partial research results; no blocking row is marked
complete, and the Phase 0 contract is not frozen.

## Phase 0 deliverables still to freeze

- `PHASE_0_CONTRACT.md`: resolved decisions and authority/state matrix.
- `MEMBERSHIP_PROTOCOL.md`: exact transition, election and recovery algorithm,
  including late messages, accepted-only branches and snapshot closure.
- `API_FORMAT_AND_COMPATIBILITY.md`: exact additive declarations and byte fixtures.
- Expanded [testing/evidence plan](TESTING_AND_EVIDENCE.md): numerical limits,
  schedules, negative evidence and independent verification inputs.
- `PHASE_0_CHECKLIST.md`: decision-by-decision review, local checks and later
  protected acceptance, without claiming the predecessor has published.
- `PHASE_1_ENTRY_PLAN.md`: version alignment, disabled API fixtures, full model,
  deterministic transport and process scaffolding before runtime enablement.

The entry batch intentionally leaves these files absent rather than publishing
empty or supposedly accepted contracts. Progress is recorded in
[development status](DEVELOPMENT_STATUS.md).
