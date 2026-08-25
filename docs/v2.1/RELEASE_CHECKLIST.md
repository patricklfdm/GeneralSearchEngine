# GeneralSearchEngine v2.1.0 release checklist

## Current state

Version `2.1.0` is the frozen release candidate. Version `2.0.0` remains the current
Maven Central release until publication completes and is the immediate compatibility
baseline. Version `1.0.0` remains the original supported application-API baseline.

The intended Central artifacts are:

- `io.github.patricklfdm:general-search-engine:2.1.0`;
- `io.github.patricklfdm:general-search-engine-processor:2.1.0`.

The reactor and travel example are build-only modules and must not be deployed. The
release retains Java 21 bytecode, Apache License 2.0, the
`patricklfdm/GeneralSearchEngine` SCM metadata, signed artifacts, and manual Central
Portal publication through server ID `central`.

Known release blocker: the final release profile reaches the GPG signing phase, but
the validation environment does not contain a secret key (`gpg: no default secret
key`). Import the project owner's release key before signing or deployment; do not
disable the signature gate.

## Release scope

- [x] `@SearchField` is the schema-only annotation for ordinary class fields/getters.
- [x] Runtime annotation discovery remains the processor-free recommended path.
- [x] `SearchEngineBuilder.textIndex(fieldName, analyzer)` installs the canonical text
  configuration and startup text index.
- [x] `SearchEngine.field(...)` and `SearchEngine.textField(...)` return canonical
  schema objects through additive default methods.
- [x] Existing-schema builders extend an immutable copy only when configuration is
  added and preserve the original schema identity otherwise.
- [x] Unknown field diagnostics list canonical choices and suggest close spellings.
- [x] The processor remains optional and generated `*SearchFields` companions remain
  the compile-time type-safety path.
- [x] The reactor-compiled travel example and one-command runner represent the
  documented newcomer workflow.
- [ ] No unrelated feature or performance work is included after release freeze.

## Source and review gate

- [ ] The release diff from `v2.0.0` has been reviewed file by file.
- [x] Every public API change is documented in `CHANGELOG.md` and
  `docs/v2/API_COMPATIBILITY.md`.
- [x] No generated report, benchmark output, local repository, IDE file, credential,
  signature, or `target/` artifact is tracked.
- [ ] The working tree is clean and the release commit is present on `master`.
- [x] JDK 21 and Maven 3.9 or newer are used for validation (OpenJDK 21.0.12 and
  Maven 3.9.11).
- [ ] CI runs the same core, reactor, compatibility, and consumer gates as the local
  release validation.
- [ ] The project owner approves the frozen 2.1.0 scope.

## Compatibility gate

The core artifact must remain source- and binary-compatible with both published
baselines. The `artifact-compat` profile contains independent
`compare-published-v1-api` and `compare-published-v2-api` executions.

- [x] The frozen v1 source/reflection fixture passes.
- [x] Japicmp passes against published `1.0.0`.
- [x] Japicmp passes against published `2.0.0`.
- [x] Both report families are present under `target/japicmp` during compatibility
  verification:
  `compare-published-v1-api.*` and `compare-published-v2-api.*`.
- [x] New `SearchEngine` methods remain interface defaults so previously compiled
  third-party implementations continue to link.
- [x] Existing public classes, records, generic signatures, constructors, methods,
  exceptions, and enum constants remain compatible.
- [x] Processor generation tests cover `@SearchField`, nested names, visibility,
  collisions, and runtime/generated schema equivalence.
- [x] Independent v1-style and current v2.1-style consumers compile and pass.

Run the compatibility comparison once with an isolated Maven repository so the
published baselines cannot be replaced by a previously installed local build:

```bash
compat_repo=$(mktemp -d /tmp/gse-compat-m2.XXXXXX)
mvn -Dmaven.repo.local="$compat_repo" clean -Partifact-compat verify
```

## Snapshot validation gate

Run before converting `2.1.0-SNAPSHOT` to the final version:

```bash
mvn -f reactor/pom.xml clean test
mvn clean -Papi-compat test
mvn clean -Partifact-compat verify
bash scripts/verify-consumer-projects.sh
bash scripts/run-travel-example.sh
mvn -q -DskipTests javadoc:javadoc
bash scripts/verify-reproducible-build.sh
```

Acceptance requires:

- [x] Core, processor, schema, text, ranking, mutation, lifecycle, randomized, and
  differential tests pass with no skipped release-critical test.
- [x] The travel example compiles from source and completes structured, text, filtered
  BM25, and dynamic-index operations.
- [x] Strict Javadocs pass for every public API.
- [x] Both independent consumer projects pass against the local artifacts.
- [x] All six publishable core/processor JARs are byte-for-byte reproducible.

## Final version conversion

After every snapshot gate is accepted:

- [x] Change core, processor, reactor, example, and consumer versions from
  `2.1.0-SNAPSHOT` to `2.1.0`.
- [x] Change `CHANGELOG.md` from `Unreleased` to `2.1.0 — 2026-08-25`.
- [x] Update the root README to identify `2.1.0` as the current stable release and use
  final Maven coordinates in runtime and processor examples.
