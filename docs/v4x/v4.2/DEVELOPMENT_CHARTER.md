# GeneralSearchEngine V4.2 development charter

- **Status:** Accepted governing charter; Phase 3 active
- **Predecessor:** Published GeneralSearchEngine `4.1.0`
- **Theme:** Storage Evolution

## Purpose

V4.0 established correct single-node durability and V4.1 made that durable history
safe to verify, back up, restore, and clean. V4.2 addresses the next boundary:

> How can an operator move canonical durable state across an explicit format, codec,
> or schema boundary without mutating the source or weakening fail-closed recovery?

V4.2 is an offline migration release. It is neither an online-upgrade mechanism nor
the persisted-derived-index release planned for V4.3.

## Governing principles

1. Published V4.0 durability, V4.1 operational safety, and V3.4 retrieval semantics
   remain frozen.
2. Merely opening a store never rewrites its format, identity, codec, schema, WAL,
   checkpoint, manifest, or history.
3. The existing default remains `gse-durable (1,0)`; creation of `(1,1)` is explicit.
4. Migration is offline, dry-run-first, source-preserving, and absent-target only.
5. A migration target is a new history at the exact source durable sequence, never a
   second writable copy of the source history.
6. Format, codec, schema, business-key, and index-configuration changes are declared
   and bound to one versioned transform identity.
7. Planning performs the complete bounded transform without publishing bytes; apply
   must reproduce the plan or fail closed.
8. The source remains the rollback authority until an independently verified target
   is explicitly selected by the operator.
9. V4.2 defines reusable format descriptors and migration-edge policy for later V4.x
   releases rather than embedding a one-off `1.0` converter.
10. Independent byte models, separate-process crashes, fake cloud, durable disks, and
    rollback proof are first-class architecture from Phase 1 onward.

## Scope

V4.2 adds:

- a public immutable live-format value with supported `gse-durable (1,0)` and `(1,1)`
  constants;
- explicit target-format selection on durable storage configuration while retaining
  `(1,0)` as the default;
- codec-free store/bundle format inspection reports that retain structural status,
  declared format, source format, and optional profile binding without a user codec;
- a `1.1` format profile that binds every authoritative member to one canonical
  format descriptor;
- `gse-backup (1,1)` for exact backups of `gse-durable (1,1)` histories while
  retaining `gse-backup (1,0)` unchanged;
- typed offline migration planning and apply operations owned by the target search
  schema builder;
- a versioned one-source-record-to-one-target-record transform contract;
- exact source-authority, target-projection, transform, capacity, and path binding in
  an immutable dry-run plan;
- fresh-history target publication at the source sequence with preserved slot order
  and `nextDocId`;
- independent structural and typed semantic target verification before success;
- source byte-identity proof before and after every apply attempt;
- stable migration failure categories and bounded diagnostics;
- immutable `1.0` source, `1.1` target, transform, corruption, and interrupted-
  publication fixtures;
- interruption testing at every target-authority boundary; and
- durable-cloud evidence that proves successful migration, target portability,
  continued operation, and published-4.1 rollback from the untouched source.

## Explicit exclusions

- automatic migration during open, build, backup, restore, checkpoint, or recovery;
- in-place migration, source deletion, source rename, directory swap, symlink switch,
  traffic cutover, or rollback automation;
- online migration from a running engine or a source with active WAL mutations;
- direct migration from a backup bundle, partial store, or safe-remnant state;
- downgrade from `(1,1)` to `(1,0)`;
- multi-hop migration hidden inside one call;
- filtering, splitting, merging, duplicating, or reordering source records;
- best-effort transform recovery, skipped decode failures, or key-collision repair;
- persisted derived indexes, memory mapping, or V4.3 reopen acceleration;
- incremental backup, replication, remote live storage, multiple writers, or history
  merge;
- new matching, ranking, ordering, highlighting, pagination, or snapshot semantics;
- a separately published migration CLI or third Maven artifact; and
- paid cloud execution before the evidence phase explicitly authorizes it.

