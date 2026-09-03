# Migration boundary: 4.0 to 4.1

## Upgrade shape

Applications may update both GSE coordinates from `4.0.0` to `4.1.0` without changing
ordinary in-memory or durable startup code. V4.1 retains Java 21, the two-artifact
layout, V3.4 retrieval behavior and live format `gse-durable (1,0)`.

An application that does not invoke backup, verification, restore or cleanup receives
no new filesystem operation. Existing V4.0 directories are not rewritten simply by
opening them with V4.1.

## Creating a supported backup

A backup is an explicit asynchronous operation on a live durable engine. Its final
target must be absent and outside the live-store directory. The capacity bound is
mandatory:

```java
Path backup = Path.of("backups/search-2026-09-03");
DurableBackupResult result = engine.backup(
        new DurableBackupRequest(backup, 16L << 30)).join();
```

Completion means a checkpoint-only bundle for exactly `result.sequence()` was
atomically published and structurally verified. It does not include mutations after
the writer-ordered cut. Keep the complete directory together; do not add, remove,
rename or edit members.

## Verifying before transport or restore

Codec-free structural verification is suitable for an offline live store or complete
immutable bundle:

```java
DurableVerificationReport structural =
        DurableStorageOperations.verifyBackup(backup);
```

`VALID` proves structure, inventory, checksums, history and sequence, not successful
application decode. Typed verification must supply the exact persisted identities and
bounded deterministic codec:

```java
DurableVerificationConfig<Integer, Document> expected =
        new DurableVerificationConfig<>(
                "travel-search-v1",
                "travel-schema-v1",
                codec,
                codec.codecVersion(),
                64,
                1 << 20,
                1_000_000);

DurableSemanticVerificationReport semantic = SearchEngine
        .builder(Document.class, ID)
        .field(BODY)
        .verifyDurableBackup(backup, expected);
```

Proceed only when structural and semantic status are explicitly valid. Treat corrupt,
incompatible, incomplete and unsupported results as operator events; do not repair or
delete the reported authority.

## Restoring as a new history

Restore is synchronous and offline. The target must be absent, use a supported local
filesystem and have enough capacity. Supply the same logical codec/schema meaning and
the intended target storage configuration:

```java
Path target = Path.of("data/restored-search");
DurableStorageConfig<Integer, Document> targetStorage =
        DurableStorageConfig.builder(target, codec)
                .storageIdentity("travel-search-v1")
                .schemaIdentity("travel-schema-v1")
                .build();

DurableRestoreResult restored = SearchEngine
        .builder(Document.class, ID)
        .field(BODY)
        .restoreDurableBackup(backup, targetStorage);
```

The result preserves the backup sequence and source provenance but publishes a new,
non-zero history identity. Open the target normally, compare application truth and
retrieval results, perform a bounded continued mutation, checkpoint, close and reopen
before directing production traffic.

## Safe cleanup

Cleanup never discovers targets by parent scan, age or glob. Name one exact offline
store or recognized operation remnant, review the dry-run plan, then apply that exact
plan without changing the filesystem in between:

```java
DurableCleanupRequest request = new DurableCleanupRequest(
        closedStore, DurableCleanupScope.LIVE_STORE);
DurableCleanupPlan plan = DurableStorageOperations.planCleanup(request);

// Review plan.directory(), authorityIdentity(), deleteSet() and planDigest().
DurableCleanupResult cleanup = DurableStorageOperations.applyCleanup(plan);
```

Apply recomputes authority and inventory and fails closed if the plan is stale. It
cannot delete a complete store or backup, skip committed corruption, truncate WAL,
repair bytes or merge histories.

## Rollout and rollback

Before rollout, retain an independently verified backup outside the live directory,
record content identity/source history/sequence, and exercise restore on a separate
target. Monitor capacity and operational failure categories without logging document
payloads or credentials.

Because the live format remains `1.0`, rollback to V4.0 may reopen an unchanged V4.0
store or a completed V4.1-restored live store when identities and configuration match.
V4.0 cannot create, verify or restore `gse-backup (1,0)` bundles. Never downgrade by
copying bundle members into a live directory. Preserve old authority until the chosen
target has been independently verified.

The executable reference is the independent
`compatibility/v4-style-consumer` project. The normative operation and failure
semantics remain in the V4.1 Phase 0 contract.
