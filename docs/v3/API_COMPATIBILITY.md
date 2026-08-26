# GeneralSearchEngine v3 API compatibility

## Baseline

V3 development is additive to the application APIs published in `1.0.0`, `2.0.0`, and
`2.1.0`. The artifact compatibility profile compares the current core JAR directly
against all three published core artifacts. The frozen v1 source/reflection fixture and
independent v1-, v2-, and v3-style consumers provide separate source-level coverage.

The optional processor remains covered by its compilation, generated-consumer,
Javadoc, service-entry, and release-artifact checks. Phase 0 does not establish a new
processor-specific Japicmp policy.

## Existing APIs

Phase 0 does not change the behavior of:

```java
List<T> SearchEngine.search(Query<T> query)
List<SearchHit<T>> SearchEngine.searchTopK(RankedSearchRequest<T> request)
```

The v2 ranking types `TextScoringQuery`, `RankedSearchRequest`, `SearchHit`, and
`Bm25Config` remain supported and are neither moved nor deprecated.

## Additive capabilities

The new overload and Explain capability are default interface methods:

```java
SearchResult<T> SearchEngine.search(SearchRequest<T> request)

Optional<SearchExplanation<T>> SearchEngine.explain(
        SearchRequest<T> request,
        K id
)
```

Previously compiled third-party `SearchEngine` implementations therefore continue to
link. Until an implementation overrides these capabilities, non-null calls fail with
`UnsupportedOperationException`; null arguments fail first with `NullPointerException`.

## Accepted null-literal ambiguity

Adding `search(SearchRequest<T>)` creates one narrow source-resolution incompatibility:

```java
engine.search(null); // ambiguous
```

The compiler cannot choose between the unrelated `Query<T>` and `SearchRequest<T>`
parameter types. Callers that intentionally test null behavior must cast explicitly:

```java
engine.search((Query<MyDocument>) null);
engine.search((SearchRequest<MyDocument>) null);
```

Ordinary typed calls remain source compatible. This accepted edge case is not detected
by Japicmp and is not a reason to rename the V3 overload.

## Future Analyzer addition

A later phase will add `AnalyzedToken` and the default
`Analyzer.analyzeWithPositions(String)` method frozen in the positional contract. It is
not implemented in Phase 0. The future default method must preserve `Analyzer` as a
functional interface and keep existing analyzer implementations source- and
binary-compatible.
