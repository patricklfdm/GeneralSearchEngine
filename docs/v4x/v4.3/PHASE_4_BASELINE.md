# GeneralSearchEngine V4.3 Phase 4 local baseline

- **Branch:** `feat/v4.3-phase4-text-images`
- **Base:** `98527a2475d69673513addb15e5693bc197ddf2c`
- **Version:** `4.3.0-SNAPSHOT`
- **Cloud/IAM/registry changes:** none

## Implemented evidence

The focused Java matrix proves complete four-kind publication and warm reopen,
text-local and structured-local selective fallback, catalog-wide fallback, refresh,
WAL mutation and dynamic text-index lifecycle replay, cold older-format migration,
capacity failure isolation, and exact text retrieval/ranking equivalence.

The independent inspector accepts production non-empty text bytes. The separate-JVM
matrix covers text component rename/force and mixed catalog publication using internal
halt and external kill. Every replacement recovers the structured/text oracle,
preserves canonical digests and leaves a valid derived generation.

## Executable gate

```bash
scripts/verify-v43-phase4-text-images.sh
```

The gate runs focused Phase 2–4 Java tests, the independent Python format suite, four
production child-process interruption cases, replacement-JVM verification and
checksummed evidence validation. CI invokes it with `--skip-build` after the complete
reactor and syntax-checks its entry point in the no-GCP lane.

## Final local acceptance

- complete reactor: core `532`, failures/errors `0/0`, conditional skips `4`;
  processor `5/5`;
- exact published-`4.2.0` cold-reopen control: `PASS`;
- independent V1/V2/V3/V4 consumer compilation: `PASS`;
- release-profile build and six-JAR integrity: `PASS`;
- two isolated release builds produced identical artifacts;
- bounded JMH plus inherited V3.4 and V4.0 operational/crash gates: `PASS`; and
- the final Phase 4 Python and four-case production crash matrix: `PASS`.

No workflow dispatch, IAM policy, VM/disk, GCS object or baseline registry was
changed by Phase 4.

## Protected acceptance

Phase 4 merged through protected PR #123 as
`2f229303168c93e81a571b1d5c931bff015eb1b5`; exact-master CI run `34460924869`
passed.
