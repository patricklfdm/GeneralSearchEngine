# GeneralSearchEngine v1.0.0 release checklist

This is the historical v1 checklist. Use
[`../v2/RELEASE_CHECKLIST.md`](../v2/RELEASE_CHECKLIST.md) for the active v2 candidate.

This checklist prepares the v1.0.0 release candidate. Its Maven identity is
`io.github.patricklfdm:general-search-engine:1.0.0`, its Java root package is
`io.github.patricklfdm.generalsearch`, and it is licensed under Apache License 2.0.
The release profile is configured for the Sonatype Central Portal with manual final
publishing. Credentials, private keys, and signing-agent configuration remain outside
the repository.

## v1.0.0 identity decisions

- [x] Set the Maven group ID to `io.github.patricklfdm` and the Java package/module
  root to `io.github.patricklfdm.generalsearch`.
- [x] Set the artifact ID to `general-search-engine` and version to `1.0.0`.
- [x] Add Apache License 2.0 as `LICENSE` and matching Maven `<licenses>` metadata.
- [x] Set project, SCM, and issue metadata to the GeneralSearchEngine GitHub repository.
- [x] Configure the verified Central namespace `io.github.patricklfdm`, publishing
  server ID `central`, and GPG signing through the local installation/agent. Never
  commit credentials, passphrases, tokens, or private signing keys.
- [x] Include the Product compatibility layer in v1.0.0 exactly as documented.

## Frozen scope

Do not add features while finalizing v1.0.0. Full-text search/BM25, fuzzy search,
WAL/persistence, and distributed search/sharding are explicitly out of scope.

## Every release candidate

- [x] Start from a clean Git worktree and review `CHANGELOG.md`.
- [x] Confirm the non-SNAPSHOT `1.0.0` project version and update
  `project.build.outputTimestamp` to the release commit time in UTC.
- [x] Run the complete functional suite: `mvn clean test`.
- [x] Run the frozen API gate: `mvn clean -Papi-compat test`.
- [x] Build release artifacts: `mvn clean -Prelease verify`.
- [x] Confirm release verification signs the POM, main JAR, sources JAR, and Javadoc
  JAR, producing four corresponding `.asc` files.
- [x] Verify the main, sources, and Javadoc JARs are reproducible:
  `bash scripts/verify-reproducible-build.sh`.
- [x] Use the same JDK major version and a clean checkout with the repository's LF
  `.gitattributes`; cross-JDK bytecode identity is not promised.
- [x] Inspect the main JAR manifest and confirm the expected version/module name.
- [x] Run the bounded concurrency regression and JMH discovery smoke. Long JMH/soak
  baselines are recorded separately on the target machine when required.
- [x] Review generated Javadocs under `target/apidocs` and release notes for accidental
  exposure of implementation-only APIs.
- [ ] Commit the release version, create an annotated Git tag, publish from that exact
  commit, and verify checksums after download.

## Maven Central deployment

- [ ] Confirm the release commit and annotated `v1.0.0` tag point to the exact audited
  source tree, and prime the local GPG agent if necessary.
- [ ] Confirm `~/.m2/settings.xml` contains the Central Portal token under server ID
  `central`; do not copy credentials into `pom.xml` or the command line.
- [ ] From the tagged source tree, upload and wait for Portal validation with:

  ```bash
  mvn clean -Prelease deploy
  ```

- [ ] Review the validated deployment in the Central Portal. The plugin has
  `autoPublish=false`, so a successful deploy does not publish automatically; publish
  or drop the deployment manually after reviewing its coordinates and artifacts.
- [ ] After manual publication, verify resolution of the POM, main, sources, and
  Javadoc artifacts from Maven Central and verify their checksums and signatures.

## After the first published artifact

- [ ] Compare every later candidate with the previous published JAR using an
  artifact-level binary compatibility tool in addition to `V1ApiCompatibilityTest`.
- [ ] Verify a clean consumer project can resolve the main, sources, and Javadoc
  artifacts from the target repository.
- [ ] Record the next development section in `CHANGELOG.md` after v1.0.0 is published.
