# GeneralSearchEngine V4.1 Phase 5 local baseline

## Entry

Phase 5 starts from accepted Phase 4 protected-master commit
`47a4a3d7e417b9034b6bc704c7b9a6213feefd32` (PR #97), whose exact-master CI run
`33726843823` passed.

## Focused evidence

The public API gate freezes both static descriptors, all four cleanup record component
orders and cleanup-scope order. Unit evidence covers deterministic read-only plans,
successful and empty idempotent apply, stale-plan zero deletion, closed-store
ownership, exact backup/restore marker binding, operation-in-progress refusal,
unknown-member refusal, abandoned staging cleanup and complete-final-target
preservation.

The separate-JVM matrix exercises six production cleanup authority transitions over
both live-store and operation-remnant scopes: 12 abrupt-halt cases in total. A Python
inspector runs before any recovery/open, checks the immutable protected-member
manifest and rejects every remnant outside the exact safe set. Each replacement JVM
replans and applies the smaller safe set when one remains, verifies authority,
continues mutation, checkpoints and reopens.

## Commands

```bash
scripts/verify-v41-phase5-cleanup.sh
./mvnw test
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase5-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase5-m2 -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

All local gates pass. The reactor executed 471 core tests and 5 processor tests with
zero failures, errors or skips. Published API comparison passed against every
configured baseline from `1.0.0` through `4.0.0`; independent v1-, v2-, v3- and
v4-style consumers compiled. The release build produced and validated all six main,
sources and javadoc JARs.

Two clean release-package builds were byte-for-byte identical. The resulting SHA-256
digests were:

```text
48e303e013b43c39a6aa73b265b5ca1328b80c28cc4462a3b0ddb8c326cba4b1  general-search-engine-4.1.0-SNAPSHOT-javadoc.jar
d40c44c548712f7770752f00d75ea4e910cd055a1bb9d16ed10d6107e744e9b2  general-search-engine-4.1.0-SNAPSHOT-sources.jar
804877c78f9b6fa1ca72ad5014d09c68c92c21f1bc1f0587450b567df66a470f  general-search-engine-4.1.0-SNAPSHOT.jar
a23f53c1291779a83028cbba53babdcd385b9cd696987dc444e7f33511ed7dfa  general-search-engine-processor-4.1.0-SNAPSHOT-javadoc.jar
ebe12fae31fbe20a73aa1ab69368f7fed15f8a26c7da60e13d081caede64dcb3  general-search-engine-processor-4.1.0-SNAPSHOT-sources.jar
2b353c06890b6f6d29ee3ca0e288cb16de2a9aa916a684cf0f3f5693021249da  general-search-engine-processor-4.1.0-SNAPSHOT.jar
```

Protected PR #98 merged as `5f1c750bd360716506a732e301ed52493650837e`.
Exact-master CI run `33730252965` passed. Phase 5 is accepted; no paid cloud execution
was performed in this phase.
