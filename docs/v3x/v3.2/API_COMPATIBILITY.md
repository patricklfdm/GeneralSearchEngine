# V3.2 API compatibility contract

## Baselines

V3.2 is additive to published `1.0.0`, `2.0.0`, `2.1.0`, `3.0.0`, and `3.1.0`.
Normal and fresh-isolated `artifact-compat` runs must compare the candidate core JAR
with all five artifacts. The pinned published 3.0.0 and 3.1.0 JAR identities remain
fail-closed; no baseline may resolve from an unverified locally installed candidate.

The frozen V1 reflection/source fixture, V1/V2/V3 independent consumers, processor,
generated sources, and travel example remain mandatory. Phase 0 changes no project
version. The later implementation entry change to `3.2.0-SNAPSHOT` must update core,
processor, reactor, examples, and current consumer properties atomically.

## Final Phase 6 API audit

Fresh-isolated Japicmp against published `3.1.0` reports only the frozen additive
surface:

- new public `OffsetAnalyzer` and `OffsetAnalyzedToken` analysis types;
- `SimpleAnalyzer` additionally implements `OffsetAnalyzer` and exposes the required
  offset method while retaining its ordinary methods;
- one new default highlighted-search overload on `SearchEngine` and its concrete
  `SnapshotSearchEngine` override;
- the six final highlighted request/result types plus the final nested request
  builder; and
- `SearchExecutionAccess.searchHighlighted`, a Javadoc-hidden sibling-package bridge
  required by the built-in engine layout.

The concrete override and hidden bridge are implementation consequences, not separate
application extension points. The bridge remains unsupported alongside the existing
search and Explain bridge methods. Japicmp reports no removed class, method, field,
constructor, interface, or generic contract and recommends an additive minor version.
The same candidate passes comparisons with all five published baselines.

## Frozen supported additions

The only supported Phase 0 additions authorized for the required V3.2 foundation are:

```java
// io.github.patricklfdm.generalsearch.analysis
public record OffsetAnalyzedToken(
        String term,
        int positionIncrement,
        int startOffset,
        int endOffset
)

@FunctionalInterface
public interface OffsetAnalyzer extends Analyzer {
    List<OffsetAnalyzedToken> analyzeWithOffsets(String text);
    default List<Token> analyze(String text);
    default List<AnalyzedToken> analyzeWithPositions(String text);
}

// io.github.patricklfdm.generalsearch.engine.SearchEngine
default HighlightedSearchResult<T> search(
        HighlightedSearchRequest<T> request
)
```

The search package adds these final immutable façade/value types:

```text
HighlightedSearchRequest<T>
HighlightedSearchRequest.Builder<T>
HighlightedSearchResult<T>
HighlightedSearchHit<T>
FieldHighlight
HighlightFragment
HighlightSpan
```

The request and builder expose exactly this shape:

```java
public static <T> HighlightedSearchRequest.Builder<T> builder(
        SearchRequest<T> searchRequest
);

public SearchRequest<T> searchRequest();
public List<TextField<T>> fields();
public int contextCharacters();
public int maxFragmentsPerField();

public Builder<T> field(TextField<T> field);
public Builder<T> contextCharacters(int contextCharacters);
public Builder<T> maxFragmentsPerField(int maxFragmentsPerField);
public HighlightedSearchRequest<T> build();
```

The builder is the only supported request construction path. The result values expose
exactly these public constructors and accessors:

```java
public HighlightedSearchResult(List<HighlightedSearchHit<T>> hits);
public List<HighlightedSearchHit<T>> hits();

public HighlightedSearchHit(
        SearchHit<T> hit,
        List<FieldHighlight> highlights
);
public SearchHit<T> hit();
public List<FieldHighlight> highlights();

public FieldHighlight(
        String fieldName,
        List<HighlightFragment> fragments
);
public String fieldName();
public List<HighlightFragment> fragments();

public HighlightFragment(
        int startOffset,
        int endOffset,
        String text,
        List<HighlightSpan> spans
);
public int startOffset();
public int endOffset();
public String text();
public List<HighlightSpan> spans();

public HighlightSpan(int startOffset, int endOffset);
public int startOffset();
public int endOffset();
```

These validating constructors let a compatible third-party engine implement the
additive default capability without depending on internal classes. Result and request
types expose no additional public constructor, mutator, subclass hook, or raw generic
escape. The semantic validation rules are frozen in
[structured highlighting](HIGHLIGHTING.md).

No public implementation subclass or service-provider registration is introduced.

## Existing public surface remains unchanged

V3.2 does not add a method or record component to `Analyzer`, `AnalyzedToken`, `Token`,
`TextField`, `SearchRequest`, `SearchResult`, `SearchHit`, `SearchExplanation`, or
`ExplanationNode`. In particular:

- `Analyzer` still has exactly one abstract method, `analyze(String)`;
- `AnalyzedToken` still has exactly `term` and `positionIncrement` components;
- existing analyzer lambdas remain source- and binary-compatible;
- existing `SearchEngine` implementations inherit a non-abstract default method;
- ordinary `search(Query)`, `searchTopK`, `search(SearchRequest)`, and `explain` retain
  all published descriptors and behavior;
- every existing query factory and builder overload remains unchanged; and
- adding highlighted search does not alter `SearchResult.hits()` or `SearchHit`.

The new `search` overload accepts a distinct request type. Calls that pass a typed
`Query`, `SearchRequest`, or `HighlightedSearchRequest` retain unambiguous overload
resolution. Untyped `search(null)` was already ambiguous between published overloads
and is not a supported compatibility pattern.

`SimpleAnalyzer` may add `OffsetAnalyzer` to its implemented-interface list. Its enum
identity, singleton constant, `Analyzer.simple()` return descriptor, existing methods,
and ordinary outputs remain unchanged.

## Unsupported internals

Offset normalization, analyzed-document mappings, match-evidence carriers, phrase
witnesses, fuzzy expansion selections, range mergers, fragment assemblers, and
snapshot-bound highlighter executors remain package-private and unsupported.

No public bridge may expose raw positions, offset arrays, mutable token lists, query
nodes, plan nodes, postings, candidate bitmaps, fuzzy trie nodes, snapshots, internal
document IDs, or retained analyzer state. If an implementation cannot remain internal
without a bytecode-public bridge, the contract must be amended and reviewed before the
bridge is added.

## Third-party capability behavior

The default `SearchEngine.search(HighlightedSearchRequest)` null-checks its argument
and otherwise throws `UnsupportedOperationException`. A third-party implementation may
override it and construct only the supported result values.

A legacy analyzer does not need modification. It remains accepted everywhere except
when its exact canonical field is explicitly requested for highlighting. The built-in
engine reports that unsupported capability deterministically instead of fabricating
offsets.

## Processor and generated consumers

V3.2 requires no annotation, annotation-processor, generated-field, generated-schema,
or service-entry change. The processor must not generate offset or highlight policy.
Applications select an offset-capable analyzer through the existing text-field
configuration path.

The V3 independent consumer will add one built-in SimpleAnalyzer highlighted-search
scenario after implementation. V1 and V2 consumers remain source-unchanged. A focused
third-party engine fixture proves the new default method preserves existing
implementations.

## Deferred public surface

Phase 0 authorizes no synonym dictionary/configuration, analyzer pipeline builder,
stemmer, ranked-prefix query, offset-storage option, HTML formatter, highlight callback,
query-clause ID, token graph, position length, search-after cursor, total-hits field,
timeout, or cancellation token. Any such addition requires its own compatibility and
semantic contract rather than opportunistic inclusion in the foundation.
