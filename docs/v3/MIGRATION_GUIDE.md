# Migrating from 2.1 to 3.0

## Compatibility first

Migration is optional. Version 3.0 keeps the structured
`SearchEngine.search(Query<T>)` and V2 ranked
`SearchEngine.searchTopK(RankedSearchRequest<T>)` APIs supported. Existing 2.1
applications may update the dependency and continue using those paths without adopting
the V3 ranked-query model.

The core remains Java 21, runtime annotations remain processor-free, and the optional
typed-field processor remains a separate artifact. Keep core and processor versions
aligned when both are used.

## Adopt V3 ranked search incrementally

V3 separates structured eligibility from ranked relevance:

```java
SearchRequest<TravelPlace> request = SearchRequest.<TravelPlace>builder()
        .query(SearchQueries.text(description, "museum river art"))
        .filter(Query.eq(city, "Paris"))
        .limit(10)
        .build();

SearchResult<TravelPlace> result = engine.search(request);
```

The request defaults to limit 10, no structured filter, and `Bm25Config.DEFAULT`.
`SearchResult.hits()` is immutable and uses descending score with deterministic
internal-document ordering for ties.

Equivalent V2 and V3 single-field text requests share the canonical execution core.
V2 retains the terms already frozen in `TextScoringQuery`; V3 analyzes its raw text
when the request is planned against one invocation-local snapshot.

## Composition, phrase, fuzzy, and Explain

Use factory methods rather than implementation classes:

```java
SearchQuery<TravelPlace> discovery = SearchQueries.<TravelPlace>bool()
        .must(SearchQueries.text(description, "museum"))
        .should(SearchQueries.text(cityText, "Paris").boost(1.5))
        .should(SearchQueries.phrase(description, "beside the river").boost(2.0))
        .build();

SearchQuery<TravelPlace> typo =
        SearchQueries.fuzzy(description, "musuem");
```

- BOOL supports ordered MUST and SHOULD clauses. With MUST clauses, every MUST must
  match; without MUST clauses, at least one SHOULD must match.
- BOOST multiplies its child score and never changes match truth.
- PHRASE is exact positional matching only; V3.0 has no slop.
- FUZZY accepts exactly one analyzed token and uses Unicode code-point AUTO bounds of
  0, 1, or 2 edits with Optimal String Alignment. It performs complete field-vocabulary
  expansion and has no hidden truncation cap.
- Cross-field clauses use each field's own BM25 statistics; V3.0 is not BM25F.

Explain evaluates a business ID independently of the request's top-K limit:

```java
Optional<SearchExplanation<TravelPlace>> explanation =
        engine.explain(SearchRequest.of(discovery), placeId);
```

A missing business ID returns `Optional.empty()`. A present but non-matching document
returns an explanation with `matched() == false`. Descriptions are stable diagnostics
for humans, not a parseable serialization format.

## Analyzer compatibility

`Analyzer` remains a functional interface. Existing implementations and lambdas keep
working because `analyzeWithPositions(String)` has a default adapter that projects the
legacy token sequence with increment 1.

Override `analyzeWithPositions` only when the analyzer intentionally emits position
gaps or same-position alternatives. Returned lists and elements must be non-null,
terms must already satisfy the analyzer's normalization contract, and increments must
be non-negative with a positive first increment. An analyzer used by concurrent reads
must itself be thread-safe.

## Source edge case

The additive overload makes an untyped null call ambiguous:

```java
engine.search(null); // does not compile
```

Tests that intentionally pass null should cast it to either `Query<T>` or
`SearchRequest<T>`. Ordinary typed calls are unaffected.

## Recommended migration sequence

1. Upgrade core—and the optional processor when used—together.
2. Run the unchanged 2.1 application and its tests first.
3. Convert one `searchTopK` call to a V3 TEXT request and compare hits, scores, and
   ordering on representative data.
4. Add BOOL/BOOST, PHRASE, or FUZZY only where their frozen semantics match the product
   requirement.
5. Add Explain for diagnostics, not as a persisted or machine-parsed score schema.

The complete runnable adoption path is the
[travel example](../../examples/travel-search/README.md). Supported descriptors and
the intentional hidden package bridges are recorded in
[API compatibility](API_COMPATIBILITY.md).
