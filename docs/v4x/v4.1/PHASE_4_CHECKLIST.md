# GeneralSearchEngine V4.1 Phase 4 checklist

- **Status:** Implementation complete; protected acceptance pending
- **Scope:** Typed semantic verification and logical new-history restore

## Entry and boundary

- [x] Phase 3 merged through protected PR #96 as `f5516df`.
- [x] Exact-master CI run `33723841861` passed on that commit.
- [x] Active coordinates remain `4.1.0-SNAPSHOT`.
- [x] Live and backup formats remain exactly `gse-durable (1,0)` and
  `gse-backup (1,0)`.
- [x] Public cleanup and paid cloud work remain absent.

## Public API and semantic verification

- [x] Builder method descriptors, immutable record components and status order match
  the accepted Phase 1 fixture.
- [x] Structural `VALID` is required before any typed claim.
- [x] Storage/schema/codec identities, version, bounds and startup indexes are matched.
- [x] Identity mismatch precedes document decode.
- [x] Every canonical key/document is decoded under explicit bounds and round-tripped.
- [x] Key identity, canonical slots, `nextDocId`, live count and dynamic indexes pass.
- [x] Required indexes rebuild from documents rather than becoming authority.
- [x] Findings are bounded, deterministic and payload-free.

## Restore and compatibility

- [x] Existing, invalid and overlapping targets fail before semantic materialization.
- [x] Target persisted config must exactly match source metadata.
- [x] Restore generates a distinct non-zero history while preserving sequence `B`.
- [x] Terminal sequence fails with inherited `SEQUENCE_EXHAUSTED` semantics.
- [x] Exact V4 target inventory contains metadata, checkpoint, manifest, generation-2
  empty WAL and zero-length lock only.
- [x] Staged and final stores pass codec-free and typed validation.
- [x] Restored stores open through the ordinary V4 path, continue at `B + 1`,
  checkpoint, close and reopen.
- [x] Backup bytes are never mutated.

## Publication, crash and gates

- [x] Restore marker/staging encoding and absent-target atomic publication are exact.
- [x] Normal pre-publication failure removes only operation-owned members.
- [x] Post-rename failure never automatically removes a valid final target.
- [x] Ten production restore barriers pass abrupt halt and pre-reopen inspection.
- [x] Every crash case restores or reopens, continues, checkpoints and reopens again.
- [x] `scripts/verify-v41-phase4-restore.sh` passes locally.
- [x] Full reactor, published compatibility, consumers, release artifacts and
  reproducibility pass locally.
- [ ] Phase 4 PR CI passes and merges to protected `master`.
- [ ] Exact-master CI passes and its commit/run are recorded.

Phase 5 plan-bound safe cleanup remains blocked until Phase 4 acceptance.
