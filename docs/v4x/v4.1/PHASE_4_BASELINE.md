# GeneralSearchEngine V4.1 Phase 4 local baseline

## Entry

Phase 4 starts from accepted Phase 3 protected-master commit
`f5516dfc05ff0e878a72f60d56792c30d480d2c3` (PR #96), whose exact-master CI run
`33723841861` passed.

## Focused evidence

The Java matrix freezes the two generic builder descriptors, three immutable value
types and semantic-status order. Production cases cover canonical typed decode,
identity mismatch before decode, codec failure without payload diagnostics, canonical
slot holes, startup/dynamic index reconstruction, exact persisted-config matching,
existing and overlapping target rejection, new-history publication, V4-format reopen,
continued mutation, checkpoint and second reopen. Injected target I/O failure proves
pre-publication rollback and backup immutability.

The separate-JVM harness exercises ten restore authority barriers from forced marker
through return. A Python byte-level inspector runs before any reopen, validates the
kind-2 marker binding, requires target absence before final rename, and independently
classifies a present post-rename V4 target. Every case then either opens the published
target or performs an independent retry into another absent target, continues at
`B + 1`, checkpoints, closes and reopens again.

## Commands

```bash
scripts/verify-v41-phase4-restore.sh
./mvnw -Dtest=V41PublicApiFoundationTest,V41SemanticRestorePublicApiTest,V41SemanticRestorePhase4Test test
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase4-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase4-m2 -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

All local gates pass. The reactor executed 463 core tests and 5 processor tests with
zero failures, errors or skips. Published API comparison passed against every
configured baseline from `1.0.0` through `4.0.0`; independent v1-, v2-, v3- and
v4-style consumers compiled. The release build produced and validated all six main,
sources and javadoc JARs.

Two clean release-package builds were byte-for-byte identical. The resulting SHA-256
digests were:

```text
72e9987de3ce88cb3068c19dc35f8182aeb5a2509ceae16779240ed806d28dba  general-search-engine-4.1.0-SNAPSHOT-javadoc.jar
4c6e816a39bc13610f7dae8d6982a88edb8e46a6c78955d87fb14f9f787a1ea5  general-search-engine-4.1.0-SNAPSHOT-sources.jar
bd6240f53754e0b61e3725c866c886115d745f9625aa4b2cf9d3e87cdc80c903  general-search-engine-4.1.0-SNAPSHOT.jar
a23f53c1291779a83028cbba53babdcd385b9cd696987dc444e7f33511ed7dfa  general-search-engine-processor-4.1.0-SNAPSHOT-javadoc.jar
ebe12fae31fbe20a73aa1ab69368f7fed15f8a26c7da60e13d081caede64dcb3  general-search-engine-processor-4.1.0-SNAPSHOT-sources.jar
2b353c06890b6f6d29ee3ca0e288cb16de2a9aa916a684cf0f3f5693021249da  general-search-engine-processor-4.1.0-SNAPSHOT.jar
```

Protected PR and exact-master CI remain pending. No paid cloud execution belongs to
Phase 4.
