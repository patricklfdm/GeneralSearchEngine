# GeneralSearchEngine V4.2 Phase 5 checklist

- **Status:** Accepted on protected `master`
- **Scope:** Lifecycle, interruption, cleanup, rollback and cross-version hardening

## Entry

- [x] Phase 4 merged through protected PR #110 as
  `043b95b735dbc7dc1f319e2bd64fccba3063597a`.
- [x] Exact-master CI run `33846632898` passed.
- [x] Work is isolated on `feat/v4.2-phase5-lifecycle-hardening`.

## Marker and authority

- [x] Exact UUID-bound staging and marker names are frozen.
- [x] CRC-protected kind-3 marker binds source, target, plan, projection and source
  member identities.
- [x] Marker locking spans target verification and final source comparison.
- [x] Target is absent before rename and valid after every observed rename barrier.
- [x] Marker deletion occurs only after target and source authority verification.
- [x] Successful return leaves no migration staging or marker.

## Safe cleanup

- [x] Existing `OPERATION_REMNANT` public API recognizes only exact migration names.
- [x] Planning remains codec-free, offline, explicit and read-only.
- [x] Apply recomputes exact marker, source, staging and target authority.
- [x] Prepublication cleanup deletes only staging members, staging and marker.
- [x] Postpublication cleanup deletes only the orphan marker.
- [x] Source and final target are never present in the delete set.
- [x] Changed source, changed plan/inventory, unknown member, alias, ambiguity and
  corrupt authority fail closed before deletion.

## Crash and lifecycle evidence

- [x] 25 production-byte barriers cover marker, staging members, verification,
  rename, parent force, source comparison, marker cleanup and method return.
- [x] Every case uses abrupt process halt and a separate verifier JVM.
- [x] Every recognizable remnant is cleaned through public plan/apply operations.
- [x] Checksummed evidence records source identity, target state and remnant class.
- [x] Normal lifecycle proves target mutation, checkpoint, close and reopen.

## Rollback and compatibility

- [x] A verified `(1,0)` backup is retained outside source and target.
- [x] Source bytes remain unchanged after migration and continued target operation.
- [x] A child JVM using only pinned published `4.1.0` reopens the source.
- [x] Target-only writes are explicitly not reverse-merged.
- [x] No automatic cutover, rollback, deletion or routing surface was added.

## Local acceptance

- [x] Focused Phase 5 gate passes.
- [x] Published-4.1 rollback compatibility gate passes from an isolated repository.
- [x] Full reactor and public compatibility matrix pass.
- [x] All four independent consumers pass.
- [x] Bounded JMH smoke passes.
- [x] Release profile, six artifacts, Javadocs and reproducibility pass.

## Protected acceptance

- [x] Phase 5 pull request #111 passed every required check.
- [x] Phase 5 merged to protected `master` as `5687a05aa2f495f58d8acc904ab1e663361cf6e3`.
- [x] Exact-master CI run `33880571096` passed.

Phase 6 began from the accepted Phase 5 commit. It owns scale, profiling,
replacement-host rollback proof, paid experiment/canonical evidence and append-only
baseline registration.
