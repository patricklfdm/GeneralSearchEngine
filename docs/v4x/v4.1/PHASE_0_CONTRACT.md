# GeneralSearchEngine V4.1 Phase 0 contract

- **Phase:** 0 — Operational-safety contract freeze
- **Status:** Complete contract candidate; protected acceptance pending
- **Reference baseline:** Published GeneralSearchEngine `4.0.0`
- **Production V4.1 implementation:** Not authorized before protected acceptance

## Objective

Phase 0 freezes the semantics and implementation boundaries for backup, restore,
offline verification, and safe cleanup. Filesystem-copy timing, recovery side effects,
or implementation convenience must not become accidental product behavior.

This phase is documentation-only. It does not change Maven coordinates, create
`4.1.0-SNAPSHOT`, add executable infrastructure, modify production or test source, run
paid cloud work, or register evidence.

## Normative language and authority

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. Published V4.0 contracts remain
authoritative for mutation completion, storage ownership, WAL/checkpoint recovery,
format `gse-durable (1,0)`, corruption behavior, and retrieval semantics. This contract
adds operational semantics only.

If a V4.1 implementation cannot satisfy this contract without changing live format
`1.0`, it MUST stop for an explicit contract amendment or defer the change to V4.2.

## Frozen inheritance from V4.0

V4.1 preserves:

- one authoritative writer and lock-free immutable-snapshot readers;
- writer-order allocation of contiguous durable logical sequences;
- force-before-publication and force-before-successful-future completion;
- crash indeterminacy for a future that did not complete successfully;
- atomic bulk all-or-nothing recovery;
- checkpoint manifest authority and checkpoint-plus-WAL live recovery;
- exact incomplete-tail versus committed-corruption handling;
- fail-closed storage/schema/codec/history identity validation;
- deterministic canonical slot, `nextDocId`, index-configuration, and document
  recovery;
- terminal handling when live source durability becomes ambiguous;
- `gse-durable (1,0)` byte meaning and allowed live-directory member policy;
- V3.4 query truth, score bits, ordering, pagination, highlighting, Explain,
  lifecycle, and in-memory defaults.

Backup-specific failure MUST NOT make the live engine terminal unless an inherited
V4.0 source write/force/publication failure makes source durability ambiguous.

## Terminology

- **source store:** the live V4 durable directory from which a backup is requested.
- **B:** the exact last durable logical sequence represented by a backup.
- **source checkpoint:** the immutable checkpoint payload captured at `B` and pinned
  while backup materializes.
- **bundle:** one finalized `gse-backup (1,0)` directory.
- **content identity:** the deterministic SHA-256 identity of authoritative logical
  bundle fields and payload member descriptors.
- **structural verification:** codec-free byte, member, authority, checksum, identity,
  and sequence validation.
- **semantic verification:** typed codec/schema decoding and logical/retrieval
  validation in addition to structural verification.
- **restore target:** the absent live-store directory created from a verified bundle.
- **safe remnant:** a member whose non-authoritative status is proven by accepted
  format and authority rules, not inferred from age.

## Public API boundary

V4.1 adds supported operations to the existing core artifact only. It does not add a
new Maven module or supported general-purpose CLI.

### Live backup

`DurableSearchEngine<K,T>` gains the additive method family:

```java
default CompletableFuture<DurableBackupResult> backup(
        DurableBackupRequest request);
```

The method is default for source/binary compatibility with an independently
implemented published `DurableSearchEngine`; an implementation that does not adopt the
V4.1 capability rejects it with `UnsupportedOperationException`. The built-in durable
engine overrides it.

`DurableBackupRequest` is an immutable value containing the final target directory and
an overflow-safe maximum permitted bundle byte count. The target MUST be absolute or
normalizable to an absolute path, MUST be absent, and MUST not overlap the live source
directory in either ancestor direction.

`DurableBackupResult` is immutable and exposes at least the finalized target, backup
format, content identity, source history identity, sequence `B`, member count, and
total authoritative bytes. Successful completion means the final bundle directory is
durably published and passes production structural verification.

### Codec-free operations

A final utility family named `DurableStorageOperations` provides:

