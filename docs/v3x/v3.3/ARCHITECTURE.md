# V3.3 architecture contract

## Boundary

V3.3 adds an opt-in application-facing page API over the existing V3 ranked pipeline.
It does not add offset pagination, snapshot retention, another planner, another scoring
model, or a second query language:

```text
SearchPageRequest
  -> lifecycle admission and one current-snapshot capture
  -> cursor ownership / request / snapshot validation
  -> existing query normalization and snapshot-bound SearchPlan
  -> existing candidate, filter, match, and score evaluation
  -> strict ordering after the cursor anchor
  -> bounded page retention plus optional exact match count
  -> SearchPageResult
```

The embedded `SearchRequest` retains exactly its published query, filter, limit, BM25,
validation, and failure semantics. The first disabled-total page returns the same
documents, score bits, order, and cardinality as ordinary `search(SearchRequest)`.

## Separate page façade

V3.3 does not add fields or methods to the published `SearchRequest`, `SearchResult`,
`SearchHit`, or highlighted result family. It introduces a distinct immutable
`SearchPageRequest<T>` wrapper, `SearchPageResult<T>` result, opaque
`SearchAfterCursor`, and `TotalHitsMode`.

`SearchEngine` receives one additive default `search(SearchPageRequest)` overload.
Existing implementations remain binary-compatible and reject the capability until
they override it. Ordinary search, highlighted search, Explain, and legacy ranked
search do not construct page or cursor objects.

This isolated façade prevents pagination policy from silently changing the ordinary
V3 result contract. Structured highlighted pagination requires a separate accepted
composition contract and is not implied by this foundation.

## Strict current-snapshot continuation

The built-in cursor is engine-owned, immutable, and opaque. It binds:

- the built-in engine instance;
- the exact immutable `SearchRequest` object used for the first page;
- the captured snapshot version;
- the last returned score as raw `double` bits; and
- the last returned internal document ID.

Only the built-in cursor implementation knows those values. The public cursor marker
exposes no accessor, serializer, equality contract, or internal document ID.

A subsequent page captures the engine's current snapshot once. The cursor is accepted
only when it belongs to the same engine, wraps the same `SearchRequest` object, and its
snapshot version equals the captured version. A successful publication before that
capture makes the cursor stale. A publication after capture does not invalidate the
admitted invocation because the operation already owns one immutable snapshot.

The cursor does not pin, retain, or re-open an old snapshot. It retains no document,
posting, bitmap, index, plan, normalized analyzer output, or business ID. Cross-engine,
cross-request, stale, and unsupported cursor failures are distinct and deterministic.

## Canonical continuation order

The existing canonical order remains:

```text
score descending by Double.compare
then internal document ID ascending
```

For anchor `(anchorScore, anchorDocumentId)`, a matching candidate is after the anchor
exactly when its score is lower, or its score compares equal and its internal document
ID is greater. Cursor logic does not round, stringify, or recompute an anchor score.

The internal document ID remains a physical tie-break and unsupported implementation
detail. It may be carried inside the opaque built-in cursor but is never exposed as a
public cursor component or promised as a portable identity.

## Exact total hits

`TotalHitsMode.DISABLED` is the default. `EXACT` counts every document that matches the
full ranked query and structured filter in the captured snapshot, independent of page
anchor and page limit. It does not mean remaining hits after the cursor.

The current executor already evaluates every scoring candidate before retaining top-K.
The implementation accumulates exact total hits during that same evaluation; it does
not run the public query, filter, analyzer, or planner a second time. Disabled mode
returns no total value and cannot introduce a second count pass.

No lower-bound relation is defined in V3.3. A meaningful lower bound first requires an
accepted early-termination strategy such as WAND. Later work must add a new explicit
contract rather than reinterpret an absent or exact value.

## Lifecycle and publication

Paged search is an admitted read. A call starting after close fails with
`EngineRejectedExecutionException(CLOSED)`; a call admitted with one captured snapshot
may complete while close proceeds. Writers never wait for a cursor or page reader
beyond the existing immutable-snapshot reachability of that invocation.

Every successful mutation batch and dynamic index create/drop publication advances
the snapshot version and therefore stales earlier cursors. Failed, rejected, or
non-publishing operations do not. Even an index-only publication stales a cursor; V3.3
chooses one conservative rule instead of trying to prove result equivalence across
physical registry changes.

## Implementation order

Implementation proceeds only after this contract merges:

1. switch all active coordinates to `3.3.0-SNAPSHOT`, add six-baseline compatibility
   fixtures, independent ordering/count oracles, and exact-V3.2 baselines;
2. add the frozen page request/result, mode, cursor marker, exception, and default
   engine capability without enabling built-in continuation;
3. implement first-page parity and disabled/exact total hits in one evaluation;
4. implement strict cursor validation and deterministic continuation;
5. harden lifecycle, mutation, dynamic-index, concurrency, retention, and scale; and
6. close the timeout/cancellation decision before release hardening.

Prepared queries, cursor serialization, snapshot pin/release, highlighted pagination,
offset/deep pagination, lower-bound counts, facets, aggregations, grouping, persistence,
vectors, and distributed retrieval are outside this contract.
