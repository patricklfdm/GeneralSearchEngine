# GeneralSearchEngine V4.3 development charter

- **Status:** Proposed governing charter for protected Phase 0 acceptance
- **Predecessor:** Published GeneralSearchEngine `4.2.0`
- **Theme:** Fast Reopen through reconstructible persisted derived state

## Purpose

V4.0 established correct single-node durability, V4.1 added operational safety, and
V4.2 added explicit storage evolution. V4.3 addresses the next measured boundary:

> How can a large durable store reopen without rebuilding every built-in index from
> every canonical document, while keeping documents and logical index configuration
> as the only recovery authority?

V4.3 is an opt-in recovery-acceleration release. It is not a new retrieval engine,
an authoritative index store, memory-mapped search, or a relaxation of fail-closed
canonical recovery.

## Governing principles

1. Published V4.0 durability, V4.1 operational safety, V4.2 storage evolution, and
   V3.4 retrieval semantics remain frozen.
2. Canonical documents, history, sequence, checkpoint authority, WAL and logical
   index descriptors remain sufficient to rebuild the complete search snapshot.
3. A persisted derived image is disposable acceleration. Its absence, staleness,
   incompatibility, interrupted publication, or integrity failure never makes valid
   canonical authority corrupt.
4. A derived image is used only after exact history, checkpoint, schema, codec,
   format-profile, index-descriptor, generator-version, size and digest binding.
5. Selective acceptance is component based: one rejected component rebuilds only its
   index when the catalog and remaining components are independently valid.
6. V4.3 never serializes arbitrary Java objects, lambdas, comparators, class names,
   object identity, hash-table order, or implementation-private object graphs.
7. Exact format `(1,2)` is explicit. The default stays `(1,0)`, and opening `(1,0)`
   or `(1,1)` never creates V4.3 files or rewrites an older store.
8. Backup, restore, and migration preserve canonical authority. Derived images are
   omitted from backup and may be regenerated only from a verified restored or
   migrated target.
9. Retained bytes, temporary amplification, decode work, image-load work, fallback
   work, and total open latency remain bounded and separately visible.
10. Independent byte models, local separate-process crashes, fake cloud, cold/warm
    replacement-host evidence, cleanup, and cost limits are first-class architecture
    from Phase 1 onward.

## Scope

V4.3 adds:

- exact live format `gse-durable (1,2)` and matching canonical-only backup format
  `gse-backup (1,2)`;
- an explicit `(1,2)` profile capability for reconstructible derived-index images;
- a non-authoritative derived catalog and independently checksummed per-index image
  components bound to one authoritative checkpoint;
- stable logical image encodings for the four durable built-in index kinds:
  equality, range, prefix, and SimpleAnalyzer text;
- component-level validation, selective load, deterministic fallback rebuild, and
  post-rebuild refresh;
- codec-free offline derived-state inspection distinct from canonical structural
  verification;
- immutable reopen diagnostics without changing the published `DurabilityMetrics`
  constructor or components;
- direct reviewed migration edges from `(1,0)` and `(1,1)` to `(1,2)`, plus meaningful
  `(1,2)` to `(1,2)` migrations under the V4.2 source-preserving model;
- exact backup/restore continuity for canonical `(1,2)` state without transporting
  cache authority;
- bounded cleanup of proven derived remnants without granting permission to remove
  canonical members; and
- local and cloud evidence comparing forced cold rebuild, valid warm load, partial
  fallback, full fallback, checkpoint-plus-WAL reopen, and replacement-host reopen.

## Explicit exclusions

- making any derived file, catalog, index image, posting list, bitmap, or statistic
  authoritative for document recovery;
- Java native serialization, Kryo-style opaque graphs, reflection-based field-value
  persistence, executable-code hashes, or user object serialization;
- persistence of arbitrary custom `IndexDefinition` implementations or application
  callbacks;
- accepting an image solely because its filename or CRC is valid;
- skipping canonical metadata/checkpoint/WAL validation or document decoding;
- silently creating `(1,2)`, upgrading `(1,0)`/`(1,1)`, or migrating during open;
- including derived images in full backups or using them as restore authority;
- online migration, reverse migration, in-place cutover, source deletion, history
  merge, repair, or salvage;
- memory mapping, off-heap query execution, lazy-ready engines, background visibility
  of partially reconstructed snapshots, or serving before recovery completes;
- persisted cursors, query/result caches, prepared-query caches, facets, vectors,
  changed scoring, matching, ordering, pagination, highlighting, or Explain behavior;
- replication, multiple writers, remote live storage, distributed recovery, or a
  third Maven artifact; and
