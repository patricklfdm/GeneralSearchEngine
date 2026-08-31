# V3.3 Phase 0 checklist

Status: contract ready for review on `feat/v3.3-phase0-contract`. It becomes executable
only after required CI and protected-master acceptance. Phase 0 is documentation-only.

## Entry boundary

- [x] V3.2 Phase 6, signed publication, remote verification, post-publication evidence,
  and exact-commit master CI are complete.
- [x] The V3.3 entry commit is
  `fc6f609bd17d58a3faafb802010b7edac906d742`; exact-commit `CI / Required` passes in
  [run 33353644671](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33353644671).
- [x] Signed `v3.2.0`, both Central artifacts, deployment, GitHub Release, and release
  commit `c96a15e41719cac8d7c1ee8f3c064338ef20ac61` remain immutable.
- [x] Published `1.0.0`, `2.0.0`, `2.1.0`, pinned `3.0.0`, pinned `3.1.0`, and pinned
  `3.2.0` remain mandatory compatibility baselines.
- [x] Project identity remains final `3.2.0` throughout Phase 0.
- [x] No production/test/JMH implementation, version conversion, preset, workflow, or
  paid cloud run is part of Phase 0.

## Frozen scope

- [x] V3.3 required implementation scope is strict current-snapshot search-after and
  explicit `DISABLED`/`EXACT` total hits for ordinary V3 ranked search.
- [x] The first page with disabled totals is bit-for-bit equivalent to ordinary
  `search(SearchRequest)` on the same controlled snapshot.
- [x] Existing ranking, filter, BM25, validation, tie-break, Explain, mutation,
  publication, and snapshot semantics remain unchanged.
- [x] Timeout/cancellation is a mandatory decision before release, not initial
  implementation authorization.
- [x] Prepared queries require measured evidence and a contract amendment; they are not
  a V3.3 release blocker.
- [x] Highlighted pagination, lower-bound counts, facets, aggregations, grouping,
  offset pagination, and snapshot pinning are outside the required foundation.

## Frozen architecture decisions

- [x] One page invocation captures one current immutable snapshot after lifecycle
  admission and performs one canonical normalization/plan/evaluation path.
- [x] No cursor pins or retrieves an old snapshot.
- [x] A built-in cursor binds engine instance, exact immutable request object,
  snapshot version, raw anchor score bits, and hidden internal document ID.
- [x] Cursor state exposes no accessor/serialization and retains no engine, snapshot,
  document, plan, index, posting, bitmap, or executor collection.
- [x] Successful document or dynamic-index publication stales every earlier cursor for
  that engine; failed/non-publishing work does not.
- [x] Publication after a page captures its matching snapshot does not invalidate that
  already admitted invocation.
- [x] No engine-side cursor registry, TTL queue, cleanup thread, global cache, or
  mutable shared scratch state is introduced.

## Frozen ordering and continuation

- [x] Canonical order remains score descending by `Double.compare`, then internal
  document ID ascending.
- [x] A candidate is after the anchor only when its score is lower, or score compares
  equal and its internal document ID is greater.
- [x] Cursor score uses raw `double` bits; no rounding, text encoding, or epsilon
  comparison is allowed.
- [x] Internal document ID remains unsupported and appears only inside the opaque
  built-in cursor implementation.
- [x] Page size is the wrapped `SearchRequest.limit()` and remains fixed because the
  same request object is mandatory for continuation.
- [x] Next cursor is present only when a later match exists and anchors the last
  returned hit.
- [x] Unchanged-snapshot page walks contain every match exactly once in canonical order.

## Frozen total-hits decisions

- [x] `TotalHitsMode` contains exactly `DISABLED` and `EXACT`; disabled is default.
- [x] Exact total counts all full-query/filter matches before cursor and limit.
- [x] Exact count is identical on every accepted page in one unchanged cursor chain.
- [x] Exact counting shares the existing candidate evaluation and does not invoke the
  query, filter, analyzer, planner, or executor a second time.
- [x] Disabled returns `OptionalLong.empty()`; exact returns a present non-negative
  `long`; no sentinel or implicit lower bound exists.
- [x] `LOWER_BOUND` remains deferred until an accepted early-termination strategy gives
  it physical meaning.

## Frozen public surface

