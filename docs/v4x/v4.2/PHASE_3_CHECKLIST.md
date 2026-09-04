# GeneralSearchEngine V4.2 Phase 3 checklist

- **Status:** Accepted through protected PR #109
- **Scope:** Production `1.1` and format-only `1.0` to `1.1` migration

## Entry

- [x] Phase 2 merged through protected PR #108 as `85fc9a4`.
- [x] Exact-master CI run `33839044114` passed.
- [x] Work is isolated on `feat/v4.2-phase3-format-migration`.

## Production format and backup

- [x] Default fresh creation remains exact `V1_0`.
- [x] Explicit `V1_1` fresh creation, mutation, checkpoint, close and reopen pass.
- [x] Every V1.1 authority-bearing live member binds the exact profile digest.
- [x] V1.1 backup uses exact minor 1, `v2` digest domain and identity.
- [x] Typed verification and restore preserve V1.1 while creating a new history.
- [x] Restored V1.1 state accepts continued mutation, checkpoint and reopen.
- [x] Existing V1.0 backup/restore behavior remains unchanged.

## Migration API and edge

- [x] Public methods and record component order match the Phase 1 fixture.
- [x] Stage and reason enum order is exact and V4.1 reasons remain unchanged.
- [x] Only `identity-format-v1@1` from exact V1.0 to exact V1.1 is admitted.
- [x] Changed codec/schema/key bytes or index descriptors fail closed for Phase 4.
- [x] Planning requires a closed canonical checkpoint plus empty continuation WAL.
- [x] Planning creates no target, staging, marker, cache or spill output.
- [x] Source member hashes, descriptor digests, projection and plan are bound.
- [x] Sequence, `nextDocId`, slot order, holes and document count are preserved.
- [x] Target history is non-zero, fresh and frozen by the plan.
- [x] Target authoritative and reserved peak bytes use overflow-safe exact arithmetic.
- [x] Apply revalidates the plan and transform and rejects target collision/staleness.
- [x] Successful apply proves staged/final structure, typed state, normal reopen,
  source preservation and marker cleanup.

## Independent and crash evidence

- [x] Independent Python parsing accepts production V1.1 live and backup bytes.
- [x] Independent WAL parsing covers complete frames and checksum corruption.
- [x] Production transitions have stable V4.2 crash barriers.
- [x] A separate JVM verifies prepublication crash leaves final target absent.
- [x] A separate JVM verifies post-parent-force crash leaves a valid V1.1 target.
- [x] Both abrupt cases prove the complete source byte identity unchanged.
- [x] Evidence uses `gse-v42-migration-evidence-v1` and is checksummed/bounded.

## Local acceptance

- [x] `scripts/verify-v42-phase3-format-migration.sh` passes.
- [x] Focused public API, production format, migration and V4.1 regressions pass.
- [x] Full reactor passes with 489 core tests and 5 processor tests; one declared
  core test is skipped.
- [x] Published artifact compatibility, consumers and Japicmp pass.
- [x] Release artifacts, Javadocs and reproducibility pass.

## Protected acceptance

- [x] Phase 3 pull request #109 passed every required check.
- [x] Phase 3 merged to protected `master` as
  `43bf2bda3f51ac28aa4aaa1be8bbd96d63bd6daf`.
- [x] Exact-master CI run `33842969788` passed.

Phase 4 may begin only after protected acceptance. It owns declared codec/schema/key
transforms, collision diagnostics and target-index rebuild; Phase 3 does not authorize
those paths.
