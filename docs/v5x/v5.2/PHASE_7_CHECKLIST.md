# V5.2 Phase 7 release preparation plan

**Status:** Phases 7 and 8 complete. Phase 7B merged through PR #366 at
`0743490458c07ef87423b8cd4d4dcf8565dbac93`; exact-master full CI `40999633695`
attempt 2 passed all 62 jobs. Signed tag `v5.2.0` and Release `41010395652/1`
published that source. Independent Central signatures/checksums, twelve canonical
hashes and seven consumers pass; see the [release record](RELEASE_CHECKLIST.md).

## Entry and preserved evidence

- [x] [Protected cloud set](PHASE_6_CLOUD_ACCEPTANCE.md), run `40841038976/1` at
  `8b9aa60ab0cc9253046b162f28c40d47ae2acc82`, independently accepted all five rounds.
- [x] The compact registry retains both true measured sources/sequences, the
  byte-compatible quota continuation and the single experiment retention waiver.
- [x] Phase 6 registration merged through PR #364,
  `a8125ebe2e02e1f6de1edead58e865e5b38729e1`; original identities are unchanged.
- [x] Review release changes against the accepted runtime and published controls.
  A source/behavior change needs explicit evidence-impact assessment. A later
  release commit is not itself the measured cloud source.

The current source already contains `compatibility/v52-style-consumer`, its
aggregator entry and version-alignment entry. Its existing tests cover stopped-handle
policy rejection without I/O/callbacks and standalone options/token behavior.
The public runtime/fault gates and cloud measurements already test real reads.
Reuse that work; do not create an eighth duplicate consumer or rerun cloud
experiments merely to update release documentation.

## 7A — snapshot release preparation

| Work | Concrete files / acceptance |
| --- | --- |
| Accepted baseline input | Add a V5.2 release-preparation validator, following `scripts/v51/release_preparation.py`, that checks the registered protected receipt, provenance, exception and executable identity; compact integrity checks must not claim another raw replay |
| Independent consumers | Extend `compatibility/v52-style-consumer` where needed; run all seven modules in an isolated Maven repository, retaining existing V1–V5.1 behavior |
| Published API/binary compatibility | Audit packaged V5.2 against pinned published 5.1 plus existing legacy checks; run a consumer compiled against published 5.1 on candidate JARs; preserve additive default-method behavior and exact token/format fixtures |
| Packaging/Javadocs | Validate all nine main/sources/Javadoc JARs and three POMs, processor isolation, excluded test assets, manifest versions and strict structural doclint; do not modify frozen cloud JAR pins |
| Migration and release notes | Add `MIGRATION_GUIDE.md`, `RELEASE_NOTES.md` and `RELEASE_CHECKLIST.md` in this directory; describe explicit read policies, callback lifetime, minimum-token semantics, indeterminate outcomes and unsupported mixed-version/member-change operations |
| Required CI integration | Connect V5.2 checks to existing release/compatibility lanes and retain their receipts; preserve the existing tiering, full-CI inventory and older-version checks |

- [x] Complete 7A implementation and focused negative fixtures for malformed or
  substituted baseline/artifacts, missing classifiers, wrong versions and source drift.
- [x] Run fresh isolated release-profile packaging, all seven consumers, API/binary
  audit and Javadocs. Keep the full original cloud archive outside any Maven clean.
- [x] Record local vs hosted validation separately; snapshot reproducibility is
  diagnostic and cannot substitute for the final frozen 7B build.
- [x] Operator review/merge of 7A; full master CI passed without a skip.

## 7B — final 5.2.0 candidate

- [x] Align all three publishable modules, reactor/examples, seven consumers and
  artifact resolvers to `5.2.0`, preserving compatibility fixtures for older releases.
- [x] Freeze the V5.2 canonical JDK/Maven/OS image and output timestamp. Two
  independent clean workspaces must produce identical nine unsigned JARs and
  three POMs. Pin all twelve hashes and source-bound reproducibility receipts.
- [x] Add V5.2 candidate/canonical commands and release fixtures, adapting the
  V5.1 `candidate_artifacts`, `verify-v51-canonical-build.sh` and phase-7 pattern.
- [x] Update `.github/workflows/release.yml`, the CI release-artifact route and
  `scripts/verify-published-release.sh` explicitly for 5.2.0. V5.2 has its own exact-byte
  checks and both V5.1/V5.2 remote consumers in addition to the five legacy consumers.
- [x] Require final `validate-evidence --source` correlation, byte checks before
  and after signing/deployment, all seven fresh remote consumers and at least
  90-day retention for release/canonical evidence.
- [x] Obtain and record protected full candidate validation on the exact final
  source. Cloud Build and the earlier cloud-support CI skips do not satisfy this.
- [x] Review final notes/version availability and operator acceptance before a tag.

## Phase 8 boundary and rollback

Only after 7B acceptance may the operator create/verify/push signed `v5.2.0`,
approve publication and independently reconcile Central/GitHub output, signatures,
checksums, frozen bytes and fresh consumers. Do not move published tags or
overwrite Central coordinates. Publication was separately authorized and executed
by the operator; this plan alone did not grant that authorization.

- [x] Signed tag verified against the repository's pinned signing key and exact
  final source; all three Release jobs passed.
- [x] All twelve remote POM/JAR signatures, SHA-1 files and frozen SHA-256 hashes
  independently verified after publication.
- [x] Seven fresh remote consumers passed 26 tests; current stable and migration
  documentation updated for `5.2.0`.

Before publication, failed preparation can be corrected in its own branch while
leaving the original cloud baseline and published 5.1.0 intact. If candidate code
changes behavior, review which evidence must be repeated. If only publication
metadata fails, use exact-tag recovery; do not rerun paid measurements to repair
metadata. The concurrently developed V5.3 worktree is outside this release scope.
