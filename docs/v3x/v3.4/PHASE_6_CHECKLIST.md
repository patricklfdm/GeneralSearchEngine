# V3.4 Phase 6 publication checklist

Status: local final-candidate preparation is complete on
`release/v3.4.0-publication`, starting from protected-master commit
`f5b573e4a9ed389ff3ec7c9e7edc783a638d82cd`. Publication remains blocked until this
branch passes protected review, merges, and its exact-master CI succeeds. No tag,
Central publication, deployment, GitHub Release, or V4 work is claimed here.

## Accepted entry boundary

- [x] Phase 5 final-source evidence merged through PR #73 as
  `fea1547accf896c3a8111ac9cfbb4080a25c5ed5`; exact-master CI run `33529997974`
  passed.
- [x] `v3.4.0-in-memory-cloud` registration merged through PR #74 as
  `f5b573e4a9ed389ff3ec7c9e7edc783a638d82cd`; exact-master CI run `33532660854`
  passed.
- [x] The Phase 6 branch starts from that exact accepted registration merge.
- [x] Final workload source remains
  `52be441f70e7f23195b8b4a0024444d315ee8eaa`; later evidence and release work change
  no production source, public API, benchmark workload, cloud preset, or baseline.

## Release metadata and documentation

- [x] Keep all seven active project, processor, reactor, example, and consumer
  coordinates aligned at final `3.4.0`.
- [x] Correct the actual release date and both publishable
  `project.build.outputTimestamp` values to `2026-09-01`.
- [x] Keep `3.3.0` documented as current stable until remote `3.4.0` verification.
- [x] Add the zero-source-change [3.3-to-3.4 migration guide](MIGRATION_GUIDE.md).
- [x] Add a state-aware [release checklist](RELEASE_CHECKLIST.md) that distinguishes
  local candidate evidence from protected merge, tag, publication, and remote proof.
- [x] Preserve historical release records and all registered cloud baselines.

## API, compatibility, consumers, and example

- [x] V3.4 remains a strict zero-addition public API release.
- [x] Frozen source/reflection fixtures pass, including the V3.4 zero-addition fixture.
- [x] Fresh-isolated Japicmp passes against published `1.0.0`, `2.0.0`, `2.1.0`,
  `3.0.0`, `3.1.0`, `3.2.0`, and `3.3.0` with pinned V3 hashes.
- [x] Independent V1/V2/V3 consumers pass; V1/V2 source remains unchanged and the V3
  consumer retains all nine supported-API tests.
- [x] The travel example executes structured, ranked, highlighting, pagination,
  phrase/slop, BOOL threshold, fuzzy, Explain, dynamic-index, and metrics scenarios.

## Evidence inheritance

- [x] Eligible 4/8/16 GiB no-swap heap evidence remains accepted.
- [x] The required two-hour Standard/GCS experiment remains accepted.
- [x] The three-member `final-v34` canonical set remains accepted and immutably
  registered as `v3.4.0-in-memory-cloud`.
- [x] Phase 6 changes only release metadata and documentation, so it does not
  invalidate source-bound workload, correctness, liveness, retention, or cleanup
  evidence.
- [x] No result or release gate requires a production fix or contract amendment.

## Local release validation

- [x] Version alignment passes for final `3.4.0`.
- [x] Reactor clean test passes with 383 core and five processor tests, with no
  failures, errors, or skips; the example compiles.
- [x] Strict core and processor Javadocs and release packaging pass.
- [x] Exactly six publishable main/sources/Javadoc JARs retain the expected processor
  service-entry boundary.
- [x] Two clean builds after the release-date correction produce byte-identical JARs;
  final hashes are recorded in the release checklist.
- [x] The complete JMH smoke, V3.4 reduced final suite, eleven production-soak
  instrumentation tests, and reduced stabilization E2E pass.
- [x] Cloud Benchmark shell syntax, synthetic analysis, fake-gcloud lifecycle, and 65
  Python 3.11.15 unit tests pass without GCP access, upload, or paid execution.
- [x] Registry validation passes with exactly three append-only baseline identities.
- [x] Diff hygiene contains release metadata and documentation only; production,
  workflow, preset, test, JMH, and registered baseline contents are unchanged.

## Protected candidate acceptance

- [ ] Merge this Phase 6 candidate through a protected PR.
- [ ] Confirm exact-master CI succeeds on the merge commit.
- [ ] Confirm `v3.4.0` is absent locally and remotely before tag creation.
- [ ] Verify version, changelog date, output timestamp, release notes, and Central
  immutability preflight on the exact accepted master commit.

## Signed tag and publication

- [ ] Create annotated signed tag `v3.4.0` on the exact approved master commit.
- [ ] Verify tag type, signature fingerprint, version alignment, commit target, and
  `origin/master` reachability locally before pushing.
- [ ] Push only the verified tag and let the protected Release workflow validate it.
- [ ] Approve `production-release` only after validation and Central preflight pass.
- [ ] Publish core and processor POM/main/sources/Javadoc artifacts and signatures.
- [ ] Verify all remote artifacts from a clean repository and run the published V3
  consumer without a reactor install.
- [ ] Confirm successful deployment and a non-draft, non-prerelease GitHub Release
  resolving to the same tag and commit.

## Post-publication and V4 handoff

- [ ] Record exact tag/master SHA, fingerprint, workflow, deployment, Central hashes,
  clean remote verification, consumer result, and GitHub Release evidence.
- [ ] Promote verified `3.4.0` to current stable and retain `3.3.0` as immediate prior.
- [ ] Freeze the published `3.4.0` core hash as the eighth future compatibility
  baseline only after it matches the recorded reproducible JAR.
- [ ] Merge the documentation-only post-publication record through protected master
  and confirm exact-master CI.
- [ ] Begin no V4 durability implementation before every item above is complete.
