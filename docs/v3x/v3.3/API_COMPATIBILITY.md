# V3.3 API compatibility contract

## Published baselines

V3.3 must remain additive to published `1.0.0`, `2.0.0`, `2.1.0`, `3.0.0`, `3.1.0`,
and `3.2.0`. Normal and fresh-isolated `artifact-compat` runs compare the candidate
core JAR with all six artifacts. The pinned V3 identities fail closed:

```text
3.0.0 core SHA-256
3b0ed72877f3c5f2ef225d1a87cac8d9546b109c91c0bec8d8dcea12e2d101f2

3.1.0 core SHA-256
d77309b58ceca6b6515177a1edbed20f88d59ec5e3ec9330173e282d53d6c86c

3.2.0 core SHA-256
8cf029b43bdd57ce93c06d71e007f1404c2d1c02c4d4dc6779461dabcd051c1c
```

No baseline may resolve from an unverified local same-coordinate install. The V1 and
V3.2 reflection/source fixtures, V1/V2/V3 independent consumers, processor, generated
sources, and travel example remain mandatory.

Phase 0 left every active project and consumer coordinate at final `3.2.0`. Phase 1
converted them atomically to `3.3.0-SNAPSHOT`; Phase 5 converted all seven active
coordinates atomically to final `3.3.0` after Phases 1–4 were accepted.

## Frozen supported additions

The required V3.3 foundation authorizes exactly these public types:

```java
// io.github.patricklfdm.generalsearch.search
public interface SearchAfterCursor {
}

public enum TotalHitsMode {
    DISABLED,
    EXACT
}

public final class SearchPageRequest<T> { ... }
public final class SearchPageResult<T> { ... }

// io.github.patricklfdm.generalsearch.engine.exception
public final class SearchCursorException extends SearchEngineException { ... }
```

`SearchAfterCursor` is an engine-owned marker, not an application SPI consumed by the
built-in engine. It intentionally declares no method.

## Page request shape

`SearchPageRequest` and its final nested builder expose exactly:

```java
public static <T> SearchPageRequest.Builder<T> builder(
        SearchRequest<T> searchRequest
);

public SearchRequest<T> searchRequest();
public Optional<SearchAfterCursor> after();
public TotalHitsMode totalHitsMode();

public Builder<T> after(SearchAfterCursor cursor);
public Builder<T> totalHits(TotalHitsMode mode);
public SearchPageRequest<T> build();
```

The builder requires a non-null immutable `SearchRequest`, defaults to no cursor and
`DISABLED`, rejects null cursor/mode at the setter, is reusable but not thread-safe,
and captures one immutable request snapshot at `build()`.

It exposes no page-number, offset, mutable token bytes, snapshot version, score anchor,
document ID, cursor TTL, or timeout field.

## Page result shape

`SearchPageResult` exposes exactly:

```java
public static <T> SearchPageResult<T> withoutTotalHits(
        List<SearchHit<T>> hits
);

public static <T> SearchPageResult<T> withoutTotalHits(
        List<SearchHit<T>> hits,
        SearchAfterCursor nextCursor
);

public static <T> SearchPageResult<T> withExactTotalHits(
        List<SearchHit<T>> hits,
        long exactTotalHits
);

public static <T> SearchPageResult<T> withExactTotalHits(
        List<SearchHit<T>> hits,
        SearchAfterCursor nextCursor,
        long exactTotalHits
);

public List<SearchHit<T>> hits();
public Optional<SearchAfterCursor> nextCursor();
public OptionalLong totalHits();
```

The overloads without a cursor represent the final page. Cursor overloads require a
non-null cursor; the public accessor never returns null. The hit list is defensively
copied and contains no null. Exact total hits are non-negative. No constructor,
mutator, subclass hook, relation sentinel, nullable optional input, or internal cursor
accessor is public.

These factories allow a third-party engine to return a page with its own cursor type.

## Cursor exception shape

The exception surface is:

```java
public final class SearchCursorException extends SearchEngineException {
    public enum Reason {
        UNSUPPORTED_CURSOR,
        DIFFERENT_ENGINE,
        DIFFERENT_REQUEST,
        STALE_SNAPSHOT
    }

    public SearchCursorException(Reason reason);
    public Reason reason();
}
```

The constructor rejects null and creates the frozen non-sensitive message for its
reason. No engine token, request reference, snapshot version, score, or document ID is
available through the exception.

## Additive engine capability

`SearchEngine<K,T>` receives exactly one new default method:

```java
default SearchPageResult<T> search(SearchPageRequest<T> request)
```

The default implementation null-checks the request and otherwise throws
`UnsupportedOperationException`. Existing third-party implementations remain binary
compatible. The built-in `SnapshotSearchEngine` adds the corresponding override.

The new overload is unambiguous for a typed `SearchPageRequest`. Untyped
`search(null)` is already unsupported because published overloads are ambiguous; V3.3
does not promise source compatibility for that pattern.

## Existing public surface remains unchanged

V3.3 adds no method, constructor, component, enum constant, or behavior to:

- `SearchRequest`, `SearchRequest.Builder`, `SearchResult`, or `SearchHit`;
- `HighlightedSearchRequest` or any highlighted result value;
- `SearchQuery`, `SearchQueries`, or ranked query-node façades;
- `Query`, schemas, fields, analyzers, tokens, ranking configuration, or Explain;
- mutation, index lifecycle, engine configuration, or metrics values; and
- the annotation processor or generated schema/field shape.

Ordinary `search(SearchRequest)` therefore retains its exact result and allocation
shape. A user opts into pagination only by constructing `SearchPageRequest`.

## Unsupported implementation types

The built-in cursor implementation, cursor owner token, request reference, snapshot
version, score bits, internal document ID, page accumulator, count accumulator,
continuation comparator, normalized input, plan, posting, bitmap, snapshot, and
physical field/index identities remain package-private and unsupported.

The existing Javadoc-hidden execution bridge may receive one page sibling method when
required by the built-in package layout. That bytecode-public bridge is unsupported and
must not appear in application examples or independent consumers.

## Deferred public surface

Phase 0 authorizes no serializable cursor, cursor codec, snapshot handle, pin/release
API, lower-bound relation, timeout/deadline token, cancellation source, prepared query,
highlighted page wrapper, aggregation/facet result, page number, offset, or public
internal/business-ID tie-break field.

Any accepted timeout/cancellation or highlighted-pagination design requires a Phase 0
amendment and a new descriptor/source fixture before production implementation.

## Post-publication baseline

Published `3.3.0` contains exactly the frozen additive page family and default engine
capability above. V1/V2 consumers remain source-unchanged. The V3 consumer uses only
supported APIs to execute two pages and verify exact totals. Fresh-isolated Japicmp
comparison against all six earlier published baselines passed before release.

The published `3.3.0` core JAR resolves from Maven Central with SHA-256:

```text
3.3.0 core SHA-256
18fb6439be074b39e5f22e2b01fba327ee919a4997e6429551481ef7fb8754f4
```

That value matches the reproducible final main-JAR hash recorded before tagging.
Future candidates compare against all seven published versions: `1.0.0`, `2.0.0`,
`2.1.0`, `3.0.0`, `3.1.0`, `3.2.0`, and `3.3.0`. The `3.3.0` coordinate and pinned
hash are immutable.
