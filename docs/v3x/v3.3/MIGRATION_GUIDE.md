# Migrating from 3.2 to 3.3

V3.3 is additive. Existing V1, V2, V3.0, V3.1, and V3.2 applications can upgrade
without changing query construction, ranking, highlighting, mutation, index, or
lifecycle code. Applications opt in only by wrapping an existing immutable
`SearchRequest` in `SearchPageRequest`.

## Dependency

The final candidate uses one aligned version for the runtime and optional processor:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>3.3.0</version>
</dependency>
```

Until the signed release workflow and clean remote verification complete, `3.3.0`
must be built from this checkout and must not be assumed to exist on Maven Central.
Published `3.2.0` remains the stable dependency. Java 21 and Maven 3.9 or newer remain
required.

## Existing code remains unchanged

The following retain their published behavior and descriptors:

- structured `Query<T>`, ranked `SearchRequest`, highlighted requests, and Explain;
- TEXT, PHRASE/slop, FUZZY, BOOL/BOOST, filtering, BM25, and canonical ordering;
- analyzers, source offsets, highlight fragments/spans, schemas, and generated fields;
- add/update/remove/bulk mutation, dynamic indexes, close, metrics, and publication;
  and
- every ordinary `search(...)` overload and its existing allocation/result shape.

Third-party `SearchEngine` implementations compile unchanged because the page
capability is a default method. Unless they override it, a non-null page request is
rejected with `UnsupportedOperationException`.

## Request a first page

Create one immutable ranked request with the desired page size, then wrap it:

```java
SearchRequest<TravelPlace> request = SearchRequest
        .<TravelPlace>builder()
        .query(SearchQueries.text(description, "museum"))
        .filter(Query.eq(city, "Paris"))
        .limit(20)
        .build();

SearchPageResult<TravelPlace> first = engine.search(
        SearchPageRequest.<TravelPlace>builder(request).build()
);
```

The default `TotalHitsMode.DISABLED` avoids promising a count. Hits on the first page
are bit-for-bit equivalent to ordinary `engine.search(request).hits()` for the same
captured snapshot. `nextCursor()` is present only when another match exists.

## Continue with the exact request object

The built-in cursor binds the engine, the exact `SearchRequest` object, and the
captured snapshot version:

```java
SearchPageResult<TravelPlace> second = engine.search(
        SearchPageRequest.<TravelPlace>builder(request)
                .after(first.nextCursor().orElseThrow())
                .build()
);
```

Do not rebuild an equivalent-looking request. Request identity is intentional: using
a different object fails with `SearchCursorException.Reason.DIFFERENT_REQUEST`.
Using the cursor with another engine fails as `DIFFERENT_ENGINE`; an application-made
cursor fails as `UNSUPPORTED_CURSOR`.

The cursor is opaque and process-local. Do not serialize it, inspect it, send it to
another service, or persist it as a resumable token.

## Request exact totals explicitly

Exact totals are opt-in on each page wrapper:

```java
SearchPageResult<TravelPlace> page = engine.search(
        SearchPageRequest.<TravelPlace>builder(request)
                .totalHits(TotalHitsMode.EXACT)
                .build()
);

long fullMatchCount = page.totalHits().orElseThrow();
```

The value counts the full query/filter match set before cursor and limit. Every page
in one unchanged chain reports the same value. It does not count returned or remaining
hits and has no lower-bound relation. Disabled mode returns `OptionalLong.empty()`.

Total mode is not part of cursor identity, so callers may branch from one cursor with
disabled or exact totals while retaining the exact wrapped request object.

## Handle publication and lifecycle

Any successful document or dynamic-index publication before the continuation captures
its snapshot makes the earlier cursor stale:

```java
try {
    engine.search(SearchPageRequest.<TravelPlace>builder(request)
            .after(cursor)
            .build());
} catch (SearchCursorException exception) {
    if (exception.reason()
            == SearchCursorException.Reason.STALE_SNAPSHOT) {
        // Restart from the first page using the current snapshot.
    }
}
```

Failed or non-publishing work does not invalidate a cursor. A page already admitted
and captured before a later publication finishes wholly from its captured snapshot.
Calling after close fails as `CLOSED` before cursor inspection.

The strict rule avoids retained snapshot registries and unbounded cursor state. A
cursor does not pin an old snapshot and does not block the asynchronous writer.

## Unsupported combinations

V3.3 does not add:

- highlighted pagination;
- offset/page-number pagination or a deep-offset API;
- cursor codecs, TTLs, snapshot pin/release, or cross-process resume;
- lower-bound total-hit relations;
- timeout/cancellation or prepared queries; or
- facets, aggregations, and grouping.

Keep using ordinary highlighted requests when source fragments are required. The
timeout/cancellation and prepared-query decisions are explicitly deferred rather than
represented by placeholder APIs.

## Upgrade checklist

1. Upgrade runtime and processor coordinates together.
2. Run the existing suite without constructing `SearchPageRequest`.
3. Reuse one immutable `SearchRequest` object for the complete cursor chain.
4. Treat `nextCursor()` as optional and stop when it is empty.
5. Request exact totals only when the full-match count is needed.
6. Restart from page one after `STALE_SNAPSHOT`.
7. Never serialize, share across engines, or retain cursors as snapshot handles.
8. Keep highlighting, offsets, lower-bound totals, and timeout controls outside the
   page API.

See [pagination and total-hits semantics](PAGINATION_AND_TOTAL_HITS.md),
[API compatibility](API_COMPATIBILITY.md), and [validation](VALIDATION.md) for the
complete frozen contract.
