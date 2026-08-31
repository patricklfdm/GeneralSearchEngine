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
| Initial candidate merge | PR #64, `fd15a8df9600bd98ec0b1926810637f0ee40ade5` |
| Calendar-correction branch | `release/v3.3.0-date-correction` |
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
- [x] Freeze output timestamp `2026-08-31T00:00:00Z` and dated changelog
  `3.3.0 — 2026-08-31`.
- [x] Add supported two-page exact-total consumer and travel executions.
- [x] Add migration, Phase 5, and state-aware release documentation.
- [x] Repeat every final validation family and record reproducible hashes.
- [x] Merge the initial candidate through protected PR #64 as
  `fd15a8df9600bd98ec0b1926810637f0ee40ade5`.
- [x] Correct the final release date and output timestamp to `2026-08-31`, rerun
  strict release/artifact/reproducibility gates, and regenerate all six hashes.
- [ ] Merge the date-corrected candidate through protected PR and record the exact
  final master commit and CI run.

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
| `general-search-engine-3.3.0.jar` | `18fb6439be074b39e5f22e2b01fba327ee919a4997e6429551481ef7fb8754f4` |
| `general-search-engine-3.3.0-sources.jar` | `2c5444f3d6e546a8b21a185271654f5d7f70ff8c235c1a98575cbf01ab7acc6e` |
| `general-search-engine-3.3.0-javadoc.jar` | `9a0a6116ade49dd412cc065e5ad415c003c6f74ea6ec68384121b124225606f0` |
| `general-search-engine-processor-3.3.0.jar` | `6ddd8ace76364fdab6392923aca8b7cdb83f8db7f74c84d571ed02f97ccc6c19` |
| `general-search-engine-processor-3.3.0-sources.jar` | `3cf85abfbaf7438ad2d00351ed56031b23393651288d7ee0fa91789bcf9e7307` |
| `general-search-engine-processor-3.3.0-javadoc.jar` | `2e58b30cb5bf2cd44a22084ff292dcb012a3e8378d2e5447ccc6fc60acf97f4a` |

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
