# V4.2 Phase 1 public API fixture

This document and `V42StorageEvolutionPublicApi.java.fixture` freeze the additive API
shape assigned to V4.2 Phases 2–5. Phase 1 compiles these declarations but ships none
of the new types or methods.

## Ownership and operation descriptors

| Owner | Exact descriptor | Execution contract |
|---|---|---|
| `DurableStorageConfig.Builder<K,T>` | `format(DurableStorageFormat): Builder<K,T>` | configuration only; default remains `V1_0` |
| `DurableStorageOperations` | `inspectStoreFormat(Path): DurableStoreFormatReport` | synchronous, codec-free, offline, exclusive and read-only |
| `DurableStorageOperations` | `inspectBackupFormat(Path): DurableBackupFormatReport` | synchronous, codec-free, concurrent-reader-safe and read-only |
| `SearchEngineBuilder<TK,TT>` | `<SK,ST> planDurableMigration(SearchEngineBuilder<SK,ST>, DurableMigrationRequest<SK,ST,TK,TT>): DurableMigrationPlan` | synchronous, typed, offline and filesystem-output-free |
| `SearchEngineBuilder<TK,TT>` | `<SK,ST> applyDurableMigration(SearchEngineBuilder<SK,ST>, DurableMigrationRequest<SK,ST,TK,TT>, DurableMigrationPlan): DurableMigrationResult` | synchronous, typed, offline and absent-target-only |

The target builder owns target schema, business-key extraction, analyzed fields and
startup indexes. The source builder is a required parameter and supplies the complete
typed source descriptor. A future change to an untyped operation owner, a combined
plan/apply call, or an optional source descriptor requires a contract amendment.

## Format values and reports

`DurableStorageFormat(String family, int major, int minor)` is an immutable record.
Its exact constants are:

```java
DurableStorageFormat.V1_0 == new DurableStorageFormat("gse-durable", 1, 0)
DurableStorageFormat.V1_1 == new DurableStorageFormat("gse-durable", 1, 1)
```

The constructor requires a non-empty lowercase hyphenated family bounded to 128
UTF-8 bytes and non-negative major/minor values. It permits intact unknown values so
inspection can retain an incompatible or unsupported declaration. Equality and hash
semantics are record component equality.

The additive inspection reports are:

- `DurableStoreFormatReport(DurableVerificationReport structuralReport,
  Optional<DurableStorageFormat> declaredFormat, Optional<String> profileDigest)`;
- `DurableBackupFormatReport(DurableVerificationReport structuralReport,
  Optional<DurableBackupFormat> declaredFormat,
  Optional<DurableStorageFormat> sourceFormat, Optional<String> profileDigest)`.

All arguments and `Optional` containers are non-null. A present profile digest is 64
lowercase hexadecimal characters. Absence means the declaration could not establish
that field; it never means semantic validity or default `1.0`. Existing V4.1 report
components and status order are unchanged.

## Transform and request values

`DurableMigrationTransform<SK,ST,TK,TT>` is a functional interface with exact method:

```java
DurableMigrationRecord<TK,TT> transform(SK sourceKey, ST sourceDocument);
```

It is not serializable, reflection-loaded, persisted, sandboxed or discovered as a
service. `DurableMigrationTransformDescriptor(String identifier, int version)` binds
an identifier matching `[a-z0-9][a-z0-9-]{0,127}` and a non-negative version.
`DurableMigrationRecord<K,T>(K key, T document)` rejects null components.

The request component order is:

```text
sourceDirectory
sourceConfig
targetConfig
transformDescriptor
transform
maxSourceAuthoritativeBytes
maxTargetAuthoritativeBytes
capacitySafetyReserveBytes
maxCollisionEntries
maxFindings
maxDiagnosticBytes
```

`sourceDirectory` is normalized to an absolute path without I/O during construction.
`sourceConfig` is a `DurableVerificationConfig<SK,ST>` and `targetConfig` is a
`DurableStorageConfig<TK,TT>` with explicit target format. Reference values are
non-null. Byte maximums and the capacity reserve are positive. Collision and finding
limits are positive and at most the target document hard maximum; diagnostic bytes
are positive and at most one MiB. Operational path, ownership and capacity checks
occur during plan/apply, not record construction.

