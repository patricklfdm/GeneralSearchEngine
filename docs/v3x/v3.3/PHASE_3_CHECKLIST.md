# V3.3 Phase 3 checklist

Status: complete and accepted on protected `master` through PR #62 as merge commit
`521e65e`.

Phase 3 completes the frozen strict current-snapshot search-after semantics without
adding or changing a public descriptor. Phase 4 remains responsible for the broad
mutation, dynamic-index, concurrency, retained-heap, scale, and timeout-decision
matrices.

## Accepted entry boundary

- [x] Phase 2 is accepted on protected `master` through PR #61 at
  `e444d40bd265c6ca855d788b75b25623ec892b50`.
- [x] Exact-commit protected-master `CI / Required` passes in
  [run 33359591742](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33359591742).
- [x] The independent Phase 3 branch starts from that exact merge commit.
- [x] Coordinates remain `3.3.0-SNAPSHOT`; public page request/result, mode, cursor
  marker, exception, and engine method descriptors remain unchanged.

## Private built-in cursor

- [x] The implementation class is package-private, immutable, constant-sized, and
  declares no public method.
- [x] It retains exactly two object references: a small per-engine owner token and the
  exact immutable `SearchRequest` object.
- [x] Snapshot version, raw score bits, and hidden internal document ID are the only
  three primitive cursor fields.
- [x] It retains no engine, snapshot, document, result, plan, posting, bitmap, index,
  analyzer output, registry, collection, or cleanup callback.
- [x] The engine retains only its owner token and no cursor registry, old-snapshot
  registry, TTL queue, cleanup thread, or per-cursor state.

## Validation and failure precedence

- [x] Lifecycle admission rejects `CLOSED` before cursor inspection and captures one
  immutable current snapshot for the admitted invocation.
- [x] Application/third-party cursor fails as `UNSUPPORTED_CURSOR`.
- [x] A private cursor with another owner token fails as `DIFFERENT_ENGINE`.
- [x] A same-engine cursor wrapping any other request object fails as
  `DIFFERENT_REQUEST`, even when the request appears equivalent.
- [x] A same-owner, same-request cursor with another captured snapshot version fails as
  `STALE_SNAPSHOT`.
- [x] The frozen order is type, owner, exact request identity, then snapshot version;
  the first applicable reason wins before query normalization or planning.
- [x] Total mode belongs to the page wrapper rather than cursor identity, so the same
  cursor may branch between `DISABLED` and `EXACT`.

## Deterministic continuation

- [x] Every matching candidate is evaluated and compared with the raw cursor anchor;
  a candidate follows the anchor only for lower score or equal score and greater
  internal document ID.
- [x] The page heap retains at most the wrapped request limit and emits a new cursor
  anchored to the last returned hit only when another eligible match exists.
- [x] Final/empty pages emit no cursor. Cursor reuse is idempotent and branching does
  not consume or mutate a cursor.
- [x] Dense equal-score walks cover every page size from one through match count plus
  one and preserve hidden insertion/document-ID order rather than business-ID order.
- [x] A deterministic matrix covers TEXT, exact/sloppy PHRASE, FUZZY, zero-score,
  nested BOOL/BOOST, filters, two BM25 configurations, and limits 1/2/5/50.
- [x] Concatenated pages equal ordinary exhaustive documents, reference identity, raw
  score bits, ordering, and cardinality with no gap or duplicate.

## Exact totals and snapshot behavior

- [x] Exact totals count every full query/filter match before anchor and limit on every
  accepted page; disabled totals remain absent.
- [x] A callback-counting continuation proves exact mode performs one filter evaluation
  per candidate and no second count pass.
- [x] Failed/non-publishing mutation leaves a cursor valid; successful publication
  advances the snapshot and makes it stale.
- [x] Publication after continuation snapshot capture does not invalidate the admitted
  call; hits, exact total, and next cursor all come from the captured old snapshot.
- [x] Close after admission cannot produce a mixed or partial page.

## Evidence and regression boundary

- [x] `V33SearchAfterBenchmark` isolates page depth, corpus score shape, and disabled
  versus exact continuation without modifying either frozen cloud family.
- [x] A reviewed three-fork local run covers depth 1/100, dense ties/score bands, and
  disabled/exact totals on 10,000 matches with page size 10.
- [x] Phase 2 ordinary/first-page controls are rerun with three forks after cursor
  emission; their latency intervals overlap.
- [x] Continuation remains full-candidate evaluation and makes no O(page-size) or
  deep-page speedup claim. Anchor filtering reduces heap admission/allocation only.
- [x] A five-fork follow-up records JVM escape-analysis allocation bifurcation in one
  dense disabled cell as a range rather than hiding it in an unstable mean.
- [x] Commands, means, errors, allocation ranges, limitations, and conclusions are
  recorded in [the Phase 3 baseline](PHASE_3_BASELINE.md).
- [x] The retained smoke gate adds one bounded continuation-exact cell; no paid cloud
  run is required.

## Local gates

- [x] All 372 core tests pass, including exhaustive walks, query matrices, cursor
  reasons, exact count, publication, lifecycle, and retention tests.
- [x] Reactor core, five processor tests, travel example, version alignment,
  independent consumers, and isolated six-baseline artifact compatibility pass.
- [x] Strict Javadocs and release-profile source packaging pass with signing disabled.
- [x] JMH packaging and the complete retained smoke gate pass.
- [x] Diff whitespace validation passes and the locally excluded master roadmap is not
  staged.

## Phase 4 handoff

- [x] Phase 4 broadens successful/failed add-update-remove-bulk publication histories,
  dynamic index create/drop, cursor reuse/branching under controlled barriers, and
  writer progress.
- [x] Phase 4 measures retained heap for one/1,000/100,000 live cursors and full
  release, high-frequency phrase/fuzzy/dense BOOL/filter/deep-page workloads, and
  closes the evidence-backed timeout/cancellation implement-or-defer decision.
- [x] Phase 4 must not add snapshot pinning, a cursor registry, serialization, a
  timeout API, prepared queries, highlighted pagination, lower-bound totals, facets,
  aggregations, or grouping without a separately accepted contract amendment.

Phase 3 completes functional search-after. Phase 4 now hardens it under publication,
concurrency, retention, and scale before consumer/documentation release closure.
