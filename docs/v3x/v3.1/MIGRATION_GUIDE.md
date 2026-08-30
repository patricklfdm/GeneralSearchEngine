# Migrating from GeneralSearchEngine 3.0 to 3.1

## Release state

V3.1.0 was published to Maven Central on August 30, 2026 from the signed `v3.1.0`
tag. Upgrade the runtime dependency and, when used, the optional annotation processor
to `3.1.0`:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>3.1.0</version>
</dependency>
```

This guide describes the frozen source-compatible upgrade from published `3.0.0`.

## Compatibility

V3.1 is additive. Existing applications can upgrade without changing calls to
structured `search(Query)`, V2 `searchTopK`, V3 `search(SearchRequest)`, Explain,
mutations, schema configuration, analyzers, or dynamic-index lifecycle methods.

The existing forms retain their behavior:

```java
SearchQueries.phrase(description, "museum beside the river"); // exact, slop zero

SearchQueries.<TravelPlace>bool()
        .must(SearchQueries.text(description, "museum"))
        .should(SearchQueries.text(cityText, "Paris"))
        .build(); // unchanged implicit SHOULD minimum
```

`Analyzer` remains a functional interface, `AnalyzedToken` is unchanged, and no
processor or generated-source migration is required.

## Ordered phrase slop

Use the new overload when terms must stay ordered but may have additional gaps:

```java
SearchQuery<TravelPlace> query = SearchQueries.phrase(
        description,
        "museum river",
        2
);
```

The third argument is a non-negative total extra-gap budget above the analyzed query's
minimum position gaps. It is not a term-reordering distance: transposition never
matches. Slop changes match truth only; a matching phrase keeps the existing
distinct-term, field-local BM25 score. Negative slop fails immediately. The
two-argument factory is exactly equivalent to an explicit zero.

## Explicit BOOL SHOULD thresholds

Use `minimumShouldMatch` when a ranked BOOL must match an exact number of declared
SHOULD clause occurrences:

```java
SearchQuery<TravelPlace> query = SearchQueries.<TravelPlace>bool()
        .should(SearchQueries.text(description, "museum"))
        .should(SearchQueries.text(description, "river"))
        .should(SearchQueries.text(cityText, "Paris"))
        .minimumShouldMatch(2)
        .build();
```

Occurrences are counted in builder order; duplicate clauses are not deduplicated.
Every matching child still contributes its score after the threshold is met. A
negative value fails when configured, a value above the declared SHOULD count fails at
`build()`, and explicit zero is accepted only when at least one MUST clause exists.
When the method is never called, the V3.0 defaults remain: zero required SHOULD clauses
with a MUST, otherwise one.

## Fuzzy search

No fuzzy source migration is needed. V3.1 replaces the internal complete vocabulary
scan with a persistent Unicode code-point trie and exact bounded OSA traversal. The
public factory, AUTO distance, accepted expansions, match truth, scoring, ordering,
Explain output, and absence of a hidden expansion cap remain unchanged.

## Validation before adoption

For a local candidate build:

```bash
./mvnw -f reactor/pom.xml clean test
scripts/verify-consumer-projects.sh
scripts/run-travel-example.sh
```

The independent V3 consumer compiles and executes both additions using only supported
public APIs. The full semantics are frozen in
[ranked-search semantics](RANKED_SEARCH_SEMANTICS.md), and the accepted binary/source
surface is recorded in [API compatibility](API_COMPATIBILITY.md).
