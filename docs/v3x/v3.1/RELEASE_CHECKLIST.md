# GeneralSearchEngine 3.1.0 release checklist

This record follows four evidence states. A later-state fact remains `PENDING` until
it actually occurs; a locally hardened snapshot is neither a final release candidate
nor a published release.

## State 1 — snapshot hardening (`3.1.0-SNAPSHOT`)

- [x] Core, processor, reactor, travel example, and all current consumer coordinates
  are aligned at `3.1.0-SNAPSHOT`; published compatibility baselines remain unchanged.
- [x] The supported V3.1 additions are limited to
  `SearchQueries.phrase(TextField<T>, String, int)` and
  `BoolBuilder.minimumShouldMatch(int)`.
- [x] Normal clean-home and fresh-isolated Japicmp runs pass against published
  `1.0.0`, `2.0.0`, `2.1.0`, and pinned `3.0.0`. The pin is
  `3b0ed72877f3c5f2ef225d1a87cac8d9546b109c91c0bec8d8dcea12e2d101f2`.
- [x] Phrase slop, BOOL minimum, fuzzy-trie equivalence, Search/Explain invariants,
  failure precedence, mutation, snapshot, lifecycle, and concurrency suites pass.
- [x] The complete reactor passes with 280 core tests and 5 processor tests.
- [x] Frozen V1 fixtures, all independent consumers, and the travel example pass.
- [x] Strict core and processor Javadocs, unsigned release packaging, six-JAR content
  inspection, JMH packaging/smoke, soak instrumentation, and reduced stabilization
  E2E pass.
- [x] Two clean release builds produce byte-identical output. Snapshot six-JAR
  SHA-256 hashes are:
  - `ad1ca1b821f773a67020e6a12b31cd60f2012e5d57702b3eb8ffb98e482c02c6`
    core Javadoc;
  - `7e32778d0b0d76a393c364fe91436551622a8f45fc5bc7fac062685af49931da`
    core sources;
  - `119d00ece336a04d8a129fa35d01410bf18218f6ecb970e8c3ec48a459983f19`
    core main;
  - `9818b5146aeb77a8f04e790a7daf784ec7bab264464fc496c0e187738066f430`
    processor Javadoc;
  - `ac29166c28ffa6dedebdb8176bcebf8ac841d8ea4a19c0255da237c929b9ef84`
    processor sources;
  - `3527dca8d119ae324ee19dc89c14f37fb60c0eb0945fc8490be6bbbcb9381ebf`
    processor main.
- [x] Python 3.11 Cloud Benchmark tests pass 61/61; shell syntax and every synthetic
  analysis, fake-gcloud, set-runner, upload, and registration lifecycle gate pass.
- [x] The diff from reviewed Phase 7 source
  `9d4c43c230abb260ac1736cc3dd4d29d4f29fbe9` changes no production source, JMH
  workload, preset, runner, workflow, JVM/toolchain, or evidence identity. Existing
  regression and ranked-feature cloud evidence is inherited without another paid run.
- [ ] Snapshot hardening commit and protected PR/master `CI / Required` evidence are
  recorded after acceptance.

## State 2 — final release preparation (`3.1.0`) — `PENDING`

- [ ] Every State 1 item, including protected CI, is accepted before conversion.
- [ ] Current project and consumer coordinates are aligned at final `3.1.0` while
  historical compatibility and cloud identities remain unchanged.
- [ ] Reproducible output timestamp and the dated changelog heading are frozen.
- [ ] Release-facing snapshot references are removed without rewriting historical
  evidence.
- [ ] Every snapshot validation family is rerun against the final version.
- [ ] Final six-JAR hashes and exact release-preparation commit are recorded.
- [ ] The release-preparation PR passes `CI / Required`, merges to protected `master`,
  and exact-commit master CI succeeds.

## State 3 — signed tag and publication — `PENDING`

- [ ] Annotated signed `v3.1.0` points to the exact approved protected-`master` commit.
- [ ] Local tag type, signature fingerprint, version, changelog, HEAD identity, and
  `origin/master` reachability checks pass.
- [ ] The protected Release workflow passes validation and Central immutability
  preflight before `production-release` approval.
- [ ] Core and processor publish to Maven Central with POM, main, sources, Javadoc,
  detached signatures, and checksums.
- [ ] Fresh remote verification and a clean published V3 consumer pass without a
  reactor install.
- [ ] GitHub Release is created from the exact verified tag and marked latest.

## State 4 — post-publication record — `PENDING`

- [ ] Record release date, exact tag/master commit, signing fingerprint, workflow run,
  deployment, Central coordinates, remote verification, and GitHub Release URL/time.
- [ ] Update root and V3.x documentation to identify `3.1.0` as current stable.
- [ ] Add published `3.1.0` as a mandatory future compatibility baseline while
  retaining `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`.
- [ ] Mark V3.1 Phase 8 complete only after the evidence commit is merged.

Published `3.1.0` and signed `v3.1.0`, once they exist, are immutable. Later fixes use
`3.1.1` or a later version.