```java
static DurableVerificationReport verifyStore(Path directory);
static DurableVerificationReport verifyBackup(Path directory);
static DurableCleanupPlan planCleanup(DurableCleanupRequest request);
static DurableCleanupResult applyCleanup(DurableCleanupPlan plan);
```

These operations load no user codec and make no semantic-decode claim.

### Typed semantic verification and restore

`SearchEngineBuilder<K,T>`, which owns the application schema and startup index
configuration, adds:

```java
DurableSemanticVerificationReport verifyDurableBackup(
        Path backupDirectory,
        DurableVerificationConfig<K,T> expectedConfig);

DurableRestoreResult restoreDurableBackup(
        Path backupDirectory,
        DurableStorageConfig<K,T> targetConfig);
```

`DurableVerificationConfig<K,T>` contains expected storage/schema identities, codec,
codec version, and decode/resource bounds but no live directory. Restore uses
`targetConfig.directory()` as the absent target and uses the builder schema/index
definitions plus the configured codec and identities to materialize format `1.0`.

Phase 1 MUST freeze constructors/builders, null handling, equality, Javadocs, generic
signatures, and compiled consumer descriptors before any production operation is
implemented. It MAY refine value-type accessor names, but changing the operation
ownership, synchronous/asynchronous split, or semantic responsibility above requires
a Phase 0 amendment.

### Operational failure type

Operational methods use a separate public `DurableOperationException`; they do not
reinterpret the stable V4.0 `DurabilityException` runtime categories. Its stable reason
family MUST distinguish at least:

- `STORAGE_IN_USE`;
- `SOURCE_INVALID`;
- `BACKUP_INVALID`;
- `IDENTITY_MISMATCH`;
- `TARGET_EXISTS`;
- `TARGET_INVALID`;
- `OPERATION_IN_PROGRESS`;
- `UNSUPPORTED_FORMAT`;
- `UNSUPPORTED_FILESYSTEM`;
- `CAPACITY_EXCEEDED`;
- `IO_FAILURE`;
- `CLOSED`.

The original cause and any known source/backup sequence MUST be retained without
exposing secrets or full document bytes in messages.

## Exact backup consistency point

Every supported V4.1 backup is a complete checkpoint-only backup at exactly `B`.
Checkpoint-plus-WAL, incremental, deduplicated, and live recursive-copy models are not
part of V4.1.

### Selection of B

1. A valid backup request is admitted as a writer-ordered control task.
2. All writer tasks accepted before it are processed according to normal V4.0 order.
3. The source coordinator forces any required state and selects the current last
   durably published logical sequence as `B`.
4. The writer captures the immutable canonical state and durable dynamic-index
   configuration at `B`.
5. It cuts the WAL generation and publishes a source checkpoint exactly at `B` using
   inherited V4.0 checkpoint authority rules.
6. The checkpoint is pinned before cleanup may make it non-authoritative or delete it.
7. The bounded writer coordination ends. Later mutations may proceed and are excluded
   from the backup.

For a fresh store, `B == 0` is valid and produces an independently restorable empty
backup. Backup does not allocate a new mutation sequence. Because V4.0 cannot cut a
new post-checkpoint WAL after `Long.MAX_VALUE`, a source already at that terminal
sequence fails the consistency cut with inherited `SEQUENCE_EXHAUSTED` behavior and
does not publish a V4.1 backup.

An existing checkpoint at exactly `B` MAY be reused only when its complete identity
and canonical-state capture are proven equivalent and it is atomically pinned before
any cleanup race. An unrelated in-flight or coalesced `checkpoint()` MUST NOT satisfy
the backup request by timing accident.

### Pinning and concurrency

- A source checkpoint pin is an in-process retention authority understood by all
  checkpoint cleanup paths.
- A pinned checkpoint and required immutable source metadata MUST remain readable
  until backup succeeds or fails and copying has stopped.
- Pinning does not make old WAL part of the backup.
- Only one backup may be active per engine. A second request fails with
  `OPERATION_IN_PROGRESS`; backup requests never coalesce.
- Readers continue throughout backup.
- Later mutations and checkpoints may run after the cut, but cleanup MUST retain the
  pinned checkpoint.
