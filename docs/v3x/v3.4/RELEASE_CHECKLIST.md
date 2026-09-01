# GeneralSearchEngine 3.4.0 release checklist

This state-aware record separates accepted final-source evidence, immutable cloud
baseline registration, local final-candidate validation, protected-master acceptance,
signed tagging, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `3.4.0` |
| Release state | unpublished final candidate; local validation complete |
| Frozen workload source | `52be441f70e7f23195b8b4a0024444d315ee8eaa` (PR #72) |
| Accepted evidence merge | `fea1547accf896c3a8111ac9cfbb4080a25c5ed5` (PR #73) |
| Registered cloud baseline | `v3.4.0-in-memory-cloud` |
| Phase 6 entry | `f5b573e4a9ed389ff3ec7c9e7edc783a638d82cd` (PR #74) |
| Publication branch | `release/v3.4.0-publication` |
| Final protected-master commit | pending protected candidate merge |
| Signed tag | pending `v3.4.0` |
| Maven Central / deployment / GitHub Release | pending independent observation |

Published `3.3.0` remains current stable. No unchecked remote item below may be marked
complete from local output or expectation.

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

## Protected candidate acceptance

- [ ] Merge the publication candidate through protected review.
- [ ] Record the exact final master commit and successful exact-master CI run.
- [ ] Verify local and remote absence of `v3.4.0` before signing.
- [ ] Run Central immutability preflight on the exact accepted commit.

## Signed tag verification

- [ ] Create annotated signed `v3.4.0` on the exact final protected-master commit.
- [ ] `git cat-file -t v3.4.0` reports `tag`.
- [ ] `git tag -v v3.4.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [ ] `scripts/verify-release-tag.sh v3.4.0` passes.
- [ ] `git rev-parse v3.4.0^{commit}` equals the recorded protected-master commit.
- [ ] Push only the verified tag.

## Protected publication

- [ ] Tag-triggered release validation checks out the exact tag and passes every gate.
- [ ] The repository owner approves `production-release` only after validation.
- [ ] Core and processor POM/main/sources/Javadoc artifacts and all signatures publish.
- [ ] `scripts/verify-published-release.sh 3.4.0` passes from a clean remote repository.
- [ ] The published V3 consumer passes without a reactor install.
- [ ] The production deployment reports success for the exact tag commit.
- [ ] GitHub Release `GeneralSearchEngine 3.4.0` is created from the verified tag,
  marked latest, and is neither draft nor prerelease.

## Post-publication evidence

| Evidence | Observed result |
|---|---|
| Release date | pending verified publication on `2026-09-01` |
| Tag and protected-master SHA | pending |
| Signing fingerprint | pending independent tag verification |
| Release workflow | pending |
| Production deployment | pending |
| Maven Central core and processor | pending |
| Clean remote artifact verification | pending |
| Published V3 consumer | pending |
| GitHub Release | pending |

Only a later documentation-only post-publication change may fill these fields and
promote `3.4.0` to current stable. That protected merge closes Phase 6 and the V3.x
development line; V4 implementation remains blocked until then.
