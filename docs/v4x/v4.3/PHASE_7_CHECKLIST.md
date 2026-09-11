# GeneralSearchEngine V4.3 Phase 7 release-candidate checklist

**Status:** local candidate validation complete; protected acceptance pending; Phase 8 not authorized

## Accepted entry boundary

- [x] Canonical review merged through protected PR #128 as `ae25c80`; exact-master
  CI run `34567122915` passed.
- [x] `v4.3.0-fast-reopen-cloud` was registered through protected PR #129 as
  `cc603a6c946169b48390960091b6157c54e9ca0b`.
- [x] Exact-master CI run `34568701485` passed on that registration.
- [x] Phase 7 started from that exact commit on `release/v4.3.0`.
- [x] Downloaded cloud evidence remains excluded from candidate artifacts.

## Final coordinates and documentation

- [x] Core, processor, reactor, travel example and V1–V4 consumer coordinates convert
  atomically to final `4.3.0`.
- [x] Both publishable artifacts fix `project.build.outputTimestamp` to
  `2026-09-11T00:00:00Z`.
- [x] Changelog and README describe a final candidate while retaining published
  `4.2.0` as the current stable release.
- [x] API/storage compatibility and 4.2-to-4.3 migration guidance are complete.
- [x] CI and release workflows invoke the exact V4.3 candidate gate.
- [x] Phase 8 alone owns signing, tag push, publication, deployment approval and
  post-publication claims.

## Independent consumer and fixtures

- [x] The V4 consumer selects `(1,2)` and uses all four built-in index kinds.
- [x] It migrates an untouched `(1,1)` source, proves cold fallback and refresh,
  complete warm reopen, query equivalence, continued mutation and source preservation.
- [x] The V4.3 API fixture and every logical/physical fixture member have frozen
  SHA-256 values.
- [x] Independent parsers validate exact `(1,2)` live, backup, catalog and component
  bytes.
- [x] The append-only fast-reopen registry identity is checked exactly.

## Candidate validation

- [x] `scripts/verify-v43-phase7-release.sh` passes with all four consumers in an
  isolated Maven repository.
- [x] Full reactor, travel example, JMH smoke and all inherited V4.3 gates pass.
- [x] Source/reflection fixtures and fresh-isolated Japicmp through `4.2.0` pass.
- [x] Strict Javadocs and exactly six publishable JARs pass inspection.
- [x] Two clean release builds produce byte-identical output; hashes are recorded in
  the release checklist.
- [x] `git diff --check`, inventory and ignored-evidence boundaries are clean.

## Protected acceptance and Phase 8 handoff

- [ ] Candidate PR passes required checks and merges to protected `master`.
- [ ] Exact-master CI passes for that merge commit.
- [ ] Local and remote `v4.3.0` tags are absent before signing.
- [ ] Central immutability preflight returns HTTP `404` for both artifacts.
- [ ] Phase 8 begins only from the exact accepted protected-master commit.

Any production or storage-semantic change after canonical source `1d59ba9` requires
explicit classification. A correctness change invalidates affected evidence; release
infrastructure and documentation cannot silently reinterpret the registered baseline.
