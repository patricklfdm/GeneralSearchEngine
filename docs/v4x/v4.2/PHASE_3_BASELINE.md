# GeneralSearchEngine V4.2 Phase 3 local baseline

- **Status:** Implementation candidate; protected acceptance pending
- **Source:** `feat/v4.2-phase3-format-migration` working tree
- **Scope:** Production `1.1`, exact-format backup/restore, format-only migration

## Implemented surface

- explicit fresh/open/write/checkpoint/recovery for `gse-durable (1,1)`;
- exact `gse-backup (1,1)` production write, structural/typed verification and
  same-format new-history restore;
- the frozen migration records, transform, stage and exception family;
- typed target-builder-owned plan/apply methods;
- exact `(1,0)` to `(1,1)` identity-format edge with source-member hashes,
  descriptor/projection/plan identities and exact capacity prediction;
- absent-target staging publication, independent validation, normal reopen and
  source-byte recheck;
- independent parsing of production `1.1` live/backup bytes and non-empty WAL frames;
  and
- production separate-JVM crash cases before final rename and after parent force.

## Focused command

```bash
scripts/verify-v42-phase3-format-migration.sh
```

The command runs the exact public descriptor tests, production V1.1 and migration
tests, V4.1 backup/restore regressions, independent Python fixtures and parsers,
production-byte live/backup inspection, and two abrupt-halt authority cases. It then
reruns the Phase 2 dual-minor gate.

## Local acceptance

The complete local acceptance matrix passed:

```bash
scripts/verify-v42-phase1-foundation.sh --skip-build
scripts/verify-v42-phase3-format-migration.sh
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v42-phase3-m2 -Partifact-compat verify
scripts/verify-consumer-projects.sh
scripts/verify-jmh-smoke.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v42-phase3-m2 \
  -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
MAVEN_OPTS='-Dmaven.repo.local=/tmp/gse-v42-phase3-m2' \
  scripts/verify-reproducible-build.sh
```

The reactor executed 489 core tests and 5 processor tests with no failure or error;
one declared core test was skipped. Published-artifact compatibility, Japicmp, all
four independent V1/V2/V3/V4 consumer projects, the bounded JMH smoke case, the
release profile and the six-JAR integrity check passed. Two clean release builds
were byte-for-byte identical, with these final SHA-256 digests:

```text
96dc5d0c5f582df70ee48a1cb8c458fd9b81df697804e00351ce034236a36231  general-search-engine-4.2.0-SNAPSHOT-javadoc.jar
784db0ae69094b7706e27278b211f8fa90393777650255a35eac0aa7be97f588  general-search-engine-4.2.0-SNAPSHOT-sources.jar
3251ddb77b4b28884899328eb3f7066f975123acc671f647a6ddc10b48bef8db  general-search-engine-4.2.0-SNAPSHOT.jar
6810c955b83b889955a619b4a2e775390d8aeafafa5ddff1c7c32afdb6ffc3a5  general-search-engine-processor-4.2.0-SNAPSHOT-javadoc.jar
4e14c2b7395a34d49b8814a9cbf480b8c9ed9e1e1be8617076f36953b181d917  general-search-engine-processor-4.2.0-SNAPSHOT-sources.jar
70762a44fb71c87ab48c2d902080faaeee80407420dc971cf08f679ee95eadc5  general-search-engine-processor-4.2.0-SNAPSHOT.jar
```

## Local observations

The format-only fixture preserves two live records in source slots `0` and `2`,
logical sequence `5`, and `nextDocId == 3`. Planning creates no target. Apply returns
the planned fresh target history and exact authoritative byte count; the target
reopens at sequence `5`, accepts sequence `6`, and the source member SHA-256 map is
unchanged.

The V1.1 production fixture passes the independent parser as both a live store and a
`gse-backup (1,1)` bundle. The backup identity uses the `gse-backup-v2-` prefix and
restore preserves format while changing history. The independent WAL parser also
checks a complete minor-1 frame and rejects checksum damage.

Both production crash cases exit by `Runtime.halt(86)` and are checked by a fresh JVM:

| Barrier | Final target | Required source |
|---|---|---|
| `v42-migration-before-final-rename-v1` | absent | structurally valid and byte-identical |
| `v42-migration-after-parent-force-v1` | valid `(1,1)` | structurally valid and byte-identical |

## Remaining acceptance

Protected PR CI and the exact protected-master evidence remain required before Phase
3 is accepted. Phase 4 remains the sole owner of changed codec/schema/key transforms
and target-index rebuild.
