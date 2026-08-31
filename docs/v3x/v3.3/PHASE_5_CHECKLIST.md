# V3.3 Phase 5 release checklist

Status: complete. Initial final-candidate preparation merged through protected PR #64
as `fd15a8df9600bd98ec0b1926810637f0ee40ade5`; the `2026-08-31` calendar correction,
strict release rerun, and regenerated hashes merged through protected PR #65 as
`b399ee999e65ca363e68503720dedd4ddd2b3c2e`. Signed tag `v3.3.0`, Maven Central
publication, clean remote verification, the production deployment, and the GitHub
Release are complete at that exact protected-master commit.

## Accepted entry boundary

- [x] Phase 4 merged through protected PR #63 as
  `9b1b880ddc947b5b4747e0251d0bd42708f94bfc`.
- [x] The release branch starts from that exact accepted protected-master merge.
- [x] Phase 4 changes no production source or public descriptor and its evidence
  remains applicable to this metadata, consumer, example, and documentation branch.
- [x] Timeout/cancellation and prepared queries are explicitly deferred; no placeholder
  descriptor or production implementation enters the release candidate.

## Final version conversion

- [x] Core, processor, reactor, travel example, and all three compatibility consumer
  coordinates convert atomically from `3.3.0-SNAPSHOT` to `3.3.0`.
- [x] `project.build.outputTimestamp` is frozen at `2026-08-31T00:00:00Z`.
- [x] The changelog receives the dated `3.3.0 — 2026-08-31` heading and records
  publication only after remote verification completes.
- [x] Published `3.2.0` remains the documented stable dependency during candidate
  validation; post-publication documentation promotes verified `3.3.0`.
- [x] All six published compatibility baselines and their pinned V3 hashes remain
  immutable.

## Consumers, examples, and documentation

- [x] V1 and V2 independent consumers remain source-unchanged.
- [x] The V3 independent consumer executes two pages, checks exact totals, and uses
  only supported public types.
- [x] The travel example executes two pages from one exact request object and prints
  exact totals and continuation presence.
- [x] The 3.2-to-3.3 migration guide explains opt-in construction, exact request
  identity, stale restart, disabled/exact totals, opacity, and unsupported features.
- [x] Candidate documentation distinguishes published `3.2.0` from unpublished
  `3.3.0`; post-publication documentation promotes verified `3.3.0` and retains
  `3.2.0` as the immediate prior baseline.
- [x] Architecture, pagination, API, validation, performance, Phase 4 evidence, timeout
  decision, migration, and release records agree.

## API and artifact freeze

- [x] The accepted public additions remain exactly `SearchAfterCursor`,
  `TotalHitsMode`, `SearchPageRequest`, `SearchPageResult`, `SearchCursorException`,
  and the additive default engine page method.
- [x] The built-in cursor and its owner/request/snapshot/order anchors remain private.
- [x] Ordinary ranked, highlighted, Explain, analyzer, query, schema, processor,
  mutation, lifecycle, and metrics descriptors remain unchanged.
- [x] Reflection/source fixtures pass against the final coordinate.
- [x] Fresh-isolated Japicmp passes against published `1.0.0`, `2.0.0`, `2.1.0`,
  `3.0.0`, `3.1.0`, and `3.2.0`.
- [x] Strict core and processor Javadocs pass; exactly six publishable main/sources/
  Javadoc JARs retain the expected service-entry boundary.
- [x] Two clean final builds produce byte-identical six-JAR output.

## Repository gates

- [x] Core and reactor verification pass with 377 core and five processor tests, no
  failures or skips.
- [x] V1/V2/V3 independent consumers and the travel example pass; the V3 consumer
  executes nine supported-API tests.
- [x] The complete retained JMH smoke gate passes.
- [x] Eleven benchmark-only production-soak instrumentation tests and reduced
  stabilization E2E pass without changing formal readiness semantics.
- [x] Python 3.11.15 Cloud Benchmark 61-test unit, shell, synthetic-analysis,
  fake-gcloud, and lifecycle gates pass without a paid cloud run.
- [x] Version alignment and six-JAR release artifact integrity pass at final `3.3.0`.
- [x] Diff hygiene confirms no core/processor production source, public descriptor,
  workflow, cloud preset, or published baseline changed during release conversion.

## Protected release and publication

- [x] Merge the date-corrected final-candidate PR and wait for exact-commit
  protected-master CI.
- [x] Create and locally verify signed annotated tag `v3.3.0` on that exact merge.
- [x] Push the tag only after central immutability preflight and local verification.
- [x] Approve the protected `production-release` deployment only after validation.
- [x] Publish core and processor POM/main/sources/Javadoc artifacts and signatures.
- [x] Verify the release from a clean remote repository and execute the published V3
  consumer without a reactor install.
- [x] Confirm the GitHub Release, deployment, Maven Central artifacts, tag, and
  protected-master commit all resolve to the same SHA.
- [x] Record post-publication evidence in this separate documentation branch; its
  protected PR is the final repository step before declaring
  V3.3 complete or opening V3.4/V4 implementation.

Every checked publication item above is backed by observed remote state. This
post-publication evidence change contains documentation only; its protected merge
closes Phase 5 in repository history.