## Format policy

V4.2 recognizes two live formats:

```text
gse-durable (1,0)  published canonical format
gse-durable (1,1)  explicit evolution-profile format
```

`(1,0)` bytes and meaning remain immutable. V4.2 may open and continue writing an
existing `(1,0)` history only as `(1,0)`. The default durable configuration also
creates `(1,0)` so an application does not cross a rollback boundary merely by
upgrading its dependency.

Creating `(1,1)` requires an explicit format selection. Migrating `(1,0)` to `(1,1)`
requires a reviewed plan and a separate absent target. Published V4.1 must reject and
must never open `(1,1)` storage. Phase 2 established that its immutable parser may
classify exact extended `1.1` bytes as corrupt before reaching its higher-minor gate;
V4.2 owns the precise incompatible/profile classifications.

The `1.1` functional change is a canonical format-profile descriptor. Metadata owns
the complete descriptor; each authority-bearing checkpoint, manifest, and WAL header
binds its digest together with the existing history and sequence relationships. The
profile names the canonical-state, WAL, checkpoint, index-configuration, integrity,
and capability encodings used by that store. Unknown required capabilities fail
closed. V4.2 does not use the profile to persist derived indexes or admit unknown
members.

The exact `1.1` magic, field order, bounds, domain-separated digest, and member bytes
belong to Phase 2, after Phase 1 freezes an independent model and immutable fixtures.
Any later capability that changes bytes or the allowed member set requires another
explicit readable format and migration edge.

## Backup and restore continuity

V4.2 preserves `gse-backup (1,0)` byte meaning and content identity. A `(1,0)` live
store still produces a `(1,0)` three-member bundle and restore still produces a new
`(1,0)` history.

An explicitly selected `(1,1)` live store produces `gse-backup (1,1)`. The bundle
retains the same three-member inventory but uses a new exact
`gse-backup-content-v2` digest and `gse-backup-v2-<sha256>` identity so the published
V4.1 `v1` algorithm is never extended in place. Restoring a `(1,1)` bundle creates a
new `(1,1)` history. Restore never changes format; migration and restore remain
distinct operations.

Published V4.1 continues to read `(1,0)` bundles and fails closed on `(1,1)` bundles
as incompatible or corrupt according to how far its immutable `1.0` layout parser
advances. V4.2 verifies and restores both exact supported bundle minors.

## Migration model

The initial format edge is:

```text
closed canonical gse-durable (1,0) source at sequence S
    ↓ read-only typed plan and complete transform projection
reviewed plan bound to source, target, format, identities and transform
    ↓ explicit apply to unique sibling staging
independently verified gse-durable (1,1) target at sequence S
```

V4.2 also permits a `(1,1)` to `(1,1)` migration when at least one declared codec,
schema, storage, transform, or target-index identity changes. A same-format,
same-identity no-op copy is rejected as not required. No other edge is supported.

The source must be closed, exclusively lockable, structurally `VALID`, semantically
valid under the supplied source codec, and in canonical checkpoint form with an empty
post-checkpoint WAL. Planning never checkpoints, truncates, cleans, or otherwise
normalizes the source.

Every source key/document pair produces exactly one target key/document pair. Target
keys must be unique and must equal the business key extracted by the target schema.
The migration preserves source slot order, document count, logical sequence `S`, and
`nextDocId`. Target indexes are the exact definitions declared by the target builder
and are rebuilt from transformed canonical documents.

Apply creates a new non-zero target history distinct from the source. The next target
WAL sequence is `S + 1`; an exhausted source sequence is not migration eligible. The
source history, source authority digest, transform identity/version, plan digest, and
target history are returned as external migration provenance. They do not cause an
implicit rewrite of the source.

## Dry-run and apply model

Planning is synchronous, typed, offline, and read-only. It:

