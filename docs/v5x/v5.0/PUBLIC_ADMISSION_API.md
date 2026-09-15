# V5.0 public-admission API delta

- **Status:** API amendment accepted in PR #151; declarations accepted in PR #153; [Step B](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md) implements configuration/transfer and typed offline operations
- **Behavior:** [Public-admission contract](PUBLIC_ADMISSION_CONTRACT.md)
- **Gates:** [Implementation and acceptance plan](PUBLIC_ADMISSION_ENTRY_PLAN.md)

## Compatibility decision

Preserve existing constructors, record components and method descriptors. Add typed
bootstrap overloads instead of changing `ReplicationBootstrapPlan` or placing codecs
in a supposedly codec-free plan. Both old under-specified bootstrap methods retain
their fail-before-side-effects `UnsupportedOperationException`; their documentation
will direct callers to the typed overloads. The existing builder entry point becomes
usable only after all public-admission gates pass.

The one accepted constant-value change is
`ReplicatedSearchEngines.PROTOCOL: "gse-replication/1.0" -> "gse-replication/1.1"`.
This is an explicit change to the unpublished V5 fixture, including Java constant
inlining implications. Recompile V5 consumers; reject old protocol peers instead of
negotiating down. It changes no published V1–V4.4 constant or artifact identity.

Core needs an additive, replication-independent configuration/backup handoff because
its existing builder and canonical backup implementation are private. No reflection,
split-package access, mandatory replication dependency or new core live-writer mode
is authorized. Existing core construction, durability and processor behavior remains
the published V4.4 behavior. The additions below are the complete approved API scope;
additional public declarations or changes need a visible amendment, not a regenerated
fixture that conceals them.

## Core additions

These signatures are declared by [Step A](PUBLIC_ADMISSION_FOUNDATION.md); each type
is a separate public source file. Record constructors validate nulls/bounds and
defensively copy lists. Configuration capture/reconstruction, backup transfer and
offline operations were reserved at the Step A boundary; [Step B](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md)
implements them.
The engine builder and administrative interface defaults remain reserved until Step C.

```java
// io.github.patricklfdm.generalsearch.engine
public record SearchEngineConfiguration<K, T>(
        SearchSchema<T, K> schema,
        List<IndexDefinition<T>> indexes,
        SnapshotEngineConfig config,
        PlannerConfig plannerConfig) {
    public SearchEngineBuilder<K, T> newBuilder();
}

// Add to SearchEngineBuilder<K, T>
public SearchEngineConfiguration<K, T> configuration();
public DurableApplicationState<T> readDurableBackup(
        Path backupDirectory, DurableVerificationConfig<K, T> expectedConfig,
        long maxSourceBytes);
public DurableBackupResult writeDurableBackup(
        DurableApplicationState<T> state,
        DurableStorageConfig<K, T> storageConfig,
        DurableBackupRequest request);

// io.github.patricklfdm.generalsearch.durability
public record DurableApplicationState<T>(
        UUID history,
        long sequence,
        List<T> documents,
        List<IndexDefinition<T>> indexes) { }
```

`configuration()` snapshots every builder option without creating an engine or
thread. `newBuilder()` recreates that configuration; manual, annotated and extended
schemas retain their canonical Field/TextField instances and query settings. Lists
are immutable; application objects/codecs retain the existing deterministic/immutable
caller obligations. A later change to either builder does not change its snapshot.

`readDurableBackup` is a bounded, source-preserving structural and typed pass. It
returns the exact history/sequence, canonical live-document order and active durable
indexes. It does not open a live store or drop dynamic indexes in favor of defaults.
The read builder must describe the complete matching schema/index configuration;
positive `maxSourceBytes` caps the complete input bundle before decoding, with a
hard maximum of 1 TiB. `writeDurableBackup` validates the typed state against the
builder's schema and uses the state's active index list, preserving dynamic changes
instead of substituting the builder's startup indexes. It writes a standalone
checkpoint-only bundle with the supplied history and sequence, using existing V4
encoders, target checks and verification. It opens no live V4 WAL, advances no
sequence and cannot add authority to a replica. `storageConfig.directory()` is an
identity/path exclusion anchor for this operation, not a scratch live-store target;
it is never created or modified by export. Output format follows `storageConfig.format()`.
Unsupported indexes, conflicting IDs, noncanonical codecs, invalid sequence/history
and capacity overflow reject using existing core validation/operation classifications.
The document list is bounded before materialization, and export freezes canonical
bytes before asynchronous replication work can advance the captured view.

