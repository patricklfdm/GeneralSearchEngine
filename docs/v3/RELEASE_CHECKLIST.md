# GeneralSearchEngine 3.0.0 release checklist

This record follows three evidence states. A later-state fact must remain `PENDING`
until it actually occurs; release-ready does not mean released.

## State 1 — snapshot hardening (`3.0.0-SNAPSHOT`)

- [x] Supported V3 API and strict Javadocs reviewed.
- [x] Japicmp additions against 1.0.0, 2.0.0, and 2.1.0 reviewed.
- [x] Release-critical BOOL, phrase, fuzzy, and Explain stress gaps covered by bounded
  tests.
- [x] V2-equivalent, composition, phrase, fuzzy, Explain, positional mutation, and
  memory evidence recorded in [the performance baseline](PERFORMANCE_BASELINE.md).
- [x] Fuzzy per-term temporary-array pathology fixed without expansion truncation.
- [x] JMH packaging now overwrites broken first-pass generated classes and CI executes
  a bounded forked smoke case.
- [x] Migration guide and supported-public-API travel scenario completed.
- [x] Normal and isolated compatibility, all consumers, travel, strict Javadocs,
  artifact inspection, reproducibility, and complete reactor tests pass on the final
  snapshot tree.
- [x] CI and release workflow audit, including clean published consumer and remote
  artifact/signature/checksum verification, is complete.
- [x] Snapshot commit and test counts are recorded: protected `master` snapshot commit
  `05eee9d254c889314cf65ab72fd1a70dd2a176b2`; core 246 tests and processor 5 tests
  (251 total) passed.

## State 2 — final release preparation (`3.0.0`)

- [x] Core, processor, reactor, example, and current consumer versions are aligned at
  `3.0.0`; historical baseline versions are unchanged.
- [x] Reproducible output timestamps and dated changelog heading are frozen.
- [x] No release-facing `3.0.0-SNAPSHOT` reference remains; remaining occurrences are
  historical snapshot evidence or state-transition instructions.
- [x] Every snapshot gate is rerun against the final version.
- [x] Core and processor main/sources/Javadoc JARs pass content inspection.
- [x] Core contains no processor service entry; processor contains exactly the expected
  processor service entry.
- [x] Final six-JAR SHA-256 hashes are recorded:
  - `c5635248ea8769b3121feaeb73d38a9e3b4ecd137a39905003b0b89fd7fb854d`
    core Javadoc;
  - `0bf00d2270858cf8d7a8027976dfc76a149babdf4599c686b9b22ff315dca106`
    core sources;
  - `3b0ed72877f3c5f2ef225d1a87cac8d9546b109c91c0bec8d8dcea12e2d101f2`
    core main;
  - `432f0a3b64cb0ad15d6620038e125ba02975ed8e376c6a8315a0af804d11e9fd`
    processor Javadoc;
  - `8b4093f66bb2b678594b4f7ec69dae882e03a3b57d8a6359fbe84b23b2ab8fed`
    processor sources;
  - `3c040a2d5ebc0cdfe61636b7d2f8072225ed4feac0ee156b7661f1ebd7941d77`
    processor main.
- [x] Final release-preparation PR passes `CI / Required` and is merged to protected
  `master` as `a47009e53765c99b792c255cee3584cebabf16ee`.
- [x] Required `master` CI passes on exact tag commit
  `a47009e53765c99b792c255cee3584cebabf16ee` in
  [run 33007043891](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33007043891).

## State 3 — signed publication and remote verification

- [x] Signed annotated `v3.0.0` tag points to the exact approved `master` commit
  `a47009e53765c99b792c255cee3584cebabf16ee`.
- [x] Local tag verification matches OpenPGP fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [x] Protected recovery [run 33009580128](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33009580128)
  validates the exact immutable tag, tests, compatibility, consumers, travel,
  packaging, reproducibility, signatures, and Central immutability after the initial
  tag-triggered runner-tool failure.
- [x] `production-release` deployment `6111290282` is approved and finishes with
  `success`.
- [x] Core and processor `3.0.0` were published automatically to Maven Central.
- [x] Remote POM, main, sources, Javadoc, `.asc`, and checksum files verify from a fresh
  isolated repository/cache.
- [x] A clean V3 consumer compiles and runs 5 tests against published `3.0.0` without
  installing the reactor.
- [x] GitHub Release is created from the exact verified tag.

## Pre-publication recovery record

- [x] The initial tag-triggered run stopped in the unprivileged validation job because
  the tagged validator assumed `rg` was installed on the runner.
- [x] No release secret, protected-environment approval, Central upload, or GitHub
  Release occurred before that failure.
- [x] The pushed signed `v3.0.0` tag remains unchanged.
- [x] The reviewed portable-validator and immutable-tag recovery workflow are merged to
  protected `master` and `CI / Required` passes.
- [x] `Release` is manually dispatched with `release_tag=v3.0.0`.
- [x] The recovery run completes all validation and publication evidence in State 3.

## Post-publication record — complete

- Release date: `2026-08-26`.
- Tag/master commit: signed `v3.0.0` ->
  `a47009e53765c99b792c255cee3584cebabf16ee`.
- OpenPGP fingerprint: `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- Workflow and deployment: recovery
  [run 33009580128](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33009580128),
  successful `production-release` deployment `6111290282`.
- Maven Central resolution evidence: published
  [`general-search-engine:3.0.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/3.0.0)
  and
  [`general-search-engine-processor:3.0.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/3.0.0)
  were independently reverified at `2026-08-26T20:54:37Z`; all eight POM/main/sources/
  Javadoc artifacts, detached signatures, and SHA-1 files passed.
- GitHub Release: [GeneralSearchEngine 3.0.0](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.0.0),
  published at `2026-08-26T20:25:36Z`.
- Published consumer result: clean isolated V3 consumer build and all 5 tests passed.
- Final stable-version documentation: the documentation-only commit containing this
  record, outside the immutable signed tag.
- Published 3.0.0 compatibility baseline: recorded as mandatory for the next
  development-version change in [API compatibility](API_COMPATIBILITY.md).

Published 3.0.0 and its signed tag are immutable. Later fixes use 3.0.1 or a later
version.
