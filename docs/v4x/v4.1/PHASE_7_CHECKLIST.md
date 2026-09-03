# GeneralSearchEngine V4.1 Phase 7 release-candidate checklist

**Status:** local final-candidate validation complete; protected PR acceptance pending

## Accepted entry boundary

- [x] Phase 6 implementation and corrections merged through protected PRs #99–#102.
- [x] `v4.1.0-operational-cloud` resolves to source
  `88205cf28f1aa80f8ea7ccf1bada723b3205215c`, three members and set digest
  `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27`.
- [x] The reviewed Phase 6 evidence and registration merged through protected PR #103
  as `049b232b12e9819a243c9d7925a39bc7ec0fec53`.
- [x] Exact-master CI run `33809198755` passed on that merge.
- [x] Phase 7 starts from that exact commit on `release/v4.1.0`.
- [x] The ignored local `benchmark-results/v41-operational/` mirror remains excluded
  from candidate source and release artifacts.

## Final-coordinate and documentation freeze

- [x] Core, processor, reactor, travel example and V1–V4 consumer coordinates convert
  atomically to final `4.1.0`.
- [x] `project.build.outputTimestamp` is fixed to `2026-09-03T00:00:00Z` in both
  publishable artifacts.
- [x] Changelog and README describe a candidate without claiming tag, Central,
  deployment or GitHub Release completion.
- [x] API compatibility documents additive operations and unchanged live format.
- [x] Migration guidance covers backup, verification, new-history restore, cleanup,
  rollout and V4.0 rollback boundaries.
- [x] Phase 8 remains the only authority for signing, pushing a tag, publishing,
  deployment approval and post-publication claims.

## Independent consumer and fixture compatibility

- [x] The independent V4 consumer depends only on public core API and JUnit support.
- [x] It executes backup, structural and semantic verification, new-history restore,
  continued mutation, checkpoint, reopen and safe-cleanup apply.
- [x] Existing V4.0 live-format fixture and negative compatibility cases remain.
- [x] The V4.1 declaration fixture has a frozen SHA-256 and compiles.
- [x] All immutable backup-format members have frozen SHA-256 values and validate
  through the independent parser.
- [x] The append-only operational registry identity is checked by a dedicated release
  fixture.

## Candidate validation gates

- [x] `scripts/verify-v41-phase7-release.sh` passes with all four consumers in a fresh
  isolated Maven repository.
- [x] Full reactor and travel example pass at final coordinates (476 tests, zero
  failures or errors).
- [x] Source/reflection API fixtures and fresh-isolated Japicmp through published
  `4.0.0` pass.
- [x] Strict release Javadocs and exactly six publishable JARs pass service-boundary
  inspection.
- [x] Two clean final builds produce byte-identical six-JAR output and hashes are
  recorded in the release checklist.
- [x] Bounded JMH plus all V4/V4.1 local crash, lifecycle, cleanup and cloud-control
  gates pass without another paid cloud run.
- [x] `git diff --check`, source inventory and ignored evidence boundary are clean.

## Protected acceptance and Phase 8 handoff

- [ ] Candidate PR merges to protected `master` without a direct push.
- [ ] Exact-master CI passes and commit/run are recorded.
- [ ] Local and remote `v4.1.0` tags are absent before signing.
- [ ] Central immutability preflight returns HTTP `404` for both artifacts.
- [ ] Phase 8 begins only from the exact accepted protected-master commit.

Any production Java, live/backup format or operational-semantic change after the
canonical source must be classified explicitly. A correctness change invalidates
affected evidence and may require a new canonical run. Test, documentation and
release-infrastructure changes cannot silently reinterpret the registered baseline.