## Replication value additions

All types below are in `io.github.patricklfdm.generalsearch.replication`.

```java
public record ReplicationBootstrapRequest<K, T>(
        ReplicationBootstrapSource source,
        Path sourcePath,
        List<ReplicationGroupConfig<K, T>> replicas,
        Path operationDirectory,
        long maxSourceBytes,
        long maxOperationBytes) { }

public record ReplicationBootstrapResult(
        Path operationDirectory,
        ReplicationBootstrapPlan plan,
        String manifestDigest,
        String genesisDigest,
        UUID applicationHistory,
        long applicationSequence,
        String receiptDigest) { }

public record ReplicationCleanupPlan(
        Path operationDirectory,
        String operationDigest,
        List<Path> deletePaths,
        String inventoryDigest,
        String planDigest) { }

public record ReplicationReplacementPlan(
        Path operationDirectory,
        Path sourceReplicaDirectory,
        ReplicationNodeId replacementNode,
        Path absentTarget,
        String manifestDigest,
        String sourceInventoryDigest,
        String planDigest) { }

public record ReplicationPeerStatus(
        ReplicationNodeId nodeId,
        boolean reachable,
        long durableIndex,
        long matchIndex,
        long appliedIndex,
        Optional<Instant> observedAt) { }

public record ReplicationDiagnostics(
        ReplicationGroupId groupId,
        String configurationId,
        Optional<String> manifestDigest,
        UUID incarnation,
        ReplicationStatus local,
        long recoveryFloor,
        boolean snapshotInstalling,
        List<ReplicationPeerStatus> peers,
        Optional<Instant> lastQuorumSuccess,
        Optional<ReplicationException.Reason> lastFailure) { }
```

Bootstrap request order is the manifest member order, not arbitrary List iteration.
Planning verifies all three local configuration bindings. The result's receipt digest
names the durably published global receipt; the receipt itself retains the complete
canonical descriptor and prepared inventories, not only this compact Java summary.
`applicationSequence` in the result is the genesis base sequence.

Cleanup `deletePaths` is the complete dependency-ordered deletion set, including
directories after their children. Its digest binds kinds, sizes, content hashes and
ownership evidence for the full observed inventory, including protected survivors.
Replacement plans additionally bind the complete supplied local configuration,
bounds and source genesis/seal through their digest. Apply always rechecks; creating
a record in user code is never proof that an operation is safe.

Diagnostics contain only the two configured remote peers in manifest order. An
unobserved peer has zero counters, no observation time and `reachable=false`.
Recovery floor and peer counters use LogIndex, not application sequence.
Counters are nonnegative, `matchIndex <= durableIndex` and
`appliedIndex <= durableIndex` within each observation.
`durableIndex` is its reported durable entry boundary; `matchIndex` is the boundary
whose digest the local node has verified; `appliedIndex` is its reported application
boundary. Lag is `max(0, local.commitIndex - peer.appliedIndex)`, interpreted with
`observedAt`. Reachability is a last observation, not a delivery guarantee. Before
startup the manifest digest is empty and incarnation is the zero UUID. Status and
diagnostics must come from one consistent local snapshot; no negative or fabricated
progress is emitted for a failed/incomplete startup.

## Replication operation additions