- Pinned checkpoint bytes remain part of live retained-byte accounting. If the source
  reaches its V4.0 capacity bound while copying is active, later work follows existing
  capacity-failure semantics; backup does not waive the bound.
- New backup admission after close begins fails with `CLOSED`.
- Close stops admissions and waits for an accepted backup operation to finish copying
  and release its pin before releasing source storage ownership.

### Failure boundary

Failure before or during the cut completes the backup future exceptionally and does
not identify a backup `B` unless the result explicitly reports the known cut. Failure
after the cut leaves the source on its ordinary legal V4.0 history. Target-copy or
target-force failure cannot roll back or invalidate source authority.

## Backup bundle format `gse-backup (1,0)`

The backup format is independent from `gse-durable (1,0)`. It is a full directory
bundle with exactly these authoritative regular files:

```text
gse-backup-metadata
gse-backup-checkpoint
gse-backup-manifest
```

No WAL, live checkpoint manifest, lock, symlink, hardlink-dependent representation,
device, socket, FIFO, nested directory, or additional member is allowed in a complete
V4.1 bundle.

### Payload members

`gse-backup-metadata` is a byte-for-byte copy of the independently validated immutable
source `gse-metadata`. It retains the source live format family/version, source
history, storage/schema/codec identities, codec version, configured safety bounds, and
startup index/analyzer descriptors. It is renamed in the bundle but is not silently
translated into a new live or backup metadata format.

`gse-backup-checkpoint` is the complete source checkpoint payload at `B`. Its embedded
source history remains unchanged in the backup. Restore decodes and re-encodes it; it
does not byte-copy that history-bound payload into the target.

### Encoding and bounds

- The backup manifest uses a versioned binary encoding, big-endian integral values,
  fixed magic/family/version fields, and length-prefixed strict UTF-8 strings. The
  metadata and checkpoint payload members retain their exact source format bytes.
- Format family is exactly `gse-backup`; major/minor is exactly `(1,0)`.
- Integrity hash is exactly SHA-256 and is stored as 32 raw bytes in binary form and
  lowercase hexadecimal in diagnostics.
- Member names are the exact ASCII names above and are sorted by unsigned UTF-8 byte
  order in canonical digest input.
- Every length, count, addition, and offset is bounded and overflow checked before
  allocation or I/O.
- Source metadata retains the V4.0 64-MiB parser bound; the backup manifest has a fixed
  maximum encoded size of 16 MiB.
- Bundle member count is exactly three after finalization.
- Checkpoint size MUST be positive and MUST NOT exceed both the request maximum and the
  source store's configured retained-byte limit.
- Total authoritative bundle bytes MUST NOT exceed the request maximum.
- A verifier MUST reject a changed-while-read file rather than accept mixed bytes.

Phase 1 owns the exact manifest byte-layout fixture, including magic constants and
every field offset, plus immutable exact source-metadata/checkpoint member fixtures,
before production writes the format. Once merged, those bytes are immutable backup
format `1.0` compatibility fixtures.

### Content identity

The content-identity preimage is domain separated with
`gse-backup-content-v1`, followed by the canonical authoritative identity fields and,
for each payload member in canonical order, its exact name, unsigned byte size, and
SHA-256 digest. The manifest and its content-identity field are not recursively hashed.

The backup identifier is:

```text
gse-backup-v1-<64 lowercase SHA-256 hex characters>
```

Two bundles with identical authoritative source identity and payload bytes at `B`
have the same content identity. Diagnostic creation time, host, process, request ID,
and elapsed measurements do not participate in content identity and MUST NOT affect
restore semantics.

The completion manifest contains the canonical fields used by the digest, the digest
itself, diagnostic creation metadata, exact member inventory, and its own format
header/checksum. Diagnostic metadata is non-authoritative; changing it may invalidate
manifest-byte integrity but cannot change the content identity after canonical fields
are revalidated.

### Publication protocol

1. The requested final target MUST not exist.
2. The implementation creates a unique sibling staging directory and a separate
   sibling operation-marker file under the same existing real parent as the final
   target. The marker binds operation kind, unique operation ID, staging name, and
   intended final target; it is forced before payload work and held locked while the
   operation is live.
