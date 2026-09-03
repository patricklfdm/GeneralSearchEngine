# V4.0 API compatibility contract

## Published baseline

Published `3.4.0` is the immediate V4.0 API and behavior baseline. Published `4.0.0`
now freezes the additive durable surface described below. V1, V2, V2.1, V3.0, V3.1,
V3.2, V3.3, and V3.4 compatibility consumers and Japicmp gates remain required. The
existing in-memory path receives no mandatory parameter or behavior.

Phase 7 adds an independently compiled V4 consumer that exercises fresh creation,
checkpoint-plus-WAL reopen, stable identity mismatch, unsupported custom startup
indexes, and every frozen format `1.0` fixture through published API only. Release
workflow verification runs that consumer again against remotely downloaded V4
artifacts rather than relying on the reactor copy.

## Additive durable surface

The public descriptor and independent fixtures compile the following Phase 0-frozen
family. New durability
types live in `io.github.patricklfdm.generalsearch.durability`; the one builder method
lives on the existing `engine.SearchEngineBuilder`:

```java
public interface DurableSearchEngine<K, T> extends SearchEngine<K, T> {
    long currentSequence();
    CompletableFuture<Void> checkpoint();
    DurabilityMetrics durabilityMetrics();
}

public final class SearchEngineBuilder<K, T> {
    public DurableSearchEngine<K, T> buildDurable(
            DurableStorageConfig<K, T> storageConfig);
}

public final class DurableStorageConfig<K, T> {
    public static <K, T> Builder<K, T> builder(
            Path directory, DurableCodec<K, T> codec);

    public Path directory();
    public String storageIdentity();
    public String schemaIdentity();
    public DurableCodec<K, T> codec();
    public int maxEncodedKeyBytes();
    public int maxEncodedDocumentBytes();
    public int maxBulkElements();
    public int maxDocuments();
    public long checkpointWalBytes();
    public long maxRetainedBytes();
}
```

Its nested builder exposes setters with the same names for every property except the
constructor-supplied directory/codec, and `build()`. `storageIdentity` and
`schemaIdentity` are required. The safety properties have frozen defaults of 1 MiB
per key, 64 MiB per document, 100,000 bulk elements, 10,000,000 live documents,
256 MiB checkpoint WAL threshold, and 8 GiB maximum retained engine-owned bytes.
Implementations may impose lower platform limits only by rejecting configuration at
open, never by silently changing configured values.

All sizes/counts are positive; `maxRetainedBytes` must exceed
`checkpointWalBytes`. `maxBulkElements` is the persisted-decoder hard bound and must
be at least the existing `SnapshotEngineConfig.maxBatchSize`; normal API admission
continues to use that existing batch-size contract.

`SearchEngineBuilder.build()` remains the in-memory operation. Durable configuration
is passed only to `buildDurable`, avoiding hidden builder mode and accidental disk I/O.

## Failure categories

`DurabilityException` is a public runtime exception with `Reason reason()` and
`OptionalLong sequence()`. `Reason` freezes these V4.0 values:

- `STORAGE_IN_USE`, `STORAGE_ACCESS`, `UNSUPPORTED_FILESYSTEM`;
- `INCOMPATIBLE_STORAGE`, `CORRUPT_CHECKPOINT`, `CORRUPT_WAL`;
- `CODEC_FAILURE`, `REPLAY_FAILURE`, `INDEX_REBUILD_FAILURE`;
- `IO_FAILURE`, `CAPACITY_EXCEEDED`, `SEQUENCE_EXHAUSTED`; and
- `CLOSED`.

Open may throw a direct `DurabilityException`. Asynchronous operations complete
exceptionally with that exception as their durable cause. Diagnostics do not expose
raw persisted document bytes or secrets.

Inherited mutation/index admission after ordinary close preserves the published
`EngineRejectedExecutionException.Reason.CLOSED` behavior. Queued work affected by a
durable writer failure receives the primary `DurabilityException`; later admission is
rejected by the existing closed writer boundary. The new `CLOSED` durability reason is
reserved for durability-only operations such as `checkpoint()`.

## Metrics compatibility

The public `SearchEngineMetrics` record is not modified because adding record
components is binary/source incompatible. `DurabilityMetrics` is a separate immutable
final class with these accessors:

```java
DurabilityStatus status();
long currentSequence();
long checkpointSequence();
long walGeneration();
long walRecords();
long walBytes();
long retainedBytes();
RecoverySource recoverySource();
long replayedRecords();
Duration recoveryDuration();
Duration indexRebuildDuration();
Optional<DurabilityException.Reason> lastCheckpointFailure();
```

`DurabilityStatus` has `OPEN`, `CAPACITY_BLOCKED`, `FAILED`, and `CLOSED`.
`RecoverySource` has `FRESH`, `WAL_ONLY`, `CHECKPOINT_ONLY`, and
`CHECKPOINT_AND_WAL`. Metrics do not include document bytes, business keys, or full
filesystem paths.

Metric values are observational and not synchronization tokens. Existing
`snapshotVersion` and counters reset per process; sequence and checkpoint sequence are
durable identities.

## Index API boundary

Existing `createIndex(IndexDefinition)` remains available through the inherited
interface. Durable implementation accepts only supported built-in definitions and
completes unsupported custom definitions exceptionally before durable sequencing.
The same restriction is validated for startup definitions during `buildDurable`.

## No accidental promises

V4.0 does not make cursors serializable, retain Java object identity across reopen,
expose WAL bytes as public API, provide manual sequence assignment, or allow multiple
processes to share a writable directory.