1. resolves and exclusively locks the exact source;
2. proves the target is absent and non-overlapping;
3. structurally and semantically verifies the source;
4. binds every authoritative source member by size and SHA-256;
5. allocates the target history used by that plan;
6. streams all records through the declared transform and target codec;
7. detects nulls, decode failures, key mismatches, collisions, limit violations, and
   transform exceptions;
8. computes the canonical target projection, document/index counts, `nextDocId`,
   sequence, expected authoritative bytes, and target content digest;
9. checks request bounds and currently observable filesystem capacity; and
10. returns a deterministic immutable plan without creating a target or staging
    directory.

Apply receives the exact request and plan, reacquires the source, and recomputes all
bindings. It refuses stale source bytes, a changed target boundary, a changed
configuration, a different transform descriptor, insufficient capacity, or a target
projection that differs from the dry run. Application transform code is invoked
serially and never concurrently. Non-determinism is a hard failure, not a warning.

## Publication and rollback model

Apply writes only to a unique sibling staging directory associated with an externally
locked operation marker. It forces each authoritative member, validates the complete
staged target independently, atomically renames staging to the absent final target,
forces the parent directory, reopens the final target through normal production code,
and completes only after structural and typed semantic verification.

Before final rename, the final target is absent. After final rename, the final target
is either independently valid or the operation fails with completion indeterminacy
that can be resolved by verification. A failed apply never modifies or deletes the
source. Recognizable staging and marker remnants are handled only by the published
V4.1 plan-bound cleanup rules extended for V4.2 migration operations.

The library does not perform cutover. Operators retain the source and its verified
pre-migration backup, verify the target, exercise continued mutation/checkpoint/close/
reopen, then change application routing externally. Rollback stops the target and
reopens the untouched `(1,0)` source with published `4.1.0`; writes accepted only by
the target after cutover are not automatically merged back.

## Public product surface

All production additions remain in the core artifact. The target
`SearchEngineBuilder<K,T>` owns typed target schema and startup indexes. Each operation
also receives a source builder, or a Phase 1-frozen immutable descriptor produced from
one, so source schema, ID extraction, and exact persisted logical indexes can be
validated. A migration request supplies the source path, source verification
configuration, explicit target storage configuration/format, versioned transform,
and resource bounds. The target builder provides one synchronous planning operation
and one synchronous apply operation.

Phase 1 freezes exact generic descriptors, record components, enum values, null and
equality behavior, Javadocs, and an independently compiled consumer before production
migration code exists. The contract requires immutable format, request, transform
descriptor, record, plan, result, stage, and failure values. It does not authorize a
general CLI, reflection-loaded transformer, service provider, or serialized executable
plan.

`DurableStorageOperations` also gains additive synchronous read-only store-format and
backup-format inspection families. Their immutable reports combine the existing
structural status/report with the declared live/backup format, bundle source format,
and optional `(1,1)` profile digest. Missing values remain explicit when a malformed
header cannot establish them; inspection never upgrades, repairs, or semantically
decodes storage.

Migration failures use a new stable `DurableMigrationException` family rather than
adding enum constants to the published V4.1 `DurableOperationException.Reason`. It
must distinguish invalid/in-use source, unsupported path, stale plan, transform
failure, non-deterministic projection, target collision/invalidity, capacity,
unsupported filesystem, I/O, and post-publication indeterminacy while retaining the
known source sequence and stage.

## Performance and capacity philosophy

V4.2 measures planning and apply separately:

- source verification, decode, and transform throughput;
- target encoding, force, and verification duration;
- plan-to-apply amplification caused by mandatory re-execution;
- target staging and final authoritative bytes;
- source, target, and temporary disk demand;
- heap and allocation bounds under streaming transformation;
- key-collision tracking cost;
- first open and continued mutation on `(1,1)`; and
- unchanged `(1,0)` open, mutation, checkpoint, backup, and restore behavior.