4. Metadata and checkpoint are copied with bounded buffers, individually forced, then
   reread and hashed.
5. The completion manifest is written last to a uniquely named staging file and
   forced.
6. The manifest is atomically renamed to `gse-backup-manifest`; the staging directory
   is forced.
7. Structural verification of the staged complete bundle passes.
8. The staging directory is atomically renamed to the still-absent final target.
9. The target parent directory is forced.
10. Production structural verification of the final bundle passes.
11. The sibling operation marker is removed and the parent is forced again before the
    future completes successfully.

The target and staging sibling MUST be on a filesystem that supports the inherited
atomic rename and directory-force assumptions. Otherwise backup fails with
`UNSUPPORTED_FILESYSTEM`. Backup never overwrites, merges into, or deletes a final
target.

The staging basename is exactly `.gse-v41-backup-UUID.staging`, where `UUID` is 32
lowercase hexadecimal UUID digits. Its sibling marker appends `.operation` to that
basename. The versioned marker uses a fixed binary `gse-operation (1,0)` header,
big-endian lengths, strict UTF-8 target/staging basenames, operation kind, UUID, and a
CRC32C checksum. Absolute paths are never serialized into the marker. A corrupt or
identity-mismatched marker authorizes no cleanup.

A crash before final-directory rename leaves no valid final bundle. A crash after the
rename and parent force but before future completion is caller-indeterminate; an
independent verifier decides whether the bundle is complete.

## Structural verification

Structural verification is read-only and never invokes production recovery as its sole
parser. At least one independent byte parser is mandatory in local and cloud evidence.

### Structural statuses

`DurableVerificationReport` exposes one primary status:

- `VALID`;
- `VALID_WITH_SAFE_REMNANTS`;
- `INCOMPATIBLE`;
- `INCOMPLETE`;
- `CORRUPT`;
- `UNSUPPORTED`.

It also exposes a deterministically ordered immutable finding list. A report status is
not an exception; access, locking, unsupported-filesystem mechanics, resource bounds,
and unexpected I/O may fail with `DurableOperationException` when no trustworthy
report can be constructed.

### Store verification

Offline store verification:

- requires exclusive acquisition of the normal V4 storage lock;
- never creates, truncates, renames, forces, deletes, or rewrites a store member;
- checks metadata checksum/format/identity shape;
- identifies authoritative checkpoint manifest and checkpoint;
- checks checkpoint structure and checksum independently;
- checks WAL history/generation headers, required post-checkpoint range, committed
  frame checksums, and sequence continuity;
- reports an otherwise permitted incomplete WAL tail but does not truncate it;
- validates retained-byte inventory and every reserved member;
- classifies only format-proven obsolete/staging members as safe remnants;
- rejects symlinks and non-regular members.

An otherwise valid store with only a V4.0-permitted incomplete final WAL tail reports
`VALID_WITH_SAFE_REMNANTS` plus an `INCOMPLETE_WAL_TAIL` finding. That status means the
tail is non-authoritative under V4.0 recovery rules; V4.1 cleanup still does not
truncate an authoritative WAL file.

### Backup verification

Backup structural verification:

- requires the exact three-member inventory;
- parses metadata and completion manifest independently;
- recomputes member SHA-256 and content identity;
- validates checkpoint structure, source history, identity, sequence `B`, configured
  bounds, and canonical member sizes;
- rejects an absent/partial manifest as incomplete;
- rejects extra members, path indirection, or changed-while-read bytes;
- does not require the bundle to be in the same filesystem or host as its source.

### Classification rules

Classification follows evidence, not a blind precedence list:

1. `UNSUPPORTED` applies only when an intact readable header declares an unknown
   family or unsupported major version.
2. `INCOMPATIBLE` applies when a structurally supported artifact is valid but supplied
   expected storage/schema/codec identity or supported-minor policy does not match.
3. `CORRUPT` applies when bytes claiming a supported format fail checksum, canonical
   encoding, authority relationship, bounds, or sequence validation.
4. `INCOMPLETE` applies when required authority/completion is absent or a recognized
   staged publication is unfinished and no present authoritative member proves
   corruption.
