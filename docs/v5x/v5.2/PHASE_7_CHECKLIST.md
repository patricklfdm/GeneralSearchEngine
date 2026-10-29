# V5.2 Phase 7 release preparation plan

**Status:** 7A snapshot preparation implemented; validation and operator acceptance
are tracked in the [release checklist](RELEASE_CHECKLIST.md). Phase 6 closeout
merged through PR #364 at `a8125ebe`. Keep `5.2.0-SNAPSHOT` until 7B. Final
candidate freeze and publication remain open; stable remains published 5.1.0.

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
- [ ] Operator review/merge of 7A; preserve any CI exception as an explicit record.

## 7B — final 5.2.0 candidate

- [ ] Align all three publishable modules, reactor/examples, seven consumers and
  artifact resolvers to `5.2.0`, preserving compatibility fixtures for older releases.
- [ ] Freeze the V5.2 canonical JDK/Maven/OS image and output timestamp. Two
  independent clean workspaces must produce identical nine unsigned JARs and
  three POMs. Pin all twelve hashes and source-bound reproducibility receipts.
- [ ] Add V5.2 candidate/canonical commands and release fixtures, adapting the
  V5.1 `candidate_artifacts`, `verify-v51-canonical-build.sh` and phase-7 pattern.
- [ ] Update `.github/workflows/release.yml`, the CI release-artifact route and
  `scripts/verify-published-release.sh` explicitly for 5.2.0. The current routes
  have 5.1.0-specific byte checks and only run the newer remote consumer for 5.1.*;
  the generic fallback is insufficient for a V5.2 release.
- [ ] Require final `validate-evidence --source` correlation, byte checks before
  and after signing/deployment, all seven fresh remote consumers and at least
  90-day retention for release/canonical evidence.
- [ ] Obtain and record protected full candidate validation on the exact final
  source. Cloud Build and the earlier cloud-support CI skips do not satisfy this.
- [ ] Review final notes/version availability and operator acceptance before a tag.

## Phase 8 boundary and rollback

Only after 7B acceptance may the operator create/verify/push signed `v5.2.0`,
approve publication and independently reconcile Central/GitHub output, signatures,
checksums, frozen bytes and fresh consumers. Do not move published tags or
overwrite Central coordinates. Publication is not authorized by this plan.

Before publication, failed preparation can be corrected in its own branch while
leaving the original cloud baseline and published 5.1.0 intact. If candidate code
changes behavior, review which evidence must be repeated. If only publication
metadata fails, use exact-tag recovery; do not rerun paid measurements to repair
metadata. The concurrently developed V5.3 worktree is outside this release scope.
