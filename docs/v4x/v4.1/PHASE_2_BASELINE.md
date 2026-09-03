# GeneralSearchEngine V4.1 Phase 2 local baseline

## Entry

Phase 2 begins from protected Phase 1 merge
`e183face9cd2649f266cc54167f5419b86144e4e` (PR #94). Exact-master CI run
`33717370973` passed on that commit.

## Implemented surface

The core artifact now exposes codec-free `verifyStore` and `verifyBackup` plus the
frozen immutable status, finding, report and operational-exception types. Later V4.1
backup, semantic verification, restore and cleanup types remain absent.

The production structural parser is independent from `DurableRecovery`. Live stores
require the normal exclusive V4 lock; immutable bundles allow concurrent readers.
Both paths reject path indirection and perform stable-read checks. Metadata,
checkpoints, manifests and WAL frames are parsed under persisted bounds with CRC32C;
backup payloads additionally use exact SHA-256 and canonical content identity.

## Local matrix

- exact public method, record-component, enum-order and reason-order descriptors;
- record normalization, immutable canonical findings and invalid-value rejection;
- running-store `STORAGE_IN_USE` refusal;
- closed WAL-only and checkpoint-plus-WAL `VALID` states;
- incomplete final WAL tail as `VALID_WITH_SAFE_REMNANTS` without truncation;
- committed WAL corruption and unknown-member `CORRUPT` findings;
- corrupt present WAL retained alongside missing-metadata evidence;
- recognized staging remnant classification without deletion;
- absent lock as `INCOMPLETE` without lock creation;
- exact V4.0 `wal-only`, `checkpoint-only`, `checkpoint-wal`, `incomplete-tail` and
  `corruption` byte fixtures;
- exact V4.1 backup fixture as `VALID` without a codec;
- missing manifest, extra member and payload corruption classification; and
- checksum-valid unknown-major `UNSUPPORTED` versus unknown-minor `INCOMPATIBLE`.

Every no-mutation test compares complete pre/post member SHA-256 inventories or exact
file sizes. The focused Java matrix and 15 independent Python V4/V4.1 inspector tests
pass locally. The full reactor reports 444 core tests and 5 processor tests with zero
failures. Exact published artifact compatibility passes for every configured 1.x
through 4.0 baseline, and the independent v1-, v2-, v3- and v4-style consumers all
compile. Release-profile main/source/Javadoc artifacts pass integrity checks, and two
independent release builds produce identical SHA-256 values for all six published
JARs.

## Commands

```bash
scripts/verify-v41-phase2-structural.sh
./mvnw -Dtest=V41PublicApiFoundationTest,V41StructuralPublicApiTest,V41StructuralVerificationTest test
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase2-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

Protected PR #95 merged Phase 2 as
`a17ad20d3cd03128abf6c4f7fbeb0b752b523b02`; exact-master CI run `33720179867`
passed. Paid cloud work was not part of this phase.
