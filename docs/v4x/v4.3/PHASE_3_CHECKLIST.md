# GeneralSearchEngine V4.3 Phase 3 checklist

- **Status:** Candidate for protected acceptance
- **Scope:** Structured image-assisted reopen and direct `(1,2)` migration

## Entry

- [x] Phase 2 merged through protected PR #121 as
  `e7d8be3580a8e007a1afcef099dcf2b7e61fdbba`.
- [x] Exact Phase 2 protected-master CI run `34446500594` passed.
- [x] Work is isolated on `feat/v4.3-phase3-structured-images`.

## Structured image load and fallback

- [x] Equality/range recover keys only through representative canonical documents.
- [x] Prefix keys use strict canonical UTF-8 and canonical bitmaps.
- [x] Every component is fully bound and validated before materialization.
- [x] Complete structured admission reports `COMPLETE_WARM`.
- [x] One component rejection preserves sibling admission and reports
  `PARTIAL_FALLBACK`.
- [x] Catalog rejection or absence reports `FULL_FALLBACK`.
- [x] Fallback rebuild failure retains inherited `INDEX_REBUILD_FAILURE` authority.
- [x] Production codec and Phase 2 inspector/parser remain independent.

## Recovery, refresh and semantics

- [x] Canonical decode precedes image admission and every post-checkpoint WAL unit is
  replayed.
- [x] Dynamic create/drop replay operates over the recovered checkpoint snapshot.
- [x] Explicit/automatic `(1,2)` checkpoint waits for one post-canonical best-effort
  refresh attempt.
- [x] Derived refresh failure cannot fail canonical checkpoint or successful reopen.
- [x] Backup-triggered canonical checkpoint does not wait on image refresh.
- [x] Fallback open refreshes only the decoded checkpoint snapshot before WAL replay.
- [x] Reopen diagnostics contain bounded counts, outcomes, rejections, bytes and
  timings.
- [x] Equality/range/prefix query results and ordering match deterministic rebuild.

## Migration

- [x] Direct `(1,0)->(1,2)` and `(1,1)->(1,2)` use exact target profile bytes.
- [x] Meaningful `(1,2)->(1,2)` remains supported; no-op and downgrade fail closed.
- [x] Source canonical and recognized derived bytes remain unchanged.
- [x] Target is published without derived members and migration verification cannot
  warm it accidentally.
- [x] First ordinary target open rebuilds canonical state before best-effort refresh.

## Phase boundary and crash evidence

- [x] Production refresh is structured-only; text publication/materialization stays
  Phase 4.
- [x] Mixed physical fixture behavior is labeled partial and does not claim complete
  text support.
- [x] Real child JVMs cover component and catalog publication cut points.
- [x] Both internal halt and external kill bypass graceful close.
- [x] Replacement JVM proves canonical digests, complete query results, fallback/warm
  handling and independently valid final derived state.
- [x] Checksummed bounded evidence uses the frozen V4.3 schema.

## Local acceptance

- [x] Focused Phase 3 Java and independent Python gates pass.
- [x] Production crash harness matrix passes locally.
- [x] Full reactor passes: core `525` tests with no failures/errors (`4`
  published-artifact conditional skips), processor `5/5`.
- [x] Published-4.2 compatibility and all independent consumers pass.
- [x] Release artifact integrity and reproducible-build gates pass.
- [x] Bounded JMH and inherited operational smoke gates pass.
- [x] CI contains reactor and no-GCP Phase 3 gates.
- [x] No paid cloud/IAM/registry action was performed.

## Protected acceptance

- [ ] Phase 3 pull request passes required checks.
- [ ] Phase 3 merges to protected `master`; exact commit is recorded.
- [ ] Exact protected-master CI passes before Phase 4.

Phase 4 alone owns SimpleAnalyzer text images and the complete four-index selective
fallback matrix. Phase 5 owns exhaustive lifecycle hardening.