5. `VALID_WITH_SAFE_REMNANTS` applies only after all authoritative state validates and
   every extra member is proven non-authoritative.
6. `VALID` applies only when authority and exact inventory validate without findings
   that change status.

Corrupt present authoritative bytes are not hidden by a simultaneous missing member.
Every finding remains visible even when the deterministic primary status represents a
higher-confidence root condition.

## Semantic verification

Semantic verification first requires `VALID` structural status for a bundle. It then:

- matches storage identity, schema identity, codec id/version, decode limits, and
  analyzer/index descriptors against the supplied typed configuration;
- decodes every canonical key and document exactly once under bounded accounting;
- verifies key/document identity consistency and canonical internal ordering;
- validates active document count, canonical slots, `nextDocId`, and dynamic durable
  index configuration;
- rebuilds required indexes without treating them as authority;
- exposes `SEMANTICALLY_VALID` only after the full pass;
- otherwise reports `IDENTITY_MISMATCH`, `DECODE_FAILURE`, or `STATE_MISMATCH` with a
  bounded diagnostic finding and no document payload.

`VALID` structural status alone never claims that application documents decode or
that searches are correct.

## Restore identity and target protocol

### Identity decision

Restore creates a new non-zero random durable history identity while preserving the
backed-up logical sequence `B`. Source history and content identity are exposed by the
backup and restore result, but are not added to the live target format.

The target retains the source storage identity, schema identity, codec id/version,
durable index/analyzer configuration, safety bounds, canonical documents, internal
ordering, `nextDocId`, and sequence `B`. The caller-supplied target configuration MUST
match these fields exactly except for target directory and any explicitly
non-persisted runtime tuning already permitted by V4.0.

Subsequent durable logical units allocate from the next legal sequence after `B`.
Sequence exhaustion follows the inherited V4.0 `SEQUENCE_EXHAUSTED` behavior and MUST
be checked without overflow.

### No live-format change

The staged target is freshly encoded as an ordinary `gse-durable (1,0)` directory:

- `gse.lock` is a zero-length regular ownership file held exclusively through staged
  validation and final publication;
- `gse-metadata` contains the new history and existing format `1.0` fields only;
- a checkpoint at `B` is encoded and checksummed against the new history;
- `gse-checkpoint-manifest` references that checkpoint and the canonical restored WAL
  generation `2`;
- `gse-wal-00000000000000000002.log` is empty, is bound to the new history, and has
  first sequence `B + 1` without overflow;
- no backup manifest, restore receipt, provenance sidecar, or unknown file is placed
  inside the live target.

Published V4.0 code configured with matching identities MUST be able to open the
restored target. Restore is a logical decode/re-encode operation, not a byte-copy of
the source-history checkpoint.

### Target rules and finalization

- `targetConfig.directory()` MUST be absent; an existing empty directory is rejected
  with `TARGET_EXISTS`.
- The target, backup, and any live source path MUST not overlap in either ancestor
  direction.
- The existing real target parent must pass the same local-filesystem assumptions as
  V4.0.
- Restore creates staging basename `.gse-v41-restore-UUID.staging` and a locked
  sibling `.operation` marker using the same encoding and binding rules as backup.
- It performs structural and semantic backup verification before target materialization.
- It decodes with explicit bounds, writes and forces all target members, rereads them,
  and runs codec-free staged-store structural verification.
- It opens/rebuilds the staged logical state through a non-mutating typed validation
  path and checks every canonical state invariant before publication.
- It forces the exact-member staging directory, atomically renames it to the absent
  target, forces the parent directory, verifies the target, removes the sibling
  marker, and forces the parent again.
- It verifies the final directory before returning success.

Restore never overwrites or merges with an existing target and never mutates the
backup. V4.1 does not resume a crashed restore; retry uses a new absent target after
explicit safe cleanup of a recognized abandoned staging directory.

A crash before target rename leaves the final target absent. A crash after target
rename and parent force but before return is caller-indeterminate; offline verification
resolves validity. A valid target is never deleted automatically because the caller
did not observe success.

### Restore result and provenance

