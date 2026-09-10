# GeneralSearchEngine V4.3 Phase 4 checklist

- **Status:** Candidate for protected acceptance
- **Scope:** SimpleAnalyzer images and complete selective fallback

## Entry

- [x] Phase 3 merged through protected PR #122 as
  `98527a2475d69673513addb15e5693bc197ddf2c`.
- [x] Exact Phase 3 protected-master CI run `34454404406` passed.
- [x] Work is isolated on `feat/v4.3-phase4-text-images`.

## Text image materialization

- [x] Only exact `gse-simple-v1` text descriptors are admitted.
- [x] Terms use strict canonical UTF-8 ordering.
- [x] Field lengths, totals, postings, frequencies and positions are cross-validated.
- [x] Posting documents are live and positions are non-empty, increasing and bounded.
- [x] Loader constructs immutable postings, lengths and fuzzy vocabulary without
  analyzer execution.
- [x] Writer adds no source text or highlight-only payload.
- [x] Production codec remains independent of codec-free inspection and Python parsing.

## Complete four-kind behavior

- [x] Valid equality/range/prefix/text generation reports `COMPLETE_WARM` as `4/0`.
- [x] Text rejection preserves three structured siblings and reports `3/1` partial.
- [x] Structured rejection preserves text and valid structured siblings.
- [x] Catalog absence/rejection reports `0/4` full fallback.
- [x] Successful fallback refresh restores independently inspected `VALID` state.
- [x] Term, phrase, fuzzy, BM25, explanation score bits, estimates and order match
  deterministic rebuild semantics.
- [x] Post-checkpoint text mutation and dynamic drop/create replay correctly.
- [x] Derived failure cannot override canonical checkpoint/reopen success.

## Migration and crash evidence

- [x] Older-to-`(1,2)` text targets are cold, rebuild all four, then publish warm state.
- [x] Backup checkpoint semantics remain canonical-only.
- [x] Text-specific component rename/force and mixed catalog publication are covered.
- [x] Internal halt and external kill bypass graceful close.
- [x] Inspector JVM runs before replacement production open.
- [x] Replacement JVM proves structured/text results, canonical hashes and final valid
  derived state.
- [x] Evidence uses the frozen bounded checksummed V4.3 schema.

## Local acceptance

- [x] Focused Phase 4 Java, Python and production crash gates pass.
- [x] Full reactor passes: core `532` tests with no failures/errors (`4`
  published-artifact conditional skips), processor `5/5`.
- [x] Published-4.2 compatibility and all independent consumers pass.
- [x] Release artifact integrity and reproducible-build gates pass.
- [x] Bounded JMH and inherited operational smoke gates pass.
- [x] CI contains reactor and no-GCP Phase 4 gates.
- [x] No paid cloud/IAM/registry action was performed.

## Protected acceptance

- [ ] Phase 4 pull request passes required checks.
- [ ] Phase 4 merges to protected `master`; exact commit is recorded.
- [ ] Exact protected-master CI passes before Phase 5.

Phase 5 owns exhaustive lifecycle hardening. Phase 6 alone owns paid evidence and
append-only baseline registration.
