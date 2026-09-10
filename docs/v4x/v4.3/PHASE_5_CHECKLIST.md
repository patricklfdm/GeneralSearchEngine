# GeneralSearchEngine V4.3 Phase 5 checklist

- **Status:** Accepted on protected `master`
- **Scope:** lifecycle and correctness hardening; no paid evidence

## Entry

- [x] Phase 4 merged through protected PR #123 as
  `2f229303168c93e81a571b1d5c931bff015eb1b5`.
- [x] Exact Phase 4 protected-master CI run `34460924869` passed.
- [x] Work is isolated on `feat/v4.3-phase5-lifecycle-hardening`.

## Cleanup authority

- [x] Existing public dry-run/apply API is reused without signature expansion.
- [x] Exact `(1,2)` planning binds canonical authority, all inventory paths,
  sizes/SHA-256, current valid catalog identity and the complete delete set.
- [x] Catalog and component staging remnants are recognized conservatively.
- [x] Only final components omitted by a current valid catalog are eligible.
- [x] Missing/rejected catalog grants no final-component deletion permission.
- [x] Current catalog, referenced components, canonical and unknown members are never
  candidates.
- [x] Symbolic links, hard-link aliases and changed inventories fail closed.
- [x] Apply replans, verifies each member, forces the directory and revalidates
  canonical authority.
- [x] Cleanup is deterministic, idempotent and converges to one valid generation.

## Lifecycle and fault hardening

- [x] Repeated mutation/checkpoint/reopen produces complete warm generations.
- [x] Concurrent mutation bursts remain deterministic across checkpoints.
- [x] Stale cleanup plans refuse before deleting additional members.
- [x] Corrupt catalog, derived staging and aliased-member cases are covered.
- [x] Stable before/during/after superseded-cleanup barriers are production-owned.
- [x] Internal halt and external kill bypass graceful close.
- [x] Codec-free inspection precedes replacement production open.
- [x] Replacement recovery completes cleanup, queries, continued mutation,
  checkpoint and a second warm reopen.
- [x] Phase 2–4 corruption, selective fallback, capacity and publication crash
  matrices remain inherited.

## Backup, restore, migration and compatibility

- [x] Exact `(1,2)` backup inventory remains canonical-only.
- [x] Typed verification/restore carries persisted `maxDerivedStateBytes`.
- [x] Restored target is cold on first open and complete-warm after refresh.
- [x] Post-restore mutation and checkpoint survive a second reopen.
- [x] Direct migration remains source-preserving and cold-target-first.
- [x] Default `(1,0)`, explicit `(1,1)` and published `4.2.0` behavior remain
  unchanged.
- [x] No public API signature or serialized enum-order change was introduced.

## Local acceptance

- [x] Focused Phase 5 Java, Python and three-case production cleanup crash gate
  pass.
- [x] Full reactor passes: core `537` tests (`4` skipped) and processor `5`
  tests, with zero failures or errors.
- [x] Published `4.2.0` cold reopen at `20,000` documents and all independent
  V1/V2/V3/V4 consumers pass.
- [x] Release artifact integrity passes for all six JARs and the reproducible-build
  gate reports identical outputs.
- [x] Bounded JMH, inherited V4.0 operational smoke, V4.1 twelve-case cleanup crash
  and V4.2 migration/lifecycle gates pass.
- [x] CI contains reactor and no-GCP Phase 5 gates.
- [x] No paid cloud/IAM/registry action was performed.

## Protected acceptance

- [x] Phase 5 pull request #124 passed required checks.
- [x] Phase 5 merged to protected `master` as
  `e241e1499861e0b44583a948d410ce0ac9c3c286`.
- [x] Exact protected-master CI run `34529966882` passed before Phase 6.

Phase 6 alone owns profiling, paid experiment/canonical evidence, review and
append-only baseline registration.
