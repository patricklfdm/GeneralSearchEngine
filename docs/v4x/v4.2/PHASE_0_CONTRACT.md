# GeneralSearchEngine V4.2 Phase 0 storage-evolution contract

- **Phase:** 0 — Storage-evolution contract freeze
- **Status:** Accepted through protected PR #106 at `8391ea67`; Phase 1 active
- **Reference baseline:** Published GeneralSearchEngine `4.1.0`
- **Production V4.2 implementation:** Authorized only by the owning later phase

## Authority and interpretation

This document is the normative V4.2 contract. The
[development charter](DEVELOPMENT_CHARTER.md) defines the release boundary, and the
[Phase 0 checklist](PHASE_0_CHECKLIST.md) records whether every required decision is
explicit. If this contract conflicts with published V4.0 or V4.1 guarantees, Phase 0
is blocked; it does not silently amend them.

Normative terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` have their ordinary standards
meaning. Examples are explanatory unless they repeat an explicit requirement.

## Inherited guarantees

V4.2 inherits without reinterpretation:

- immutable search snapshots, lock-free readers, one authoritative writer, and
  atomic publication;
- all V3.4 matching, ranking, ordering, pagination, highlighting, Explain, timeout,
  cancellation, and lifecycle semantics;
- the in-memory default and opt-in durable construction boundary;
- V4.0 force-before-completion, contiguous logical-unit sequencing, bulk atomicity,
  incomplete-future indeterminacy, deterministic recovery, and corruption fail-close;
- live family `gse-durable`, exact published format `(1,0)`, history identity,
  checkpoint authority, WAL-generation, and retained-byte semantics;
- V4.1 codec-free structural verification, typed semantic verification, exact-cut
  backup, new-history restore, and plan-bound safe cleanup;
- backup family `gse-backup`, exact published format `(1,0)`, three-member inventory,
  and `gse-backup-content-v1` identity meaning; and
- all published Java source/binary compatibility and two-artifact release boundaries.

Migration does not turn a formerly unsuccessful or indeterminate source mutation
into a committed mutation. Only the source's independently recovered canonical state
at its authoritative durable sequence is eligible.

## Exact reference identity

The published predecessor is the signed tag `v4.1.0` at commit
`9db6efce275d25eb8da75d6532ea103982e591c6`. Release workflow run `33820284974`,
production deployment `6255241071`, GitHub Release `382405193`, and Maven Central
coordinates:

```text
io.github.patricklfdm:general-search-engine:4.1.0
io.github.patricklfdm:general-search-engine-processor:4.1.0
```

are the external API/artifact baseline. The accepted operational evidence baseline is
`v4.1.0-operational-cloud`, source
`88205cf28f1aa80f8ea7ccf1bada723b3205215c`, canonical run `33758217508`, and set
digest `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27`.

Phase 1 MUST resolve the published artifacts in a fresh isolated repository and pin
immutable `(1,0)` live/backup fixtures from the release. A reactor install, current
working-tree class, or mutable cloud artifact is not a substitute for this baseline.

## Terms

- **source:** one closed, exclusively lockable, canonical live-store directory.
- **target:** one absent directory into which apply may publish a migrated history.
- **S:** the exact durable sequence represented by the canonical source checkpoint.
- **source authority identity:** a migration-only SHA-256 identity over the exact
  canonical authoritative source-member inventory and bytes.
- **format:** immutable family, major, and minor values attached to live storage.
- **format profile:** the canonical list of encoding capabilities whose digest is
  bound by every authority-bearing `(1,1)` member.
- **edge:** one explicitly supported source-format to target-format transition.
- **transform:** deterministic versioned application code mapping one decoded source
  key/document pair to one target key/document pair.
- **projection:** the complete target logical state and canonical encoded-byte hashes
  computed without publishing a target.
- **plan:** an immutable dry-run result binding source authority, target boundary,
  target history, formats, identities, transform, projection, bounds, and digest.
- **apply:** the only V4.2 operation permitted to publish migrated target bytes.
- **cutover:** an external operator action that routes an application to a verified
  target; it is not a library migration step.
- **rollback:** stopping the target and reopening the preserved source; it does not
  merge target-only writes.

## Non-goals

V4.2 MUST NOT provide automatic-open rewrite, in-place conversion, online/live-source
migration, downgrade, direct backup-bundle migration, source cleanup, directory swap,
symlink cutover, record filtering, record fan-out, history merge, repair, salvage,
persisted derived indexes, replication, remote live storage, or new retrieval
semantics.

## Public API ownership

All V4.2 product API remains in `general-search-engine`. No new Maven module, service
provider, reflection-loaded transformer, or supported general-purpose CLI is added.

### Format selection

A public immutable format value represents family, major, and minor and exposes exact
constants for `gse-durable (1,0)` and `(1,1)`. `DurableStorageConfig.Builder<K,T>`
gains additive explicit format selection.

The builder default MUST remain `(1,0)`. For an existing store, configured format is
an exact expectation, not an upgrade request. A mismatch fails before recovery or
write. Selecting `(1,1)` for an existing `(1,0)` directory MUST NOT migrate it.

Phase 1 freezes the exact type name, constructor/factory behavior, accessor names,
constant names, equality, validation, and builder descriptor.

### Codec-free format inspection

`DurableStorageOperations` gains additive synchronous read-only operation families
conceptually equivalent to:

```java
DurableStoreFormatReport inspectStoreFormat(Path directory);
DurableBackupFormatReport inspectBackupFormat(Path directory);
```

The store report combines the existing structural report with an optional declared
live format and optional profile digest. The backup report additionally exposes an
optional declared backup format and source live format. A malformed or incomplete
header may leave a declaration absent; an intact unsupported or incompatible header
is retained alongside its structural classification. Reports never load a user codec,
repair bytes, or claim semantic validity. Live-store inspection remains offline and
exclusive; immutable bundle inspection permits concurrent readers.

Phase 1 freezes the exact operation names, report components, optionality, and
relationship to the existing verification methods. Existing V4.1 report record
components and enum order MUST NOT change.

### Typed migration operations

The target `SearchEngineBuilder<TK,TT>` owns the target schema and startup indexes and
adds one planning and one apply family conceptually equivalent to:

```java
<SK,ST> DurableMigrationPlan planDurableMigration(
        SearchEngineBuilder<SK,ST> sourceBuilder,
        DurableMigrationRequest<SK,ST,TK,TT> request);

