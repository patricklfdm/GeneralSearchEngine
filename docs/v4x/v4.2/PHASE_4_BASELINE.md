# GeneralSearchEngine V4.2 Phase 4 local baseline

- **Status:** Accepted on protected `master`
- **Source:** `043b95b735dbc7dc1f319e2bd64fccba3063597a`
- **Scope:** Versioned typed transforms and exact target-index rebuild

## Implemented surface

- declared `(1,0)` to `(1,1)` codec/schema/key transformations;
- meaningful `(1,1)` to `(1,1)` identity or index evolution;
- canonical target key/document round trips and exact encoded-key collision checks;
- complete target descriptor, projection, request-limit, capacity and plan binding;
- prepublication target-index construction and authoritative apply-time rebuild;
- apply-time stale-plan and non-deterministic-projection rejection;
- independent changed-identity and same-format migration models; and
- separate-JVM typed catalog crashes at both sides of target publication.

## Focused command

```bash
scripts/verify-v42-phase4-transform-migration.sh
```

The command runs the typed production/API/oracle tests, both catalog crash barriers,
evidence validation, the complete Phase 3 production-byte and crash gate, and the
Phase 2 dual-minor regression gate.

## Local observations

The true transform fixture starts from a `V1_0` integer-key legacy codec and ends as
a `V1_1` string-key catalog codec. It retains slots `0` and `2`, sequence `5`, and
`nextDocId == 3`; reports equality-title as retained, range-score as removed, and
prefix-category as added; verifies rebuilt query behavior; and then accepts sequence
`6`, checkpoints, closes, and reopens. The complete source member digest map remains
unchanged.

The same-format fixture admits an index-only `(1,1)` migration and rejects an exact
same-identity no-op. Collision, key mismatch, thrown transform, broken index
extractor, changed bounds/configuration, tampered plan, unsupported edge, identity
mismatch, and plan/apply nondeterminism all fail in their frozen category without a
published target.

Both typed catalog crash cases use separate JVMs and `Runtime.halt(86)`:

| Barrier | Final target | Required source |
|---|---|---|
| `v42-migration-before-final-rename-v1` | absent | structurally valid and byte-identical |
| `v42-migration-after-parent-force-v1` | typed/searchable `(1,1)` | structurally valid and byte-identical |

## Acceptance matrix

The complete local acceptance matrix passed:

```bash
scripts/verify-v42-phase4-transform-migration.sh
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v42-phase4-m2 -Partifact-compat verify
scripts/verify-consumer-projects.sh
scripts/verify-jmh-smoke.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v42-phase4-m2 \
  -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
MAVEN_OPTS='-Dmaven.repo.local=/tmp/gse-v42-phase4-m2' \
  scripts/verify-reproducible-build.sh
```

The reactor executed 496 core tests and 5 processor tests with no failure or error;
one declared core test was skipped. Published-4.1 artifact compatibility, Japicmp,
all four independent V1/V2/V3/V4 consumers, the bounded JMH smoke matrix, release
profile, Javadocs, and six-JAR integrity check passed. Two clean release builds were
byte-for-byte identical with these final SHA-256 digests:

```text
c926c4495cce7ed62708b3e8729a0d3766b923589240290465850535dc282a5f  general-search-engine-4.2.0-SNAPSHOT-javadoc.jar
7c858d5ac50c8634f722805bffab6ed248835dde6aa54bc245a60250ed0c7ac8  general-search-engine-4.2.0-SNAPSHOT-sources.jar
071dee1153b16fdc062f814cde205d0d5fd7062198a46d47049b3e5c7aad2f35  general-search-engine-4.2.0-SNAPSHOT.jar
6810c955b83b889955a619b4a2e775390d8aeafafa5ddff1c7c32afdb6ffc3a5  general-search-engine-processor-4.2.0-SNAPSHOT-javadoc.jar
4e14c2b7395a34d49b8814a9cbf480b8c9ed9e1e1be8617076f36953b181d917  general-search-engine-processor-4.2.0-SNAPSHOT-sources.jar
70762a44fb71c87ab48c2d902080faaeee80407420dc971cf08f679ee95eadc5  general-search-engine-processor-4.2.0-SNAPSHOT.jar
```

Protected PR #110 and exact-master CI run `33846632898` passed. Phase 5 remains the
owner of lifecycle, interruption, cleanup, rollback, and cross-version hardening.