- [x] Add only `SearchAfterCursor`, `TotalHitsMode`, `SearchPageRequest`,
  `SearchPageResult`, `SearchCursorException`, and one default
  `SearchEngine.search(SearchPageRequest)` overload for the required foundation.
- [x] `SearchPageRequest` wraps one exact `SearchRequest`, optional cursor, and total
  mode through a final reusable builder.
- [x] `SearchPageResult` exposes immutable hits, optional next cursor, and optional-long
  exact total through frozen public factories/accessors.
- [x] Cursor exception reasons and precedence are `UNSUPPORTED_CURSOR`,
  `DIFFERENT_ENGINE`, `DIFFERENT_REQUEST`, then `STALE_SNAPSHOT`.
- [x] Existing `SearchRequest`, `SearchResult`, `SearchHit`, highlighted, Explain,
  query, schema, analyzer, mutation, metrics, and processor shapes remain unchanged.
- [x] Third-party engine implementations remain binary-compatible through the default
  unsupported method and may construct pages with their own opaque cursor type.

## Frozen lifecycle and failure decisions

- [x] Paged search is an admitted read: close-before-call reports `CLOSED`; an admitted
  captured-snapshot invocation may complete.
- [x] Closed admission wins over cursor failures; cursor validation then follows the
  frozen reason order and wins over query normalization/planning failures.
- [x] First-page failures remain equivalent to ordinary search after page/lifecycle
  validation.
- [x] No partial page or partial exact count escapes on analyzer, extractor, filter,
  scoring, lifecycle, or cursor failure.
- [x] Cursor reuse is immutable and deterministic while its engine/request/snapshot
  binding remains valid.

## Validation and evidence gates

- [x] Independent exhaustive sorting, page slicing, exact-count, snapshot-transition,
  and retention oracles are required before production cursor execution.
- [x] Descriptor/source fixtures freeze every addition and unchanged published type.
- [x] Six-baseline normal and fresh-isolated Japicmp are mandatory.
- [x] Focused, exhaustive, randomized, mutation, dynamic-index, lifecycle, concurrency,
  failure-precedence, and retention matrices are frozen.
- [x] V1/V2 consumers remain source-unchanged; V3 consumer and travel example add
  supported page and exact-total scenarios.
- [x] Exact signed-v3.2 local baseline precedes implementation; first-page parity,
  cursor depth/ties, exact-count overhead, retention, and mixed concurrency are measured.
- [x] Existing cloud families remain immutable; Phase 0 adds no cloud lane or run.
- [x] No fixed percentage threshold is claimed without repeated comparable histories.

## Decision and implementation entry gates

- [ ] Phase 0 PR passes required CI and merges to protected `master`; record exact
  commit and CI run here.
- [ ] Create an independent Phase 1 branch from that accepted merge.
- [ ] Convert all active core/processor/reactor/example/consumer coordinates atomically
  to `3.3.0-SNAPSHOT` without changing published baseline identities.
- [ ] Add fresh-isolated six-baseline compatibility and V3.3 public descriptor/source
  fixtures before production implementation.
- [ ] Materialize independent order/page/count/snapshot/retention oracles.
- [ ] Capture exact-v3.2 ordinary ranked, highlighted-regression, and page-harness
  pre-change evidence.

## Required V3.3 exit gates

- [ ] First-page disabled-total results remain bit-for-bit ordinary-search equivalent.
- [ ] Full unchanged-snapshot cursor walks have no gap, duplicate, or reordering.
- [ ] Exact totals equal the independent full-match oracle on every page.
- [ ] Cursor ownership/request/stale reasons and failure precedence pass focused tests.
- [ ] Mutation, bulk, dynamic-index, close, concurrency, and retention hardening pass.
- [ ] Six published baselines, consumers, Javadocs, artifacts, reproducibility, and
  release gates pass.
- [ ] Timeout/cancellation closes with an accepted implementation amendment or an
  explicit evidence-backed deferral; no speculative API remains.
- [ ] Prepared query remains deferred unless a separately accepted evidence-backed
  contract authorizes logical-only caching.

No item below the protected-merge gate authorizes implementation before this Phase 0
contract is accepted. Any change to public shape, request identity, stale policy,
ordering, count meaning, highlighted integration, or cancellation requires amendment
before production code.
