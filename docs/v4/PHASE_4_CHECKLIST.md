# V4.0 Phase 4 checklist

**Status:** implementation and checkpoint crash matrix complete; final validation and
protected merge pending

## Entry and scope

- [x] Phase 3 protected PR #80 merged at
  `266463851aff5b742f26338bc3b3c1867f247ea1`.
- [x] Exact-master Phase 3 CI run `33589193180` completed successfully.
- [x] Published V1–V3.4 API and in-memory behavior remain unchanged.
- [x] Phase 2 WAL frame bytes remain version `1.0`; no format migration is added.

## Format, authority and execution

- [x] Versioned checkpoint and manifest layouts have magic, history, bounds and CRC32C.
- [x] Canonical sparse slots, `nextDocId`, business keys, documents and built-in index
  descriptors are persisted; derived postings are not.
- [x] Staging and unreferenced data are never recovery authority.
- [x] One exact manifest identifies one exact checkpoint and post-cut WAL boundary.
- [x] Writer cut forces the old WAL and next generation header before admission resumes.
- [x] Serialization and validation run asynchronously from an immutable capture.
- [x] Explicit requests coalesce and automatic threshold crossing does not change
  mutation success semantics.
- [x] Close drains accepted checkpoint work and creates no implicit checkpoint.

## Recovery, corruption and cleanup

- [x] WAL-only multi-generation, checkpoint-only and checkpoint-plus-WAL recovery pass.
- [x] Post-checkpoint sequence and internal document IDs continue monotonically.
- [x] Missing, truncated, checksum-invalid or mismatched authoritative checkpoint state
  fails closed with `CORRUPT_CHECKPOINT`.
- [x] Manifest publication precedes directory force and all old-history cleanup.
- [x] Cleanup deletes only generations older than the authoritative post-cut WAL and
  checkpoint files not named by the manifest.
- [x] Retained-byte admission preserves space for a future WAL generation header.
- [x] Checkpoint capacity failure is diagnostic and does not consume a mutation
  sequence or silently publish partial authority.

## Crash and independent evidence

- [x] Eleven stable checkpoint barriers cover old/new WAL force, partial/forced data,
  data publication, partial/forced manifest, manifest rename, directory force and
  before/after cleanup.
- [x] Every barrier passes in a separate JVM under internal hard halt.
- [x] External kill covers partial manifest and post-directory-force authority.
- [x] Recovery performs a continued write and second reopen after every crash.
- [x] Independent Python inspection validates checkpoint, manifest, generation and
  staging classification without production Java readers.
- [x] Fake-cloud `phase4-checkpoint` failure-drill evidence validates without GCP.

## Acceptance

- [x] Focused checkpoint/recovery/corruption tests pass.
- [x] Full checkpoint crash and fake-cloud matrix passes.
- [x] Clean reactor passes (414 core and 5 processor tests, zero failures).
- [x] Published 1.0.0–3.4.0 compatibility and all three consumers pass.
- [x] Strict Javadocs, six release JARs, JMH smoke and reproducibility pass.
- [ ] Required PR, protected merge and exact-master Phase 4 CI pass.

Phase 5 owns broader lifecycle races, concurrent-producer stress, repeated crash loops,
disk-full/cleanup failure injection and sustained retained-footprint hardening. Phase 4
closes the checkpoint authority and single-crash storage protocol those tests consume.
