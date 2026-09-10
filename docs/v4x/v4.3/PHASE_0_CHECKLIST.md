# GeneralSearchEngine V4.3 Phase 0 checklist

- **Status:** Candidate for protected acceptance
- **Scope:** Documentation-only fast-reopen freeze
- **Authoritative contract:** [PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md)

Checked items mean the candidate documents contain an explicit decision. They do not
record protected-master acceptance until the final acceptance section is completed.

## Scope and inheritance

- [x] V4.3 is fast reopen through reconstructible persisted derived state.
- [x] Published V4.0 durability, V4.1 operations, V4.2 storage evolution, and V3.4
  retrieval semantics are inherited without reinterpretation.
- [x] Signed `v4.2.0`, protected commit, Central artifacts, GitHub Release,
  deployment reconciliation, and migration baseline are pinned.
- [x] Phase 1 must resolve published artifacts and fixtures in fresh isolation.
- [x] Authoritative indexes, Java serialization, custom-index persistence, memory
  mapping, lazy readiness, repair, replication, and retrieval changes are excluded.
- [x] Phase 0 is documentation-only.

## Format and compatibility

- [x] Exact live/backup minors `(1,0)`, `(1,1)`, and `(1,2)` are recognized.
- [x] Existing/default construction remains exact `(1,0)`.
- [x] Fresh `(1,2)` requires explicit selection.
- [x] Explicit derived-state configuration on `(1,0)` or `(1,1)` is rejected rather
  than ignored.
- [x] Opening `(1,0)` or `(1,1)` never writes derived files or changes format.
- [x] Configuring `(1,2)` against an older directory fails rather than upgrading.
- [x] `(1,2)` gains a new canonical profile and required reconstructible-derived-state
  capability while permitting image absence.
- [x] Same-major higher minor, unknown required capability, malformed canonical
  binding, and derived-state failure remain distinguishable.
- [x] Exact bytes, bounds, profile digest, magic and immutable fixtures belong to
  Phase 2.

## Authority separation

- [x] Metadata, checkpoint authority, canonical documents/index descriptors, and WAL
  remain the complete recovery authority.
- [x] Catalogs, components, staging, old generations and diagnostics are always
  non-authoritative.
- [x] Removing every derived member leaves a valid recoverable `(1,2)` store.
- [x] Derived bytes alone can never form a store, backup, checkpoint, migration result,
  or committed sequence.
- [x] Canonical verification runs independently and before derived admission.
- [x] A valid image cannot mask canonical corruption, identity mismatch, missing WAL,
  codec failure, or schema mismatch.
- [x] Derived failure does not turn valid canonical authority into `CORRUPT`.

## Catalog and components

- [x] One atomically published derived catalog inventories independent per-index
  components for one checkpoint sequence.
- [x] Catalog identity binds live format/profile, history, checkpoint file/hash,
  sequence, schema, codec, generator, and complete descriptor order.
- [x] Each component repeats store/checkpoint/descriptor identity and has independent
  size, checksum and SHA-256 binding.
- [x] Names and staging families cannot collide with canonical V4 members.
- [x] Timestamps, paths, PIDs, hostnames, Java classes/object hashes and enumeration
  order are excluded from content identity.
- [x] Catalog failure rejects the generation; component failure permits selective
  rejection only when remaining bindings are independently trustworthy.

## Stable built-in image model

- [x] Equality, range, prefix and SimpleAnalyzer text are the complete supported image
  set.
- [x] No arbitrary custom `IndexDefinition` or application callback is persisted.
- [x] Equality/range values are recovered through representative canonical documents,
  not serialized Java objects.
- [x] Representative slots are live, members of their bitmaps, canonical and bounded.
- [x] Range compare-to-equivalent groups remain unique under published semantics.
- [x] Prefix keys and text terms use strict UTF-8 canonical order.
- [x] Text images bind analyzer identity and encode bounded postings, positions,
  lengths, frequencies and vocabulary state required by published behavior.
- [x] Document IDs, bitmaps, counts, positions and statistics are canonical,
  overflow-safe and validated.
- [x] Warm-versus-rebuild differential tests cover results, score bits, order,
  estimates, statistics and mutation lifecycle.

## Reopen and fallback

- [x] Canonical authority is validated and canonical documents decoded before image
  use.
