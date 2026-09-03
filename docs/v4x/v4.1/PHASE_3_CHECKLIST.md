# GeneralSearchEngine V4.1 Phase 3 checklist

- **Status:** Implementation complete; protected acceptance pending
- **Scope:** Exact-sequence live backup and immutable bundle publication

## Entry and boundary

- [x] Phase 2 merged through protected PR #95 as `a17ad20`.
- [x] Exact-master CI run `33720179867` passed on that commit.
- [x] Source live format remains exactly `gse-durable (1,0)`.
- [x] Semantic verification, restore and public cleanup remain absent.

## API and consistency cut

- [x] The default asynchronous backup descriptor and three immutable values match the
  Phase 1 fixture.
- [x] The built-in durable engine overrides the default method and never returns null.
- [x] Backup is writer ordered and represents exactly the published durable sequence
  `B` without allocating a mutation sequence.
- [x] A new source checkpoint is published at `B`; no unrelated checkpoint is treated
  as backup success.
- [x] Sequence zero is backup eligible and later mutations are excluded.
- [x] Only one backup is active; close rejects new work and waits for accepted work.

## Pinning and publication

- [x] The source checkpoint is pinned before asynchronous copy begins.
- [x] Later checkpoint cleanup retains the pinned checkpoint.
- [x] Metadata/checkpoint copy is bounded, stable-read checked, forced and SHA-256
  hashed.
- [x] Manifest bytes and canonical content identity match the frozen format.
- [x] Staging and locked operation-marker names/encoding/binding are exact.
- [x] Staging and final bundles pass production structural verification.
- [x] Final publication uses absent-target atomic rename plus parent-directory force.
- [x] Successful completion occurs only after marker removal and final parent force.

## Failure and evidence

- [x] Capacity, target I/O and target-collision failures leave source authority usable.
- [x] Normal rollback deletes only exact operation-owned staging members.
- [x] One-byte short writes and immutable target preservation pass.
- [x] Production output passes the independent Python bundle parser.
- [x] All 16 authority transitions have abrupt-halt barriers and pre-reopen inspection.
- [x] Every crash source reopens and continues durably in a replacement JVM.
- [x] `scripts/verify-v41-phase3-backup.sh` passes locally.
- [x] Full reactor, exact published compatibility, consumers, release artifacts and
  reproducibility pass locally.
- [ ] Phase 3 PR CI passes and merges to protected `master`.
- [ ] Exact-master CI passes and its commit/run are recorded.

Phase 4 semantic verification and restore remain blocked until Phase 3 acceptance.
