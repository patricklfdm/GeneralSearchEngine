# GeneralSearchEngine V4.2 Phase 0 checklist

- **Status:** Accepted through protected PR #106
- **Scope:** Documentation-only storage-evolution freeze
- **Authoritative contract:** [PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md)

Checked items mean the candidate documents contain an explicit decision. They do not
record protected-master acceptance until the final acceptance section is completed.

## Scope and inheritance

- [x] V4.2 storage-evolution scope and exclusions are explicit.
- [x] Published V4.0 durability, V4.1 operations, and V3.4 retrieval semantics are
  inherited without reinterpretation.
- [x] Existing `gse-durable (1,0)` and `gse-backup (1,0)` bytes remain immutable.
- [x] Signed `v4.1.0` commit, Central coordinates, release workflow/deployment, and
  immutable operational baseline identity are pinned explicitly.
- [x] Phase 1 must resolve published artifacts and fixtures in fresh isolation rather
  than substituting reactor output.
- [x] Online/in-place migration, automatic rewrite, downgrade, repair, persisted
  derived indexes, replication, and new retrieval semantics are excluded.
- [x] Phase 0 is documentation-only.

## Format and open policy

- [x] V4.2 recognizes exact live formats `(1,0)` and `(1,1)` only.
- [x] Default durable construction remains `(1,0)`.
- [x] Fresh `(1,1)` creation requires explicit format selection.
- [x] Opening `(1,0)` continues writing `(1,0)` without metadata, checkpoint,
  manifest, or WAL rewrite caused by library upgrade.
- [x] Configuring `(1,1)` against an existing `(1,0)` directory fails rather than
  migrating.
- [x] Same-major higher-minor, unknown required capability, unknown family/major,
  malformed known format, and incomplete authority classifications are distinct.
- [x] A mixed-minor history is corrupt.

## Format `(1,1)` profile

- [x] The functional delta is a canonical format profile owned by metadata and bound
  by every authority-bearing member.
- [x] The SHA-256 digest domain is frozen.
- [x] Initial required capability identifiers and their canonical order are frozen.
- [x] Optional capabilities are empty in V4.2.
- [x] Unknown required capabilities fail as incompatible; malformed known bindings
  fail as corrupt.
- [x] Directory roles and naming families remain those of `(1,0)`; no derived-index
  or provenance member is added.
- [x] Phase 2 owns exact magic, bytes, offsets, bounds, and immutable fixture hashes.
- [x] Later byte/member changes require a new format and explicit migration edge.

## Backup and restore continuity

- [x] `(1,0)` stores continue producing exact `gse-backup (1,0)` bundles.
- [x] `(1,1)` stores produce exact `gse-backup (1,1)` bundles.
- [x] Both backup minors retain the three-member inventory.
- [x] Backup `1.1` binds the live profile digest through new exact
  `gse-backup-content-v2` and `gse-backup-v2-*` identities without extending the
  published `v1` algorithm.
- [x] Restore preserves source format rather than migrating it.
- [x] V4.2 verifies/restores both supported backup minors; published V4.1 treats
  intact backup `1.1` as incompatible.
- [x] Direct backup-to-new-format migration is excluded.

## Public surface

- [x] Public live-format selection is additive in the core artifact.
- [x] Additive codec-free store/bundle format inspection exposes structural status,
  declared formats, source format, and optional profile digest without changing V4.1
  report components or enum order.
- [x] The target `SearchEngineBuilder` owns typed planning and apply operations.
- [x] Each operation also receives a source builder or equivalent Phase 1-frozen typed
  source descriptor so source schema, ID extraction, and logical indexes are
  independently validated and plan-bound.
- [x] Planning is synchronous, offline, typed, and read-only.
- [x] Apply is synchronous, offline, typed, and absent-target only.
- [x] Request responsibilities include source verification, explicit target format,
  target configuration, transform descriptor/implementation, and resource bounds.