## Plan values

`DurableMigrationSourceMember(String name, long size, String sha256)` binds an exact
regular authoritative member. Name is a bounded canonical member name, size is
non-negative and SHA-256 is lowercase hexadecimal.

`DurableMigrationIndexChange(List<String> added, List<String> removed,
List<String> retained)` stores three canonical, duplicate-free, defensively copied,
unmodifiable descriptor lists.

`DurableMigrationPlan` has exact component order:

```text
schemaVersion, sourceDirectory, targetDirectory,
sourceFormat, targetFormat, sourceHistory, targetHistory,
sourceSequence, nextDocId, sourceMembers,
sourceAuthorityIdentity, sourceDescriptorDigest, targetDescriptorDigest,
transformDescriptor, documentCount, sourceIndexCount, targetIndexCount,
indexChange, targetAuthoritativeBytes, peakTargetBytes,
capacitySafetyReserveBytes, projectionDigest, planDigest
```

Schema version is exactly `1`. Paths are normalized absolute values. Histories are
non-zero and distinct. Sequences, counts and sizes are non-negative; reserve is
positive; peak bytes are at least authoritative bytes plus reserve under exact
overflow-safe arithmetic. Lists are defensively copied and canonical. Digests use
their contract prefixes and 64 lowercase hexadecimal suffixes. The plan contains no
timestamp, hostname, PID, elapsed duration, free-space observation or executable
transform. Record equality is canonical component equality.

## Result and failure values

`DurableMigrationResult` component order is:

```text
sourceDirectory, targetDirectory, sourceFormat, targetFormat,
sourceHistory, targetHistory, sequence, nextDocId, documentCount,
sourceAuthorityIdentity, projectionDigest, planDigest, authoritativeBytes
```

Its paths, histories, counts and identities obey the plan rules. Successful return
means publication, parent force, independent structural/semantic verification,
normal target open/close, source byte recheck and marker cleanup completed. It does
not mean application cutover.

`DurableMigrationStage` order is:

```text
VALIDATE_REQUEST, ACQUIRE_SOURCE, VERIFY_SOURCE, PROJECT_TARGET,
VALIDATE_CAPACITY, PREPARE_TARGET, WRITE_METADATA, WRITE_CHECKPOINT,
WRITE_MANIFEST, WRITE_WAL, VERIFY_STAGING, PUBLISH_TARGET, FORCE_PARENT,
VERIFY_TARGET, VERIFY_SOURCE_PRESERVED, CLEANUP_MARKER, COMPLETE
```

`DurableMigrationException.Reason` order is:

```text
STORAGE_IN_USE, SOURCE_INVALID, IDENTITY_MISMATCH,
MIGRATION_PATH_UNSUPPORTED, MIGRATION_NOT_REQUIRED, PLAN_STALE,
TRANSFORM_FAILURE, TRANSFORM_NONDETERMINISTIC, TARGET_EXISTS, TARGET_INVALID,
UNSUPPORTED_FILESYSTEM, CAPACITY_EXCEEDED, IO_FAILURE,
PUBLICATION_INDETERMINATE
```

The exception constructor takes reason, stage, `OptionalLong sourceSequence`, and an
optional cause. It retains those values, uses identity equality, rejects a negative
present sequence, and never copies application payloads or unbounded cause text into
its stable message. V4.1 `DurableOperationException.Reason` is not extended.

## Production Javadoc obligations

Production Javadocs must identify synchronous/offline/read-only or mutating behavior,
successful-return authority, source preservation, target absence, default-format
continuity, unsupported edge behavior, plan staleness, post-publication indeterminacy,
units and hard bounds. Inspection must not be described as typed validity; planning
must not be described as permission to skip apply re-execution; successful migration
must not be described as traffic cutover or source disposal.