Planning and apply are bounded by maximum source members/bytes, encoded key/document
sizes, document count, target bytes, and transformation diagnostics. Capacity checks
use overflow-safe arithmetic and an explicit safety reserve. An observed usable-space
value is a preflight, not a guarantee; apply rechecks and treats ENOSPC as a target
failure without weakening source authority.

## Local crash and cloud evidence

Phase 1 establishes the evidence foundation before production `1.1` writing or
migration:

- an independent `1.0` to `1.1` migration oracle;
- immutable source/target and transform fixtures;
- a Python inspector that understands both supported formats without production
  parsers;
- separate-JVM plan/apply commands and stable authority barriers;
- checksummed evidence bundles and source-before/source-after byte identities;
- fake filesystem and deterministic transform faults;
- a no-GCP control plane with exact resource and cleanup assertions; and
- a calibrated quota-safe paid evidence plan.

Every later production authority transition adds its crash barrier and expected
independent classification in the same change.

The V4.2 cloud family is distinct:

- local artifact schema: `gse-v42-migration-evidence-v1`;
- cloud suite: `v4.2-storage-evolution-suite-v1`;
- cloud preset: `v4.2-storage-evolution-v1`;
- eventual append-only baseline: `v4.2.0-migration-cloud`.

Canonical execution uses serial independent members. Each member materializes a
published-4.1-compatible `(1,0)` source on one persistent disk, records a verified
backup and byte identity, migrates to `(1,1)` on a separate target disk, moves the
target to a replacement VM, verifies and continues it, then proves the untouched
source still opens with published `4.1.0`. The lane never runs source and target
writers concurrently and never treats GCS as live-store authority.

Phase 1 must freeze machine, disk, corpus, transforms, duration, maximum runtime,
retention, GCS prefix, budget, and serial resource ordering before any paid run.
Dry-run, fake-cloud, exact-source CI, OIDC restriction, explicit confirmation, and
complete cleanup remain mandatory.

## Phase order

| Phase | Scope | Exit boundary |
|---|---|---|
| 0 | freeze format/readability/migration/API/evidence contracts | documentation only; protected acceptance required |
| 1 | open `4.2.0-SNAPSHOT`; pin published 4.1; API fixtures, independent models, immutable bytes, crash/fake-cloud scaffolding and baseline | no production `1.1` writer or migration |
| 2 | format values, codec-free dual-minor structural inspection, exact bytes and independent parsers | no production open/write, target publication or migration apply |
| 3 | explicit `1.1` durable creation plus format-only `1.0` to `1.1` plan/apply | no codec/schema transform migration |
| 4 | versioned codec/schema/key transform and target-index rebuild | full typed migration matrix passes |
| 5 | lifecycle, interruption, cleanup, rollback and cross-version hardening | no unresolved source/target authority state |
| 6 | scale, performance, replacement-host, rollback, canonical cloud and registration | reviewed eligible evidence and immutable registration |
| 7 | final coordinates, consumers, compatibility, Javadocs, artifacts, reproducibility and release docs | exact-master release gates pass |
| 8 | signed publication and post-publication proof | Central, release, deployment, consumer and evidence identities close |

## Release gates

V4.2 requires:

- no regression in V4.0 durability, V4.1 operations, or V3.4 retrieval;
- byte-identical published `(1,0)` behavior and explicit-only `(1,1)` creation;
- fail-closed readable-format and migration-edge policy;
- immutable independently parsed `(1,1)` live and backup fixtures;
- complete dry-run/apply binding and source byte preservation;
- deterministic one-to-one typed transforms with collision refusal;
- verified new-history targets at the exact source sequence;
- crash-safe absent-target publication and plan-bound cleanup;
- published-4.1 source rollback after target migration and continued target operation;
- bounded large-corpus time, heap, disk, and amplification evidence;
- clean external consumer and source/binary compatibility evidence; and
- signed post-publication verification.

## North star

> GeneralSearchEngine V4.2 evolves durable state only through an explicit,
> source-preserving, independently verifiable migration whose target authority can be
> accepted or rejected without ambiguity.
