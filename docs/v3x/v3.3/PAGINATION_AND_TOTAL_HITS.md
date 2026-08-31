# V3.3 pagination and total-hits contract

## Request model

The required request shape is:

```java
SearchPageRequest<TravelPlace> first = SearchPageRequest
        .builder(searchRequest)
        .totalHits(TotalHitsMode.EXACT)
        .build();

SearchPageResult<TravelPlace> page = engine.search(first);

SearchPageResult<TravelPlace> next = page.nextCursor()
        .map(cursor -> engine.search(SearchPageRequest
                .builder(searchRequest)
                .after(cursor)
                .totalHits(TotalHitsMode.EXACT)
                .build()))
        .orElseThrow();
```

The exact same immutable `searchRequest` object must be reused for continuation. This
is deliberate: arbitrary application `Query<T>` filters and analyzer/field objects do
not have a portable structural identity. V3.3 does not invent equality for consumer
lambdas or mutable third-party query implementations.

The builder defaults to no cursor and `TotalHitsMode.DISABLED`. The wrapped
`SearchRequest.limit()` is the page size. It remains positive and cannot change during
one cursor chain because request identity is fixed.

## Cursor ownership

`SearchAfterCursor` is an opaque engine-owned marker. Applications may retain it and
pass it back to a page request, but must not expect:

- public fields or accessors;
- a stable string or byte representation;
- equality or hash semantics;
- portability across engine instances or process restarts;
- compatibility with another request object, even one that appears equivalent; or
- validity after any successful snapshot publication.

The interface permits another `SearchEngine` implementation to return its own opaque
cursor type. The built-in engine accepts only its own implementation. Application-made
or foreign implementations fail as `UNSUPPORTED_CURSOR` rather than being cast or
interpreted.

Reusing an accepted cursor is deterministic and idempotent while the engine snapshot
and request remain the same. A cursor is not consumed or invalidated by a read.

## Cursor failure contract

Built-in cursor rejection uses `SearchCursorException` and this frozen reason order:

1. `UNSUPPORTED_CURSOR` — the object is not a built-in cursor;
2. `DIFFERENT_ENGINE` — it came from another built-in engine instance;
3. `DIFFERENT_REQUEST` — it is not bound to the exact wrapped request object; and
4. `STALE_SNAPSHOT` — the current captured version differs from the cursor version.

The first applicable reason wins. Cursor validation occurs after closed-engine
admission and before query normalization/planning, so `CLOSED` wins over cursor
failures and a cursor reason wins over later query/index/analyzer failures.

The exception exposes only its reason. It does not reveal engine identity, snapshot
version, score bits, internal document ID, query structure, or retained objects.

## First-page parity

For a request with no cursor and total hits disabled:

```text
engine.search(SearchPageRequest.builder(request).build()).hits()
```

must equal:

```text
engine.search(request).hits()
```

in document reference, raw score bits, ordering, and cardinality. Both capture their
own current snapshot; parity comparisons therefore use a controlled unchanged state.

Enabling exact total hits cannot change the hit list. It adds only one exact count.

## Continuation semantics

The full result order is the existing deterministic score/doc-ID order. Each page:

- excludes the anchor and every better candidate;
- retains at most the wrapped request limit;
- contains no duplicate within the page;
- returns only candidates strictly after the anchor;
- emits a next cursor only when at least one later matching candidate exists; and
- anchors the next cursor to the last returned hit.

An empty corpus or no-match query returns an empty page, no cursor, and exact total
zero when requested. A final non-empty page returns no cursor. A page after a valid
anchor may be empty only when no later hit exists, in which case no new cursor exists.

Walking pages without publication must produce every matching hit exactly once in the
same order as an independent exhaustive sort. The concatenated list is independent of
page size, except that page size is fixed by the request object for one cursor chain.

## Score and tie behavior

Continuation uses `Double.compare`, matching the existing executor. The cursor carries
the raw score bits produced for the anchor. It never uses decimal text, epsilon
comparison, rounded score, business-ID comparison, or document object equality.

Dense equal-score fixtures are mandatory because internal document ID is the only tie
break. The ID remains hidden; tests may observe it only through package-private
fixtures and an independent expected order.

If deterministic application code and the same snapshot produce a score different
from the cursor anchor, that indicates a correctness violation. V3.3 does not weaken
ordering to tolerate mutable analyzers, filters, fields, or documents; those already
violate the engine contract.

## Total-hits semantics

`TotalHitsMode` has exactly:

```java
DISABLED
EXACT
```

Disabled results expose `OptionalLong.empty()`. Exact results expose a present,
non-negative `long`. Exact total hits count all full-query/filter matches in the
captured snapshot:

- before applying the cursor anchor;
- before applying the page limit;
- after structured filter evaluation;
- after ranked match evaluation; and
- regardless of whether a score is zero.

The value therefore remains the same on every accepted page in a cursor chain. The
count does not include non-matching candidates, removed documents, or documents
rejected by the filter.

The executor may use an `int` candidate space internally, but the public result uses
`long` and checks overflow. It cannot use `-1`, `Long.MAX_VALUE`, or another sentinel
for disabled or lower-bound status.

## Result construction

`SearchPageResult<T>` is immutable and copies its ordered hit list. Four public factory
overloads distinguish disabled/exact totals and final/continuable pages:

```java
SearchPageResult.withoutTotalHits(hits)
SearchPageResult.withoutTotalHits(hits, nextCursor)
SearchPageResult.withExactTotalHits(hits, exactTotalHits)
SearchPageResult.withExactTotalHits(hits, nextCursor, exactTotalHits)
```

The overloads without a cursor represent the final page. Cursor overloads reject null,
and the accessor returns `Optional<SearchAfterCursor>`. Hit lists and elements are
non-null. Exact totals are non-negative. Factories and accessors do not expose an
implementation cursor.

Third-party engines may construct results and use their own cursor implementation.
The built-in engine makes no promise to consume those cursors.

## Snapshot transitions

The following successful publications stale a cursor:

- add, update, remove, and their atomic bulk forms;
- document removal followed by re-add;
- dynamic index creation after scan/replay publication; and
- dynamic index drop when it publishes a changed registry.

Failed analysis, failed extractor work, invalid bulk input, queue rejection, cancelled
index build, and other operations that publish no new snapshot leave it valid. Tests
assert observed version behavior instead of guessing from future completion alone.

The stale rule is intentionally conservative. V3.3 does not continue across a mutation
by relying on score/doc-ID anchors, because updates can move hits across the anchor and
add/remove can create gaps or duplicates.

## Explicit exclusions

V3.3 Phase 0 authorizes no cursor serialization/signing, persistence across restart,
old-snapshot registry, cursor TTL, cursor cleanup thread, public snapshot version,
business-ID tie-break replacement, deep offset, random page number, bidirectional
cursor, lower-bound/estimated count, highlighted page result, or aggregation count.

Any snapshot-pinning design must freeze acquisition, release, retention limits,
close behavior, memory accounting, and misuse recovery before changing the strict
stale-cursor contract.
