# GeneralSearchEngine V4.2 Phase 7 release-candidate checklist

**Status:** complete — protected candidate accepted and handed to Phase 8

## Accepted entry boundary

- [x] Phase 6 implementation and corrections merged through protected PRs #112–#114.
- [x] Canonical review merged through protected PR #115 as
  `b957965c80458f6df2325ac736ee0d6ed4602350`; exact-master CI `33929774635` passed.
- [x] `v4.2.0-migration-cloud` was registered through protected PR #116 as
  `94d320f4213e229e206f6ae5202df66a1d9a5ae1`.
- [x] Exact-master CI run `33930894450`, attempt 2, passed on that registration.
- [x] Phase 7 started from that exact commit on `release/v4.2.0`.
- [x] Ignored local cloud evidence remains excluded from candidate artifacts.

## Final-coordinate and documentation freeze

- [x] Core, processor, reactor, travel example and V1–V4 consumer coordinates convert
  atomically to final `4.2.0`.
- [x] `project.build.outputTimestamp` is fixed to `2026-09-09T00:00:00Z` in both
  publishable artifacts.
- [x] Changelog and README describe a candidate without claiming Phase 8 completion.
- [x] API compatibility and 4.1-to-4.2 migration guidance are complete.
- [x] CI and release workflows invoke the exact V4.2 final-candidate gate.
- [x] Phase 8 remains the only authority for signing, tag push, publication,
  deployment approval and post-publication claims.

## Independent consumer and fixtures

- [x] The V4 consumer selects format `(1,1)` and executes public-only migration from
  a preserved `(1,0)` source.
- [x] It verifies plan/result bindings, distinct history, source byte preservation,
  target continued mutation, checkpoint and reopen.
- [x] The V4.2 API declaration fixture and every physical/logical fixture member have
  frozen SHA-256 values.
- [x] Independent parsers validate exact `(1,1)` live/backup bytes and migration
  projection.
- [x] The append-only migration registry identity is checked exactly.

## Candidate validation gates

- [x] `scripts/verify-v42-phase7-release.sh` passes with all four consumers in an
  isolated Maven repository.
- [x] Full reactor, travel example and all inherited V4/V4.1/V4.2 local gates pass.
- [x] Source/reflection API fixtures and fresh-isolated Japicmp through `4.1.0` pass.
- [x] Strict release Javadocs and exactly six publishable JARs pass inspection.
- [x] Two clean release builds produce byte-identical six-JAR output; hashes are
  recorded in the release checklist.
- [x] `git diff --check`, source inventory and ignored evidence boundaries are clean.

## Protected acceptance and Phase 8 handoff

- [x] Candidate PR #117 merged to protected `master` without a direct push as
  `5742b01def2fa5b1dd84b57f00ba6026c661f634`.
- [x] Exact-master CI run `34388796604` passed for that commit.
- [x] Local and remote `v4.2.0` tags were absent before signing.
- [x] Central immutability preflight returned HTTP `404` for both artifacts.
- [x] Phase 8 began only from the exact accepted protected-master commit.

Any production Java or storage-semantic change after canonical source
`d0afbb593ab5df468c0b7c4b2622ebc6daa69317` requires explicit classification. A
correctness change invalidates affected evidence; release infrastructure and docs
cannot silently reinterpret the registered baseline.
