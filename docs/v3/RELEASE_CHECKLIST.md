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
- [ ] Snapshot commit and test counts are recorded.

## State 2 — final release preparation (`3.0.0`)

- [ ] Core, processor, reactor, example, and current consumer versions are aligned at
  `3.0.0`; historical baseline versions are unchanged.
- [ ] Reproducible output timestamps and dated changelog heading are frozen.
- [ ] No release-facing `3.0.0-SNAPSHOT` reference remains.
- [ ] Every snapshot gate is rerun against the final version.
- [ ] Core and processor main/sources/Javadoc JARs pass content inspection.
- [ ] Core contains no processor service entry; processor contains exactly the expected
  processor service entry.
- [ ] Final six-JAR SHA-256 hashes are recorded.
- [ ] Final release-preparation PR passes `CI / Required`, is approved, and is merged to
  protected `master`.
- [ ] Required `master` CI passes on the exact intended tag commit.

## State 3 — signed publication and remote verification

- [ ] Signed annotated `v3.0.0` tag points to the exact approved `master` commit.
- [ ] Local tag verification matches the expected OpenPGP fingerprint.
- [ ] Tag-triggered workflow validates tests, compatibility, consumers, travel,
  packaging, reproducibility, signatures, and Central immutability.
- [ ] `production-release` deployment is approved.
- [ ] Core and processor `3.0.0` publish automatically to Maven Central.
- [ ] Remote POM, main, sources, Javadoc, `.asc`, and checksum files verify from a fresh
  isolated repository/cache.
- [ ] A clean V3 consumer compiles and runs against published `3.0.0` without installing
  the reactor.
- [ ] GitHub Release is created from the exact verified tag.

## Post-publication record — currently `PENDING`

- Release date: `PENDING`
- Tag/master commit: `PENDING`
- OpenPGP fingerprint: `PENDING`
- Workflow run and deployment ID: `PENDING`
- Maven Central resolution evidence: `PENDING`
- GitHub Release URL and publication time: `PENDING`
- Published consumer result: `PENDING`
- Final stable-version documentation commit: `PENDING`
- Published 3.0.0 compatibility-baseline addition: `PENDING`

After publication, fill this section from real remote evidence in a documentation-only
follow-up commit outside the immutable signed tag. Never overwrite published 3.0.0;
later fixes use 3.0.1 or a later version.
