# GeneralSearchEngine V4.3 Phase 5 lifecycle hardening

- **Status:** Local acceptance complete; protected acceptance pending
- **Scope:** lifecycle, cleanup, backup/restore, crash, capacity, concurrency and
  published-4.2 hardening
- **Paid execution:** prohibited

## Closed lifecycle boundary

Phase 5 completes the local correctness boundary for exact `gse-durable (1,2)`.
Canonical metadata, checkpoint and WAL authority remain unchanged. Derived catalogs
and per-index components remain disposable and are never required to recover a valid
store.

Repeated mutation/checkpoint/reopen cycles publish a new four-component generation.
The replacement catalog is the only derived authority; prior final components become
eligible for an explicit offline cleanup plan only after the current catalog has
passed its complete canonical binding parser.

## Plan-bound derived cleanup

The existing public V4.1 dry-run/apply API is extended without a signature change.
For exact `(1,2)` live stores, planning holds the store lock and binds:

- the canonical verification report and complete live-store inventory;
- every member's real normalized path, size and SHA-256;
- the current valid derived catalog content identity, when one exists; and
- the sorted complete delete set and reason for every candidate.

Only `gse-derived-manifest.staging`, recognized component staging files and recognized
final component files omitted by the current valid catalog may be selected. A missing,
stale, incompatible, incomplete or corrupt catalog grants no authority to delete a
final component. Current catalog and referenced components, canonical members,
unknown members, symbolic links, hard-link aliases and changed inventory fail closed.

Apply reacquires the lock, recomputes the exact plan before deletion, verifies each
candidate immediately before deletion, forces the parent directory and revalidates
canonical authority. The stable cleanup barriers are:

- `v43-derived-before-superseded-cleanup-v1`;
- `v43-derived-during-superseded-cleanup-v1`; and
- `v43-derived-after-superseded-cleanup-v1`.

Replacement-process recovery replans from the observed post-crash inventory. It may
finish remaining proven deletions, then proves a complete warm reopen, query equality,
continued mutation, checkpoint and second warm reopen.

## Backup, restore and migration

Exact `(1,2)` backups remain canonical-only: no derived catalog or component is
transported. Phase 5 corrected typed semantic verification and restore so their
bounded temporary decode configuration carries the persisted
`maxDerivedStateBytes`. A restored `(1,2)` target is therefore accepted cold, performs
full deterministic rebuild/refresh on first open, and is complete-warm on the second
open. No restore operation treats optional images as backup authority.

The Phase 3 direct migration rules remain unchanged: source derived members are
read-only and target publication is cold-first. Phase 5 gates retain the complete
Phase 2–4 format, migration, fallback and crash matrices.

## Capacity, concurrency and compatibility

Focused lifecycle tests cover repeated concurrent mutation bursts and checkpoints,
complete four-kind warm reopen, stale-plan rejection, alias rejection, corrupt-catalog
conservatism, canonical-only backup/restore and post-restore continuation. Existing
Phase 2–4 tests retain truncation, corruption, stale/swapped binding, component-local
fallback, ENOSPC isolation, WAL replay and publication crash coverage. V4.1 cleanup
and V4.2 migration gates remain inherited by the acceptance matrix.

Default `(1,0)`, explicit `(1,1)`, published `4.2.0` and public API shape do not
change. Phase 5 adds no workflow dispatch, IAM mutation, VM, disk, GCS object or
baseline registration.

## Executable gate

```bash
scripts/verify-v43-phase5-lifecycle.sh
```

The gate runs focused Phase 2–5 Java tests, the independent Python format suite,
three abrupt cleanup boundaries using both internal halt and external kill, evidence
validation, replacement-JVM continuation and the inherited complete Phase 4 gate.
CI invokes it after the full reactor with `--skip-build`.

Phase 6 alone owns scale profiling, paid experiment/canonical cloud execution,
evidence review and append-only baseline registration.
