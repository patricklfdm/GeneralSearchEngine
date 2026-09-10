# GeneralSearchEngine V4.3 Phase 3 structured images and migration

- **Phase:** 3 — Structured image-assisted reopen and direct migration
- **Status:** Candidate for protected acceptance
- **Entry:** Phase 2 protected-master commit `e7d8be3580a8e007a1afcef099dcf2b7e61fdbba`
- **Scope:** Equality, range and prefix images for explicit `(1,2)` stores

## Delivered boundary

Phase 3 activates the first production consumers and producers of the exact bytes
frozen in Phase 2. Explicit `(1,2)` stores can publish and reopen equality, range and
prefix snapshots. Canonical checkpoint documents and descriptors remain mandatory;
the image is never recovery authority. Exact `(1,0)` and `(1,1)` behavior and the
default `(1,0)` selection are unchanged.

SimpleAnalyzer text image materialization and normal production publication remain
Phase 4 work. A structurally valid mixed physical fixture may load its three
structured components and rebuild its text component, but Phase 3 does not claim a
complete text warm path or publish a mixed generation.

## Reopen pipeline

An exact `(1,2)` open now performs these ordered operations:

1. validate format/profile, metadata, manifest, checkpoint and WAL authority;
2. decode the canonical checkpoint documents, IDs and descriptors;
3. independently parse the optional catalog and component bindings;
4. materialize every admitted equality, range and prefix snapshot;
5. rebuild only absent or rejected checkpoint snapshots;
6. make one synchronous bounded best-effort refresh when fallback occurred;
7. replay every post-checkpoint WAL unit over that complete checkpoint snapshot,
   including dynamic index create/drop; and
8. publish one immutable ready snapshot and one immutable reopen report.

The checkpoint image never skips WAL. Dynamic index creation after checkpoint is
replayed from the recovered document state; dynamic drop removes the corresponding
snapshot. The externally visible version remains zero after reopen, preserving the
published recovery contract.

Catalog failure selects full fallback. An independently corrupt component selects
component-local fallback while valid siblings remain admitted. Rebuild failure keeps
the inherited `INDEX_REBUILD_FAILURE` primary. Derived rejection is bounded secondary
diagnostic context.

## Structured logical materialization

Equality and range images retain representative live document IDs plus canonical
bitmaps. Load recovers each Java key only through the already-decoded representative
document and the configured field extractor; arbitrary Java key serialization is not
introduced. Range keys additionally rebuild the published compare-to ordering.

Prefix images decode strict canonical UTF-8 keys and canonical bitmaps. Every loaded
document ID must be live and within the checkpoint slot bound. Ordering, uniqueness,
statistics, descriptor identity, component length, CRC32C, SHA-256, format profile,
history, checkpoint and codec/schema/storage bindings are verified before admission.

The production codec is deliberately separate from
`DurableDerivedStateInspector` and the independent Python Phase 2 parser. Tests use
those independent readers to validate production output.

## Publication and Future semantics

After an explicit or automatic canonical checkpoint is fully published, an exact
`(1,2)` checkpoint performs one bounded best-effort structured refresh before its
Future completes. The refresh writes and forces unique component staging files,
atomically renames and parent-forces each component, validates them, then writes,
forces and atomically replaces the catalog and parent-forces the directory. It
reopens the published generation before reporting success.

Capacity, serialization, write, force, rename or validation failure makes refresh
unsuccessful but cannot fail an already successful canonical checkpoint or a
successful fallback open. Backup-triggered checkpoint cuts do not wait on image
generation, so derived work cannot delay or fail backup after the canonical cut.

Phase 5 owns exhaustive temporary-amplification, stale-generation cleanup, fault,
capacity and concurrency hardening. Phase 3 retains any unreferenced recognized
member as non-authoritative state for later inspection/cleanup.

## Direct migration edges

The existing source-preserving offline framework now supports direct:

```text
(1,0) -> (1,2)
(1,1) -> (1,2)
(1,2) -> (1,2)  when another identity/transform change is meaningful
```

The target metadata, checkpoint, WAL and manifest use the requested exact target
profile. The source remains byte-for-byte unchanged. Recognized source `(1,2)`
derived members do not participate in canonical migration identity or target output.
The target is independently opened with derived assistance disabled during apply, so
successful migration publishes a cold target. Its first ordinary open rebuilds from
canonical authority and then attempts refresh. A no-op `(1,2)` request remains
`MIGRATION_NOT_REQUIRED`; downgrade is rejected.

## Crash evidence

`scripts/v43/structured_image_harness.py` drives real production `(1,2)` bytes in a
child JVM. Internal halt and external kill cover component rename, component parent
force, pre-catalog publication and post-catalog parent force. Before production
reopen, a separate read-only inspector JVM verifies canonical authority and records
the interrupted derived classification, while the parent records canonical member
digests. A replacement JVM validates the complete equality/range/prefix oracle,
performs the contracted warm or fallback path, and leaves a valid independently
inspectable generation without changing canonical bytes.

The checksummed artifact continues to use
`gse-v43-fast-reopen-evidence-v1`; this is local evidence and does not authorize a
paid cloud run.

## Deferred work

Phase 4 owns production text image encoding/materialization, mixed structured/text
publication and the complete four-index selective matrix. Phase 5 owns the exhaustive
crash/fault/capacity/concurrency, backup/restore/migration/cleanup and cross-version
hardening matrix. Phase 6 alone may run paid evidence or mutate the append-only cloud
registry.
