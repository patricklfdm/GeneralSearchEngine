# Migrating from 3.1 to 3.2

V3.2 is additive. Existing V1, V2, V3.0, and V3.1 search code can upgrade without
changing query construction, analyzers, result handling, or index configuration.
Applications opt in only when they need exact source offsets or structured
highlighting.

## Dependency

Published `3.2.0` is available from Maven Central. Update both the runtime and optional
processor together:

```xml
<dependency>
    <groupId>io.github.patricklfdm</groupId>
    <artifactId>general-search-engine</artifactId>
    <version>3.2.0</version>
</dependency>
```

No Java, Maven, annotation, generated-source, or service-entry requirement changes.
V3.2 still requires Java 21 and Maven 3.9 or newer.

## Existing code remains unchanged

The following remain source- and binary-compatible:

- `Analyzer` lambdas and custom implementations;
- the two-component `AnalyzedToken` record;
- structured `Query<T>`, V2 `RankedSearchRequest`, and V3 `SearchRequest` execution;
- TEXT, exact/sloppy PHRASE, FUZZY, BOOL/BOOST, filtering, BM25, and Explain semantics;
- schema, index, mutation, lifecycle, and snapshot behavior; and
- V3.1 phrase-slop and `minimumShouldMatch` APIs and defaults.

The built-in `SimpleAnalyzer` now also implements `OffsetAnalyzer`, while its ordinary
`analyze` and `analyzeWithPositions` output remains identical.

## Request structured highlights

Wrap an existing immutable `SearchRequest` and select one or more canonical text
fields:

```java
SearchRequest<TravelPlace> ranked = SearchRequest.of(
        SearchQueries.phrase(description, "museum beside the river", 1)
);

HighlightedSearchResult<TravelPlace> highlighted = engine.search(
        HighlightedSearchRequest.<TravelPlace>builder(ranked)
                .field(description)
                .contextCharacters(40)
                .maxFragmentsPerField(3)
                .build()
);
```

The wrapped `SearchHit` values are canonical: highlighting cannot change match truth,
score bits, order, filter behavior, or limit. The engine obtains hits and source text
from one captured immutable snapshot.

Requested field order is retained. Defaults are 40 UTF-16 context units on each side
and three fragments per field. At least one field is required, context may be zero,
and the fragment cap must be positive.

## Render safely in the application

`HighlightFragment.text()` is the exact source substring. Fragment and span offsets
are absolute, zero-based, half-open UTF-16 indices into the original Java string:

```java
for (HighlightedSearchHit<TravelPlace> resultHit : highlighted.hits()) {
    for (FieldHighlight field : resultHit.highlights()) {
        for (HighlightFragment fragment : field.fragments()) {
            String text = fragment.text();
            for (HighlightSpan span : fragment.spans()) {
                int relativeStart = span.startOffset() - fragment.startOffset();
                int relativeEnd = span.endOffset() - fragment.startOffset();
                String matchedSource = text.substring(relativeStart, relativeEnd);
                // Escape text and apply presentation markup in the application.
            }
        }
    }
}
```

The library deliberately emits no HTML and performs no escaping. Escape untrusted
source text before inserting markup. Spans are ordered, non-overlapping, and contained
by their fragment.

## Implement a custom offset analyzer

Use `OffsetAnalyzer` only when the application can provide exact mappings back to the
original string:

```java
OffsetAnalyzer analyzer = text -> List.of(
        new OffsetAnalyzedToken(text.toLowerCase(Locale.ROOT), 1, 0, text.length())
);
```

Every range is into the exact input string, must be non-empty and in bounds, and must
not split a surrogate pair. Term/position projection must equal ordinary analysis.
Sequence validation rejects malformed output before a partial result can escape.

A legacy `Analyzer` remains valid for indexing and all ordinary searches. If its exact
canonical field is explicitly requested for highlighting, the operation fails
deterministically with unsupported capability rather than inventing approximate
offsets.

## Operational characteristics

V3.2 stores no offsets in postings, snapshots, or a sidecar. It re-extracts and
offset-analyzes only explicitly requested fields of returned top-K documents. This
keeps ordinary index shape and ordinary search allocation unchanged, but an explicit
highlight request pays work proportional to returned hits, requested fields, source
length, query evidence, and fragment construction.

Accepted documents remain immutable. Mutating a document object after insertion was
already outside the engine contract and cannot provide source/index consistency.

## Upgrade checklist

1. Upgrade runtime and processor together.
2. Run the existing application suite without enabling highlighting.
3. Use canonical `TextField` instances from the engine/schema.
4. Keep legacy analyzers unless exact highlighting is required.
5. For custom offset analyzers, test Unicode normalization and surrogate boundaries.
6. Treat all offsets as UTF-16 source coordinates, not code-point or byte indices.
7. Escape source text and own all markup/display policy in the application.
8. Compare wrapped highlighted hits with the application's ordinary ranked results.

See [token metadata and offsets](TOKEN_METADATA_AND_OFFSETS.md),
[structured highlighting](HIGHLIGHTING.md), and
[API compatibility](API_COMPATIBILITY.md) for the complete frozen contracts.
