# V5.2 release checklist

Current scope: Phase 7A snapshot preparation. Stable remains 5.1.0. No tag,
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
- [ ] Operator review/merge and protected CI observation for this change.

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
change or measurement retry was needed. Snapshot reproducibility remains the
existing CI lane's diagnostic; final canonical reproduction is still open.

Reproduce preparation with Java 21, the Maven wrapper and Python 3.11+ from an
isolated checkout (outputs must be new paths):

```bash
./mvnw -B -ntp -f reactor/pom.xml -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh 5.2.0-SNAPSHOT
scripts/verify-consumer-projects.sh
python3 -m unittest scripts.v52.test_release_preparation
python3 -m scripts.v52.release_preparation --output target/v52-release-preparation
```

Keep original cloud evidence outside any build directory that will be cleaned.
The preparation receipt records toolchain, current checkout, twelve file hashes,
published controls and accepted runtime-source equivalence. `candidateFrozen`,
`publication`, `paidCloud` and `rawCloudReplayed` remain false. This is a snapshot
check, not a final release manifest or proof of cloud/candidate JAR-byte equality.

## Phase 7B and publication — not complete

- [ ] Final `5.2.0` version alignment, canonical toolchain/output timestamp and
  two clean independent builds with identical nine JAR/three POM hashes.
- [ ] Explicit V5.2 release workflow, `validate-evidence --source`, byte checks
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