- paid cloud execution before the evidence phase explicitly authorizes it.

## Format and authority boundary

V4.3 recognizes three exact live minors:

```text
gse-durable (1,0)  published default canonical format
gse-durable (1,1)  published explicit evolution-profile format
gse-durable (1,2)  explicit reconstructible-derived-state format
```

The `(1,2)` profile changes the permitted member set and binds the derived-state
capability, so it requires a new minor rather than extending `(1,1)` in place. Existing
and default construction remains `(1,0)`. Configuration is always an exact expected
format, never an upgrade request.

For `(1,2)`, metadata, the authoritative checkpoint manifest and checkpoint, and the
active WAL generation retain their V4 roles. A separate derived catalog points to
zero or more component images. Neither the catalog nor any component participates in
the committed sequence, checkpoint authority, WAL continuity, backup content identity,
or the proof that a mutation Future completed durably.

Canonical structural failure retains the inherited fail-closed result. Derived-state
failure is reported through a separate bounded classification and selects rebuild.
The two channels must not be collapsed.

## Stable logical images

Durable mode already limits persisted index descriptors to the four built-in kinds
and SimpleAnalyzer text. V4.3 may persist their logical immutable state without
persisting arbitrary Java values:

- equality and range images identify each value group by a representative live
  document slot plus its canonical sorted document-ID bitmap;
- prefix images use strict UTF-8 string keys and canonical sorted bitmaps;
- text images use strict UTF-8 terms, document frequencies, canonical postings,
  positions, field-length data, and the exact SimpleAnalyzer identity; and
- every component binds its durable index descriptor and ordinal from the canonical
  checkpoint configuration.

On load, equality/range representative values are re-extracted from already decoded
canonical documents. No general field-value codec is introduced. A representative
must belong to its bitmap and every structural relation must pass before the component
is admitted. Content-integrity and identity binding protect persisted bytes; complete
warm-versus-rebuild differential tests protect semantic equivalence.

The exact magic, framing, limits, canonical order, checksum, SHA-256 domains and
immutable bytes belong to Phase 2 after Phase 1 creates independent models. Production
image writing/loading remains prohibited until its owning implementation phases.

## Publication and fallback

Derived publication is always downstream of a fully durable authoritative checkpoint.
Components are written to unique sibling staging files, forced, renamed, and parent-
forced before a staged catalog atomically replaces the fixed catalog and is parent-
forced. Replacing a catalog never changes canonical authority. Components no longer
named by the new catalog become proven non-authoritative only after the new catalog is
durable.

The inherited `checkpoint()` Future continues to mean canonical checkpoint success.
For `(1,2)`, it waits for one bounded best-effort refresh attempt after canonical
publication, so a caller that checkpoints and closes has a deterministic warm-state
boundary. An image-generation or cleanup failure is reported separately but cannot
turn an already published canonical checkpoint into a failed or indeterminate one.

Reopen validates and decodes canonical state first. It then validates the optional
catalog and each component, loads admissible built-in components, rebuilds every
missing or rejected index deterministically from canonical documents, replays later
WAL units in sequence, and publishes exactly one fully reconstructed immutable search
snapshot. No partial snapshot is visible.

A catalog-level identity or integrity failure rejects the complete generation. A
component-level failure rejects only that component if catalog integrity and all other
bindings remain trustworthy. If any image-assisted result cannot be materialized,
normal fallback rebuild is attempted. Before a cold or fallback open returns, it makes
one synchronous bounded best-effort refresh attempt for the checkpoint snapshot; only
failure of canonical recovery or fallback rebuild may fail open under inherited
reasons.

## Backup, restore, and migration

An exact `(1,2)` store creates `gse-backup (1,2)` with the same canonical three-member
shape used by V4.1/V4.2: backup metadata, checkpoint payload, and completion manifest.
No derived catalog or component is included. A new domain-separated backup-content
identity prevents extension of published V4.2 algorithms in place.

Restore produces canonical `(1,2)` state with no derived image. Its first open uses
the required rebuild path and makes the contracted refresh attempt only after complete
canonical verification. The same cold-first rule applies to a newly migrated `(1,2)`
target.

V4.3 retains every V4.2 migration edge and adds explicit direct `(1,0)` to `(1,2)` and
`(1,1)` to `(1,2)` edges. These are separately registered one-step edges, not hidden
multi-hop conversion. A `(1,2)` to `(1,2)` migration still requires a meaningful
declared identity/schema/codec/transform/index change. Downgrade remains unsupported.
Source bytes and any source-derived cache remain untouched and are excluded from target
authority identity.

