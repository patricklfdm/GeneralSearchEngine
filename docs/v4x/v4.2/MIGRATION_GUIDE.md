# Migration boundary: 4.1 to 4.2

## Upgrade shape

Applications may update both GSE coordinates from `4.1.0` to `4.2.0` without
changing ordinary in-memory or durable startup code. Java 21, the two-artifact layout,
retrieval behavior and the default live format `(1,0)` are unchanged.

Merely opening a V4.1 store with V4.2 does not migrate, rewrite or upgrade it. Select
`DurableStorageFormat.V1_1` only for a fresh target or for an explicit reviewed
migration. The configured format must match on every reopen.

## Inspect and protect the source

Stop source writes, checkpoint and close the engine. Keep an independently verified
V4.1 backup outside the source and target directories. Codec-free inspection exposes
the declared live and backup-source formats without recovery or mutation:

```java
DurableStoreFormatReport sourceFormat =
        DurableStorageOperations.inspectStoreFormat(source);
DurableBackupFormatReport backupFormat =
        DurableStorageOperations.inspectBackupFormat(backup);
```

Proceed only after structural and typed semantic verification succeed and the source
format, identities, sequence, inventory and backup identity are recorded.

## Plan before applying

Construct an explicit target configuration and a deterministic one-to-one transform.
The descriptor names the transform semantics; it is not a persisted class name:

```java
DurableStorageConfig<Integer, Document> targetStorage = DurableStorageConfig
        .builder(target, codec)
        .format(DurableStorageFormat.V1_1)
        .storageIdentity("travel-search-v1")
        .schemaIdentity("travel-schema-v1")
        .build();

DurableMigrationRequest<Integer, Document, Integer, Document> request =
        new DurableMigrationRequest<>(
                source,
                sourceVerification,
                targetStorage,
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                maxSourceBytes,
                maxTargetBytes,
                capacityReserveBytes,
                maxCollisionEntries,
                maxFindings,
                maxDiagnosticBytes);

DurableMigrationPlan plan = targetBuilder.planDurableMigration(
        sourceBuilder, request);
```

Planning is synchronous, read-only and creates no target. Review the exact source
members and authority identity, source/target formats and descriptor digests, index
changes, transform descriptor, projected document count and bytes, capacity reserve,
projection digest, target history and plan digest.

## Apply and validate the target

Apply only the reviewed plan against the same closed source and absent target:

```java
DurableMigrationResult result = targetBuilder.applyDurableMigration(
        sourceBuilder, request, plan);
```

Apply refuses a changed source, stale plan, occupied target, collision, transform
failure, insufficient bounds or unsupported edge. A successful result identifies a
new target history at the source sequence. Independently verify the target, open it
with the exact target format/configuration, compare application truth and retrieval,
perform a bounded continued mutation, checkpoint, close and reopen before cutover.

## Cutover and rollback

Cutover is application/operator orchestration, not part of the library. Keep the
source immutable during the rollback window. Stop the target before rollback and
reopen the untouched `(1,0)` source with V4.1 or V4.2. Published V4.1 cannot open the
`(1,1)` target.

Writes accepted only by the target are not merged back automatically. Rolling back
therefore requires external reconciliation for those writes. V4.2 provides no reverse
migration or history merge. Never copy individual members between source and target,
rename a partially published target into service, or reinterpret a target as the
source history.

## Cleanup and failure handling

An incomplete migration target is non-authoritative only when the exact structured
operation marker and source bindings prove that classification. Use the V4.1
dry-run-first cleanup API with `OPERATION_REMNANT`, review the exact plan, then apply
without intervening filesystem changes. A completed target is authority and cannot be
deleted by that cleanup path.

Treat source corruption, incompatibility, ambiguous target publication and capacity
failure as operator events. Preserve both directories and bounded diagnostics until
their authority is understood. Migration never repairs committed source bytes.

The executable reference is the independent
`compatibility/v4-style-consumer` project. The normative semantics remain in the
V4.2 Phase 0 contract.
