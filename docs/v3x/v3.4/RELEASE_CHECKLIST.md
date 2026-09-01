# GeneralSearchEngine 3.4.0 release checklist

This state-aware record separates accepted final-source evidence, immutable cloud
baseline registration, local final-candidate validation, protected-master acceptance,
signed tagging, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `3.4.0` |
| Release state | published and remotely verified |
| Frozen workload source | `52be441f70e7f23195b8b4a0024444d315ee8eaa` (PR #72) |
| Accepted evidence merge | `fea1547accf896c3a8111ac9cfbb4080a25c5ed5` (PR #73) |
| Registered cloud baseline | `v3.4.0-in-memory-cloud` |
| Phase 6 entry | `f5b573e4a9ed389ff3ec7c9e7edc783a638d82cd` (PR #74) |
| Publication branch | `release/v3.4.0-publication` |
| Final protected-master commit | `7077446a3be3ac5eefff78366aa61d6a48e55ee1` (PR #75) |
| Signed tag | verified `v3.4.0` at the exact final commit |
| Maven Central | core and processor `3.4.0` published and remotely verified |
| GitHub Release | ID `380695065`, published `2026-09-01T17:25:37Z` |

Publication and remote-verification items below were completed only after independent
observation. Published `3.4.0` is now immutable; later fixes require a new version.

## Frozen release contents

- zero supported public API additions or removals relative to `3.3.0`;
- unchanged structured, ranked, phrase/slop, fuzzy, BOOL/BOOST, Explain, highlighting,
  pagination, total-hits, mutation, lifecycle, and snapshot behavior;
- benchmark-only cold-construction, nine-axis extreme-corpus, bounded-heap,
  multi-producer burst/recovery, and windowed long-run diagnostics;
- isolated `final-v34` suite/preset and registered
  `v3.4.0-in-memory-cloud` comparison anchor;
- eligible 4/8/16 GiB heap, required two-hour experiment, and three-member canonical
  evidence tied to exact source and environment identities; and
- explicit V4 deferral until publication and post-publication evidence close V3.x.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — final `3.4.0` across all seven active coordinates |
| Reactor verification | PASS — 383 core, 5 processor, no failures/errors/skips; example compiled |
| API fixture | PASS — frozen V1/V3.2/V3.3 and V3.4 zero-addition contracts |
| Published compatibility | PASS — fresh-isolated Japicmp against seven baselines with pinned V3 hashes |
| Independent consumers | PASS — source-unchanged V1/V2 and nine-test V3 consumer |
| Travel example | PASS — complete supported V3.0–V3.3 scenario |
| Strict release artifacts | PASS — core/processor Javadocs and six-JAR service isolation |
| Reproducible build | PASS — two clean final-version builds byte-identical after date correction |
| JMH and soak tooling | PASS — full smoke, reduced final-v34, 11 instrumentation tests, stabilization E2E |
| Cloud Benchmark local gates | PASS — shell/synthetic/fake lifecycle plus 65 Python 3.11.15 tests; no paid run |
| Baseline registry | PASS — three immutable identities; V3.4 points to reviewed canonical set |
| Diff hygiene | PASS — release date metadata and documentation only |

## Final reproducible artifact hashes

Two clean builds after the `2026-09-01T00:00:00Z` output-timestamp correction
produced byte-identical artifacts:

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-3.4.0.jar` | `e4dee61efacbff8d042b1ffda50f8b4ec1117b90689b55e621464f0c3a1c525f` |
| `general-search-engine-3.4.0-sources.jar` | `4bbf3ed85be5b5f40d099239c7bf81be4b0655f0b959252a967c1c866232c843` |
| `general-search-engine-3.4.0-javadoc.jar` | `e1373b91489608d7fc8184cc13b78a4d6195509219f722770b270f1808eef58f` |
| `general-search-engine-processor-3.4.0.jar` | `03e825a53249735da41cbc8260d40ed3d9aecc8d50611090caa36ec93e91d0c4` |
| `general-search-engine-processor-3.4.0-sources.jar` | `5730da015b2846f344c29d2f60a58d2ffe151acff35df38e6d6739c03a82a25c` |
| `general-search-engine-processor-3.4.0-javadoc.jar` | `4ff95b229f895ef7253ae59cc0eed2beaecba7b8a90ad7edc08b098494bce052` |

These are the two-build local release-validation hashes. Post-publication download
records the immutable Central archives separately:

| Published Maven Central artifact | SHA-256 |
|---|---|
| `general-search-engine-3.4.0.jar` | `e4dee61efacbff8d042b1ffda50f8b4ec1117b90689b55e621464f0c3a1c525f` |
| `general-search-engine-3.4.0-sources.jar` | `f4a83cded80a850558ea3c6f3193b14720a840740f5ed4889df7d3c81779fb52` |
| `general-search-engine-3.4.0-javadoc.jar` | `5592bf7ad052195c0578a64a0578ef4d49e4b84b80ca365d8aec249808da421a` |
| `general-search-engine-processor-3.4.0.jar` | `03e825a53249735da41cbc8260d40ed3d9aecc8d50611090caa36ec93e91d0c4` |
| `general-search-engine-processor-3.4.0-sources.jar` | `5730da015b2846f344c29d2f60a58d2ffe151acff35df38e6d6739c03a82a25c` |
| `general-search-engine-processor-3.4.0-javadoc.jar` | `532b07c1e262b4a4e819a10d633f808254b8aea774c36da24e7ccef56bfe4a41` |

Both main JARs and the processor sources JAR match the local record byte for byte. The
core sources difference is limited to empty directory entries; the Javadoc differences
are limited to JDK-distribution legal files. No Java source, class, manifest, service,
or API content differs. The release gate guarantees two clean builds within the frozen
build environment; it does not claim byte identity for Javadoc bundles produced by a
different JDK distribution. All Central archives independently pass detached-signature,
checksum, manifest, and service-boundary verification.

## Protected candidate acceptance

- [x] Merge the publication candidate through protected PR #75 as
  `7077446a3be3ac5eefff78366aa61d6a48e55ee1`.
- [x] Record exact-master CI run `33535775072` as `success` before tagging.
- [x] Verify local and remote absence of `v3.4.0` before signing.
- [x] Run Central immutability preflight on the exact accepted commit.

## Signed tag verification

- [x] Create annotated signed `v3.4.0` on the exact final protected-master commit.
- [x] `git cat-file -t v3.4.0` reports `tag`.
- [x] `git tag -v v3.4.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [x] `scripts/verify-release-tag.sh v3.4.0` passes.
- [x] `git rev-parse v3.4.0^{commit}` equals the recorded protected-master commit.
- [x] Push only the verified tag.

## Protected publication

- [x] Tag-triggered release validation checks out the exact tag and passes every gate.
- [x] The repository owner approves `production-release` only after validation.
- [x] Core and processor POM/main/sources/Javadoc artifacts and all signatures publish.
- [x] `scripts/verify-published-release.sh 3.4.0` passes from a clean remote repository.
- [x] The published V3 consumer passes all nine tests without a reactor install.
- [x] The production deployment reports success for the exact tag commit.
- [x] GitHub Release `GeneralSearchEngine 3.4.0` is created from the verified tag,
  marked latest, and is neither draft nor prerelease.

## Post-publication evidence

| Evidence | Observed result |
|---|---|
| Release date | `2026-09-01` |
| Tag and protected-master SHA | signed `v3.4.0` -> `7077446a3be3ac5eefff78366aa61d6a48e55ee1` |
| Signing fingerprint | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Release workflow | [run 33536435020](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33536435020), tag push, `success`, `2026-09-01T17:12:49Z` to `2026-09-01T17:25:41Z` |
| Production deployment | ID `6206483105`, ref `v3.4.0`, same SHA, verified `success`, updated `2026-09-01T17:25:41Z` |
| Maven Central core | [`io.github.patricklfdm:general-search-engine:3.4.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/3.4.0), main JAR SHA-256 `e4dee61efacbff8d042b1ffda50f8b4ec1117b90689b55e621464f0c3a1c525f` |
| Maven Central processor | [`io.github.patricklfdm:general-search-engine-processor:3.4.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/3.4.0), main JAR SHA-256 `03e825a53249735da41cbc8260d40ed3d9aecc8d50611090caa36ec93e91d0c4` |
| Clean remote artifact verification | PASS — eight remote artifacts, detached signatures, SHA-1 files, manifests, and service boundary verified |
| Published V3 consumer | PASS — supported-public-API consumer, 9/9 tests, no reactor install |
| GitHub Release | ID `380695065`, [`GeneralSearchEngine 3.4.0`](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.4.0), published `2026-09-01T17:25:37Z`, not draft or prerelease |

The tag, protected-master commit, workflow, deployment, Central artifacts, GitHub
Release, and registered `v3.4.0-in-memory-cloud` baseline resolve to reviewed release
identities. The published core hash exactly matches the recorded reproducible main JAR
and is frozen as the eighth future compatibility baseline. Published `3.4.0` and
signed `v3.4.0` are immutable; later fixes use `3.4.1` or a later version. The
protected merge of this documentation-only record closes Phase 6 and the V3.x line.