- [x] Update compatibility documentation and commands from the development snapshot
  to the final release where appropriate.
- [x] Freeze `project.build.outputTimestamp` in both publishable POMs to
  `2026-08-25T19:15:48Z`.
- [x] Confirm that `rg -n "2.1.0-SNAPSHOT"` returns no release-facing occurrence.
- [ ] Commit the conversion as `chore(release): prepare version 2.1.0`.

## Final release validation

Run every gate again after version conversion:

```bash
mvn -f reactor/pom.xml clean test
mvn clean -Papi-compat test
mvn clean -Partifact-compat verify
bash scripts/verify-consumer-projects.sh
bash scripts/run-travel-example.sh
mvn -f reactor/pom.xml clean -Prelease verify
bash scripts/verify-reproducible-build.sh
```

- [x] Core test count: recorded in the release record below.
- [x] Processor test count: recorded in the release record below.
- [x] Frozen v1 fixture test count: recorded in the release record below.
- [x] Both Japicmp baselines pass from an isolated Maven repository.
- [x] Consumer fixtures use `2.1.0`, not a snapshot or locally overwritten `2.0.0`.
- [ ] The release profile validates Javadocs, sources, signatures, and both published
  modules without deploying the reactor or example.
- [ ] The final working tree is clean after validation.

## Artifact inspection

- [x] Core main, sources, and Javadoc JARs exist for `2.1.0`.
- [x] Processor main, sources, and Javadoc JARs exist for `2.1.0`.
- [ ] Both POMs and all six JARs have valid detached ASCII-armored signatures.
- [x] Manifest `Implementation-Version` values are exactly `2.1.0`.
- [x] Core and processor artifacts contain the expected license, SCM, developer,
  issue-management, Java 21, and module-name metadata.
- [x] The core JAR contains no annotation-processor service entry.
- [x] The processor JAR contains exactly the expected
  `javax.annotation.processing.Processor` service entry.
- [x] No example, reactor, test, benchmark, or internal validation artifact is staged
  for Central publication.
- [x] SHA-256 checksums for the six reproducible JARs are recorded below.

## Tag and publication

- [ ] The final release commit is on `master`, reviewed, and has a clean working tree.
- [ ] Create signed tag `v2.1.0` on the exact approved release commit.
- [ ] Verify the tag signature before building the deployment.
- [ ] Run `mvn -f reactor/pom.xml clean -Prelease deploy` from the tagged commit.
- [ ] Confirm `autoPublish=false` leaves the Central deployment unpublished.
- [ ] Inspect both coordinates, POMs, JARs, sources, Javadocs, signatures, checksums,
  and service isolation in Central Portal.
- [ ] Publish the validated Central deployment manually.
- [ ] Verify both `2.1.0` coordinates resolve from Maven Central in a clean repository.
- [ ] Push the signed tag and create the GitHub `v2.1.0` release from the matching
  changelog section.
- [ ] Verify README links, Maven Central links, GitHub release assets, and tag links.

Published Maven Central versions are immutable. If validation fails before manual
publication, discard the Central deployment and fix the release branch. If a defect is
found after publication, prepare a new patch version; never replace `2.1.0` artifacts.

## Release record

Complete this section before marking the release finished:

- Release date: Pending (release candidate frozen 2026-08-25)
- Release commit: Pending
- Signed tag and verification: Pending
- Central deployment ID: Pending
- Core tests: PASS — 122 tests, 0 failures/errors/skips
- Processor tests: PASS — 5 tests, 0 failures/errors/skips
- Frozen v1 fixture tests: PASS — 3 tests, 0 failures/errors/skips
- Japicmp 1.0.0 report: PASS — `target/japicmp/compare-published-v1-api.*`
- Japicmp 2.0.0 report: PASS — `target/japicmp/compare-published-v2-api.*`
- Consumer fixtures: PASS — v1-style and v2.1-style
- Travel example: PASS — structured, text, filtered BM25, and dynamic index
- Strict Javadocs and signatures: Javadocs PASS; signatures BLOCKED — no GPG secret key
- Reproducible-build result: PASS — all six JARs matched byte-for-byte
- Core JAR SHA-256: `7b6dc19497dbb3b1cb88061fc93712baf30e8512dc25f7def795050fa56d9b19`
- Core sources JAR SHA-256: `1849d0e6e0a5df910a3cf5f3a00c92dc9b303658962aaeaaf8dd103dd3d8a6c9`
- Core Javadoc JAR SHA-256: `05ef39f330381acdcff285b1417ad0c2dc25a3947d117956761a0f882f8b9678`
- Processor JAR SHA-256: `1bd6a4352ef6ba1fd9d025e687ea84860eda17eed5a4948019d69a386bf3c841`
- Processor sources JAR SHA-256: `07a623268f884a5e33ca16b6800c908100a738732abae83f720d8e44c00a80b0`
- Processor Javadoc JAR SHA-256: `abefdee831097d5730b0ce317fa5170b57d0d83a0c899824faf04f17d90b76bb`
- Central publication verification: Pending
- GitHub release: Pending