- [x] Phase 1 freezes exact generic descriptors, value components, enum order, null,
  equality, path, and Javadoc behavior before production implementation.
- [x] A distinct migration exception family avoids extending the published V4.1
  operational-reason enum.
- [x] V4.2 adds neither a third Maven artifact nor a supported general CLI.

## Supported migration edges

- [x] Initial format evolution is `(1,0)` to `(1,1)`.
- [x] `(1,1)` to `(1,1)` is allowed only for a declared identity/schema/codec/
  transform/index change.
- [x] Same-format no-op copy, `(1,0)` to `(1,0)`, downgrade, unknown versions, and
  hidden multi-hop migration are rejected.
- [x] Future edges require an accepted contract and append-only edge registry.

## Source eligibility and preservation

- [x] Source must be closed, real, local, exclusively lockable, and exact `VALID`.
- [x] Source must have an authoritative checkpoint at `S` and a valid empty
  post-checkpoint WAL beginning at `S + 1`.
- [x] Safe remnants, incomplete tails, extra/unknown members, mixed formats, and
  operation markers make the source ineligible.
- [x] Source identities, codec, logical indexes, and typed canonical decode are
  verified before transformation.
- [x] Planning/checkpoint/cleanup/recovery never normalizes or writes source bytes.
- [x] Ordered source member hashes and authority identity are compared before and
  after plan/apply.
- [x] Exhausted sequence or `nextDocId` cannot produce a writable target.

## Transform semantics

- [x] Transform identity and non-negative version are explicit plan inputs.
- [x] Every source record maps to exactly one target record in source-slot order.
- [x] Dropping, splitting, merging, duplicating, or reordering records is forbidden.
- [x] Nulls, exceptions, target-ID mismatch, target-key collision, codec
  non-canonicality, and bounds violations fail closed.
- [x] Target key type/value may change only through the explicit one-to-one transform.
- [x] Target indexes are the exact builder definitions and are rebuilt from target
  documents.
- [x] Changed target index configuration is exposed and plan-bound even when document
  transformation is identity.
- [x] Plan and apply invoke the transform serially and independently.
- [x] A changed apply projection is classified as transform non-determinism.
- [x] Transform sandboxing and side-effect enforcement are not claimed.

## Dry-run plan and identity

- [x] Planning executes full decode/transform/encode projection without filesystem
  output or hidden spill/cache authority.
- [x] Target history is non-zero, distinct, and allocated/bound during planning.
- [x] Source inventory, source authority, formats, identities, indexes, transform,
  target profile, counts, bytes, paths, and capacity bounds are plan inputs.
- [x] Projection and plan use separate domain-separated SHA-256 identities.
- [x] Repeated planning may choose a distinct target history; each returned plan is
  canonically encoded and immutable rather than promised to have a repeatable digest.
- [x] Diagnostic time, host, PID, elapsed time, and usable-space observation are not
  identity inputs.
- [x] Apply recomputes all authority/configuration/projection bindings.
- [x] Any source, target, request, transform, path, or projection change makes the
  plan stale.

## Target publication

- [x] Target must be absent and non-overlapping with source in either ancestor
  direction.
- [x] Real-path, symlink, same-file, special-file, and recognizable hard-link aliases
  fail closed.
- [x] Unique sibling staging and an externally locked operation marker are required.
- [x] Target members are logically re-encoded; source history-bound bytes are never
  copied as target authority.
- [x] Every target member and directory is forced in a frozen order.
- [x] Staged structural and semantic verification precedes atomic rename.
- [x] Final parent force, final verification, normal open/close, and source identity
  recheck precede success.
- [x] Successful target uses a new history at source sequence `S`, preserves slot
  order and `nextDocId`, and begins an empty WAL at `S + 1`.
- [x] Process-crash completion indeterminacy is resolved by independent verification,
  not overwrite/retry against an existing target.

## Capacity, security, and diagnostics

