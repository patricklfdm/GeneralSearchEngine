# GeneralSearchEngine V4.3 Phase 5 local baseline

- **Branch:** `feat/v4.3-phase5-lifecycle-hardening`
- **Base:** `2f229303168c93e81a571b1d5c931bff015eb1b5`
- **Version:** `4.3.0-SNAPSHOT`
- **Cloud/IAM/registry changes:** none

## Implemented evidence

Phase 5 extends the inherited V4.1 offline cleanup transaction to exact `(1,2)`
derived state. The authority digest binds the complete live inventory plus the valid
catalog identity and exact derived delete set. Superseded final components are
selected only when omitted by that catalog; staging remnants remain independently
recognizable. Replanning, per-member fingerprints, alias checks, directory force and
post-apply canonical verification prevent stale or broadened deletion authority.

The focused matrix also proves canonical-only `(1,2)` backup, cold restore, full
refresh, second warm reopen, post-restore mutation, repeated concurrent mutation
bursts and checkpoint/reopen continuity. It includes the regression for carrying
`maxDerivedStateBytes` into typed backup verification and restore.

## Crash evidence

The production cleanup path exposes stable before/during/after barriers. Each child
process creates two complete four-kind generations and an abandoned catalog staging
member, then dies through `Runtime.halt` or parent `SIGKILL`. A codec-free inspector
runs before production reopen. The replacement JVM replans the surviving inventory,
completes cleanup, proves a complete warm retrieval oracle, continues mutation,
checkpoints and proves a second complete warm reopen. Evidence uses the frozen
`gse-v43-fast-reopen-evidence-v1` bundle and remains local-only.

## Acceptance command

```bash
scripts/verify-v43-phase5-lifecycle.sh
```

## Local acceptance result

The Phase 5 gate passed its focused Java/Python suite and all three production-owned
cleanup crash boundaries. The complete reactor then passed with `537` core tests
(`4` skipped) and `5` processor tests, with zero failures or errors. Published
`4.2.0` cold reopen at `20,000` documents and the independent V1/V2/V3/V4 consumers
all passed.

Release-profile packaging produced and verified all six expected JARs; the
reproducible-build comparison reported identical outputs. Bounded JMH and the
inherited V4.0 operational smoke gates passed. The V4.1 cleanup harness passed all
`12` crash cases, and the V4.2 migration/lifecycle matrix also passed in full.

No paid resource, IAM mutation, cloud workflow or baseline-registry action was
performed. Protected PR #124 merged the phase as
`e241e1499861e0b44583a948d410ce0ac9c3c286`; exact-master CI run `34529966882`
passed. This is the accepted Phase 6 base.
