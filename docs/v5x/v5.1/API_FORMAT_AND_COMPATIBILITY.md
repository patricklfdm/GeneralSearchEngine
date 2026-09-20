# V5.1 API, format and compatibility candidate

**Status:** Phase 0 design accepted through PR #184; revision 0.1, D04-D10.
Phase 1 adds guarded declarations; the runtime behavior below belongs to later enablement.
**Reviewed source:** `09d2bf247f004eb134eb81c59ee88005affafe92`.

**Acceptance update:** protected PR [#184](https://github.com/patricklfdm/GeneralSearchEngine/pull/184)
accepted this Phase 0 design at `31b70d08b509ac75037a8eb6386780affc353ed9`.
[Exact-master CI 35487644896](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35487644896)
passed the documentation lane; reactor/compatibility/packaging jobs were skipped.
Original candidate wording below records the reviewed design, not runtime evidence.
The user subsequently authorized Phase 1; see its [foundation record](PHASE_1_FOUNDATION.md).

## Additive public surface

All new types live in `io.github.patricklfdm.generalsearch.replication`, in the
existing optional replication artifact. Existing public records, enum members,
constructors, defaults and constants stay unchanged, including
`ReplicatedSearchEngines.PROTOCOL = "gse-replication/1.1"`. Core and processor gain
no dependency or declaration. A separate automatic interface avoids redefining
`activateConfiguredLeader`, `CONFIGURED_LEADER` or the old replication-status record.

The following is the complete proposed public addition inventory. Ordinary record
accessors/canonical constructors and enum compiler methods are implicit; no extra
convenience constructors or mutable setters are authorized. Each top-level type
is a separate source file when Phase 1 is authorized. Method bodies are omitted here.

```java
public record AutomaticLeadershipPolicy(
        int heartbeatIntervalMillis,
        int minElectionTimeoutMillis,
        int maxElectionTimeoutMillis,
        int operationTimeoutMillis) {
    public static AutomaticLeadershipPolicy forBounds(ReplicationBounds bounds);
}

public record AutomaticReplicationGroupConfig<K, T>(
        ReplicationGroupId groupId,
        String configurationId,
        ReplicationNodeId localNodeId,
        List<ReplicationMember> members,
        Path replicaDirectory,
        DurableStorageConfig<K, T> materialization,
        ReplicationBounds bounds,
        AutomaticLeadershipPolicy leadershipPolicy) { }

public enum AutomaticReplicationState {
    STOPPED, STARTING, FOLLOWER, CANDIDATE, RECOVERING,
    LEADER_READY, UNAVAILABLE, FAILED, CLOSED
}

public record AutomaticReplicationStatus(
        ReplicationNodeId localNodeId,
        AutomaticReplicationState state,
        Optional<ReplicationNodeId> observedLeader,
        Optional<ReplicationNodeId> promisedLeader,
        long promisedEpoch,
        UUID promisedIncarnation,
        long activeEpoch,
        long provenIndex,
        long appliedIndex,
        long applicationSequence,
        int pendingOperations,
        Optional<Instant> lastQuorumSuccess,
        List<ReplicationPeerStatus> peers) { }

public interface AutomaticReplicatedSearchEngine<K, T>
        extends DurableSearchEngine<K, T> {
    CompletableFuture<AutomaticReplicationStatus> start();
    AutomaticReplicationStatus leadershipStatus();
}

public final class AutomaticReplicatedSearchEngines {
    public static final String PROTOCOL = "gse-replication/1.2";
    public static <K, T> AutomaticReplicatedSearchEngineBuilder<K, T> builder(
            SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationGroupConfig<K, T> configuration);
}

public final class AutomaticReplicatedSearchEngineBuilder<K, T> {
    public SearchEngineBuilder<K, T> applicationBuilder();
    public AutomaticReplicationGroupConfig<K, T> configuration();
    public AutomaticReplicatedSearchEngine<K, T> build();
}

public final class AutomaticReplicationException extends RuntimeException {
    public enum Reason {
        NOT_LEADER, NOT_READY, QUORUM_UNAVAILABLE, STALE_EPOCH,
        CONFLICTING_HISTORY, CAPACITY_EXCEEDED, PROTOCOL_MISMATCH,
        INTEGRITY_FAILURE, STORAGE_FAILURE, DEADLINE_EXCEEDED,
        REENTRANT_CALL, CLOSED
    }
    public enum Outcome { NOT_APPLICABLE, NOT_SUBMITTED, INDETERMINATE }
    public AutomaticReplicationException(Reason reason, Outcome outcome,
            Optional<ReplicationNodeId> observedLeader, String message);
    public AutomaticReplicationException(Reason reason, Outcome outcome,
            Optional<ReplicationNodeId> observedLeader, String message, Throwable cause);
    public Reason reason();
    public Outcome outcome();
    public Optional<ReplicationNodeId> observedLeader();
}

public record AutomaticReplicationBootstrapRequest<K, T>(
        ReplicationBootstrapSource source,
        Path sourcePath,
        List<AutomaticReplicationGroupConfig<K, T>> replicas,
        Path operationDirectory,
        long maxSourceBytes,
        long maxOperationBytes) { }

public final class AutomaticReplicationStorageOperations {
    public static <K, T> ReplicationBootstrapPlan planBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationBootstrapRequest<K, T> request);
    public static <K, T> ReplicationBootstrapResult applyBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan);
    public static <K, T> ReplicationBootstrapResult resumeBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan);
    public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory);
    public static ReplicationCleanupPlan planCleanup(Path operationDirectory);
    public static void applyCleanup(ReplicationCleanupPlan plan);
}
```

Imports are the existing core builder/durability types, `java.nio.file.Path`,
`java.time.Instant`, `java.util.List/Optional/UUID` and
`java.util.concurrent.CompletableFuture`. Utility classes have private constructors;
the builder constructor is package-private. Record constructors reject nulls and
invalid ranges, defensively copy lists, and retain the existing deterministic,
immutable document/schema/codec obligations. This is an inventory for source and
reflection fixtures, not a request to create Java files in Phase 0.

Automatic group configuration has exactly three unique ordered nodes and endpoints,
contains the local node, and has no permanent leader field. Identity/path validation
inherits the strict existing configuration rules. Member order supplies election
rank and is immutable group identity. Application configuration is captured by
`build` or offline planning, not by every later method invocation.

Status is one consistent local snapshot. Before start: STOPPED, epochs/positions
zero, zero incarnation, empty leader observations and two unobserved peers in
manifest order. After verified genesis, promisedEpoch starts at 1; promisedLeader
is empty and promisedIncarnation is the zero UUID until a real promise. Positions,
counts and epochs are nonnegative; `activeEpoch <= promisedEpoch`. An epoch above
1 requires a member proposer and nonzero incarnation. Peer records are distinct,
exclude self and follow manifest order; list values are defensive copies.
`activeEpoch` is nonzero only for this handle's activated leadership and resets on
step-down. `appliedIndex <= provenIndex`; application
sequence counts application entries plus the imported base. `observedLeader` and
peer progress retain observation semantics, not permission to submit or a fresh
quorum claim. An observed leader is cleared after a newer promise invalidates it.

## Lifecycle and method contracts

| Surface | Admission, ordering and result | Failure/cancellation/close |
| --- | --- | --- |
| Factories, record constructors, `build` | Pure validation/config capture; no codecs, paths opened, threads, sockets or election | Argument exceptions; build yields a STOPPED handle |
| `start` | One shared asynchronous attempt; own/validate sealed 1.2 files and local configuration, reconstruct proven state, start bounded transport/scheduler; complete as locally started follower, without waiting for quorum | Independent caller futures; cancellation does not cancel shared startup; failure releases acquired resources and leaves FAILED; rebuild a handle to retry |
| Election/activation | Internal only after start; promise, recover and publish new activation NO_OP before LEADER_READY | No public manual activation/promotion; missing quorum remains started but unavailable for application calls |
| Single/bulk mutations and create/drop index | Local LEADER_READY, bounded admission before codecs, one writer-ordered entry per call; deterministic validation before authority; success only after entry/proof quorum and publication | Structured mutation outcome; cancellation never undoes admitted work; override inherited bulk defaults |
| All `get/search/searchTopK/page/highlight/explain`, `currentSequence`, application `metrics` | Local LEADER_READY; synchronous call waits for its fresh NO_OP and pinned immutable view; every overload uses exactly one barrier | Throw classified runtime exception; no follower/stale fallback; pin released on all paths |
| `schema`, `field` overloads, `textField` | Pure immutable configuration metadata on any role, before start and after close | Preserve existing pure argument/lookup errors |
| `leadershipStatus` | Any lifecycle state, thread-safe local snapshot, no synchronous IO/network/codec call | Last observations may be stale; does not guarantee the next operation succeeds |
| `durabilityMetrics`, `lastReopenReport` | Initialized local storage diagnostics on any role; application sequence versus log index remains explicit; reopen report stays the inherited empty default | No fresh quorum implication; unopened/failed storage reports its classified unavailable/error condition |
| `checkpoint` | Started healthy voter, local serialized proven cut, no remote ACK or application entry; unresolved next acceptance rejects before replacing authority | Does not erase accepted state or advance global recovery floor; cancellation retains admitted accounting |
| `backup` | LEADER_READY, fresh barrier, writer-ordered captured cut, bounded canonical V4 export and absent-target force/verification | Core backup errors preserved; interrupted publication may be indeterminate; never delete a possibly published target |
| `close` | Any state; stop timers/admission, quiesce authority/control/application work, settle futures, release pins/transport and finally ownership | Repeatable; callback/force timeout retains ownership and reports failure; retry can finish |

All shared state is thread-safe. Read pins protect application slots across recovery
and close; no mutation of a pinned slot. A method may observe a role change after its
initial check, so it must recheck on the ordered path and before authority-sensitive
responses. Already captured reads may finish under the overlap rule in the
[read contract](LEADERSHIP_AND_RECOVERY.md#strong-read-ordering).

Current-snapshot cursors remain local to the owning engine/request and application
snapshot. A NO_OP alone does not advance that snapshot. Mutation, reconstruction or
leader change can invalidate a cursor; there is no automatic cursor transfer,
repinning, historical snapshot service or follower pagination. Existing argument,
document, query, index and cursor exception types remain unchanged where their
original condition applies; role/deadline failures use the new exception family.

## Client outcomes and reentrancy

| Result | Meaning for an application mutation | Retry guidance |
| --- | --- | --- |
| Future success | Exact single operation published after both quorum rounds | Do not replay as another call |
| Automatic exception / NOT_SUBMITTED | This attempt was rejected before any authority-changing IO or replication dispatch; queued work was removed/settled under the writer lock | Caller may submit a fresh attempt after correcting the condition |
| Automatic exception / INDETERMINATE | An authority write or dispatch was attempted; it may later be recovered/committed, even if no ACK was observed | Do not replay automatically; reconcile at the application level |
| CancellationException, process death, lost RPC response | Caller lacks a returned definitive result | Treat mutation as indeterminate unless independently established otherwise |
| Existing business/codec validation exception before authority | Atomic operation rejected without entry/dispatch | Original validation semantics; correct input before retry |
| NOT_APPLICABLE | Read, lifecycle, maintenance or offline operation; the mutation retry classification is inapplicable | Inspect the operation-specific contract, especially backup/bootstrap publication |

Mark the mutation indeterminate **before** the first attempted local authority write
or network dispatch, including an IO error with unknown partial-write outcome.
Failure reason alone cannot establish retry safety: NOT_LEADER/STALE_EPOCH/deadline
after dispatch can still be indeterminate. A caller-constructed exception, leader
hint or later status snapshot is not evidence about an earlier invocation.

No forwarding, durable request deduplication or transparent retry of application
operations is added. Internal exact-byte transport retries are permitted under a
fixed ballot/value and existing bounded retry count. A new epoch is protocol
recovery, not permission to call the user's mutation again with freshly encoded data.

Application calls made reentrantly from a query, codec or completion callback while
the same handle's ordered/pinned context is active reject as REENTRANT_CALL before
admission. Pure schema/status inspection remains permitted. Internal completion must
not execute user callbacks while holding protocol serialization locks. Read barrier
and queue waits use operationTimeout; arbitrary user callbacks and filesystem force
still require cooperation and are not forcibly cancelled.

Reentrant `close`, `start`, checkpoint or backup from the same active callback/pin
context also reject before changing lifecycle or waiting for that context to drain.
An ordinary external close waits for existing pins; it cannot release ownership by
closing a still-used application slot. Completion callbacks run after internal
locks/context are released, so a normal callback on an already completed Future
may issue another operation. Rejection concerns actual active context, not the
mere fact that a Java call is a callback.

## Offline bootstrap and cleanup

Use the existing public bootstrap source kinds and summary plan/result/cleanup
records; their constructors and components do not change. The new operations class
accepts only automatic 1.2 descriptors; existing operations retain their 1.1 meaning.
A summary plan does not authorize effects: apply/resume recompute its full request,
application configuration, format, local policies, paths and inventories.

EMPTY has no source and sequence zero. VERIFIED_V44_BACKUP means an independently
verified V4 backup with the published V4.4 semantics, including one exported through
the supported V5.0 path. It does not mean a replica directory is a V4 backup.
Import preserves source bytes, document order, active indexes and sequence; the new
group has a new GroupId/application-history identity and LogIndex zero. The existing
history derivation from a fresh GroupId remains valid because it does not encode
leadership policy. Reusing a previous GroupId for a new automatic group is forbidden.

Offline plan/apply/resume retains the 1.1 coordinator decision ordering:
PREPARING -> PREPARED -> COMMITTING -> COMMITTED -> all three local seals. All paths
must be absent, disjoint, non-aliased and exclusively owned. All three automatic
genesis authorities are forced before the single global decision. Startup needs
the local seal, not a live coordinator. A half-prepared directory cannot vote.

Planning is read-only; readBootstrapResult is codec-free and validates the committed
receipt under ownership. Cleanup is inventory-bound and limited to proven pre-
COMMITTING output. Missing/ambiguous decision, corruption, unknown members, changed
paths or live ownership reject. Cancellation/interruption cannot reverse a committed
bootstrap. This candidate adds no automatic same-group replacement methods.

## Explicit storage and wire 1.2

Families remain `gse-replicated` and `gse-replication`; automatic storage and wire
both require exact `(1,2)` / `gse-replication/1.2`. V5.0 public `(1,1)` and historical
internal `(1,0)` files, fixtures, decoders and constants remain separate. Unknown
family/version/mode, reserved kind/flag, foreign manifest or extra field rejects
before authority mutation. No downgrade negotiation or version inference from the
presence of a genesis file.

Reuse the GSER/GSRP 48-byte checksummed frame, big-endian scalars, strict UTF-8,
bounded canonical JSON, full-file inventory hashing and explicit nested frames.
Every automatic envelope binds the exact manifest and an explicit proposer identity
in addition to sender/recipient, acceptance epoch/incarnation, trace/sequence, type
and payload. Sender may be a responder; proposer must match the ballot's ranked
owner. Handshake/status without a live campaign use genesis epoch 1, zero incarnation
and an explicit absent proposer. Storage/wire frame minor and body protocol agree.

The following semantic record layout is selected. Phase 1 must freeze the exhaustive
ordered byte/schema catalog and independent positive/negative fixtures before any
production reader/writer; it cannot change these meanings as an encoding convenience.

| Record | Required 1.2 content and rule |
| --- | --- |
| Manifest (kind 1) | Exact storage/wire versions; group/config; genesis epoch; mode AUTOMATIC; three ordered voters/endpoints; codec/schema/index identities; genesis digest/history/base. No configured leader field or covert preferred-owner authority. |
| Node/genesis/seals/plan (existing kinds) | Same ownership, imported-state and all-three publication concepts, explicit 1.2 nested records; local automatic policy and bounds included in plan binding. No replacement origin is admitted. |
| Promise (kind 4) | Manifest, monotonically increasing epoch, ranked proposer, nonzero campaign incarnation; genesis is the only epoch-1 absent-proposer/zero-incarnation record. |
| Immutable entry (kind 5) | Existing slot/op/predecessor/canonical payload structure and origin epoch/incarnation. These origin fields never change on re-proposal. |
| ACCEPT (new kind 24) | Manifest, current acceptance epoch/proposer/incarnation, complete immutable entry, its digest. Force this complete record before the receipt; a bare entry file never proves acceptance. |
| Proof (kind 6) | Manifest, acceptance ballot, slot, stable entry and predecessor digests, sorted distinct voter receipt identities. Validate receipts against acceptance ballot, not entry origin. |
| Snapshot (kind 8) | Genesis base/application sequence, full bounded stable-entry ancestry, terminal proof and canonical application image. Terminal acceptance epoch may exceed origin epoch. |
| Recovery basis (new kind 25) | Local voter, forced promise, basis identity, exact snapshot/ledger inventory, optional complete accepted next record, hashes/lengths. Bound immutable transfer; no live STATUS synthesis. |
| Selected recovery (new kind 26) | New ballot, two complete basis identities, selected prefix digest/index, optional selected next entry and its source acceptance ballot. Force before installation can erase any old accepted next value. |
| Generations/selectors/floor | Bind the complete recovery representation; latest root promise remains monotonic outside application replacement. Inventory includes still-required ACCEPT/selected records and respects two-source floor proof. |

Entry receipt digest domain is `gse-replication/1.2/ACCEPT_ACK`, followed by manifest,
voter, acceptance epoch, proposer, incarnation, slot and stable entry digest in that
order. Proof ACK binds voter, manifest, acceptance ballot, slot and full proof record
digest under `gse-replication/1.2/PROOF_ACK`. Both use length-prefixed strings and the
existing UUID/hash scalars; they are integrity receipts under trusted peers.
Retries compare exact bound bytes. No old 1.1 receipt can become a 1.2 receipt.

Kinds 1-23 retain their numeric identities with explicitly versioned layouts;
unsupported automatic replacement kinds reject. New wire kinds start after the
sixteen historical IDs: 17 PREPARE, 18 PROMISE, 19 BASIS_CHUNK, 20 ACCEPT,
21 ACCEPT_ACK, 22 HEARTBEAT, 23 HEARTBEAT_ACK. COMMIT_PROOF/ACK and snapshot/status
families retain their IDs but use the 1.2 schemas. ACTIVATE_EPOCH and the old APPEND
path reject in automatic mode. HEARTBEAT only observes a matching live campaign
and progress; it cannot establish a readable cut or extend a read lease.

Full disk filenames, field order, exact optional discriminants and positive/negative
bytes belong in the Phase 1 fixture catalog and must be reviewed before Phase 2.
There is no production acceptance of partially specified frames in this phase.

## Resource and timing bounds

The existing `ReplicationBounds` defaults/maxima remain unchanged. Automatic mode
adds these cross-field rules without changing that record's constructor:

- Frame bound at least twice the existing 64-KiB metadata ceiling (128 KiB), so a
  complete maximum metadata frame plus base64/envelope overhead fits. Default 8 MiB
  remains valid. Actual encoded messages are projected and checked before dispatch.
- At least two in-flight slots per peer; reserve one for control responses/promises.
  At most one consensus slot is unresolved. Normal payload admission retains the
  inspected four-frame byte budget and maxPendingClientOperations count.
- Snapshot chunks at least 4096 bytes, at most the configured bound and the projected
  frame capacity. Fragment large bases through the existing bounded transfer pattern;
  never embed complete histories in a 64-KiB promise message.
- Existing 64-MiB complete snapshot/recovery-image limit, 1,000,000 ancestry anchors,
  10,000 promises, 10,000 indexes, source/operation ceilings and local retained/staging
  limits remain. The tighter byte/count limit wins. NO_OP reads consume anchors.
- Duplicate ACCEPT/PROOF retries re-force exact stored records rather than append
  duplicate rows. Re-proposals may add accepted-ballot records; their storage and
  recovery-basis copies count against retained/staging limits. Cleanup cannot remove
  the last selected/unresolved value to regain capacity.
- At most one campaign, one consensus operation, one transfer per peer and one frozen
  basis per requesting peer. Read pins count against maxPendingClientOperations;
  they cannot cause additional unbounded materializations. At most four application
  engine instances coexist during an admitted rebuild (two current, two staged).
  If older pins prevent reclamation, reject/defer the rebuild rather than allocate more.

Let R be requestTimeoutMillis. `AutomaticLeadershipPolicy.forBounds` proposes
heartbeat=R, election range=[3R,5R], operation timeout=4R, using checked arithmetic.
For the inherited default R=5000 ms these are 5 s, 15-25 s and 20 s. The rationale
is to keep election suspicion outside several complete request windows and permit
two durability rounds plus queue/dispatch allowance for a fresh read; these are
configuration defaults, **not measured latency guarantees or acceptance thresholds**.

Constructors require positive values; heartbeat <= the inherited 300,000-ms request
ceiling, minimum election >=3*heartbeat and maximum election >=minimum+heartbeat.
Maximum election <=5*300,000 ms; operation timeout <=4*300,000 ms. Cross-validation
with the selected bounds additionally requires heartbeat >=R and operation timeout
>=2R. Policies are configurable at bootstrap, bound into local seals/plans and not
hot-swappable; they need not be identical on all voters. Arithmetic never wraps.

Election delay is independently randomized in the configured inclusive interval.
For an activated leader, a fresh same-ballot heartbeat sequence resets suspicion
even when there are no application writes; an idle healthy group must not elect
continuously. Before activation, only an advancing verified recovery stage/chunk
resets the recovery-progress timer. Replayed sequences, arbitrary status traffic or
unchanged recovery heartbeats cannot suppress elections forever. A heartbeat does
not confer read authority. At most maxRetryAttempts retries per peer exchange, using the
existing backoff. A stalled exchange ends the attempt; the node retries a campaign
with a newer epoch after a new randomized delay. Transfers advance bounded chunks;
repeated campaigns never accumulate old basis pins, timers or executor tasks.

Every application deadline starts at invocation and covers queue/barrier waits.
For mutations, expiration before authority is NOT_SUBMITTED; after possible mutation
authority it is INDETERMINATE. Read errors use NOT_APPLICABLE and release their own
accounting once work settles. Hard
force/callback termination is not promised. Sustained no-quorum can exhaust the
finite promise budget and then fails closed; automatic mode does not claim unlimited
campaigns or indefinitely growing history. Increasing these ceilings needs evidence
and an explicit later contract, not an undocumented retry loop.

## Compatibility and operator transition

| Axis | Supported candidate behavior | Rejected or unqualified |
| --- | --- | --- |
| Published source/binary API | All V1-V5.0 descriptors/constants unchanged; new automatic types additive | Replacing old records, adding required methods to third-party implementations, reinterpreting old reasons/roles |
| Core/processor | Existing embedded/single-node APIs and artifacts | Mandatory networking/replication dependency |
| Configured operation | Existing factory, 1.1 bootstrap/start/manual activation/quorum-loss reads/replacement | Silently enabling elections or strong reads on an old handle |
| Automatic operation | New factory, 1.2 group, autonomous election and strong leader reads | Follower reads, configured activation, same-group disk re-enrollment |
| Storage/wire | Exact mode/version/manifest admission | 1.1/1.2 mixing, unknown minors, implicit conversion or downgrade |
| Deployment | Homogeneous qualified artifact set, explicit stopped migration to a new group | Mixed-version rolling upgrade; protocol equality alone is not a binary-compatibility qualification |
| Search/backup truth | V4.4 semantics and canonical V4 transfer | Reinterpreting replica authority as a V4 live store or an ordinary backup |

Unchanged configured 1.1 wire does not advertise artifact build/version; do not
claim it can detect every mixed-binary deployment. Homogeneous deployment is an
operator precondition, and no rolling-upgrade claim is made. Automatic 1.2 rejects
V5.0's 1.1 wire before authority changes. Future same-protocol artifact combinations
still need explicit qualification; a successful handshake is insufficient evidence.

Supported configured-to-automatic transition is source-preserving and offline:

1. Stop application submissions to the old group, settle/reconcile indeterminate
   operations and establish one complete resolved committed cut. Do not use a stale
   isolated-leader view while acknowledged or ambiguous later work remains unresolved.
2. Export and independently verify its canonical V4 application backup; retain old
   volumes and backup. Stop the old group before application cutover.
3. Plan/apply bootstrap to three absent automatic targets with a **new** GroupId,
   complete matching application configuration, distinct paths and reviewed policies.
4. Start all new nodes, let election/recovery occur, compare a strong read with the
   backup oracle, then direct application submissions to the new group.
5. Once new writes succeed, reopening the old group as current truth is not rollback.
   An application-level reverse transfer would require its own quiesced export/new
   group procedure and explicit loss/compatibility review; it is not a binary downgrade.

The same new-group procedure restores redundancy after an automatic voter disk is
lost while two survivors can still supply a fresh resolved cut. If that cut cannot
be established, reject migration rather than invent a safe data-loss-free recovery.
No online dual-write, identity reuse, automatic cleanup of old authority or live
volume cloning is authorized. Directory/operation cleanup uses only reviewed exact
ownership/inventory plans under the corresponding format's public operations.
