# V5.2 release checklist

Current scope: Phase 7B final candidate preparation. Stable remains 5.1.0. No tag,
publication, paid cloud execution or final candidate qualification is implied.

## Accepted input

- [x] Phase 6 closeout merged in [PR #364](https://github.com/patricklfdm/GeneralSearchEngine/pull/364),
  `a8125ebe2e02e1f6de1edead58e865e5b38729e1`.
- [x] Original protected [cloud baseline](PHASE_6_CLOUD_ACCEPTANCE.md) and
  verifier `40841038976/1` retained with true measured source/sequence identities.
- [x] Original failed experiment/ledger records remain FAIL; the specific
  retention exception is recorded without creating a general waiver.

## Phase 7A implementation and validation

- [x] [Preparation policy](release-preparation.json) pins original receipt,
  provenance, registry, waiver, published controls and token fixtures.
- [x] Guard all 328 runtime/resource/build-input files, including additions and
  deletions, against the accepted snapshot; no historical checkout or fetch is
  needed by the offline gate. A change requires explicit evidence-impact review.
- [x] Inventory nine JARs and three POMs, embedded POM identity, main manifests,
  API presence, test-asset exclusion and annotation-processor service isolation.
- [x] Compare published 5.1 declarations in isolated class loaders; compile old
  consumer/implementation against 5.1 only, then execute with candidate JARs and
  check all inherited default read policies. Existing V5.0 API checks stay active.
- [x] Check all three original token vectors and corruptions through packaged
  public classes; extend the existing seventh independent consumer.
- [x] Add [migration guidance](MIGRATION_GUIDE.md), [draft notes](RELEASE_NOTES.md)
  and required release-lane evidence retention for 90 days.
- [x] Complete isolated local release-profile build, all seven consumers,
  packaged checks and focused Python/CI/documentation validation (2026-10-29).
- [x] Phase 7A merged through [PR #365](https://github.com/patricklfdm/GeneralSearchEngine/pull/365)
  at `abc8bc1b1f9f0a8f42ecc1a9d5344cb17a9187cc`; [master full CI 40968660073](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40968660073)
  passed all 62 jobs. This is the preceding snapshot source, not final-candidate CI.

Local validation: the fresh isolated reactor passed 1003 tests (four existing
skips), release packaging and structural doclint. Seven independently installed
consumers passed 26 tests. The published-5.1 audit preserved 2394 declarations
and found 76 additions; the existing published-5.0 check also passed. Old
implementation bytecode inherited the unsupported read default for all policies;
three golden token vectors and 336 byte mutations passed. Eleven new Python
regressions, the existing quota/retention regressions, CI inventory/tiering and
documentation checks passed. Consumer installation left all twelve release hashes
unchanged. Java was Ubuntu 21.0.12.1, Maven 3.9.11 and Python 3.11.15: this is local
snapshot validation, not canonical byte reproduction or protected final-source CI.

Receipts/logs are retained in `target/v52-release-preparation-jpms/`,
`target/v51-release-preparation/` and the sibling ignored
`target/v52-phase7a-validation/` directory of the development repository. Initial
Maven sandbox-cache rejection, Python-3.10-only failures in existing 3.11 tests,
and the corrected module-prefixed Javadoc probe remain recorded. No production
change or measurement retry was needed. At Phase 7A, snapshot reproducibility
was the existing CI lane's diagnostic; final canonical reproduction was still open.

Reproduce packaging preparation at the current version with Java 21, the Maven wrapper and Python 3.11+ from an
isolated checkout (outputs must be new paths):

```bash
./mvnw -B -ntp -f reactor/pom.xml -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh 5.2.0
scripts/verify-consumer-projects.sh
python3 -m unittest scripts.v52.test_release_preparation
python3 -m scripts.v52.release_preparation --output target/v52-release-preparation
```

Keep original cloud evidence outside any build directory that will be cleaned.
The preparation receipt records toolchain, current checkout, twelve file hashes,
published controls and accepted runtime-source equivalence. `candidateFrozen`,
`publication`, `paidCloud` and `rawCloudReplayed` remain false. This compatibility
check is separate from the final manifest and never asserts cloud/candidate JAR-byte equality.

## Phase 7B candidate and publication

- [x] Final `5.2.0` version alignment, canonical toolchain/output timestamp and
  two clean independent builds with identical nine JAR/three POM hashes.
- [x] Explicit V5.2 release workflow, `validate-evidence --source`, byte checks
  around signing/deployment, seven remote consumers and 90-day release evidence.
- [ ] Protected full CI on the exact final source. Cloud-support skips or Cloud
  Build do not replace this acceptance.
- [ ] Operator-authorized signed tag/publication; independent Central/GitHub
  signatures/checksums/bytes and all fresh consumers; final availability record.

The [Phase 7 plan](PHASE_7_CHECKLIST.md) defines the full boundary and rollback.
Before release, correct/revert preparation tooling on its own branch. Do not
change the accepted evidence, rewrite cloud failures, move published tags, or
overwrite Central coordinates. An implementation change needs impact assessment
before reusing the measured baseline.

## Final candidate source and toolchain boundary

The [original preparation policy](release-preparation.json), its 328-file digest
and all registered cloud files remain unchanged. The source comparison permits
only the exact project version line `5.2.0-SNAPSHOT` → `5.2.0` in the core,
processor, replication and reactor POMs. It reconstructs the original line before
comparing the original digest; dependency/plugin/output-timestamp edits, new
runtime files and deleted files still reject. The remaining eight application
and consumer POMs are independently checked for final coordinate alignment.

[release-toolchain.json](release-toolchain.json) pins the inherited Temurin
21.0.12+8 Jammy linux/amd64 image/index, Maven 3.9.11 ZIP checksum, plugin versions,
locale, timezone, file modes and `2026-09-19T00:00:00Z` output timestamp. Keeping
this timestamp avoids an unrelated build-input change; it is not the release
date. Historical V5.1 toolchain and candidate hashes are unchanged.

Local `--working-tree` canonical preparation records its base commit and archive
hash honestly. It cannot satisfy `validate-evidence --source`. After the operator
commit/merge, CI and Release must build the exact clean checkout twice and match
all twelve frozen hashes with a `git-commit` receipt for that exact SHA. CI and
Release retain V5.2 canonical and packaging receipts for 90 days. The existing
Required jobs and full-suite coverage are preserved.

```bash
scripts/verify-v52-phase7-release.sh --skip-consumers
scripts/verify-v52-canonical-build.sh
python3 -m scripts.v52.candidate_artifacts validate-evidence target/v52-canonical-reproducibility --source "$(git rev-parse HEAD)"
```

Before any signed tag, review final-source full CI and the candidate date/notes.
Signing/deployment must match the frozen unsigned bytes both before and after;
remote verification checks all twelve POM/JAR signatures, checksums and frozen
hashes, then executes seven fresh consumers. No publication is implied by local
build success. If a candidate hash differs, inspect the artifact and toolchain;
do not update the frozen manifest just to turn a failed gate green.

Local canonical receipt: `target/v52-canonical-reproducibility/evidence.json`
(`working-tree`, base `abc8bc1b1f9f0a8f42ecc1a9d5344cb17a9187cc`).
The [twelve candidate hashes](candidate-artifacts.sha256) were generated from
that two-workspace result. The local Docker Desktop credential helper was
unavailable under WSL; a task-local empty `DOCKER_CONFIG` allowed anonymous
access to the public pinned image without changing system credentials. Earlier
bootstrap diagnostics are retained in `target/v52-release-candidate-review/`.

Final-version local qualification uses the pinned Temurin 21.0.12+8 JDK:
1003 reactor tests (four existing skips, no failures/errors), seven consumers
with 26 tests in a new isolated Maven repository, packaged API checks against
published 5.0 and 5.1, inherited-default behavior and golden token probes pass.
All twelve local release hashes match the canonical manifest before and after
consumer installation. No runtime Java or frozen cloud source was changed.

The initial 1516-test V5.2 Python sweep exposed a historical cloud-fixture
version mismatch after finalizing the POMs. Its synthetic snapshot checkout now
uses the matching snapshot artifact layout; real cloud admission still rejects
final-version inputs. Nested fixtures register cleanup before setup, with an
injected-setup-failure regression covering all six nesting paths. Original
failures and the targeted recheck receipts remain in
`target/v52-release-candidate-review/`; these local checks do not replace full CI
on the final committed source.
