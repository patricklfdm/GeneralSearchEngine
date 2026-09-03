# V4.1 Phase 1 public API fixture

This document and `V41OperationalPublicApi.java.fixture` jointly freeze the production
API shape admitted in Phases 2–5. Phase 1 compiles the declarations but ships none of
the new types or methods.

## Operation descriptors

| Owner | Descriptor | Execution |
|---|---|---|
| `DurableSearchEngine<K,T>` | `backup(DurableBackupRequest): CompletableFuture<DurableBackupResult>` | asynchronous default method; never returns `null` |
| `DurableStorageOperations` | `verifyStore(Path): DurableVerificationReport` | synchronous, codec-free |
| `DurableStorageOperations` | `verifyBackup(Path): DurableVerificationReport` | synchronous, codec-free |
| `DurableStorageOperations` | `planCleanup(DurableCleanupRequest): DurableCleanupPlan` | synchronous, codec-free and read-only |
| `DurableStorageOperations` | `applyCleanup(DurableCleanupPlan): DurableCleanupResult` | synchronous, codec-free |
| `SearchEngineBuilder<K,T>` | `verifyDurableBackup(Path, DurableVerificationConfig<K,T>): DurableSemanticVerificationReport` | synchronous and typed |
| `SearchEngineBuilder<K,T>` | `restoreDurableBackup(Path, DurableStorageConfig<K,T>): DurableRestoreResult` | synchronous and typed |

`DurableStorageOperations` is final and has no public constructor. The default backup
method throws `UnsupportedOperationException` for an independent implementation that
does not adopt V4.1. The built-in engine overrides it.

## Exact immutable value components

The fixture uses records to freeze constructor order, accessor names, structural
equality and hash semantics:

- `DurableBackupRequest(Path targetDirectory, long maxBundleBytes)`;
- `DurableBackupFormat(String family, int major, int minor)`;
- `DurableBackupResult(Path targetDirectory, DurableBackupFormat format, String
  contentIdentity, UUID sourceHistory, long sequence, int memberCount, long
  totalBytes)`;
- `DurableVerificationFinding(String code, String member, String detail)`;
- `DurableVerificationReport(Path directory, DurableVerificationStatus status,
  List<DurableVerificationFinding> findings, OptionalLong sequence, long
  authoritativeBytes)`;
- `DurableVerificationConfig<K,T>(String storageIdentity, String schemaIdentity,
  DurableCodec<K,T> codec, int codecVersion, int maxEncodedKeyBytes, int
  maxEncodedDocumentBytes, int maxDocuments)`;
- `DurableSemanticVerificationReport(DurableVerificationReport structuralReport,
  DurableSemanticVerificationStatus status, List<DurableVerificationFinding>
  findings, long documentCount)`;
- `DurableCleanupRequest(Path directory, DurableCleanupScope scope)`;
- `DurableCleanupEntry(Path member, String reason, long size, String fingerprint)`;
- `DurableCleanupPlan(Path directory, DurableCleanupScope scope, String
  authorityIdentity, List<DurableCleanupEntry> deleteSet, String planDigest)`;
- `DurableCleanupResult(Path directory, String planDigest, List<Path> deletedMembers,
  long deletedBytes)`; and
- `DurableRestoreResult(Path targetDirectory, UUID newHistory, UUID sourceHistory,
  String sourceContentIdentity, long restoredSequence, long authoritativeBytes)`.

## Construction, null and equality rules

- Every reference constructor argument is non-null. No public operation accepts a
  null request, directory, config or plan.
- Paths are converted to normalized absolute paths before storage and equality.
  Existing-parent real-path and overlap checks occur at operation admission; value
  construction performs no I/O.
- Every list is defensively copied, preserves deterministic order and is exposed as
  unmodifiable. Findings and delete sets must already be in their contracted canonical
  order; constructors reject duplicate entries.
- Sizes, counts, versions and sequences are non-negative unless a stronger rule
  applies. Request maximum bytes is positive, completed bundle member count is exactly
  three, and complete authoritative bundle bytes are positive.
- History identities are non-zero. Restore source and new histories must differ.
- `DurableBackupFormat.V1_0` is exactly `("gse-backup", 1, 0)`.
- Backup content identities match `gse-backup-v1-[0-9a-f]{64}`. Plan digests and
  fingerprints are lowercase SHA-256 hex. Identity strings follow inherited V4.0
  non-empty UTF-8 bounds.
- Record equality is component equality after normalization and defensive copying;
  diagnostic time, host, PID and elapsed values are intentionally absent. Reports and
  plans produced from identical authority bytes compare equal.
- Invalid value construction throws `IllegalArgumentException`; null throws
  `NullPointerException`. Operational filesystem, ownership, capacity and I/O failures
  use `DurableOperationException` instead.

## Stable status families

Structural status order is `VALID`, `VALID_WITH_SAFE_REMNANTS`, `INCOMPATIBLE`,
`INCOMPLETE`, `CORRUPT`, `UNSUPPORTED`. Semantic status order is
`SEMANTICALLY_VALID`, `IDENTITY_MISMATCH`, `DECODE_FAILURE`, `STATE_MISMATCH`.
Cleanup scopes are `LIVE_STORE` and `OPERATION_REMNANT`.

`DurableOperationException.Reason` order is `STORAGE_IN_USE`, `SOURCE_INVALID`,
`BACKUP_INVALID`, `IDENTITY_MISMATCH`, `TARGET_EXISTS`, `TARGET_INVALID`,
`OPERATION_IN_PROGRESS`, `UNSUPPORTED_FORMAT`, `UNSUPPORTED_FILESYSTEM`,
`CAPACITY_EXCEEDED`, `IO_FAILURE`, `CLOSED`. Its reason and non-negative optional
sequence are retained; the cause may be absent, but when present is retained. The
exception intentionally has identity equality rather than value equality.

## Javadoc obligations

Production Javadocs must state whether each operation is offline or live, synchronous
or asynchronous, codec-free or typed, read-only or mutating, and what successful
return/future completion proves. Each value accessor must identify units, bounds and
authority meaning. No Javadoc may describe structural `VALID` as a semantic decode
claim or cleanup planning as permission to apply a stale plan.
