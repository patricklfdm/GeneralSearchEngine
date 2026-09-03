# GeneralSearchEngine V4.1 Phase 6 local pre-cloud baseline

## Entry

Phase 6 starts from accepted Phase 5 protected-master commit
`5f1c750bd360716506a732e301ed52493650837e` (PR #98), whose exact-master CI run
`33730252965` passed. All active coordinates remain `4.1.0-SNAPSHOT`.

## Local evidence

The bounded smoke path uses real production backup, structural verification, typed
semantic verification and restore through the benchmark-only probe. It removes the
source store before restore, invokes the independent Python byte inspector, checks the
complete restored checksum and equality retrieval, proves the post-cut mutation is
absent, continues mutation, checkpoints, closes and successfully reopens a second
time. Its output uses the frozen checksummed evidence schema and exact cleanup.

The Phase 1 fake control plane still passes experiment, canonical and failure-drill
topologies without invoking GCP. Phase 6 adds strict plan validation, readable Job
Summary rendering, shell syntax gates, a dry-run member plan, independent-set
aggregation and append-only registration tooling.

## Commands

```bash
scripts/verify-v41-phase6-evidence.sh
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase6-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase6-m2 -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

## Outcomes

- Focused Phase 6 evidence: PASS.
- Full reactor: PASS, 471 core tests and 5 processor tests.
- Artifact compatibility: PASS.
- V1-, V2- and V3-style consumer projects: PASS.
- Release profile and six-JAR integrity: PASS.
- Reproducible release artifacts: PASS.

The two release builds produced these identical SHA-256 digests:

```text
48e303e013b43c39a6aa73b265b5ca1328b80c28cc4462a3b0ddb8c326cba4b1  general-search-engine-4.1.0-SNAPSHOT-javadoc.jar
d40c44c548712f7770752f00d75ea4e910cd055a1bb9d16ed10d6107e744e9b2  general-search-engine-4.1.0-SNAPSHOT-sources.jar
804877c78f9b6fa1ca72ad5014d09c68c92c21f1bc1f0587450b567df66a470f  general-search-engine-4.1.0-SNAPSHOT.jar
a23f53c1291779a83028cbba53babdcd385b9cd696987dc444e7f33511ed7dfa  general-search-engine-processor-4.1.0-SNAPSHOT-javadoc.jar
ebe12fae31fbe20a73aa1ab69368f7fed15f8a26c7da60e13d081caede64dcb3  general-search-engine-processor-4.1.0-SNAPSHOT-sources.jar
2b353c06890b6f6d29ee3ca0e288cb16de2a9aa916a684cf0f3f5693021249da  general-search-engine-processor-4.1.0-SNAPSHOT.jar
```

Paid experiment/canonical evidence and registry population remain pending until this
exact source is merged, protected-master CI passes, the OIDC workflow identity is
allowed and the operator explicitly authorizes the run.