- [x] Admitted images are bound to the exact authoritative checkpoint.
- [x] Missing/rejected indexes rebuild deterministically from canonical documents.
- [x] Reopen refresh uses the exact checkpoint snapshot before WAL replay and never
  serializes post-replay state under the checkpoint sequence.
- [x] Post-checkpoint WAL always replays contiguously; images never skip WAL.
- [x] Dynamic index create/drop after the checkpoint preserves exact behavior.
- [x] No partial search snapshot is visible before complete recovery.
- [x] Failed image materialization receives one rebuild fallback.
- [x] Successful fallback opens with diagnostics; failed fallback retains inherited
  `INDEX_REBUILD_FAILURE` as the primary cause.
- [x] Complete warm, partial fallback, full fallback and not-applicable outcomes are
  distinct.

## Publication and Future semantics

- [x] Canonical checkpoint publication and parent force precede derived publication.
- [x] Component staging/write/force/rename/parent-force precedes catalog publication.
- [x] Proposed and published generations are independently re-read and validated.
- [x] A catalog never names an unforced component.
- [x] Components omitted from the replacement catalog become cleanup candidates only
  after new catalog durability.
- [x] Every interruption leaves canonical authority independently recoverable.
- [x] Existing `checkpoint()` Future continues to report canonical checkpoint success.
- [x] Derived failure cannot retroactively fail or make canonical checkpoint/mutation
  completion indeterminate.
- [x] Cold/fallback recovery makes one synchronous bounded best-effort refresh attempt
  before returning; open success proves attempt completion, not cache persistence.
- [x] `(1,2)` checkpoint Future completion follows one bounded refresh attempt, while
  refresh failure cannot change canonical checkpoint success.

## Backup, restore, and migration

- [x] Backup `(1,2)` retains exactly three canonical members.
- [x] Derived catalog/components are excluded from backup identity and byte limit.
- [x] Backup `(1,2)` uses a new domain-separated content identity.
- [x] Restored `(1,2)` targets are cold and first reopen rebuilds before refresh.
- [x] Existing V4.2 edges remain unchanged.
- [x] Direct `(1,0)` to `(1,2)` and `(1,1)` to `(1,2)` are explicit registered
  one-step edges rather than hidden multi-hop conversion.
- [x] `(1,2)` to `(1,2)` requires a meaningful declared change.
- [x] Migration projection/success excludes derived bytes; migrated targets are cold.
- [x] Downgrade, online migration, source mutation/deletion and automatic cutover
  remain excluded.
- [x] Published V4.2 rejects exact `(1,2)` fail-closed and remains the rollback/API
  compatibility baseline.

## Inspection and diagnostics

- [x] Codec-free derived inspection is offline, exclusive, read-only and distinct
  from canonical structural verification.
- [x] Inspection reports normalized path, status, identities, checkpoint, catalog,
  ordered components, byte categories and bounded findings.
- [x] `NOT_APPLICABLE`, `ABSENT`, `VALID`, `PARTIAL`, `STALE`, `INCOMPATIBLE`,
  `INCOMPLETE`, and `CORRUPT` meanings are frozen conceptually.
- [x] Phase 1 freezes exact public type names, components, optionality and enum order.
- [x] Published `DurabilityMetrics` constructors/components remain unchanged.
- [x] A separate optional last-reopen report is exposed through an additive default
  capability.
- [x] Reopen diagnostics separate canonical load, image inspection/load, rebuild, WAL
  replay, refresh, total open, bytes and component counts.
- [x] Diagnostics are observations rather than durability or query authority.

## Bounds, cleanup, and security

- [x] Derived allowance, per-component/total bytes, counts, strings, synchronous
  refresh work/bytes, temporary amplification and diagnostics are bounded.
- [x] Filesystem calls have no false wall-clock guarantee; external process/workflow
  maximum runtime remains explicit.
- [x] Derived bytes count toward total retained engine-owned bytes.
- [x] Canonical WAL/checkpoint space has priority over cache generation.
- [x] Overflow, capacity, ENOSPC or derived I/O failure omits/rejects cache without
  invalidating canonical authority.
- [x] Cleanup remains offline, dry-run-first and bound to exact authority, catalog,
  member hashes, real paths, links and inventory.
- [x] Only unreferenced staging files and components omitted from the current valid
  catalog may be deleted.
- [x] Current referenced components, canonical files, unknown members and ambiguous
  aliases are never deleted.
