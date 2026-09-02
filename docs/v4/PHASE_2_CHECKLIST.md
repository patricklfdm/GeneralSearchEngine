# V4.0 Phase 2 checklist

**Status:** accepted on protected master

## Entry and API

- [x] Phase 1 protected-master commit is
  `8758106d30223cc1ad6c2faf66a2f0d1131d507c`.
- [x] Exact Phase 1 master CI run `33578036261` passed.
- [x] The additive durable codec/config/engine/failure/metrics family matches Phase 0.
- [x] Existing `build()` remains storage-free; only `buildDurable()` touches disk.
- [x] Phase 3 recovery and Phase 4 checkpoint execution remain absent.

## Storage and format

- [x] Absolute normalized real directory and lifetime exclusive lock are enforced.
- [x] Symlink/unsupported filesystem, non-empty target, second owner, and initialized
  Phase 2 reopen fail closed with stable reasons.
- [x] Metadata is checksummed, forced, atomically renamed, and directory-forced.
- [x] Random history identity is shared by metadata and forced generation-1 header.
- [x] Exact metadata, generation, frame, payload and CRC32C bytes are documented.
- [x] All configured and hard decode/allocation/frame limits are persisted and bounded.
- [x] Independent Java and Python inspectors do not invoke production recovery.

## Commit semantics

- [x] Codec canonical round trip and decoded document/key identity precede sequence.
- [x] Accepted sequences start at 1 and remain contiguous across single, grouped, bulk,
  no-op and built-in index units.
- [x] Non-empty bulk has one sequence/frame/Future and empty bulk consumes none.
- [x] Grouped singles retain independent frames/sequences and share one force/publication.
- [x] Force precedes immutable publication, published sequence and Future completion.
- [x] Capacity rejection consumes no sequence and can return to OPEN after a smaller
  successful unit.
- [x] Append/force ambiguity moves the durable writer to terminal FAILED without
  publishing the candidate.
- [x] Built-in dynamic index install/drop is sequenced; custom behavior is rejected.

## Crash and evidence

- [x] All ten Phase 2 production WAL barrier IDs are reached by a separate JVM.
- [x] Partial fixed-header, payload and trailer cases classify as incomplete newest tail.
- [x] Complete-before-force, after-force, before/after publication and before-Future
  cases expose one structurally valid inspected unit.
- [x] Internal `Runtime.halt` covers every barrier and external kill covers after-force.
- [x] Shutdown hooks do not run and successful evidence records the independent prefix.
- [x] Evidence says recovery is deferred rather than treating successful inspection as
  Phase 3 replay evidence.
- [x] CI runs the bounded production WAL matrix and no-GCP byte-inspector tests.

## Acceptance

- [x] Focused API/config/engine/WAL tests pass locally.
- [x] Python complete-frame/incomplete-tail/corruption tests pass locally.
- [x] The full local process-crash matrix passes.
- [x] Full reactor passes (401 core and 5 processor tests, zero failures).
- [x] Published 1.0.0 through 3.4.0 compatibility and all three independent consumers
  pass; the obsolete V3.4 zero-addition rule is removed while binary/source
  incompatibility checks remain mandatory.
- [x] Strict Javadocs, six release JARs and two-build byte reproducibility pass.
- [x] Required PR #79 passed and merged at protected-master commit
  `7056a5ad00d1f38757f984c51ad21d83ee922443`.
- [x] Exact-master Phase 2 CI run `33583721019` completed successfully.

Phase 3 reuses these exact bytes, inspectors and crash artifacts without changing the
writer format or reopening the accepted Phase 2 storage boundary.
