# GeneralSearchEngine V4.4 Phase 4 checklist

- **Status:** Local implementation complete; protected entry and acceptance pending
- **Baseline:** [PHASE_4_BASELINE.md](PHASE_4_BASELINE.md)

## Entry

- [x] Phase 3 records `ZERO_PRODUCTION_CHANGE_REQUIRED` locally.
- [x] No contract violation or measured regression is admitted.
- [x] Phase 2 merged through protected `master`; exact-master CI `34591678426`
  passed on `96b43c9`.
- [ ] Phase 3 merges through protected `master` with exact-master CI.

## Bounded hardening

- [x] Separate JVM uses one-GiB heap, G1 and a 240-second external deadline.
- [x] Dense corpus is exactly 20,000 documents, 16 declared tokens, four indexes,
  eight-byte keys and 256-byte encoded documents.
- [x] One writer and four readers make measured concurrent progress.
- [x] Exactly 2,000 updates, four checkpoints and two verified backups complete.
- [x] Complete document and structured/text query oracles pass before close.
- [x] Three reopens and one continued mutation/second reopen pass.
- [x] Four inherited migration interruption cases pass in their owning gate.
- [x] Retained, WAL, peak/final directory, heap, GC, CPU and wall-time values record.
- [x] Local probe artifacts are cleaned; checksummed evidence remains bounded.

## Admission and scope

- [x] Result is `PASS_NO_MEASURED_REGRESSION`.
- [x] `admittedOptimization=false` and no `src/main` change exists.
- [x] Public API, format and authority remain unchanged.
- [x] No paid cloud resource is created.
- [x] Local measurements are explicitly non-portable diagnostics, not SLAs.

## Verification

- [x] Positive and negative Python validator contracts pass.
- [x] V4.2 transform/migration interruption matrix passes.
- [x] V4.4 semantic and cleanup evidence validates independently.
- [x] Version alignment remains `4.4.0-SNAPSHOT`.

## Protected acceptance

- [ ] Phase 4 PR passes required checks after accepted predecessors.
- [ ] Phase 4 merges through protected `master`.
- [ ] Exact-master CI passes before Phase 5 acceptance.
