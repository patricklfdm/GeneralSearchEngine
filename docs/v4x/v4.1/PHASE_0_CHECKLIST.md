# GeneralSearchEngine V4.1 Phase 0 checklist

- **Status:** Contract complete; protected acceptance pending
- **Scope:** Documentation-only operational-safety freeze
- **Authoritative contract:** [PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md)

Checked items mean the candidate contract contains an explicit decision. They do not
record protected-master acceptance until the final acceptance section is completed.

## Scope and inheritance

- [x] V4.1 operational-safety scope and exclusions are explicit.
- [x] V4.0 durability, storage, retrieval, and in-memory inheritance is enumerated.
- [x] Live format `gse-durable (1,0)` remains unchanged.
- [x] Replication, migration, persisted indexes, salvage, and new retrieval semantics
  remain outside V4.1.
- [x] Phase 0 is documentation-only.

## Public surface

- [x] Running-engine backup is a typed asynchronous default Java capability, preserving
  independently implemented interface compatibility.
- [x] Store/backup structural verification and cleanup are codec-free core APIs.
- [x] Semantic verification and restore are typed builder-owned APIs.
- [x] Structural validity is not semantic validity.
- [x] Operational failures use a separate stable exception family.
- [x] V4.1 adds neither a third Maven artifact nor a supported general CLI.
- [x] Phase 1 owns exact value-type descriptors and external consumer fixtures before
  production implementation.

## Backup consistency and lifecycle

- [x] Every backup represents one exact durable sequence `B`.
- [x] `B` is selected as a writer-ordered bounded cut after preceding accepted work.
- [x] V4.1 backup is full and checkpoint-only; no active WAL is copied.
- [x] A fresh sequence-zero store is backup eligible.
- [x] A source at exhausted `Long.MAX_VALUE` cannot cut a post-checkpoint WAL and
  fails without publishing a backup.
- [x] Source checkpoint and metadata are pinned against cleanup through copy.
- [x] Later mutations resume after the cut and are excluded from the bundle.
- [x] Only one backup is active; later requests fail instead of coalescing.
- [x] Close rejects new backup requests and waits for an accepted backup.
- [x] Backup-target failures do not invalidate known-good source authority.

## Bundle format and authority

- [x] Backup family/version is `gse-backup (1,0)`.
- [x] Exact three-member inventory is frozen.
- [x] WAL and live manifests are excluded from the bundle.
- [x] Canonical encoding rules and Phase 1 immutable byte fixture are required.
- [x] Per-member integrity and content identity use SHA-256.
- [x] Content digest is domain-separated and excludes diagnostic metadata.
- [x] Counts, sizes, offsets, and total bytes are bounded and overflow checked.
- [x] Symlinks, special files, nested/extra members, and changed-while-read members are
  rejected.
- [x] Completion manifest is published last.
- [x] Sibling staging, file/directory force, atomic directory rename, and parent force
  are frozen.
- [x] Backup/restore staging and external operation-marker naming/encoding are frozen.
- [x] Existing/overlapping targets and unsupported filesystems fail closed.
- [x] Crash after final publication but before future completion is independently
  resolvable indeterminacy.

## Verification

- [x] Live-store verification is offline, exclusive, and read-only.
- [x] Backup structural verification is codec-free and portable.
- [x] At least one independent parser cannot delegate to production recovery.
- [x] Verification never truncates an incomplete WAL tail or repairs authority.
- [x] Primary structural statuses are frozen.
- [x] Deterministic ordered findings accompany the primary status.
- [x] Unsupported, incompatible, corrupt, incomplete, and safe-remnant evidence rules
  are distinguished.
- [x] Typed semantic verification validates identities, decode, canonical state, and
  required index rebuild.

## Restore

- [x] Restore accepts only a structurally and semantically valid backup.
- [x] Restore creates a new non-zero history and preserves logical sequence `B`.
- [x] Restore logically decodes/re-encodes instead of copying history-bound checkpoint
  bytes.
- [x] Source provenance remains in the bundle/result rather than changing live format
  `1.0`.
- [x] Target must be absent; an existing empty target is rejected.
- [x] Restore uses a unique sibling staging directory plus a separately locked sibling
  operation marker, so the final directory retains its exact inventory.
