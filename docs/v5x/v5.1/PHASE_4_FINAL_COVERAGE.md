# V5.1 Phase 4P: final coverage reconciliation

**Status:** local qualification passed. Batches A–O are
accepted through PR #207, master `1a043615ec4a8de5b7f110d999c5f7268e5e165c`,
[exact-master CI 35794875603](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35794875603).
Protected Batch P and full Phase 4 acceptance remain pending.

This reconciles the accepted [E01–E12 matrix](TESTING_AND_EVIDENCE.md#scenario-matrix).
It adds missing witnesses without changing the protocol, public API, resource limits,
read semantics, or the accepted model bounds. Production transport gains only an
`AFTER_REQUEST_READ` call on its existing internal observation seam (default no-op),
so the real request can pause before dispatch. A transport regression verifies that
a second connection proceeds during that pause. Phase 5 and paid cloud remain separate.

## Four new public process witnesses

Run `scripts/verify-v51-phase4-final-coverage.sh --skip-build` after reactor package.
The gate compiles the external public consumers against candidate JARs, starts real
TCP voters, and retains source/JAR hashes, every attempted operation, raw wire/force
traces, process identities, authority inventories and failed-case receipts under
`target/v51-final-coverage`. The existing public lifecycle CI lane always uploads it.

| Case | Actual schedule | Required independent evidence |
| --- | --- | --- |
| `heartbeat-request` | Hold a naturally generated HEARTBEAT after request read on node-3; isolate the old leader; the other majority elects and serves a read/write; force a higher promise before releasing the old request. | Same-process pause → higher PROMISE force → release → actual STALE_EPOCH reply; old leader refuses later read/write; retained restart and later service preserve the complete chosen history. |
| `heartbeat-response` | Hold an actual HEARTBEAT_ACK after response read on the old leader; form a new majority and process a higher promise on the old leader before delivering the ACK. | Exact original request/response bytes, higher fence before receipt, then public read/write refusal; no old-epoch revival. |
| `one-disk-loss` | Complete a public backup, SIGKILL node-3, move its authority directory out of service, attempt public startup twice, and continue read/write service with the other two voters. | Missing directory stays absent; both starts fail; later majority write/read is real. A fresh GroupId imports the earlier verified backup cut, deliberately excluding the later write. |
| `two-disk-loss` | Complete a backup, SIGKILL node-2 and node-3, remove their authority directories, attempt both starts twice, then attempt a read/write on the remaining voter. | Both absent voters remain rejected; the minority reports conservative refusal. A fresh GroupId imports the exact verified backup cut and subsequently serves new writes. |

Disk loss means **replication authority is unavailable**, while existing application
materializations cannot enroll replacement voters. It is not physical device failure
or recovery of unreadable sectors. Displaced directories under `lost/` are immutable
forensic witnesses. Normal inspection/startup still rejects copied/stale paths.
The explicit archive inspector requires the original path to remain absent, exact
pre-move hashes, and the original sealed path, then checks every retained record.
It neither skips lost voters' history nor repairs/opens them as runtime authority.

Both old and new groups include a separate retained JVM restart. Their histories and
physical oracles are checked independently. The same backup is restored by the
hash-pinned published V4.4 core in a separately compiled process; document values,
order, sequence and imported index definitions must match. New group and history
identities must differ. Backup/source bytes remain unchanged.

Negative evidence removes the higher force/delivery/refusal, fabricates success,
changes the epoch/archive/cut/order, drops a startup attempt or substitutes an
unpublished control. Common history negatives also reject stale/partial/reordered
reads, borrowed barriers and missing proof forces. A PASS receipt alone is insufficient.

## E01–E12 disposition

The model gate remains the Phase 1 bounded scheduler and I01–I08 mutation checks.
It models logical durable decisions, not JVM scheduling or physical device behavior.
The named Java tests below are deterministic kernel/storage witnesses executed by
reactor package; public gates add actual process and API observations. Every row
has both layers; not every combinatorial schedule has been enumerated publicly.

| Row | Public schedules and gate suffix (`verify-v51-…sh`) | Deterministic/physical witness and remaining boundary |
| --- | --- | --- |
| E01 | A `phase4-bootstrap`: EMPTY and imported genesis; B `phase4-public-runtime`: leader kill, majority recovery and retained rejoin; E `phase4-public-recovery`: `import-halt`, `import-kill`; H `phase4-public-bounds`: no quorum. | `V51AutomaticProtocolTest.timerElectsAndPublicationMustCompleteBeforeReadiness`; each physical oracle reconstructs chosen entries, fresh activation NO_OP and complete acknowledged prefix. Local start is FOLLOWER admission, not leader readiness. |
| E02 | F `phase4-public-protocol`: competing campaigns/asymmetric requests/responses; I/J `phase4-public-promises` / `phase4-public-candidates`: peer/candidate promise cuts; N `phase4-public-selection`: `duplicate-prepare`, `higher-ballot-accept`, `higher-ballot-proof`. | `higherPrepareIsServicedWhileAnOlderCampaignWaitsForNetwork`, `lostAcceptAndProofRepliesRetryExactRecordsWithoutDuplicateRows`; progress is observed after healing within the declared finite schedule, not an unconditional timing guarantee. |
| E03 | D `phase4-public-faults`: isolated leader and capture/promise order; F asymmetric partitions; N delayed ACCEPT/PROOF replies; P `phase4-final-coverage`: both crossed-heartbeat cases and old-handle refusal/rejoin. | `healthyIdleHeartbeatsSuppressRepeatedElections`, `replayedOrNonprogressingRecoveryHeartbeatsDoNotSuppressElection`, `publicationAfterStepDownCannotRestoreReadiness`; correlate raw messages and process-local order, never clocks across JVMs. |
| E04 | I/J write/force/basis/ACK/PREPARE halt+kill schedules and retained reopen. | L `phase4-resources`: actual 10,000-row promise limit and ranked overflow are internal store/kernel fixtures. These are not 10,000 public elections. Independent pre-reopen inventories establish retained authority. |
| E05 | C `phase4-public-qualification`: read/view/response loss; D ACCEPT/PROOF/publication cuts; K `phase4-public-pressure`: delayed exact force; O `phase4-lifecycle-hardening`: actual partial ACCEPT/PROOF write failures. | `writeCompletionRequiresBothProofAcknowledgementsAndLocalPublication`, `entryChosenWithoutProofSurvivesAnotherCandidatesPrepareQuorum`, `applicationFailureCannotBecomeClientSuccess`; bind invocation, forced votes, proof ACKs, publication and response; uncertain writes are not replayed. |
| E06 | F minority selected/discarded; N `hidden-proof`, `lagging-candidate`, delayed chosen mutation across a higher ballot. | `V51AutomaticRecoveryTest.equalBallotConflictsAndMixedBasisIdentityReject`, `highestOriginDoesNotOverrideHigherAcceptanceBallot`, `higherCampaignRetainsPreviouslySelectedButUnprovenVote`; conflicts and malformed mixed bases remain internal fixtures, not manufactured valid public votes. |
| E07 | F basis/snapshot progress/selector halt+kill; G `phase4-public-reclamation`: source floors/deletion cuts; N `epoch-during-basis`; O held query with installed snapshot and queued reconstruction. | `higherAcceptedTailIsNotDeletedByAnOlderTwoSourceFloor`, `sameVoterOrDifferentCutCannotBecomeDurableFloor`, `transferProgressRetriesAndRestartBindExactImage`; O proves view release precedes actual reconstruction, not simultaneous replacement of a pinned application. |
| E08 | B–O retained rejoin/crashes; E missing promise/acceptance and copied path/voter; P one/two lost authority directories, repeated failed starts, published-control restore and fresh-group transition. | `V51PublicRuntimeTest.missingAuthorityFailsWithoutCreatingVotersAndRequiresNewHandle`; archive path/hash negatives; no same-group disk replacement, no surviving-minority service claim. |
| E09 | B façade; C rich query/ranking/highlight/explain/page comparison; D capture fencing; E `cursor-rebuild`; O pinned old view and recovered prefix; P metadata calls. | `completeFacadeUsesOneEntryPerCallAndNoOpKeepsPageCursor`, `expiredReadWaitingToCaptureNeverInvokesItsQuery`; each observed successful ordinary read has its own post-invocation NO_OP and exact immutable view. Full method map below. |
| E10 | C/D uncertain response cuts; E cancel/close/pins; H rejection; K pressure drain; M `phase4-backpressure`: queued deadlines, reentrancy/callbacks; O partial I/O/quarantine and repeated timeout cleanup. | `queuedDeadlinesAndCancellationDoNotInvokeInvalidArgumentsOrAppend`, `oversizedEncodingIsNotSubmittedButFirstAuthorityIoIsIndeterminate`, `closeRetainsOwnershipWhileReadViewIsActiveAndRetryReleasesIt`; explicit NOT_SUBMITTED versus INDETERMINATE; no retry hiding uncertainty. |
| E11 | H tiny limits/no quorum; K transport reservations/slow force; L staging/retained capacity and surviving majority; M callback admission; O three queued-timeout waves and three network-timeout rounds. | L counters and M 32/16 mailbox saturation remain internal. Samples verify finite declared bounds/reservation balance, not unbounded endurance, arbitrary blocked control accumulation or OS exhaustion. |
| E12 | A bootstrap/resume/cleanup; H public mode/schema/manifest/configuration and old wire/disk refusal; compatibility lane external V1–V5.0 consumers; P explicit bidirectional decoder checks. | `V51BootstrapTest.cleanupRejectsUnknownMembersLiveOwnersAndAmbiguousDecision`; `V51VersionBoundaryTest` plus original format fixtures. Ambiguous cleanup is an internal public-API test; no ambiguous authority is deleted. |

## Complete runtime method inventory

`PublicSemanticConsumer` is compiled independently against candidate and published
V4.4 core. Its rich scenario runs three public voters in **one JVM**. Separate
qualification/fault/lifecycle scenarios use three actual JVMs. Rich query equivalence
must not be described as a multi-process crash test for every query overload.

| Method / overload | External witness | Additional ordering / failure witness |
| --- | --- | --- |
| `add`, `update`, `remove` | `PublicSemanticConsumer.exercise` → `AdmissionSemanticModel.populate`; `PublicRuntimeConsumer` add/update | B failover; full façade kernel test |
| `addAll`, `updateAll`, `removeAll` | `PublicSemanticConsumer.exercise`; tagged bulk histories in `PublicQualificationConsumer` / `PublicLifecycleConsumer` | C–P chosen-byte/linearizability oracles; D/O interrupted writes |
| `createIndex`, `dropIndex` | Rich consumer drops/recreates category and compares reports to V4.4 | Full façade kernel test; checkpoint/backup imported index inspection |
| `get` | Rich consumer `get(5)` | Full façade test explicitly counts its fresh barrier |
| `search(Query)` | Rich model predicates, equality/prefix/range/terms/boolean queries; public histories use tagged match-all | Captured raw application/order and per-call barrier; D/O pin/epoch overlap |
| `search(SearchRequest)` | Rich phrase/fuzzy/text requests | Full façade per-overload barrier |
| `search(SearchPageRequest)` | Rich cursor pages; `PublicCursorConsumer` | NO_OP preserves cursor; mutation/rebuild invalidates as specified |
| `search(HighlightedSearchRequest)` | Rich exact highlights compared to V4.4 | Full façade per-overload barrier |
| `searchTopK(RankedSearchRequest)` | Rich scores/order compared to V4.4 | Full façade per-overload barrier |
| `explain(SearchRequest, K)` | Rich explanation reports compared to V4.4 | Full façade per-overload barrier |
| `metrics`, `currentSequence` | Rich index count/sequence; runtime consumer diagnostics | Full façade proves these strong reads use barriers |
| `schema`, `field(String)`, `field(String, Class)`, `textField` | Rich consumer checks canonical field identity and records names | Metadata only; no follower freshness promise |
| `start`, `leadershipStatus` | Runtime startup cancellation/repeated start and every worker's local hint | Stopped/failed/closed behavior and local-only startup in `V51PublicRuntimeTest`; hints may race dispatch |
| `checkpoint`, `backup` | B maintenance and published V4.4 restore; C rich backup; P backup → fresh group | Capacity refusal remains visible; checkpoint is not a reclamation floor; P binds completed backup to its released barrier/view |
| `durabilityMetrics`, `lastReopenReport` | Runtime checkpoint sequence; rich OPEN diagnostics and empty automatic reopen report | B failed/closed diagnostics regressions; these are local diagnostics, not strong-read substitutes |
| `close` | Every public worker; E close-pinned/reopen; M reentrant callbacks | Ownership retained while active work/pins remain; original handle cancellation/close semantics |

Factories/builders/configuration are also covered by the frozen public API inventory
and B startup tests. Offline methods `planBootstrap`, `applyBootstrap`,
`readBootstrapResult`, `resumeBootstrap`, `planCleanup`, `applyCleanup` are exercised
by A's separately compiled `AutomaticOfflineConsumer` and force/deletion fixtures.
This table inventories the declared automatic runtime façade, not every overload
of every core builder or query factory.

## Compatibility directions

| Boundary | Exact check | Layer |
| --- | --- | --- |
| Disk 1.0/1.1 → automatic 1.2 | H `disk-v10` / `disk-v11`, two unchanged failed public opens; P `automaticStorageRejectsBothOlderMinorsWithValidChecksums` | Public admission plus internal decoder |
| Disk 1.2 → legacy 1.0 / configured 1.1 | P `legacyAndConfiguredDiskReadersRejectAutomaticRecords`; H `configured-on-automatic` | Explicit internal version boundary plus public mode admission |
| Wire 1.0/1.1 → automatic 1.2 | H `wire-v10` / `wire-v11` at live endpoint; P all frozen wire fixtures with correctly rechecksummed foreign minors | Actual endpoint plus internal decoder |
| Wire 1.2 → configured/legacy decoder | P `wireReadersRejectForeignMinorsInBothDirections` over all frozen automatic messages | Internal; not claimed as a reverse live-endpoint campaign |
| Mode/configuration/group/schema/manifest mismatch | H `automatic-on-configured`, `configured-on-automatic`, configuration/group/schema/bounds and wire descriptor cases | Public rejection and unchanged authority, with healthy controls |
| Valid old clients / formats | Existing external API compatibility lane and hash-pinned published controls; original 1.0/1.1 fixture suites | Separate compatibility/control lane, unchanged |
| Absent-target bootstrap; partial decision / ambiguous cleanup | A process halt/kill/resume and deletion interruption; `cleanupRejectsUnknownMembersLiveOwnersAndAmbiguousDecision`, `partialCommitRowIsNotCleanupAuthorityButExactResumeCanCompleteIt` | External lifecycle plus internal public offline API fixtures |

## Acceptance still required

After this batch's local gates pass, the protected full CI on the submitted source
must pass. Record the resulting merge SHA and exact-master run, review all E-row
layer boundaries above, then make an explicit Phase 4 acceptance/Phase 5 entry
record. A locally generated receipt or this coverage table cannot approve itself.

## Local validation

Base: `1a043615ec4a8de5b7f110d999c5f7268e5e165c`; source inventory and JAR hashes
are retained by each gate. Final public matrix:
`target/v51-final-coverage/run.dFjNH8/evidence/receipt.json`.

- Four cases PASS, 24 runtime JVM instances, six distinct rejected startup attempts,
  and 58 negative variants, including three backup-capture mutations per disk case.
- Complete reactor package passed: 853 tests reported, four skipped, no failures/errors.
  The subsequently added receive-observation call and version checks passed the final
  targeted transport/version run: nine tests. Production protocol behavior is unchanged.
- Existing public qualification: six halt/SIGKILL schedules and the independently
  compiled V4.4 rich semantic/backup comparison PASS, including new metadata calls.
  Receipt: `target/v51-public-qualification/run.QslDnK/evidence/receipt.json`.
- Final Phase 1 foundation PASS: all 220 V5.1 Python tests, bounded model/negative
  checks, formats and 39-document contract. Evidence:
  `target/v51-foundation/run.NmU6yw/evidence`.
- CI routing/toolchain fixtures: 25 tests PASS. YAML structure comparison confirms
  all prior jobs/steps/settings preserved, adding exactly one gate and one always-upload;
  shell syntax and whitespace checks PASS.

Logs and counts: `target/v51-final-coverage/validation-summary.json`,
`reactor.log`, `transport-tests-final.log`, `qualification-complete.log`,
`public-qualification.log`, `foundation.log`, `ci-tests.log` in that directory.
These local results do not replace protected CI on the submitted source.
