# GeneralSearchEngine V4.3 Phase 2 local baseline

- **Status:** Local implementation accepted; protected acceptance pending
- **Branch:** `feat/v4.3-phase2-derived-format`
- **Scope:** Exact `(1,2)` canonical/backup/derived bytes and inspection

## Implemented boundary

Phase 2 adds exact `V1_2` live and backup values, the profile-bound canonical format,
the 2 GiB default derived allowance, canonical-only backup/restore, exact derived
catalog/component parsers, immutable report types, and codec-free inspection.
Production open remains deliberately rebuild-only and returns no reopen report.

Canonical verification ignores recognized non-authoritative derived content while
still counting its regular bytes toward retained storage. Derived inspection rejects
aliases, non-regular members, allowance overflow, stale/incompatible catalog binding,
truncation, corruption, missing components and per-component corruption separately.

## Frozen identities

```text
profileDigest=596a1cdd7cf38f97f7bc740ff7a6e340fcca9c86b62ad261886db4c687b4595a
catalogIdentity=gse-derived-catalog-v1-5ffe7bbd7255fd5df581bae9c352f4c59c55214b5348bbd13c410063b6b266a6
backupIdentity=gse-backup-v3-37ce729783b1bdb6a49203c7543f48d2f3e97f7771f45b5a8eaae54e34779783
```

| Fixture member | Bytes | SHA-256 |
|---|---:|---|
| metadata | 443 | `967e008b…f39b` |
| checkpoint | 159 | `ef029738…3a3e` |
| checkpoint manifest | 176 | `d2d4e8b0…5e40` |
| WAL generation | 80 | `659777de…d5ba` |
| equality component | 273 | `ca31ea9f…0bf4` |
| range component | 270 | `8251e435…3b5a` |
| prefix component | 270 | `23f3b120…7f78` |
| text component | 298 | `6b190bb5…4506` |
| derived catalog | 943 | `d9f49e52…c368` |
| backup manifest | 363 | `ed05c5f3…d313` |

The inventory file carries every complete digest. The independent encoder reproduces
all frozen bytes and independently validates four components plus the exact three-
member backup.

## Executable acceptance

```bash
scripts/verify-v43-phase2-derived-format.sh

./mvnw -q \
  -Dtest=V43DerivedFormatPhase2Test,V43PublishedV42FormatCompatibilityTest \
  test

python3.11 -m unittest scripts.v43.test_derived_format_v12
python3.11 -m scripts.v43.derived_format_v12 inspect \
  src/test/resources/compatibility/v43-derived-v12
```

The focused gate, full core tests, independent Python tests and package build pass
locally. The fixture test proves inspection is byte-preserving, canonical verification
remains valid after derived damage, backup excludes derived state, restored targets
are cold, and production reopen still rebuilds rather than loading a valid image.

The complete local acceptance matrix also passed:

- the clean reactor ran 517 core tests and 5 processor tests with no failures or
  errors;
- the checksum-pinned published-artifact profile ran the isolated `4.2.0`
  fail-closed probe and all published API comparisons;
- all v1-, v2-, v3- and v4-style independent consumers compiled;
- the release profile produced all six main/processor binary, source and Javadoc
  JARs and passed integrity validation;
- two clean release builds produced identical SHA-256 values; and
- the bounded JMH and historical operational smoke matrix passed.

CI runs the Phase 2 shell gate after reactor tests and repeats the Python parser in
the no-GCP lane. No paid workflow, IAM change, cloud execution or baseline mutation
is part of this phase.
