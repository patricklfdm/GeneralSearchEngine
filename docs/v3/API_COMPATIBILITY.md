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

## Phase 3 internal execution bridge

The frozen Phase 3 package layout keeps `SearchQueryNode`, `SearchPlanner`, `SearchPlan`,
and `SearchExecutor` package-private in
`io.github.patricklfdm.generalsearch.search`. Java sibling-package access requires one
narrow bytecode-public `SearchExecutionAccess` bridge for the built-in engine and the
legacy ranking façade.

This bridge is Javadoc-hidden and explicitly unsupported application infrastructure.
Its Java visibility is not permission to expose query nodes, plans, postings, candidate
bitmaps, positions, or internal document IDs. It performs complete request execution
only. No method is added to the supported `SearchQuery` façade to reveal its internal
representation.

Japicmp may report the bridge as an additive class after Phase 3 implementation. The
supported compatibility surface remains the existing public request, result, engine,
ranking, schema, query, and index APIs. The bridge carries no application compatibility
guarantee and exists only to accommodate the current package boundaries without using
reflection or widening the query-tree API.

## Phase 4 internal ranked composition

Phase 4 implements the BOOL and BOOST façades already added and frozen in Phase 0. It
adds no supported public type, method, field, constructor, or descriptor. Cross-field
ranked search is ordinary composition of existing `SearchQueries.text(...)` leaves on
different existing canonical `TextField<T>` values.

The normalized recursive query representation, `TextPlan`/`BoolPlan`/`BoostPlan`
equivalents, matched-plus-score value, prepared postings/statistics, and candidate
bitmaps remain package-private. The existing Javadoc-hidden `SearchExecutionAccess`
class remains the only bytecode-public bridge, continues to expose complete execution
only, and does not reveal or accept any Phase 4 internal representation.

Japicmp is therefore expected to report no Phase 4 public addition. The normal and
isolated artifact comparisons against 1.0.0, 2.0.0, and 2.1.0, the frozen v1 fixture,
and the independent v1-, v2-, and v3-style consumers remain mandatory. Third-party
`SearchEngine` implementations retain the existing default unsupported V3 behavior,
and all V2 ranked descriptors and frozen-term execution semantics remain unchanged.

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

## Position-aware Analyzer addition

Phase 1 added `AnalyzedToken` and the default
`Analyzer.analyzeWithPositions(String)` method frozen in the positional contract.
`Analyzer` remains a functional interface, and existing implementations inherit a
default all-ones projection of their unchanged legacy token output.

Phase 2 is the first production consumer. Existing pre-Phase-1 analyzers retain their
published text and BM25 behavior through the default adapter. V3-native positional
overrides become active consistently across indexed, scan, and BM25 term projection so
an exact text index cannot drift from its scan predicate. `TextField.analyzeDocument(T)`
retains its existing descriptor and legacy behavior, and no public posting-positions API
is added.
