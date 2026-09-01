# V4.0 Phase 0 checklist

**Status:** contract content complete; protected-merge acceptance pending

**Production implementation:** not authorized

**Reference:** published GeneralSearchEngine `3.4.0`

## Scope and architecture

- [x] V4.0 is opt-in durable single-node storage, not a retrieval-feature release.
- [x] In-memory `build()` remains storage-free and preserves V3.4.
- [x] Immutable snapshots, lock-free readers, and one authoritative writer remain.
- [x] Durable truth includes canonical slot/internal-ID order and `nextDocId`.
- [x] Derived indexes are rebuilt; persisted production indexes are deferred.
- [x] Linux/Java 21/local-filesystem/device assumptions and physical-disk-loss exclusion
  are explicit.

## Completion and ordering

- [x] Successful Future order is private candidate prepare/apply/validate, sequence,
  append, force, publish, complete.
- [x] Committed sequences start at one and are contiguous with no gaps/duplicates.
- [x] Bulk is one sequence and one all-or-nothing recovery unit.
- [x] Empty bulk consumes no sequence; other successful no-ops do.
- [x] Group commit preserves per-unit sequence, atomicity, and Future results.
- [x] A crash-time incomplete Future is documented as indeterminate.
- [x] Runtime ambiguous WAL I/O makes that engine instance terminal for mutations.

## WAL, recovery, and checkpoint

- [x] Bounded framing, format, history, operation, payload, sequence, and checksum
  validation are frozen.
- [x] Only a physically incomplete newest terminal frame may be discarded.
- [x] A complete checksum-invalid terminal frame and committed-region corruption fail
  closed.
- [x] Startup publishes no partially recovered engine.
- [x] Recovery equivalence covers canonical state and all applicable V3.4 results.
- [x] Checkpoint staging, force, validation, manifest rename, directory force, and
  cleanup order are frozen.
- [x] Authoritative checkpoint corruption has no silent older fallback.
- [x] Explicit/automatic checkpoint, WAL generation cleanup, and hard disk bound are
  part of V4.0.

## Codec, indexes, storage, and API

- [x] One deterministic codec covers both business key and document.
- [x] Codec ID/version, schema/storage identity, key/document equality, and size bounds
  are frozen.
- [x] Durable mode supports only built-in equality/range/prefix/text definitions and
  built-in analyzers with stable IDs.
- [x] Dynamic create becomes durable on successful install; drop is sequenced.
- [x] Format family `gse-durable` `(1,0)`, history identity, directory authority, and
  compatibility policy are frozen.
- [x] The additive durable API family is frozen without modifying `SearchEngineMetrics`.
- [x] Snapshot version and existing metrics remain process-local; durable sequence is
  cross-restart identity.

## Evidence and phase boundary

- [x] Independent history, V3.4 semantic, and byte-inspector oracles are required.
- [x] The local crash harness is Phase 0 architecture with a parent/child protocol,
  stable barrier IDs, independent recovery JVM, and checksummed artifact schema.
- [x] Phase 1 must implement the executable harness scaffold and fake cloud lane before
  production WAL begins.
- [x] Process-crash, corruption, concurrency, lifecycle, capacity, and injected-I/O
  matrices are accepted.
- [x] Preserved-device VM failure evidence is required; graceful close alone is not.
- [x] V4 uses independent `v4.0-durable-single-node-v1` evidence identities and
  separates experiment, canonical, and failure-drill profiles.
- [x] Paid cloud runs are manual and require fake/dry-run, budget, retention, checksum,
  persistent-disk lifecycle, and cleanup gates.
- [x] Published `3.4.0` remains the immediate API/consumer/performance baseline.
- [x] Phase 0 changes documentation only; version bump and harnesses begin in Phase 1,
  production WAL begins in Phase 2.
- [ ] This contract set is merged through protected review and exact-master CI passes.

## Exit gate

Phase 0 exits only after the final unchecked item passes. Until then, the documents
are implementation-ready proposals but do not authorize code. After acceptance,
Phase 1 may establish `4.0.0-SNAPSHOT`, compatibility fixtures, crash/corruption
harnesses, independent oracles, and pre-change evidence.