```java
// Add to ReplicationStorageOperations (all synchronous, offline operations).
public static <K, T> ReplicationBootstrapPlan planBootstrap(
        SearchEngineBuilder<K, T> applicationBuilder,
        ReplicationBootstrapRequest<K, T> request);
public static <K, T> ReplicationBootstrapResult applyBootstrap(
        SearchEngineBuilder<K, T> applicationBuilder,
        ReplicationBootstrapRequest<K, T> request,
        ReplicationBootstrapPlan plan);
public static <K, T> ReplicationBootstrapResult resumeBootstrap(
        SearchEngineBuilder<K, T> applicationBuilder,
        ReplicationBootstrapRequest<K, T> request,
        ReplicationBootstrapPlan plan);
public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory);
public static ReplicationCleanupPlan planCleanup(Path operationDirectory);
public static void applyCleanup(ReplicationCleanupPlan plan);
public static ReplicationReplacementPlan planReplacement(
        ReplicationGroupConfig<?, ?> configuration,
        Path sourceReplicaDirectory,
        Path operationDirectory);
public static void applyReplacement(
        ReplicationGroupConfig<?, ?> configuration,
        ReplicationReplacementPlan plan);
public static void resumeReplacement(
        ReplicationGroupConfig<?, ?> configuration,
        ReplicationReplacementPlan plan);

// Add to ReplicatedSearchEngine<K, T> as default methods.
public default CompletableFuture<Long> catchUp(ReplicationNodeId peer);
public default CompletableFuture<ReplicationStatus> reconstructConfiguredLeader();
public default ReplicationDiagnostics replicationDiagnostics();
```

The new interface defaults throw `UnsupportedOperationException` without side
effects, preserving third-party implementations. The admitted engine overrides all
three. `catchUp` returns a verified peer LogIndex, never an application sequence.
Existing `start`, `activateConfiguredLeader`, `replicationStatus`, inherited checkpoint,
backup and close descriptors remain unchanged. The implementation must override every
application operation, including inherited default query/bulk/backup methods, so a
follower cannot bypass role admission through another overload.

`readBootstrapResult` is codec-free and acquires operation ownership while checking
the receipt/journal. A result is available only for COMMITTED authority; the operation
must not race unfinished receipt forcing. Reading a Java result does not repair seals.
Successful `applyBootstrap`/`resumeBootstrap` additionally prove all three seals were
delivered. Replacement planning/cleanup acquire source and target ownership in a
stable path order and never hold one node's lock while invoking a network operation.

### Planned usage after implementation acceptance

```java
var request = new ReplicationBootstrapRequest<>(
        ReplicationBootstrapSource.EMPTY, null,
        List.of(leaderConfig, followerAConfig, followerBConfig),
        operationDirectory, maxSourceBytes, maxOperationBytes);
var plan = ReplicationStorageOperations.planBootstrap(applicationBuilder, request);
// The operator reviews request + plan; apply recomputes every binding.
var result = ReplicationStorageOperations.applyBootstrap(applicationBuilder, request, plan);

// On each respective node, with its local configuration and prepared volume:
var engine = ReplicatedSearchEngines.builder(applicationBuilder, localConfig).build();
engine.start().join();
// Once peers have started, on the configured leader only:
engine.activateConfiguredLeader().join();
```

This is a future API sketch, not an example runnable against the current snapshot.

## Inventory and artifact review

The declaration PR must include a human-readable old-to-new signature diff, additive
core consumer coverage and a new full V5 signature fixture. Retain the Phase 1 `v1`
inventories as historical evidence; compare current declarations against an explicitly
reviewed `v2` inventory and verify that its delta is exactly this document. Existing
constructors/components/method descriptors may not disappear. The protocol constant
change must be visible, including a stale-inlined-constant rejection test.

No published core/processor API baseline is regenerated. Published V1–V4.4 binary
and source consumers, optional artifact direction, POM coordinates, nine-JAR integrity
and fixture exclusion remain required. New static/core methods add capabilities;
they do not replace `build`, `buildDurable`, restore, migration, cleanup or backup.
Existing V4 format fixtures remain byte-identical; new replica `1.1` fixtures are
separate from both those formats and the retained V5 `1.0` historical fixtures.
