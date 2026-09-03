# Migration boundary: 3.4 to 4.0

## Staying in memory

Existing applications may upgrade coordinates and continue using `build()` or
`fromAnnotatedClass(...)`. They supply no storage path or codec and retain the V3.4
process-lifetime behavior. V4.0 does not transparently persist an existing engine.

## Opting into durability

A durable application must deliberately provide a local directory, stable storage and
schema identities, deterministic key/document codec, safety bounds, checkpoint
threshold, and disk limit, then call `buildDurable(...)`.

The first open creates a new empty durable history. Importing an already populated
V3.4 in-memory instance is not implicit: the application must open a fresh durable
engine and bulk-add source-of-truth documents. Successful bulk completion is the
durable import boundary.

The minimum shape is deliberately explicit:

```java
DurableStorageConfig<Integer, Document> storage = DurableStorageConfig
        .builder(Path.of("data/search"), new DocumentCodec())
        .storageIdentity("travel-search-v1")
        .schemaIdentity("travel-schema-v1")
        .maxEncodedKeyBytes(64)
        .maxEncodedDocumentBytes(1 << 20)
        .maxBulkElements(10_000)
        .maxDocuments(1_000_000)
        .checkpointWalBytes(256L << 20)
        .maxRetainedBytes(8L << 30)
        .build();

try (DurableSearchEngine<Integer, Document> engine = SearchEngine
        .builder(Document.class, ID)
        .field(BODY)
        .buildDurable(storage)) {
    engine.addAll(sourceDocuments).join();
    engine.checkpoint().join();
}
```

`DocumentCodec` must encode keys and complete documents deterministically, return a
stable `codecId()` and non-negative `codecVersion()`, reject malformed bytes, and
round-trip each business key exactly. The independently compiled implementation in
[`compatibility/v4-style-consumer`](../../compatibility/v4-style-consumer) is the
executable reference rather than an additional framework dependency.

## Application responsibilities

- Treat accepted documents as immutable just as in V3.4.
- Keep codec and schema meanings stable for a storage identity.
- Change explicit identities/versions when persisted meaning changes.
- Use only built-in durable index/analyzer configurations.
- Place storage on a supported local filesystem and monitor capacity.
- Treat incomplete Futures at crash as indeterminate and inspect recovered state by
  business key or application idempotency rules.
- Back up or replicate the persistent device for physical-disk-loss protection.

Before deployment, verify that the chosen path is a supported local filesystem, that
only one process owns it, and that the retained-byte limit fits both steady state and
checkpoint staging. Keep a rollback copy outside the live directory. Never copy files
between histories, select a checkpoint by timestamp, or edit an incomplete WAL tail by
hand.

## Reopen differences

Reopen blocks while documents decode, WAL replays, and indexes rebuild. Recovered
objects are newly decoded instances. Snapshot versions, metrics counters, and cursors
are process-local and reset/expire; durable sequence continues. Query truth, score
bits, canonical ordering, and successfully completed mutations must not change.

## Downgrade and format change

V3.4 cannot read V4 storage. Copying V4 files into an older engine is unsupported.
Changing codec/schema identities requires an explicit export/import or future offline
migration tool; opening under a different interpretation fails closed.

## Operational rollout

Start with a fresh durable directory and a bounded source-of-truth import. Wait for the
bulk Future, request a checkpoint, close cleanly, and reopen once before directing
traffic. Record storage, schema, codec and format identities with the deployment. On
restart, wait for `buildDurable(...)` to finish and inspect `durabilityMetrics()` before
accepting traffic. Treat `CORRUPT_WAL`, `CORRUPT_CHECKPOINT`, and
`INCOMPATIBLE_STORAGE` as fail-closed operator events, not as requests to delete or
rewrite storage.

V4.0 has no online upgrade or repair command. Moving from one codec/schema meaning to
another requires export to application-owned source data and import into a new empty
directory with new identities. Preserve the old directory until the new history has
been independently verified.
