# GeneralSearchEngine V4.1 Phase 5 plan-bound safe cleanup

## Scope

Phase 5 admits the final frozen V4.1 operational API: synchronous codec-free
`planCleanup` and `applyCleanup`. Cleanup is offline, explicit and dry-run-first. It
does not repair corrupt authority, truncate WAL, scan parents, expand prefixes or
globs, use age rules, or mutate complete backup/restored targets.

## Live-store authority

Planning acquires the ordinary `gse.lock`, invokes the independent locked structural
verifier, and accepts only `VALID` or `VALID_WITH_SAFE_REMNANTS`. The exact real path,
parent, structural result, complete member inventory, sizes and SHA-256 fingerprints
produce a deterministic authority identity. Only verifier-proven safe staging files,
obsolete checkpoints and fully obsolete WAL generations enter the ordered delete set.
An incomplete final WAL tail is never truncated or deleted.

Apply reacquires the same lock and recomputes the entire plan. Any authority,
inventory, byte, path, reason or digest difference is a stale-plan refusal before the
first deletion. Successful apply checks every member again, deletes exactly the
ordered set, forces the containing directory and reruns structural verification.
Empty plans are valid and idempotent.

## Operation remnants

The caller names one exact V4.1 backup/restore staging directory or its exact sibling
operation marker. Cleanup parses and checks the marker format, CRC, kind, non-zero
operation ID, UUID-derived staging name and simple final-target name while holding the
marker lock. No parent discovery is performed.

An abandoned staging directory is eligible only when the bound final target is
absent, every child is a non-symbolic, non-aliased regular member admitted by that
operation kind, and the marker binding is exact. Children are removed first, then the
empty staging directory and marker. An orphan marker is removable by explicit marker
request only after a present final target independently verifies as complete and
valid. A marker left after an interrupted cleanup may also be removed when both bound
paths are absent; this is required for idempotent crash recovery and grants no other
deletion authority.

## Failure and crash safety

Storage/marker ownership remains held from plan recomputation through deletion and
post-verification. Unknown members, links, malformed or mismatched markers, live
writers, in-progress operations, invalid authority and stale plans fail closed.
Deletion is one exact member at a time; interruption can only reduce the already
proven-safe remnant set.

Six stable production barriers cover before/after member deletion, before/after
directory force and before/after post-verification. Both cleanup scopes traverse all
six barriers, for 12 real `Runtime.halt(86)` cases. Before replacement-JVM reopen, an
independent Python inspector requires every authoritative live-store member to retain
its pre-cleanup SHA-256 and allows only the exact scope-specific remnants. The
replacement process replans and applies when remnants remain, then opens the protected
store, mutates, checkpoints and reopens again.

## Boundary

Live and backup formats remain `gse-durable (1,0)` and `gse-backup (1,0)`. No user
codec is loaded by cleanup. No paid cloud work, migration, incremental backup, online
cleanup, heuristic repair, or new retrieval semantics are introduced.
