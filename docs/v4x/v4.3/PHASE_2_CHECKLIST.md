# GeneralSearchEngine V4.3 Phase 2 checklist

- **Status:** Candidate for protected acceptance
- **Scope:** Exact `(1,2)` bytes and codec-free derived inspection

## Entry

- [x] Phase 1 merged through protected PR #120 as `148d253`.
- [ ] Exact Phase 1 protected-master CI run is recorded.
- [x] Work is isolated on `feat/v4.3-phase2-derived-format`.

## Public and canonical format

- [x] Public `V1_2`, configuration allowance, report and diagnostic declarations
  match the Phase 1 fixture.
- [x] Default remains exact `(1,0)` and older format bytes remain unchanged.
- [x] Explicit `(1,2)` create/open/checkpoint/WAL is profile-bound.
- [x] Metadata persists the separately bounded derived allowance.
- [x] Unknown higher minor remains fail-closed and prior tests now use minor `3`.
- [x] Production open remains rebuild-only and `lastReopenReport()` remains empty.

## Derived physical format

- [x] Exact catalog/component magic, byte order, fields and SHA/CRC domains are frozen.
- [x] Exact capability order and profile digest are frozen.
- [x] UUID generation-token rendering and filename placement are frozen.
- [x] Catalog binds canonical checkpoint, profile, identities and descriptor order.
- [x] Components repeat authority/descriptor binding and use kind-specific encodings.
- [x] Equality/range representative/bitmap, prefix UTF-8 and text posting/position
  invariants are independently bounded.
- [x] Catalog/component/count/string/diagnostic/total-byte bounds fail closed.
- [x] Immutable exact physical fixture hashes and identities are checked in-repo.

## Inspection and authority separation

- [x] Inspection is synchronous, codec-free, lock-exclusive and byte-preserving.
- [x] Older, absent, valid, partial, stale, incompatible, incomplete and corrupt
  paths remain distinct.
- [x] Missing or corrupt one component preserves admission of other components.
- [x] Staging and unreferenced bytes are reported separately.
- [x] Derived aliases and allowance overflow fail derived inspection without changing
  canonical validity.
- [x] Recognized derived corruption cannot mask or alter canonical authority.
- [x] Production reopen ignores even valid fixture images in Phase 2.

## Backup and compatibility

- [x] Backup `(1,2)` is exactly three canonical members.
- [x] `gse-backup-content-v3\0` and `gse-backup-v3-` are frozen.
- [x] Restore produces a valid cold `(1,2)` target without derived members.
- [x] Published checksum-pinned `4.2.0` rejects exact live/backup `(1,2)` bytes
  fail-closed in an isolated child JVM.
- [x] Independent Python and production Java parsers accept the same immutable bytes.

## Local acceptance

- [x] Focused Phase 2 Java gate passes.
- [x] Independent Python encoder/parser and tamper matrix pass.
- [x] Full core test suite passes with no failures or errors.
- [x] Package compilation and whitespace checks pass.
- [x] Full reactor, artifact compatibility, all consumers, release artifacts,
  reproducibility and JMH smoke are recorded before commit.
- [x] CI contains both reactor and no-GCP Phase 2 gates.
- [x] No paid cloud/IAM/registry action was performed.

## Protected acceptance

- [ ] Phase 2 pull request passes required checks.
- [ ] Phase 2 merges to protected `master`; exact commit is recorded.
- [ ] Exact protected-master CI passes before Phase 3.

Phase 3 alone owns structured equality/range/prefix image publication/load/fallback
and direct migration edges. Text images and complete selective behavior remain Phase 4.
