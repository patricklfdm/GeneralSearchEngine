# GeneralSearchEngine v2.0.0 release checklist

## Current state

P7 validation and final version conversion of the `2.0.0` release candidate are
complete. Do not publish, tag, or commit without separate owner approval.
The representative JMH regression matrix is recorded in
[`phases/p7/PERFORMANCE_BASELINE.md`](phases/p7/PERFORMANCE_BASELINE.md).

Release artifacts are:

- `io.github.patricklfdm:general-search-engine:2.0.0`;
- `io.github.patricklfdm:general-search-engine-processor:2.0.0`.

Both use Java 21 bytecode, Apache License 2.0, the
`patricklfdm/GeneralSearchEngine` repository metadata, and manual Central Portal
publication through server ID `central`.
`general-search-engine-reactor` is a local-only aggregator with deployment explicitly
disabled; it is not a third Central artifact.

## Candidate freeze

- [x] P1–P6 are complete and their semantics/performance evidence is frozen.
- [x] No P7 feature or performance optimization was added.
- [x] v1 source/reflection fixture and artifact-level binary/source comparison pass.
- [x] Independent v1-style and processor-enabled v2-style consumers compile.
- [x] Core/processor unit, randomized, lifecycle, concurrency, and mixed oracle tests pass.
- [x] Strict Javadocs, signatures, service isolation, and reproducible artifacts pass.
- [x] The 300-second target-machine v2 concurrency soak passes.
- [x] The 141-row P7 representative JMH regression matrix is reviewed and accepted.
- [x] The project owner approves release-version conversion.

## Complete validation gate

```bash
mvn clean test
mvn clean -Papi-compat test
mvn clean -Partifact-compat verify
mvn -f reactor/pom.xml clean test
bash scripts/verify-consumer-projects.sh
mvn -f reactor/pom.xml clean -Prelease verify
bash scripts/verify-reproducible-build.sh
```

Run the target-machine commands in
[`phases/p7/RELEASE_VALIDATION.md`](phases/p7/RELEASE_VALIDATION.md) separately because they
are intentionally excluded from normal Maven test execution.

## Final version conversion

After every gate is accepted:

- [x] change core, processor, and reactor versions from `2.0.0-SNAPSHOT` to `2.0.0`;
- [x] set both `project.build.outputTimestamp` values to the frozen release source time
  `2026-08-25T08:39:19Z`;
- [x] run the complete validation gate again with consumer fixtures using
  `-Dgse.version=2.0.0`;
- [x] change `CHANGELOG.md` from Unreleased to the release date;
- [x] inspect the release diff and ensure no benchmark result under `target` is included;
- [x] inspect both POMs, all six JARs, eight `.asc` files, manifests, Maven metadata,
  package roots, processor service entry, license, SCM, issue URL, and checksums;
- [x] confirm the core JAR contains no annotation-processor service entry and the
  processor JAR contains exactly the expected entry.

Final candidate validation on 2026-08-25: core 118 tests, processor 4 tests, frozen-v1
fixture 3 tests, published-v1 artifact comparison, both independent consumers, strict
Javadocs, all signatures, service isolation, and six-JAR reproducibility all PASS.

The release profile must be invoked through the reactor so both Central artifacts are
validated together:

```bash
mvn -f reactor/pom.xml clean -Prelease verify
```

## Deployment — only after separate approval

From the exact approved release commit/tag, upload and wait for Central validation:

```bash
mvn -f reactor/pom.xml clean -Prelease deploy
```

`autoPublish=false`; a successful deploy must remain unpublished until both artifact
coordinates, signatures, sources, Javadocs, and Portal validation are reviewed. Publish
or drop the deployment manually. Do not commit, tag, push, deploy, or publish as an
implicit part of this checklist.