- [x] Source/target bytes, key/document sizes, documents, indexes, capabilities,
  collision entries, findings, diagnostics, paths, and identities are bounded.
- [x] All size arithmetic is overflow-safe.
- [x] Planning and apply separately check caller maximum, predicted peak, reserve, and
  observed usable space.
- [x] ENOSPC and changed capacity fail without source mutation.
- [x] Migration streams records instead of retaining the full corpus in heap.
- [x] Encoded/decoded payloads, credentials, tokens, and unbounded custom exception
  text are excluded from diagnostics.
- [x] SHA-256 is integrity/identity evidence, not authentication.

## Rollback and cleanup

- [x] The library never performs traffic cutover, directory swap, source rename, or
  source deletion.
- [x] Operators retain a verified pre-migration backup and untouched source through
  the rollback window.
- [x] Continued target writes are explicitly not reverse-merged during rollback.
- [x] Published `4.1.0` source reopen is mandatory rollback evidence.
- [x] V4.1 plan-bound cleanup extends only to exact proven V4.2 migration remnants.
- [x] Complete target, source authority, unknown sibling, corrupt authority, or stale
  identity is never deleted.
- [x] Retry requires a new absent target after separately reviewed cleanup.

## Crash harness and cloud lane

- [x] Phase 1 establishes independent models, immutable bytes, local child-process
  harness, fake cloud, and calibrated evidence plan before production migration.
- [x] Every production authority transition adds its barrier and expected state in
  the same change.
- [x] Plan interruption proves zero filesystem output and unchanged source.
- [x] Apply barriers cover marker, staging, each file/force, staged verification,
  rename, parent force, final verification, source recheck, and marker cleanup.
- [x] Transform, codec, path, source mutation, capacity, I/O, and cleanup fault
  families are enumerated.
- [x] Local artifact schema is `gse-v42-migration-evidence-v1`.
- [x] Cloud suite is `v4.2-storage-evolution-suite-v1`.
- [x] Cloud preset is `v4.2-storage-evolution-v1`.
- [x] Eventual registration is `v4.2.0-migration-cloud`.
- [x] Experiment is one member; canonical is three independent serial members.
- [x] Separate source/target persistent disks and replacement-target host are frozen.
- [x] Canonical evidence proves target continuation and published-4.1 rollback from
  the untouched source.
- [x] GCS is immutable fixture/evidence transport, never live storage or cutover
  authority.
- [x] Phase 1 must freeze exact workload, transforms, runtime, machine/disks, cost,
  retention, GCS prefix, OIDC, serial cleanup, and budget before paid execution.
- [x] Paid runs remain Phase 6-only after local/fake/dry-run/exact-source gates and
  explicit confirmation.

## Compatibility and phase ownership

- [x] Published `4.1.0` is pinned as API, consumer, live/backup format, operations,
  and rollback baseline.
- [x] Existing consumers and default `(1,0)` durable behavior remain unchanged.
- [x] Backup/restore behavior is exact-format-preserving.
- [x] V4.2 `1.1` novelty is separated from Java API compatibility.
- [x] Phase ownership separates fixtures/readers, format-only migration, transforms,
  hardening, paid evidence, release candidate, and publication.

## Protected acceptance

- [x] Contract and checklist reviewed on their Phase 0 branch.
- [x] Documentation links and whitespace checks pass.
- [x] The diff contains no POM version, production code, executable test/harness,
  workflow, cloud-IAM, or paid-resource change.
- [x] Phase 0 pull request CI passes.
- [x] Phase 0 pull request #106 merges to protected `master` as
  `8391ea67e451da476f8dc8f7c25c3f78e3656173`.
- [x] Exact-master CI run `33830552115` passes before Phase 1 begins.

## Exit decision

Phase 0 is accepted. Phase 1 may establish the non-production foundation described by
this contract. Production V4.2 format and migration code remain unauthorized until
their owning phases.
