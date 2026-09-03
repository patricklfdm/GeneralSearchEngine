# GeneralSearchEngine V4.1 Phase 5 checklist

- **Status:** Accepted on protected `master`
- **Scope:** Offline plan-bound cleanup and operational integration

## Entry and boundary

- [x] Phase 4 merged through protected PR #97 as `47a4a3d`.
- [x] Exact-master CI run `33726843823` passed on that commit.
- [x] Active coordinates remain `4.1.0-SNAPSHOT`.
- [x] Live/backup formats and retrieval semantics remain unchanged.
- [x] Paid cloud work remains unauthorized.

## Public API and planning

- [x] Static descriptors, record components and scope order match the Phase 1 fixture.
- [x] Cleanup is synchronous, codec-free, offline and dry-run-first.
- [x] Requests name one exact live store, staging directory or marker.
- [x] Planning holds exclusive ownership and never mutates the named boundary.
- [x] Authority identity binds real path, parent, structural authority and inventory.
- [x] Every candidate binds exact path, reason, size and SHA-256 fingerprint.
- [x] Plan ordering and digest are deterministic; an empty plan is valid.

## Deletion authority and refusal

- [x] Only proven staging, obsolete checkpoint/WAL and bound operation remnants delete.
- [x] Incomplete WAL tails are reported but never truncated or deleted.
- [x] Lock, metadata, manifest, authoritative/pinned checkpoint and required WAL remain.
- [x] Complete backup and restored targets are never deleted.
- [x] Parent scans, globs, age/prefix inference and arbitrary invalid targets are absent.
- [x] Unknown, linked, malformed, mismatched, occupied or corrupt inputs fail closed.
- [x] Apply recomputes the full plan and stale input deletes nothing.
- [x] Successful apply forces the directory and reverifies surviving authority.

## Interruption and gates

- [x] Six production cleanup barriers span both scopes in 12 real abrupt-halt cases.
- [x] Independent pre-reopen inspection proves all authoritative hashes unchanged.
- [x] Every interrupted case safely replans, applies, mutates, checkpoints and reopens.
- [x] `scripts/verify-v41-phase5-cleanup.sh` passes locally.
- [x] Full reactor, published compatibility, consumers, release artifacts and
  reproducibility pass locally.
- [x] Phase 5 PR CI passes and merges through protected PR #98 as `5f1c750`.
- [x] Exact-master CI run `33730252965` passes on
  `5f1c750bd360716506a732e301ed52493650837e`.

Phase 5 is accepted. Paid durable-cloud calibration remains owned by Phase 6.