- [x] Staged target structural/semantic validation precedes atomic publication.
- [x] Final target is ordinary V4.0-readable `gse-durable (1,0)`.
- [x] Restored live member set, ownership lock, checkpoint manifest, and canonical
  empty WAL generation `2` at `B + 1` are frozen.
- [x] Full state/retrieval equivalence oracle is frozen.
- [x] Continued mutation, checkpoint, close, and second reopen are required.
- [x] Source cursors, process-local versions, object identity, and metrics are excluded
  from equivalence.
- [x] Restore is non-overwriting, non-resumable in V4.1, and retry uses a new absent
  target.

## Safe cleanup

- [x] Cleanup is offline and dry-run-first.
- [x] A plan binds exact path, identity, authority, inventory, delete set, and digest.
- [x] Apply reacquires ownership and rejects a stale plan before deletion.
- [x] Supported scopes are one live store or one explicitly identified V4.1 staging
  directory/operation marker.
- [x] Parent scans, age rules, globs, and prefix-only ownership are forbidden.
- [x] Exact safe live/staging member classes are frozen.
- [x] Locks, authority, pinned checkpoints, required WAL, complete backups, valid
  targets, corrupt authority, and ambiguous members are never deleted.
- [x] Interrupted cleanup remains idempotently replannable and cannot invalidate
  authority.

## Failure, security, and capacity

- [x] Backup, restore, and cleanup failure-stage precedence is frozen.
- [x] Later cleanup errors cannot hide the primary failure.
- [x] Real paths and ancestor overlap checks are required.
- [x] Parse/allocation arithmetic is bounded and overflow safe.
- [x] Live retained bytes and external backup/restore capacity are accounted
  separately.
- [x] Diagnostics are bounded and exclude document payloads and credentials.
- [x] Authoritative corruption has no repair path in V4.1.

## Crash harness and cloud lane

- [x] Phase 1 establishes local child-process and fake-cloud infrastructure before
  production backup/restore.
- [x] Each production authority transition must add its barrier and expected state in
  the same change.
- [x] Backup, verification, restore, and cleanup interruption matrices are enumerated.
- [x] Stable local artifact schema is `gse-v41-operational-evidence-v1`.
- [x] Cloud suite is `v4.1-operational-safety-suite-v1`.
- [x] Cloud preset is `v4.1-operational-safety-v1`.
- [x] Eventual registration is `v4.1.0-operational-cloud`.
- [x] Reference machine/disk envelope and serial quota-safe execution are frozen.
- [x] Experiment is one member; canonical is three independent serial members.
- [x] GCS is bundle/evidence transport, never live-store authority.
- [x] Replacement-host proof makes source VM/disk unavailable before restore.
- [x] Cleanup, maximum runtime, retention, OIDC, dry-run, fake-cloud, exact-source CI,
  and explicit paid-run authorization are required.
- [x] Phase 1 must calibrate and freeze exact workload, duration, runtime, GCS layout,
  and budget before paid execution.

## Compatibility and phase ownership

- [x] Published `4.0.0` becomes a pinned API/consumer/format baseline.
- [x] V4.1 reads V4.0 live stores without silent rewrite.
- [x] A restored live store remains V4.0-readable with matching identities.
- [x] Backup format novelty is separated from live-format compatibility.
- [x] Existing in-memory and durable paths are unchanged unless the new API is
  invoked.
- [x] Production verifier, backup, restore, cleanup, paid evidence, release candidate,
  and publication each have one owning phase.

## Protected acceptance

- [ ] Contract and checklist reviewed on their Phase 0 branch.
- [ ] Documentation links and whitespace checks pass.
- [ ] Phase 0 pull request CI passes.
- [ ] Phase 0 pull request merges to protected `master`.
- [ ] Exact-master CI passes on the merge commit.
- [ ] Protected merge commit and CI run are recorded before Phase 1 begins.

## Exit decision

The candidate is semantically complete and ready for protected Phase 0 review. Phase 1
remains blocked until every protected-acceptance item above is complete. Acceptance
authorizes only the Phase 1 foundation described by the contract; it does not authorize
production V4.1 operational code.
