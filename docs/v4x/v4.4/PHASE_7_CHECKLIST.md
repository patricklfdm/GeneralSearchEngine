# GeneralSearchEngine V4.4 Phase 7 release-candidate checklist

**Status:** complete — protected candidate accepted and handed to Phase 8

## Accepted entry boundary

- [x] Canonical review merged through protected PR #141 as `1bb85f1`; exact-master
  CI run `34888837170` passed.
- [x] `v4.4.0-final-durable-cloud` registered through protected PR #142 as
  `c9f77d2b203bab48360b55d80d67e09463984f8e`.
- [x] Exact-master CI run `34892824621` passed on that registration.
- [x] Phase 7 started from that exact commit on `release/v4.4.0`.
- [x] Downloaded cloud evidence remains excluded from candidate artifacts.

## Final coordinates and documentation

- [x] Core, processor, reactor, travel example and V1–V4 consumer coordinates convert
  atomically to final `4.4.0`.
- [x] Both publishable artifacts fix `project.build.outputTimestamp` to
  `2026-09-14T00:00:00Z`.
- [x] Changelog and README describe a final candidate while retaining published
  `4.3.0` as the current stable release.
- [x] API/storage compatibility and 4.3-to-4.4 migration guidance are complete.
- [x] CI and release workflows invoke the exact V4.4 candidate gate.
- [x] One strict validator binds the canonical receipt, unsigned release build,
  post-deploy local build and Phase 8 download directory to the same exact six-JAR
  `candidate-artifacts.sha256` inventory.
- [x] The V4.4 release path selects Temurin `21.0.12+8`, `C.UTF-8`, UTC and umask
  `0022`; the digest-pinned container remains the canonical identity authority.
- [x] Phase 8 alone owns signing, tag push, publication, deployment approval and
  post-publication claims.

## Independent compatibility and fixtures

- [x] All four independent consumers compile and test against final coordinates.
- [x] V4.4 exposes the exact frozen declaration inventory: 177 public types,
  2,939 declaration lines and no additions after the accepted Phase 1 boundary.
- [x] The ten-family logical fixture, toolchain manifest and API inventory have
  frozen SHA-256 identities.
- [x] Inherited V4.1/V4.2/V4.3 physical fixtures and independent parsers remain
  required by CI.
- [x] The append-only final-durable registry identity is checked exactly.

## Candidate validation

- [x] `scripts/verify-v44-phase7-release.sh` passes with all four consumers in an
  isolated Maven repository.
- [x] Full reactor, travel example, JMH smoke and inherited V4/V4.x gates pass.
- [x] Source/reflection fixtures and fresh-isolated Japicmp through `4.3.0` pass.
- [x] Strict Javadocs and exactly six publishable JARs pass inspection.
- [x] Two clean builds under the digest-pinned canonical toolchain are byte-identical
  and the six hashes are recorded in both `candidate-artifacts.sha256` and
  `RELEASE_CHECKLIST.md`.
- [x] `git diff --check`, inventory and ignored-evidence boundaries are clean.

## Protected acceptance and Phase 8 handoff

- [x] Candidate PR #143 passed every required check and merged through protected
  `master` as `1052a0bc0d84cb0d4245b07f3ba1ff6dae651dda`.
- [x] Exact-master CI run `34899198199` passed on that merge commit.
- [x] Local and remote `v4.4.0` tags were absent before signing.
- [x] Central immutability preflight returned HTTP `404` for both artifacts.
- [x] Phase 8 began only from the exact accepted protected-master commit.

Any production or storage-semantic change after canonical source `6301d855` requires
explicit classification and invalidates affected evidence. Phase 7 must not create a
tag, publish an artifact or rewrite the registered baseline.
