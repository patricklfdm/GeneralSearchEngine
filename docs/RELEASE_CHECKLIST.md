# Release checklist

This checklist prepares a local release candidate. Publishing to an external Maven
repository is intentionally not automated until project ownership and legal metadata
are selected.

## One-time decisions before 1.0.0

- [ ] Replace the placeholder `org.example` group ID with a namespace controlled by
  the publisher, and decide whether Java package/module names should change with it.
- [ ] Choose a software license, add `LICENSE` (and `NOTICE` if required), then add the
  matching Maven `<licenses>` metadata.
- [ ] Select the target Maven repository and configure credentials/signing outside the
  repository. Never commit secrets or private signing keys.
- [ ] Decide whether the current Product compatibility layer is included in the first
  stable artifact exactly as documented.

## Every release candidate

- [ ] Start from a clean Git worktree and review `CHANGELOG.md`.
- [ ] Set a non-SNAPSHOT project version and update
  `project.build.outputTimestamp` to the release commit time in UTC.
- [ ] Run the complete functional suite: `mvn clean test`.
- [ ] Run the frozen API gate: `mvn clean -Papi-compat test`.
- [ ] Build release artifacts: `mvn clean -Prelease verify`.
- [ ] Verify the main, sources, and Javadoc JARs are reproducible:
  `bash scripts/verify-reproducible-build.sh`.
- [ ] Use the same JDK major version and a clean checkout with the repository's LF
  `.gitattributes`; cross-JDK bytecode identity is not promised.
- [ ] Inspect the main JAR manifest and confirm the expected version/module name.
- [ ] Run the bounded concurrency regression and JMH discovery smoke. Long JMH/soak
  baselines are recorded separately on the target machine when required.
- [ ] Review generated Javadocs under `target/apidocs` and release notes for accidental
  exposure of implementation-only APIs.
- [ ] Commit the release version, create an annotated Git tag, publish from that exact
  commit, and verify checksums after download.

## After the first published artifact

- [ ] Compare every later candidate with the previous published JAR using an
  artifact-level binary compatibility tool in addition to `V1ApiCompatibilityTest`.
- [ ] Verify a clean consumer project can resolve the main, sources, and Javadoc
  artifacts from the target repository.
- [ ] Move the released changelog section out of “Unreleased” and record its date.
