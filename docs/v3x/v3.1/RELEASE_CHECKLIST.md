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
- [x] Snapshot hardening was merged by PR #47 to protected `master` as
  `322527031d31065b1c6921656015ee6d3a100ce3`; exact-commit `CI / Required` passed in
  [run 33331504798](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33331504798).

## State 2 — final release preparation (`3.1.0`) — complete

- [x] Every State 1 item, including protected CI, is accepted before conversion.
- [x] Current project and consumer coordinates are aligned at final `3.1.0` while
  historical compatibility and cloud identities remain unchanged.
- [x] Reproducible output timestamp is `2026-08-30T00:00:00Z` and the changelog
  heading is dated `2026-08-30`.
- [x] Release-facing snapshot references are removed without rewriting historical
  evidence.
- [x] Every snapshot validation family is rerun against final `3.1.0`: reactor,
  frozen fixture, normal and fresh-isolated Japicmp, consumers, travel, strict
  packaging, artifact inspection, reproducibility, JMH, soak, and Python/cloud
  synthetic lifecycle gates all pass.
- [x] Final six-JAR SHA-256 hashes are recorded:
  - `f53f35c0d54bfdaba42d1815163c23ef414d971f517486cb1aed66462600fc5e`
    core Javadoc;
  - `1f5777fc0d2f4ff34fa6b37eb06c86a7148884508636908156f6c5f58a3d4d41`
    core sources;
  - `d77309b58ceca6b6515177a1edbed20f88d59ec5e3ec9330173e282d53d6c86c`
    core main;
  - `2b5501f0c51ce5ec6d7e14d0db82860eb38ff65dec7c8a02319094cf65fddf51`
    processor Javadoc;
  - `a9ba5fce93cf1776ad11e8a7535af83784b3937945c22ff1fd621cef2718fe5f`
    processor sources;
  - `7e2de871db7f543bc5323ea89b86793b52f8ea2a66eeaddbb1f2456d4e5b37ed`
    processor main.
- [x] Release-preparation commit
  `c4186f98d889f7c17edf926f94c4836d4b9af86e` is recorded; PR #48 merged it to
  protected `master` as `9ad9c716459312a916028d1ecd3946486661b743`.
- [x] Exact-commit `CI / Required` succeeds on the protected merge in
  [run 33332884970](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33332884970).

## State 3 — signed tag and publication — complete

- [x] Annotated signed `v3.1.0` points to the exact approved protected-`master` commit
  `9ad9c716459312a916028d1ecd3946486661b743`.
- [x] Local tag type, signature fingerprint, version, changelog, HEAD identity, and
  `origin/master` reachability checks pass.
- [x] Protected recovery
  [run 33333645494](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33333645494)
  passes validation and Central immutability preflight before `production-release`
  approval.
- [x] Core and processor publish to Maven Central with POM, main, sources, Javadoc,
  detached signatures, and checksums.
- [x] Fresh remote verification passes for all eight artifacts, detached signatures,
  and SHA-1 files; a clean published V3 consumer passes 7/7 tests without a reactor
  install.
- [x] [GeneralSearchEngine 3.1.0](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.1.0)
  is created from the exact verified tag and marked latest.

## Immutable-tag recovery record

- [x] Initial tag-triggered
  [run 33333303580](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33333303580)
  passed unprivileged validation and preflight, then stopped before the publish runner
  because environment pattern `v*.*.*` was mistakenly typed as a branch policy rather
  than a tag policy; deployment `6170859742` was rejected.
- [x] No protected publish step, Central upload, or GitHub Release occurred in the
  failed run; signed `v3.1.0` remained unchanged.
- [x] The environment retains `master` as the recovery branch rule and now matches
  `v*.*.*` as a tag rule. Manual recovery validated and published the same immutable
  tag in successful run `33333645494`.

## State 4 — post-publication record — complete

- [x] Release date, exact tag/master commit, signing fingerprint, workflow run,
  deployment, Central coordinates, remote verification, and GitHub Release URL/time
  are recorded below.
- [x] Root and V3.x documentation identify `3.1.0` as current stable.
- [x] Published `3.1.0` is a mandatory future compatibility baseline while retaining
  `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`.
- [x] The post-publication evidence change is the final V3.1 Phase 8 deliverable; its
  protected-master merge completes Phase 8.

## Post-publication evidence

- Release date: `2026-08-30`.
- Tag/master commit: signed `v3.1.0` ->
  `9ad9c716459312a916028d1ecd3946486661b743`.
- OpenPGP fingerprint: `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- Workflow and deployment: successful protected recovery
  [run 33333645494](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33333645494)
  and approved `production-release` deployment `6170932080`, both completed with
  `success` on exact commit `9ad9c716459312a916028d1ecd3946486661b743`.
- Maven Central: published
  [`general-search-engine:3.1.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/3.1.0)
  and
  [`general-search-engine-processor:3.1.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/3.1.0).
- Remote verification: all eight POM/main/sources/Javadoc artifacts, detached
  signatures, and SHA-1 files passed on `2026-08-30`; the main JARs expose the expected
  processor-service boundary.
- Published consumer: a clean V3 consumer resolved only remote `3.1.0` artifacts and
  passed 7/7 tests without a reactor install.
- GitHub Release: [GeneralSearchEngine 3.1.0](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.1.0),
  published at `2026-08-30T20:39:31Z`.
- Future compatibility: the pinned published 3.1.0 core JAR SHA-256 is
  `d77309b58ceca6b6515177a1edbed20f88d59ec5e3ec9330173e282d53d6c86c`;
  all five published baselines remain mandatory.

Published `3.1.0` and signed `v3.1.0`, once they exist, are immutable. Later fixes use
`3.1.1` or a later version.