## Retention and cleanup

All engine-owned derived and staging bytes count toward the existing retained-byte
hard bound. V4.3 adds a separately bounded derived-state allowance; it cannot reserve
space needed for canonical checkpoint/WAL publication. Overflow, insufficient space,
ENOSPC, or an image larger than its limit causes omission/fallback and a diagnostic,
not canonical mutation failure.

Cleanup recognizes only exact `(1,2)` catalog/component/staging families. It may
delete an unreferenced component or interrupted staging file only after proving it is
non-authoritative and not named by the current valid catalog. Unknown members,
canonical members, the fixed current catalog, referenced components, ambiguous hard
links, and changed inventories remain protected by V4.1 plan-bound rules.

## Public surface

All additions remain in `general-search-engine` and are additive:

- `DurableStorageFormat` and `DurableBackupFormat` gain exact `(1,2)` constants;
- `DurableStorageConfig.Builder` gains bounded derived-state configuration that is
  meaningful only for exact `(1,2)`; explicitly configuring it for an older format
  is rejected rather than ignored;
- `DurableStorageOperations` gains codec-free offline inspection of derived-state
  presence, binding, per-component status, byte counts and findings; and
- `DurableSearchEngine` gains a default diagnostic capability returning an optional
  immutable last-reopen report. Independent implementations remain source and binary
  compatible and may return absence.

Published constructors, records, enum constant order, `DurabilityMetrics`, existing
verification reports and exception reasons are not extended incompatibly. Phase 1
freezes exact names, components, null/equality behavior, enum order and Javadocs in an
independently compiled consumer before production behavior exists.

## Evidence from Phase 1

Phase 1 must establish, before production image code:

- `4.3.0-SNAPSHOT` and exact published-4.2 artifact/fixture compatibility;
- a declaration-only public API fixture and independent consumer;
- an independent logical oracle for all four built-in image kinds;
- immutable handcrafted valid, absent, stale, partial, corrupt, incompatible, and
  interrupted-publication `(1,2)` fixtures;
- a separate-JVM crash harness with stable barrier commands and pre-open inspection;
- a no-GCP fake control plane modeling fresh disks, replacement hosts, serial members,
  retention, failure and cleanup;
- a workload that records forced cold, warm, partial/full fallback, checkpoint-plus-
  WAL, restored-target and migrated-target reopen separately; and
- a calibrated quota-safe cost/resource envelope before any paid run.

The evidence identities are distinct:

```text
artifact schema: gse-v43-fast-reopen-evidence-v1
cloud suite:     v4.3-fast-reopen-suite-v1
cloud preset:    v4.3-fast-reopen-v1
baseline:        v4.3.0-fast-reopen-cloud
```

Experiment is one member and canonical is three independent serial members. The user
initiates paid work only in Phase 6 after exact-source CI, local/fake/dry-run gates,
budget validation and explicit confirmation.

## Phase ownership

| Phase | Authorized work | Exit evidence |
|---|---|---|
| 0 | Documentation-only contract and checklist | protected acceptance of exact scope |
| 1 | `4.3.0-SNAPSHOT`, published-4.2 gates, API fixtures, independent models/bytes, crash/fake-cloud scaffolding, pre-change baseline | no production `(1,2)` or image behavior |
| 2 | exact `(1,2)`/backup bytes, derived catalog/component codecs, codec-free inspection and independent parsers | production open still rebuild-only |
| 3 | explicit `(1,2)` operation, structured equality/range/prefix image publication/load/fallback and direct migration edges | text image remains rebuild-only |
| 4 | SimpleAnalyzer text images, component-selective fallback and refresh | complete four-kind differential matrix |
| 5 | checkpoint/WAL/backup/restore/migration/cleanup, crash, fault, capacity, concurrency and cross-version hardening | no paid evidence |
| 6 | scale profiling, replacement-host experiment/canonical evidence, review and append-only registration | no unmeasured optimization |
| 7 | final coordinates, consumers, compatibility, Javadocs, artifacts, reproducibility and release docs | no publication |
| 8 | signed tag, Central, deployment, GitHub Release and post-publication proof | V4.3 closed |

## Release decision

V4.3 is accepted only if image-assisted and forced-rebuild results are bit-for-bit or
semantically identical across the complete retrieval and mutation matrix, every cache
failure safely rebuilds, retained space remains bounded, and canonical cloud evidence
shows a material repeatable warm-reopen improvement without hiding cold or fallback
cost. If the evidence does not justify persisted images, V4.3 must not ship speculative
production acceleration merely because it appears on the roadmap.