- [x] A corrupt catalog grants no deletion permission for ambiguous components.
- [x] Encoded documents/keys, extracted values, terms beyond bounded finding identity,
  credentials and unbounded exception text are excluded from diagnostics.
- [x] SHA-256 is integrity/identity evidence, not authentication.

## Crash harness and fake cloud from Phase 1

- [x] Phase 1 establishes the separate-process harness before production images.
- [x] Every production authority/cache transition adds a stable barrier and expected
  pre-open classification in the same change.
- [x] Barriers cover component and catalog write/force/rename/publication/validation,
  fallback/refresh, cleanup, and completion boundaries.
- [x] Faults cover corruption, swapping, stale bindings, missing/duplicate members,
  malformed logical encodings, capacity/I/O, permissions, races and WAL-after-image.
- [x] Independent parsing occurs before production reopen.
- [x] Every case proves complete retrieval oracle, continued mutation, checkpoint,
  close and second reopen where canonical authority is valid.
- [x] Local artifact schema is `gse-v43-fast-reopen-evidence-v1`.
- [x] Fake cloud models fresh disks, disk detach/attach, replacement host, retention,
  serial members, failure artifacts and cleanup receipts.

## Performance and paid evidence

- [x] Cloud suite is `v4.3-fast-reopen-suite-v1`.
- [x] Cloud preset is `v4.3-fast-reopen-v1`.
- [x] Eventual append-only registration is `v4.3.0-fast-reopen-cloud`.
- [x] Experiment is one member; canonical is three independent serial members.
- [x] Frozen cells include published-4.2 cold, current cold, complete warm, structured
  and text partial fallback, catalog/full fallback, checkpoint-plus-WAL, restored and
  migrated targets, and continued operation.
- [x] Each cell records corpus/index/configuration, sequences, bytes, heap/GC/CPU,
  filesystem/device/cache state, stage durations, checksums and cleanup.
- [x] OS page-cache state is explicit and cannot be mislabeled.
- [x] Forced-rebuild controls remain benchmark-only, and evidence separates recovery-
  ready time before refresh from complete open-return time.
- [x] Phase 1 calibrates numeric thresholds before production image implementation.
- [x] Final provisional gate requires complete-warm median at most 50% of paired
  current-source forced-rebuild median and no member ratio above 0.65.
- [x] The gate is release evidence rather than a portable user SLA.
- [x] Serial topology respects 32-vCPU global and 500-GiB regional SSD quotas.
- [x] Exact machine/image/zone/disks/filesystem/corpus/runtime/cost/retention/GCS/OIDC/
  cleanup are frozen in Phase 1 before paid execution.
- [x] GCS is evidence transport only, never live or derived authority.
- [x] Paid runs remain Phase 6-only after local/fake/dry-run/exact-source gates and
  explicit user confirmation.

## API and phase ownership

- [x] Additions remain in the core artifact; no third module or CLI is added.
- [x] Format constants, bounded config, derived inspection, report values and optional
  engine diagnostic are additive.
- [x] Existing records/constructors/enums and independent implementations remain
  source/binary compatible.
- [x] Phase 1 owns exact API fixtures/models/harness/calibration but no production
  format behavior.
- [x] Phase 2 owns physical bytes/codecs/inspection but production open remains
  rebuild-only.
- [x] Phase 3 owns `(1,2)`, structured images and direct migration edges.
- [x] Phase 4 owns text images and complete selective fallback.
- [x] Phase 5 owns lifecycle and correctness hardening.
- [x] Phase 6 alone owns paid evidence and registration.
- [x] Phases 7/8 own release candidate and publication separately.

## Protected acceptance

- [x] Contract, charter, roadmap links and checklist are reviewed on their Phase 0
  branch.
- [x] Documentation links and whitespace checks pass.
- [x] The diff contains no POM version, production code, executable test/harness,
  workflow, cloud-IAM, registry, or paid-resource change.
- [ ] Phase 0 pull request CI passes.
- [ ] Phase 0 pull request merges to protected `master`; exact commit is recorded.
- [ ] Exact-master CI passes before Phase 1; run is recorded.

## Exit decision

Phase 0 remains a candidate until protected acceptance is complete. Phase 1 may begin
only after the final three acceptance items are checked on a follow-up source branch.
Production `(1,2)` or derived-image implementation remains unauthorized until its
owning phase.