`DurableRestoreResult` exposes target path, new history, source history, source backup
content identity, restored sequence, and authoritative byte counts. Applications may
write that immutable result as a receipt outside the live directory. Such a receipt is
diagnostic provenance, not required live authority and cannot change open/recovery
semantics.

## Restore correctness oracle

The following is a mandatory fixture, differential-test, crash-harness, and cloud
evidence oracle. A generic production restore invocation cannot invent application
queries and therefore does not execute this entire query matrix as runtime validation.
Runtime restore instead performs the complete typed decode and canonical-state checks
defined above before publication.

For sequence `B`:

```text
source logical state captured at B == restored logical state at B
```

Equivalence covers:

- canonical keys and decoded documents;
- active internal ordering, canonical slots, and `nextDocId`;
- durable dynamic-index configuration;
- equality/range/prefix/text query membership;
- ranked membership, exact score bits, and canonical order;
- phrase, fuzzy, BOOL, BOOST, filter, highlighting, Explain, pagination, cursors
  created after restore, and exact totals;
- a continued durable mutation, checkpoint, close, and second reopen on the new
  history.

Process-local snapshot versions, pre-backup cursors, Java object identity, thread
identity, timestamps, and ordinary runtime metrics need not match. Cursors from the
source history are never portable through backup.

## Safe cleanup

### Supported scopes

V4.1 cleanup is offline and supports only:

1. a closed live store whose format and authority can be structurally verified; or
2. one exact backup/restore staging directory paired with a valid sibling V4.1
   operation marker and explicitly named by the request; or
3. one orphaned sibling operation marker whose bound final target is already complete
   and valid.

It does not scan a parent for candidates, expand globs, infer ownership by prefix, or
delete arbitrary invalid targets.

### Plan

Planning is read-only and acquires exclusive ownership of the specified live store or
staging candidate. `DurableCleanupPlan` binds:

- canonical real directory and parent identities;
- history or operation ID;
- authoritative manifest/content digest when present;
- exact observed member names, types, sizes, and integrity fingerprints;
- exact ordered delete set and reason for each member;
- plan version and deterministic plan digest.

An empty plan is valid and apply is idempotent.

### Apply

Apply reacquires exclusive ownership and recomputes the bound inventory and authority.
Any path, member, size, fingerprint, operation, or authority change makes the plan
stale and deletes nothing. A valid plan deletes one exact member at a time, records
bounded progress, forces the containing directory where required, and re-verifies the
surviving authority.

Only the following may be planned:

- a uniquely named incomplete metadata/checkpoint/manifest staging member whose
  non-authority is proven by the current valid live manifest;
- an obsolete checkpoint not referenced by current authority and not pinned;
- a WAL generation proven entirely older than the authoritative checkpoint and not
  required by recovery;
- an exact abandoned V4.1 operation staging directory and its sibling marker when the
  marker binding validates, the final target is absent, the marker lock is not held,
  no symbolic/non-regular member exists, and no authoritative completed bundle/store
  would be removed;
- an orphaned sibling marker, by itself, when its bound final target independently
  verifies as complete and valid and the marker lock is not held.

Cleanup MUST NOT delete:

- `gse.lock` as an ordinary cleanup member;
- live metadata or authoritative manifest;
- an authoritative or pinned checkpoint;
- a required WAL generation or committed data;
- a complete backup or valid restored target;
- corrupt authoritative data;
- unknown, ambiguous, identity-mismatched, symbolic, or non-regular members.

Cleanup interruption may leave a smaller set of still-proven safe remnants, but must
never make previously valid authority invalid. Replanning and applying after a crash
must be safe.

## Capacity, security, and path safety

- All operations use normalized absolute paths and real existing parents.
- Source, backup, staging, and target paths are checked against equality and ancestor
  overlap before mutation.
- No operation follows symlinks for authority or payload members.
- Hard-link count or file-key checks SHOULD reject aliased payloads when the platform
  exposes them; inability to establish required path safety is
  `UNSUPPORTED_FILESYSTEM`.
- Counts and sizes are parsed before allocation using overflow-safe arithmetic.
- Usable-space checks are preflight diagnostics, not permission to exceed the explicit
  request/configuration maximum.