<SK,ST> DurableMigrationResult applyDurableMigration(
        SearchEngineBuilder<SK,ST> sourceBuilder,
        DurableMigrationRequest<SK,ST,TK,TT> request,
        DurableMigrationPlan plan);
```

Both operations are synchronous, typed, offline, and reject `null`. Planning is
read-only. Apply mutates only a unique target staging boundary and the absent target.

The source builder supplies the source schema, business-ID extraction, analyzed-field
configuration, and exact expected logical startup indexes. Phase 1 MAY replace the
mutable builder parameter with an immutable public source descriptor captured from a
builder, but the operation MUST receive equivalent typed source semantics and bind
their canonical descriptor in the plan. Apply rejects a changed source descriptor.

The request MUST contain:

- exact source directory;
- expected source storage/schema identities and source codec/version;
- source decode and resource bounds;
- target `DurableStorageConfig<TK,TT>` including explicit target format;
- versioned transform implementation and descriptor;
- maximum source authoritative bytes;
- maximum target authoritative bytes; and
- explicit filesystem-capacity safety reserve.

The transform consumes one source business key and document and returns exactly one
target business key and document. Its descriptor contains a stable lowercase
identifier and non-negative version. Returning `null`, returning a null component,
throwing, changing target bytes between plan and apply, or producing a key unequal to
the target schema's extracted ID is failure.

Phase 1 MUST freeze exact generic descriptors, immutable component order, enum order,
path normalization, collection copying, equality/hash semantics, Javadocs, and an
independently compiled public consumer. It MAY refine the conceptual type/accessor
names above. It MUST NOT move migration to an untyped or codec-free owner or combine
planning and apply into one call without a Phase 0 amendment.

### Migration failure family

V4.2 introduces `DurableMigrationException` rather than appending values to the
published V4.1 `DurableOperationException.Reason` enum. Its stable reason family MUST
distinguish at least:

- `STORAGE_IN_USE`;
- `SOURCE_INVALID`;
- `IDENTITY_MISMATCH`;
- `MIGRATION_PATH_UNSUPPORTED`;
- `MIGRATION_NOT_REQUIRED`;
- `PLAN_STALE`;
- `TRANSFORM_FAILURE`;
- `TRANSFORM_NONDETERMINISTIC`;
- `TARGET_EXISTS`;
- `TARGET_INVALID`;
- `UNSUPPORTED_FILESYSTEM`;
- `CAPACITY_EXCEEDED`;
- `IO_FAILURE`; and
- `PUBLICATION_INDETERMINATE`.

The exception retains the reason, stable operation stage, optional non-negative
source sequence, and original cause when safe. Messages and reports MUST NOT include
encoded key/document payloads, credentials, environment tokens, or unbounded custom
exception text.

## Readable-format policy

V4.2 supports exact live formats `(1,0)` and `(1,1)` only.

| Observed header | Classification |
|---|---|
| exact `gse-durable (1,0)` and valid bytes | supported |
| exact `gse-durable (1,1)` and valid known profile | supported |
| same family/major with intact higher minor | incompatible |
| known `(1,1)` with intact unknown required capability | incompatible |
| another family or major | unsupported |
| claims known format/profile but violates its bytes or binding | corrupt |
| missing/recognizably unfinished authority | incomplete |

Readers MUST select parsing rules from an intact header before parsing versioned
payload fields. They MUST NOT guess a minor from filename, payload length, directory
enumeration, or a later member. No higher minor is treated as backward compatible
without a future explicit reader and fixture matrix.

Opening `(1,0)` through V4.2 writes only `(1,0)` checkpoints, manifests, and WAL.
Opening `(1,1)` writes only `(1,1)`. A mixed-minor history is corrupt even when
individual members are otherwise valid. Neither open path writes a format-selection
marker merely because the dependency version changed.

## Format `(1,1)` semantics

### Functional delta

`(1,1)` preserves the canonical document, business-key, internal-slot,
`nextDocId`, logical index-configuration, sequence, checkpoint-authority, WAL-unit,
CRC32C, and recovery meaning of `(1,0)`.

It adds one canonical format profile. Metadata stores the full profile and every WAL
header, checkpoint-data header, and checkpoint manifest binds its SHA-256 digest.
The digest domain is `gse-durable-format-profile-v1` followed by the canonical
profile encoding.

The initial required capability identifiers, in canonical UTF-8 byte order, are:

```text
canonical-documents-v1
checkpoint-authority-v1
crc32c-wal-v1
logical-index-config-v1
sha256-profile-binding-v1
```

The optional-capability set is empty. V4.2 does not accept unrecognized optional
members by inference. Profile identifiers are non-empty lowercase ASCII, bounded to
128 bytes each, unique, and canonically ordered. Capability count and total encoded
profile bytes are independently bounded.

The same profile digest MUST appear in every authority-bearing member of one history.
Missing, mismatched, reordered, duplicate, or incorrectly hashed known profile data
is corruption. An intact different required set is incompatible, not corruption.

### Physical boundary

`(1,1)` retains the `(1,0)` directory roles and naming families. It does not add a
derived-index member, provenance sidecar, migration receipt, mutable profile file, or
unknown-member allowance. Exact byte layout, magic, field offsets, maximum counts,
and independent fixture hashes are Phase 2 deliverables governed by the semantics
above.

### Explicit construction

Fresh `(1,1)` construction is allowed only through explicit format selection and is
implemented in Phase 3. It creates a new history and the canonical initial
`(1,1)` member set. Default/fresh `(1,0)` creation remains byte-identical to published
V4.1 for equivalent deterministic inputs.

## Backup-format policy

`gse-backup (1,0)` remains immutable and is produced only from a `(1,0)` source.
V4.2 adds `gse-backup (1,1)` for a `(1,1)` source.

Both minors retain exactly:

```text
gse-backup-metadata
gse-backup-checkpoint
gse-backup-manifest
```

The `1.1` bundle embeds exact `(1,1)` source metadata/checkpoint bytes and binds the
source format profile digest in its completion manifest. It uses a new exact digest
domain `gse-backup-content-v2` and identity
`gse-backup-v2-<64 lowercase SHA-256>`. The backup minor, source minor, profile digest,
and otherwise frozen manifest identity/payload fields are canonical `v2` inputs.
The published `v1` digest algorithm and identity accept only backup `(1,0)` and are
never extended in place.

A `(1,0)` bundle never becomes `(1,1)` because V4.2 reads it. V4.2 restore preserves
the bundle's source format in its new-history target. Format conversion is available
only through migration. Published V4.1 is required only to classify intact `(1,1)`
bundles as incompatible under its existing higher-minor policy.

Phase 2 freezes exact `1.1` bundle bytes and extends independent structural parsing.
Phase 3 extends backup and restore only after live `(1,1)` publication is supported.

## Supported migration edges

V4.2 supports exactly:

| Source | Target | Conditions |
|---|---|---|
| `gse-durable (1,0)` | `gse-durable (1,1)` | format-only identity transform or declared codec/schema/key transform |
| `gse-durable (1,1)` | `gse-durable (1,1)` | at least one declared storage/schema/codec/transform/index identity differs |

`(1,0)` to `(1,0)`, `(1,1)` to `(1,0)`, any unknown version, and any hidden multi-hop
edge are rejected. Future edges require a new accepted minor-release contract and an
append-only edge registry; they cannot be activated by configuration or a plugin.

## Source eligibility

Planning and apply MUST independently prove all of the following:

1. source path resolves to an existing real local directory and is not a symlink;
2. exclusive V4 ownership is acquired for the complete operation;
3. codec-free verification reports exact `VALID`, not safe remnants;
4. expected format, storage identity, schema identity, codec identity/version, and
   logical index configuration match;
5. the authoritative manifest selects a complete checkpoint at `S`;
6. the post-checkpoint WAL generation exists, begins at `S + 1`, contains no logical
   frames or incomplete tail, and has valid header/profile binding;
7. no extra, staging, cleanup, operation-marker, unknown, symlink, special-file,
   cross-history, or mixed-format member exists;
8. full typed decode is canonical and within source bounds;
9. `S` and `nextDocId` permit a writable target continuation; and
10. complete source member content hashes match the plan/apply observation.

Migration MUST NOT invoke production recovery if recovery would truncate, rewrite,
checkpoint, clean, or publish source bytes. Operators explicitly checkpoint, close,
verify, and clean the source before planning.

Lock acquisition and ordinary filesystem access-time metadata are coordination and
platform effects, not source-byte mutation. File content, length, member inventory,
and authority identity MUST remain byte-identical before and after plan/apply.

## Target and path eligibility

- The target is absent; an existing empty directory is rejected.
- Source and target MUST NOT overlap in either ancestor direction.
- Source, target parent, staging, marker, backup, and any configured temporary path
  are checked by normalized absolute path, existing-ancestor real path, and
  `Files.isSameFile` where available.
- Symlink aliases, special files, and recognizable hard-link aliases are rejected.
- The target parent and unique sibling staging directory reside on the same supported
  local filesystem so final rename can be atomic.
- Atomic move, file force, directory force, and usable-space queries must be
  supported before transformation begins.
- Apply never follows a link created after planning; changed path identity is stale.

## Transform contract

For every source slot in ascending internal document-ID order:

1. decode the complete canonical source key and document under source bounds;
2. invoke the transform once with that pair;
3. require one non-null target key/document pair;
4. require target-schema business-key extraction to equal the returned target key;
5. encode key/document canonically under target codec and bounds;
6. require decode/encode round-trip equality under the target codec;
7. reject duplicate target keys or duplicate target canonical key bytes; and
8. preserve that source slot as the target slot.

The transform MUST be deterministic for the complete request and MUST NOT depend on
clock, randomness, host, thread, environment, mutable global state, network, directory
enumeration, or invocation count. The implementation is called serially in plan and
again in apply. V4.2 does not sandbox arbitrary application code; deterministic,
side-effect-free behavior is a caller obligation, and output mismatch is detected and
rejected.

No source record may be dropped, duplicated, split, merged, or reordered. Target
document count equals source document count. A changed business-key type/value is
allowed only when the one-to-one and uniqueness rules pass.

Target startup indexes are exactly the ordered definitions on the target builder.
Source logical indexes are decoded and recorded in the plan but are not silently
copied when the target schema differs. The plan exposes a deterministic added/
removed/retained descriptor comparison. A non-identical target index configuration
is itself a declared migration change and is bound into the plan digest; it does not
require document bytes to change when an identity transform is otherwise valid.

## Planning algorithm

Planning MUST complete the following without creating any target, staging, marker,
receipt, cache, or spill file:

1. validate request values and supported edge;
2. resolve path identities and acquire source ownership;
3. inspect target absence and filesystem capabilities;
4. structurally verify the source with an independent-code-path cross-check;
5. hash the complete canonical authoritative source inventory;
6. semantically decode the source and validate expected identities/indexes;
7. allocate one non-zero target history distinct from source and freeze it in plan;
8. stream the transform and target encoding in stable source-slot order;
9. compute exact target canonical state, profile, index, member, and projection
   digests without retaining the corpus in heap;
10. detect all transform, key, bound, count, arithmetic, and sequence failures;
11. calculate target authoritative bytes, staging peak, and safety reserve with
    overflow-safe arithmetic;
12. require current usable space and caller maximum to satisfy the complete bound;
13. rehash source authority before releasing ownership; and
14. construct the immutable canonically encoded plan and plan digest.

Planning MAY use bounded in-memory collision structures proportional to document
count within the frozen hard limit. It MUST NOT persist a hidden cache that apply
trusts instead of rerunning the transform.

Planning allocates a fresh target history. Repeated planning over otherwise identical
inputs therefore MAY produce distinct valid plans, projections, and digests. Once a
plan exists, its encoding and digest are deterministic and immutable.

## Plan identity and staleness

The plan digest domain is `gse-migration-plan-v1`. Canonical inputs include at least:

- plan schema version;
- source/target normalized path identities;
- source family/version/history/sequence/`nextDocId`;
- ordered source member names, sizes, and SHA-256 hashes;
- source authority identity;
- source storage/schema/codec identity and codec version;
- canonical source schema, business-ID, analyzed-field, and startup-index descriptors;
- ordered source logical-index descriptors;
- target family/version/history and complete format-profile digest;
- target storage/schema/codec identity, version, bounds, and ordered index descriptors;
- transform identifier/version;
- document and index counts;
- target authoritative bytes and capacity reserve;
- projection digest; and
- canonical added/removed/retained index comparison.

The printed identity is `gse-migration-plan-v1-<64 lowercase SHA-256>`. The target
projection identity is independently domain-separated as
`gse-migration-projection-v1-<sha256>`.

Plan timestamps, hostnames, PIDs, elapsed time, free-space observations, and diagnostic
messages are not identity inputs. A plan grants permission only while every authority,
path, configuration, transform, and projection binding remains exact.

## Apply algorithm

Apply MUST:

1. validate request/plan structural equality and digest;
2. resolve paths and reacquire exclusive source ownership;
3. prove target absence and marker/staging ownership;
4. recompute source structure, semantics, inventory, and authority identity;
5. recheck target filesystem capabilities, caller bounds, and usable capacity;
6. create and force one externally locked operation marker;
7. create one unique sibling staging directory;
8. rerun the transform in canonical order while writing fresh target bytes;
9. reproduce the exact planned projection or fail as non-deterministic;
10. force each file and staging directory in the contracted order;
11. independently parse and typed-verify the complete staged target;
12. require source authority to remain byte-identical;
13. atomically rename staging to the absent final target and force the parent;
14. independently verify and normally open/close the final target;
15. reverify source byte identity;
16. remove and force the operation marker only after target authority is resolved; and
17. return immutable result/provenance.

Target writing is a logical decode/transform/re-encode operation. Source checkpoint,
metadata, WAL, history-bound bytes, manifests, and locks are never copied as target
authority.

## Target canonical state

Successful migration preserves:

- durable logical sequence `S`;
- source internal document-slot order;
- source `nextDocId`;
- exactly one target record per source record; and
- atomic logical-state completeness.

It changes:

- history identity to the plan's new non-zero target history;
- format according to the supported edge;
- storage/schema/codec identities only as explicitly requested;
- key/document bytes only through the versioned transform; and
- logical index configuration to the exact target builder descriptors.

The initial target checkpoint is authoritative at `S`. The canonical empty target WAL
generation begins at `S + 1`. The target MUST pass codec-free structural verification,
typed semantic reconstruction, complete document/key equality with the planned
projection, target index reconstruction, a normal production open, and close.

No source cursor, snapshot object identity, process-local version, metric, diagnostic,
lock, or operation receipt is migrated.

## Publication states and completion

| Last durable transition | Final target | Allowed independent classification |
|---|---|---|
| before target staging | absent | absent |
| partial staging/member writes | absent | recognizable incomplete migration remnant |
| staged bytes forced, not renamed | absent | complete non-authoritative staging remnant |
| final rename before parent force | present | valid target, publication durability indeterminate |
| parent force complete | present | valid authoritative target |
| final verification before return | present | valid authoritative target; caller completion indeterminate |

Successful method return means target rename and parent force completed, structural
and semantic verification passed, normal open/close passed, source bytes still match,
and marker cleanup completed. It does not mean application traffic was cut over.

A process crash may make method completion indeterminate after target publication.
Operators resolve this by exact target verification and plan/result identity, never by
rerunning apply against an existing target.

## Source preservation and rollback

Plan and apply MUST record ordered source-member content hashes before and after.
Any content, length, inventory, history, sequence, or authority change is failure.
Apply NEVER deletes, renames, cleans, checkpoints, truncates, or writes the source.

Before migration, operators retain a verified `gse-backup (1,0)` outside both source
and target. After migration they verify the target, run bounded continued mutation,
checkpoint, close, and reopen before cutover. The original source remains stopped and
unchanged through the rollback window.

Published `4.1.0` MUST reopen the untouched `(1,0)` source with matching application
identities. It is not required to open `(1,1)`. Once the target accepts post-cutover
writes, rollback loses those writes unless the application reconciles them outside
GSE. V4.2 provides no reverse migration or history merge.

## Cleanup integration

V4.2 extends `OPERATION_REMNANT` cleanup classification only for exact migration
staging and marker names with independently proven operation identity. A complete
target, any source member, an unknown sibling, a changed plan, ambiguous ownership,
or corrupt authoritative bytes are never deleted.

Cleanup remains offline, dry-run-first, and separately invoked. Apply does not scan a
parent or opportunistically remove remnants from another attempt. A retry requires a
new absent target path after exact cleanup of a proven remnant.

## Failure precedence

The primary failure is the earliest failure that prevents a trustworthy next
authority state. Later cleanup errors are suppressed and reported separately; they do
not replace transform, force, validation, rename, or source-preservation failure.

Pre-publication apply failure leaves target absent and source valid. Post-rename
failure first resolves whether target authority is valid; if valid, the exception is
publication indeterminacy rather than a claim that migration did not occur. Source
corruption or mutation observed at any point is always a hard source-preservation
failure and no target is accepted by the operation.

## Capacity and resource bounds

The request and implementation enforce hard maximums for:

- source authoritative members and bytes;
- source and target encoded key/document bytes;
- document count and collision entries;
- logical index descriptor count and encoded bytes;
- format-profile capability count and bytes;
- target authoritative and staging bytes;
- finding count and diagnostic bytes; and
- path and identity encoding lengths.

All addition and multiplication use exact overflow checks. Planning reports predicted
target authoritative bytes, peak target-filesystem demand, safety reserve, and current
usable-space observation. Apply recomputes all four. Capacity failure publishes no
target and does not alter source authority.

Migration streams canonical records and MUST NOT retain all decoded documents or all
encoded payloads in heap. Collision detection may use a bounded key digest/index
structure. Phase 1 freezes measurable hard limits before production code.

## Security and diagnostics

- No persisted key/document bytes, decoded `toString()`, credentials, tokens, or
  application exception messages appear in stable diagnostics.
- Paths in reports are caller-selected normalized paths and remain bounded.
- SHA-256 identities are diagnostic/integrity values, not authentication.
- User transforms execute with application privileges; V4.2 does not claim sandboxing.
- The migration API never loads code by persisted class name, transform identity, or
  service discovery.
- Unknown format capabilities, members, identities, and migration edges fail closed.
- Verification and migration never repair corrupt committed source bytes.

## Crash and fault matrix

Phase 1 establishes stable harness commands before production migration. At minimum,
evidence covers interruption:

- before/after source lock and initial authority hash;
- throughout plan decode/transform/projection, proving no filesystem mutation;
- before/after marker publication and staging creation;
- before/during/after each metadata, checkpoint, manifest, and WAL write/force;
- before/after staging-directory force;
- during independent staged structural and semantic verification;
- after staged verification before final rename;
- immediately before/after atomic target rename;
- before/after target-parent force;
- during final target verification and normal open/close;
- before/after final source identity comparison;
- before/during/after marker deletion and parent force; and
- after complete authority before method return.

Fault injection covers short writes, read/force/rename/directory-force failure,
ENOSPC, changed usable space, changed source member, stale plan, target collision,
symlink/hard-link alias, unknown member, malformed profile, mixed minor, transform
throw/null/key mismatch/collision/non-determinism, codec failure, index rebuild
failure, source lock contention, and cleanup failure.

Every crash barrier has a frozen expectation for source validity, target absence or
validity, staging/marker classification, source byte identity, and safe cleanup. No
expected state relies on production open repairing source or target.

## Compatibility matrix

| Producer / operation | Published 4.1 | V4.2 |
|---|---|---|
| open/write `gse-durable (1,0)` | supported | supported without rewrite |
| create default durable store | creates `(1,0)` | creates `(1,0)` |
| explicit create `gse-durable (1,1)` | unavailable | supported |
| open/write `gse-durable (1,1)` | incompatible | supported with exact selection |
| verify/restore `gse-backup (1,0)` | supported | supported unchanged |
| verify/restore `gse-backup (1,1)` | incompatible | supported |
| plan/apply migration | unavailable | supported for exact registered edges |

Published `4.1.0` becomes a pinned Japicmp, source consumer, binary consumer, live
format, backup format, operational API, and rollback baseline. V4.2 API additions are
additive. Existing V1–V4.1 consumers and in-memory behavior remain valid.

## Evidence architecture from Phase 1

### Local foundation

Before production `(1,1)` writing, Phase 1 adds:

- independent logical migration and new-history target models;
- a declaration-only public API fixture and external consumer;
- immutable handcrafted `(1,0)` source and `(1,1)` target/bundle fixtures;
- independent Python parsing for both live and backup minors;
- source-before/source-after byte-identity assertions;
- schema-versioned checksummed plan/apply artifacts;
- separate-JVM crash modes and stable expected-state classifications;
- deterministic codec/transform/filesystem fault controls;
- fake cloud resource, attachment, replacement-host, retention, and cleanup behavior;
- published-4.1 source reopen/rollback proof; and
- pre-change `(1,0)` recovery, backup, restore, heap, disk, and latency evidence.

Production format readers/writers and migration remain prohibited in Phase 1.

### Evidence identities

- local artifact schema: `gse-v42-migration-evidence-v1`;
- cloud suite: `v4.2-storage-evolution-suite-v1`;
- cloud preset: `v4.2-storage-evolution-v1`;
- eventual registration: `v4.2.0-migration-cloud`.

These identities are independent from `v4.0.0-durable-cloud` and
`v4.1.0-operational-cloud`.

### Cloud topology and authorization

The eventual canonical member MUST:

1. validate an exact protected-`master` source commit;
2. create or materialize a published-4.1-compatible canonical `(1,0)` source on its
   own persistent disk;
3. record source oracle, exact bytes, sequence, and independently verified `(1,0)`
   backup;
4. checkpoint, close, and prove canonical migration eligibility;
5. plan and apply to an absent `(1,1)` target on a distinct persistent disk;
6. prove source bytes unchanged;
7. detach target authority and attach it to a replacement VM;
8. independently inspect, open, compare, continue mutation, checkpoint, close, and
   reopen the target;
9. stop target writing before rollback proof;
10. reopen the original untouched source using the published `4.1.0` artifact and
    compare the pre-cutover oracle;
11. retain checksummed evidence; and
12. prove VM, disk, staging object, and local workspace cleanup independently.

Source and target writers never run concurrently. GCS stores immutable fixtures and
evidence only. It is not source/target authority, WAL, or cutover state.

Experiment uses one member and canonical uses three independent serial members.
Serial execution MUST stay within the established 32-vCPU global and 500-GiB regional
SSD quotas by deleting each member's resources before the next begins. Phase 1 freezes
exact machine, disks, corpus, transformations, durations, maximum runtime, cost,
retention, GCS prefix, OIDC conditions, and cleanup order.

No paid run occurs before local smoke, fake cloud, dry-run, exact-source CI, explicit
confirmation, and resource/cost plan validation. Only Phase 6 may run or register paid
evidence.

## Phase ownership

| Phase | Authorized work | Explicitly not yet authorized |
|---|---|---|
| 0 | these documents and indexes | version/code/tests/harness/cloud changes |
| 1 | `4.2.0-SNAPSHOT`, published-4.1 gates, API fixtures, models, immutable format/migration fixtures, crash/fake-cloud scaffolding and calibrated evidence plan | production `1.1` reader/writer, migration, paid run |
| 2 | public format values/reports, exact `1.1` bytes, codec-free dual-minor structural inspection and independent parsers | production `1.1` open/write, target publication and migration apply |
| 3 | explicit fresh `1.1`, `1.1` backup/restore, format-only `1.0` to `1.1` plan/apply | codec/schema/key transform migration |
| 4 | versioned typed transforms, changed identities, key collision rules, target-index rebuild | cutover automation or source deletion |
| 5 | lifecycle, interruption, safe-remnant cleanup, rollback and cross-version hardening | paid evidence or speculative optimization |
| 6 | scale/profiling, replacement-host and published-4.1 rollback evidence, experiment/canonical cloud and registration | unmeasured optimization |
| 7 | final coordinates, consumers, compatibility, Javadocs, artifacts, reproducibility and release docs | publication |
| 8 | signed tag, Central, GitHub Release, deployment and post-publication proof | later-version work |

## Phase 0 exit gate

Phase 0 exits only when the checklist confirms:

- inheritance, non-goals, explicit-only `(1,1)`, and no silent rewrite are frozen;
- readable-format and migration-edge policies are exact;
- `1.1` profile semantics and backup/restore continuity are reconciled;
- typed API ownership, transform cardinality, plan/apply split, and failure family are
  frozen;
- source eligibility, byte preservation, target absence, path safety, and capacity
  semantics are explicit;
- plan/projection identities and stale/non-deterministic refusal are explicit;
- new-history target state, publication durability, completion indeterminacy,
  rollback, and cleanup are explicit;
- crash/fault states and Phase 1-first infrastructure are frozen;
- cloud identities, topology, quota serialization, retention, cleanup, and paid-run
  authorization are frozen; and
- compatibility and phase ownership are explicit.

After protected acceptance, Phase 1 may open `4.2.0-SNAPSHOT`, pin published `4.1.0`,
and implement only the non-production fixture/model/harness/fake-cloud foundation.
Production format or migration implementation remains prohibited until its owning
phase.
