# GeneralSearchEngine 3.3.0 release checklist

This state-aware record separates final-candidate evidence, protected-master
acceptance, signed tagging, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `3.3.0` |
| Active candidate | final `3.3.0`, unpublished |
| Phase 5 entry / accepted Phase 4 merge | `9b1b880ddc947b5b4747e0251d0bd42708f94bfc` |
| Final-candidate branch | `release/v3.3.0` |
| Final protected-master commit | `PENDING` |
| Signed tag | `PENDING` |
| Maven Central | `PENDING`; published `3.2.0` remains stable |
| GitHub Release | `PENDING` |

No publication or remote-verification item below is complete until independently
observed. Final candidate coordinates alone do not imply availability.

## Frozen release contents

- immutable `SearchPageRequest` and `SearchPageResult` values around one exact ranked
  request;
- opaque, constant-sized, engine-owned strict search-after cursor;
- disabled-by-default and explicitly exact full-match totals;
- deterministic unsupported/different-engine/different-request/stale failure reasons;
- current-snapshot invalidation after successful publication with no snapshot pinning,
  cursor registry, serialization, TTL, or cleanup thread;
- exhaustive order/count, lifecycle, publication, concurrency, retention, scale,
  independent-consumer, and benchmark evidence; and
- explicit deferral of timeout/cancellation, prepared queries, highlighted pagination,
  lower-bound totals, offsets, facets, aggregations, and grouping.

## Final `3.3.0` candidate

- [x] Start from accepted Phase 4 merge
  `9b1b880ddc947b5b4747e0251d0bd42708f94bfc` on protected `master`.
- [x] Convert all seven active project/consumer coordinates together.
- [x] Preserve all six published baselines and historical release records.
- [x] Freeze output timestamp `2026-08-30T00:00:00Z` and dated changelog
  `3.3.0 — 2026-08-30`.
- [x] Add supported two-page exact-total consumer and travel executions.
- [x] Add migration, Phase 5, and state-aware release documentation.
- [x] Repeat every final validation family and record reproducible hashes.
- [ ] Merge through protected PR and record exact master commit and CI run.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — `3.3.0` across seven active coordinates |
| Core and reactor verification | PASS — 377 core, 5 processor; example compiled |
| API and artifact compatibility | PASS — frozen fixtures plus fresh-isolated Japicmp against all six published baselines |
| Independent consumers and example | PASS — source-unchanged V1/V2, nine-test V3, and two-page travel execution |
| Strict release artifacts | PASS — strict core/processor Javadocs and six-JAR service-entry isolation |
| Reproducible six-JAR build | PASS — two clean final-version builds byte-identical |
| JMH and production-soak gates | PASS — retained smoke, 11 instrumentation tests, and reduced stabilization E2E |
| Cloud Benchmark local gates | PASS — Python 3.11.15, 61 unit tests, shell/synthetic/fake-gcloud/lifecycle suites |
| Diff hygiene | PASS — release metadata, consumer, example, and docs only; no production/workflow/baseline change |

## Final reproducible artifact hashes

Two clean builds produced byte-identical final artifacts:

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-3.3.0.jar` | `8d8deb0d9c93ed81ae12b4bac2b47c5ead6b67914a0f00a1526418346d3689e9` |
| `general-search-engine-3.3.0-sources.jar` | `4d3d892327141328c2c7fd47594cfc9002187619ccdd30739dc686ab12380fd3` |
| `general-search-engine-3.3.0-javadoc.jar` | `9035aaa4b38ae329ea47523b0f0a5fee06665249f601c97b3f4a71bb6cce72ee` |
| `general-search-engine-processor-3.3.0.jar` | `11c272c58ef36a78bf6c5e40489f20a90db572de816ca5736f2284f5985e83e2` |
| `general-search-engine-processor-3.3.0-sources.jar` | `f7f1da236d8492a777dd7a459d64fbda4ddea9cda13d74874628a06e41014012` |
| `general-search-engine-processor-3.3.0-javadoc.jar` | `350c6d858b3534606065c1e30bacd5707c97825920fff763aaed253a7975df37` |

## Signed tag verification

- [ ] Create annotated signed `v3.3.0` on the exact final protected-master commit.
- [ ] `git cat-file -t v3.3.0` reports `tag`.
- [ ] `git tag -v v3.3.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [ ] `scripts/verify-release-tag.sh v3.3.0` passes.
- [ ] `git rev-parse v3.3.0^{commit}` equals the recorded master commit.
- [ ] Push only after every local check and central immutability preflight pass.

## Protected publication

- [ ] Tag-triggered release validation checks out the exact tag and passes every gate.
- [ ] Central immutability preflight confirms `3.3.0` does not already exist.
- [ ] The repository owner approves `production-release` after validation.
- [ ] Core and processor POM/main/sources/Javadoc artifacts and all signatures publish.
- [ ] `scripts/verify-published-release.sh 3.3.0` passes from a clean remote repository.
- [ ] The published V3 consumer passes without a reactor install.
- [ ] GitHub Release `GeneralSearchEngine 3.3.0` is created from the verified tag and
  marked latest.

## Post-publication evidence

Record exact tag/master SHA, signing fingerprint, workflow run, production deployment,
Central links, clean remote verification, consumer result, GitHub Release ID/URL, and
timestamps only after they exist. Published `3.3.0` and signed `v3.3.0` then become
immutable; later fixes use `3.3.1` or a later version.