- Temporary bytes, pinned-source retention, and final bytes are separately measured.
- Logs/reports contain identity hashes, paths selected by the caller, sizes, sequence,
  status, and bounded reasons; they do not emit encoded keys/documents or credentials.

## Failure precedence and findings

### Backup

1. request/path/target validation;
2. engine lifecycle or operation-in-progress rejection;
3. source durability/consistency-cut failure;
4. source pin or capacity failure;
5. target materialization/hash failure;
6. bundle publication/durability failure;
7. final structural-verification failure;
8. success.

### Restore

1. request/path/existing-target validation;
2. backup structural status;
3. expected identity and semantic verification;
4. capacity and filesystem preflight;
5. target materialization;
6. staged structural/semantic validation;
7. target publication/durability;
8. final verification;
9. success.

### Cleanup

1. request/path/ownership validation;
2. structural authority and safe-remnant proof;
3. plan binding;
4. apply-time stale-plan revalidation;
5. deletion/directory durability;
6. post-apply verification;
7. success.

The primary exception follows the first failed stage. Later cleanup failures are
suppressed or recorded as findings and do not replace a known primary failure.

## Crash and fault matrix

Every named production authority transition introduced by V4.1 MUST add, in the same
change, a stable child-process barrier, abrupt-halt expectation, independent artifact
inspection, reopen/retry proof where applicable, and fake-cloud representation.

At minimum evidence covers interruption:

- before backup admission and before the writer cut;
- after `B` selection, after WAL cut, and before/after source checkpoint authority;
- before/after checkpoint pin and during payload copy;
- after each payload force and during partial writes;
- before/after completion-manifest force and rename;
- before/after final backup-directory rename and parent force;
- after final backup publication before future completion;
- during structural and semantic verification, proving no mutation;
- before/during restore decode and each target member write;
- after staged target validation before authority publication;
- before/after final target rename and parent force;
- after final target publication before method completion;
- before each safe-remnant deletion, between deletion and directory force, and during
  post-cleanup verification.

Every barrier has a frozen expected classification: source valid, bundle absent,
bundle incomplete, bundle valid, target absent, target incomplete staging, target
valid, or valid authority with safe remnants. No expected state is “production open
repairs it.”

Fault injection also covers short writes, read failure, force failure, atomic-move
failure, directory-force failure, changed-while-read files, checksum mismatch,
truncation, extra/unknown members, symlinks, target collision, pin/cleanup races,
close/backup races, and capacity exhaustion.

## Compatibility

- V4.1 MUST open published V4.0 `gse-durable (1,0)` without rewriting it merely because
  it was opened by V4.1.
- A V4.1-created or restored live store remains format `(1,0)` and is readable by
  published V4.0 when configured with matching identities.
- `gse-backup (1,0)` is new and unreadable by V4.0; that is backup-format capability,
  not live-format incompatibility.
- Published `4.0.0` becomes the next pinned Japicmp, source-consumer, binary-consumer,
  and immutable live-format fixture baseline.
- Existing V1 through V4.0 consumers remain valid. Backup APIs are additive only.
- In-memory construction and behavior allocate or execute no backup/restore code unless
  explicitly invoked.
- No live metadata field, allowed member, magic, version, checkpoint, manifest, or WAL
  meaning changes in V4.1.

## Evidence architecture from Phase 1

### Local foundation

Phase 1, before production operations, establishes:

- an independent logical backup model at sequence `B`;
- an independent restore oracle;
- immutable handcrafted `gse-backup (1,0)` fixtures;
- an independent Python byte inspector that shares no production parser;
- schema-versioned checksummed artifact bundles;
- separate-JVM crash commands and stable expected-state classifications;
- fake filesystem/fault controls where real abrupt process death is unnecessary;
- fake cloud planning, lifecycle, artifact upload, and cleanup;
- pre-change V4.0 checkpoint, recovery, latency, heap, and retained-byte evidence.

Production backup begins only in Phase 3, but every earlier verifier transition is
already exercised by the same evidence family.

### Evidence identities

