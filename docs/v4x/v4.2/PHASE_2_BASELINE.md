# GeneralSearchEngine V4.2 Phase 2 local baseline

- **Status:** Local acceptance complete; protected acceptance pending
- **Source:** `feat/v4.2-phase2-format-inspection` working tree
- **Scope:** Exact format bytes, dual-minor structural inspection, compatibility

## Implemented surface

- `DurableStorageFormat` with exact `V1_0` and `V1_1` constants;
- additive `DurableStorageConfig.Builder.format` with unchanged `V1_0` default;
- immutable store and backup format reports;
- synchronous codec-free inspection operations;
- exact structural readers for `1.0` and `1.1` metadata, checkpoints, manifests,
  WAL generations/frames, and backup manifests;
- immutable physical `1.1` live/backup fixtures and an independent Python parser;
- an isolated published-4.1 artifact probe; and
- early rejection of `V1_1` production open/write before filesystem mutation.

## Focused commands

```bash
scripts/verify-v42-phase2-format.sh

./mvnw -q \
  -Dtest=V42PublishedV41FormatCompatibilityTest,V42FormatInspectionPhase2Test \
  test

python3.11 -m unittest scripts.v42.test_storage_format_v11
```

The published probe is active under `-Partifact-compat`, after the pinned `4.1.0`
artifact has been copied and checksum-verified. A normal focused run without that
artifact explicitly skips only that isolated probe.

## Frozen fixture evidence

| Member | Bytes | SHA-256 |
|---|---:|---|
| `gse-metadata` | 321 | `132ab633193287f81c705e960307e43a5503418c107a208845f112313c92f853` |
| checkpoint payload | 115 | `97706b2b735904eae1fcb3e873d1d10b02254fed47111c121b8bd44cb2c68f90` |
| `gse-checkpoint-manifest` | 176 | `36bc0719f71cc2ed239b1f3ca24444c8cf4ea29afbd99028926e39f197ea3bf0` |
| WAL generation | 80 | `e5ba5b1cff7327d4b6cbb80fd9207394e204b48c4822b23bcbe19c0e72099cee` |
| `gse-backup-manifest` | 363 | `c405d2ee5b10fc40fbba6546093fa4c593222a2322859e125e13b13b1a5dc063` |

Both production and independent readers report sequence `7`, the exact profile
digest, and valid live/backup structure. Read-only inspection preserves every member
SHA-256. The corruption matrix covers checksum-invalid declarations, unsupported
major, higher minor, unknown intact profile, mixed minor, and mismatched profile
binding.

## Published artifact finding

The exact same fixtures executed in an isolated JVM against immutable published
`4.1.0` produce:

```text
publishedV41 kind=store status=CORRUPT findings=STRING_LENGTH:gse-metadata,...
publishedV41 kind=backup status=CORRUPT findings=STRING_LENGTH:gse-backup-manifest,...
```

This proves fail-closed rejection but disproves the earlier assumption that real
extended bytes reach V4.1's higher-minor `INCOMPATIBLE` branch. Phase 2 documents the
feasibility correction rather than weakening profile binding or changing the
published artifact.

## Local acceptance

The completed local gate set is:

- core and reactor tests: `484` core tests plus `5` processor tests, with no
  failures or errors;
- `-Partifact-compat verify`: pinned artifact checks, Japicmp, and the isolated
  published-`4.1.0` child-JVM probe passed;
- all independent V1, V2, V3, and V4 consumer projects passed;
- the release profile produced the core and processor main, sources, and Javadoc
  JARs, and the six-artifact integrity check passed;
- two clean release builds produced byte-identical JARs;
- the bounded JMH smoke suite passed; and
- the Phase 2 shell/Python gate and whitespace checks passed.

CI now executes the Phase 2 gate after reactor tests and independently compiles and
runs the Python exact-format fixtures in the no-GCP job.

## Remaining acceptance

Protected PR CI and exact-master evidence remain required before Phase 2 closes.
Phase 3 remains the sole owner of production `1.1` create/open/write and format-only
migration.