- local artifact schema: `gse-v41-operational-evidence-v1`;
- cloud suite: `v4.1-operational-safety-suite-v1`;
- cloud preset: `v4.1-operational-safety-v1`;
- final registration: `v4.1.0-operational-cloud`.

These identities are distinct from and cannot replace `v4.0.0-durable-cloud`.

### Cloud resource and cost envelope

- trusted source is an exact protected-`master` commit;
- authentication remains environment-bound OIDC with no stored service-account key;
- Standard `c3d-standard-30` is the reference machine unless Phase 1 calibration
  proves it unavailable or unsuitable through a contract amendment;
- source and restore storage use `pd-balanced`, at most 200 GiB each;
- members run serially so a 32-vCPU global quota and 500-GiB regional SSD quota are
  not exceeded by workflow concurrency;
- experiment profile uses one member; canonical uses three independent members;
- canonical and source-loss failure-drill evidence require durable GCS retention;
- Actions retention alone is noncanonical;
- every VM has a maximum runtime and delete-on-expiry policy;
- every run reports VM, source disk, restore disk, staging object, and local artifact
  cleanup independently;
- no paid workflow runs before a dry-run plan, fake-cloud test, exact-source CI, and
  explicit manual confirmation pass.

Phase 1 freezes exact corpus, operation counts, duration, maximum runtime, GCS layout,
and budget ceiling after local calibration and before paid work. Those values may not
drift between canonical members.

### Replacement-host proof

The canonical source-loss lane MUST:

1. create and mutate a source store;
2. establish exact source state and backup `B`;
3. upload the verified bundle and evidence through durable transport;
4. make the source VM and source live disk unavailable to the restore step;
5. create a new empty restore disk and replacement VM;
6. download and independently verify the bundle;
7. restore a new history and compare the full correctness oracle;
8. perform a continued durable mutation, checkpoint, close, and second reopen;
9. retain checksummed evidence and prove cleanup.

GCS transports immutable bundles/evidence only. It is not a live WAL, live checkpoint,
or remotely authoritative store.

## Phase ownership

| Phase | Authorized work | Explicitly not yet authorized |
|---|---|---|
| 0 | these documents and indexes | version/code/tests/harness/cloud changes |
| 1 | `4.1.0-SNAPSHOT`, published-4.0 gates, public fixtures, independent models, immutable format fixtures, crash/fake-cloud scaffolding, calibrated evidence plan | production verifier/backup/restore/cleanup; paid run |
| 2 | codec-free read-only structural verification/reporting | backup, restore, deletion |
| 3 | live backup, checkpoint pin, bundle writer, backup interruption/lifecycle | restore and cleanup |
| 4 | typed semantic verification, logical new-history restore, restore crash matrix | safe-remnant deletion |
| 5 | plan-bound cleanup, operational integration, full fault/lifecycle matrix | new feature semantics |
| 6 | profiling, large corpus, source-loss/replacement-host, experiment/canonical cloud, registration | speculative optimization |
| 7 | final coordinates, consumers, compatibility, Javadocs, artifacts, reproducibility, release docs | publication |
| 8 | signed tag, Central, GitHub Release, deployment and post-publication proof | later-version work |

## Phase 0 exit gate

Phase 0 exits only when the separate checklist confirms:

- scope and inherited semantics are explicit;
- checkpoint-only `B`, pinning, concurrency, and close behavior are frozen;
- bundle member set, encoding policy, SHA-256 identity, bounds, and publication are
  frozen;
- public API ownership and structural/semantic separation are frozen;
- new-history logical restore and unchanged live format `1.0` are reconciled;
- absent-target staging/finalization and indeterminate completion are frozen;
- verifier classifications/findings and no-repair behavior are frozen;
- offline plan-bound cleanup and exact refusal rules are frozen;
- crash/fault states and Phase 1-first infrastructure are frozen;
- cloud identities, source-loss topology, quota-safe serialization, retention,
  cleanup, and paid-run authorization are frozen;
- compatibility and phase ownership are explicit.

After protected acceptance, Phase 1 may open `4.1.0-SNAPSHOT`, pin published `4.0.0`,
and implement the non-production model, fixture, crash-harness, and fake-cloud
foundation. Production V4.1 operational code remains prohibited until its owning
phase.
