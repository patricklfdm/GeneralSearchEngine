# GeneralSearchEngine v3 API compatibility

## Baseline

V3.0 is additive to the application APIs published in `1.0.0`, `2.0.0`, and `2.1.0`.
The 3.0.0 release artifact compatibility profile compared the final core JAR directly
against all three earlier published core artifacts. The frozen v1 source/reflection
fixture and independent v1-, v2-, and v3-style consumers provided separate
source-level coverage.

Published `3.0.0` is now an immutable compatibility baseline for subsequent V3.x
development. The next development-version change must retain the 1.0.0, 2.0.0, and
2.1.0 comparisons and add a direct comparison with the published 3.0.0 core artifact.

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
bitmaps remain package-private. At the Phase 4 boundary, the existing Javadoc-hidden
`SearchExecutionAccess` class remains the only bytecode-public bridge, continues to
expose complete execution only, and does not reveal or accept any Phase 4 internal
representation.

Japicmp is therefore expected to report no Phase 4 public addition. The normal and
isolated artifact comparisons against 1.0.0, 2.0.0, and 2.1.0, the frozen v1 fixture,
and the independent v1-, v2-, and v3-style consumers remain mandatory. Third-party
`SearchEngine` implementations retain the existing default unsupported V3 behavior,
and all V2 ranked descriptors and frozen-term execution semantics remain unchanged.

## Phase 5 internal positional bridge

Phase 2 keeps `IntPositions` and direct posting-position reads package-private in the
text-index implementation package, while Phase 5 phrase plans remain package-private
in the search package. Exact phrase execution therefore permits one additional narrow
bytecode-public class, conceptually named `PhrasePositionAccess`, solely to cross this
Java package boundary without reflection or a supported positions API.

The class is Javadoc-hidden, final, non-instantiable, stateless, and explicitly
unsupported. Its one role is to return exact phrase match truth for an internal
document ID from already-prepared relative slots, alternative postings, and an anchor.
It does not analyze text, resolve indexes, build candidates, score hits, or retain
request state. It returns no `IntPositions`, raw position array, collection, iterator,
stream, callback, query node, plan, snapshot, candidate bitmap, score state, or other
position handle. No position method is added to the supported `PostingList`,
`TextIndexSnapshot`, or application query APIs.

Japicmp may report this hidden bridge as one additive class after Phase 5
implementation. That report is expected and must be reviewed to confirm the exact
frozen boundary; it does not make the bridge a supported application API. The Phase 3
`SearchExecutionAccess` remains complete-execution-only. No further visibility bridge
or supported public descriptor is permitted in Phase 5.

## Phase 6 internal vocabulary bridge

The canonical normalized vocabulary remains inside the package-private posting map of
`TextIndexSnapshot`, while Phase 6 expansion and planning remain package-private in the
search package. Phase 6 therefore permits one additional bytecode-public class,
conceptually named `FuzzyVocabularyAccess`, solely to cross that Java package boundary
without reflection or a supported vocabulary API.

The class is Javadoc-hidden, final, non-instantiable, stateless, synchronous, and
explicitly unsupported. Its only operation visits normalized vocabulary terms from one
supplied `TextIndexSnapshot` through a standard string consumer. It returns no term
collection, posting, dictionary, bitmap, position, iterator, stream, snapshot handle,
expansion, plan, score, or internal document ID; retains no snapshot or callback; and
performs no analysis, distance, expansion, candidate, or scoring work. No method is
added to supported `TextIndexSnapshot`, `PostingList`, or query APIs.

Japicmp reports `FuzzyVocabularyAccess` as the one additive bytecode-public Phase 6
class. Normal and isolated comparisons against 1.0.0, 2.0.0, and 2.1.0 confirm that
exact hidden boundary. It does not make vocabulary traversal a supported application
SPI. Phase 6 otherwise adds no supported public type, method, field, constructor,
record component, or descriptor.
`SearchExecutionAccess` and `PhrasePositionAccess` remain otherwise unchanged, and no
second Phase 6 bridge is permitted.

## Phase 7 internal Explain entry point

`SnapshotSearchEngine` owns the atomic published-state business-ID map in the engine
package, while `SearchPlanner`, `SearchPlan`, scoring nodes, and Explain execution stay
package-private in the search package. Phase 7 therefore permits exactly one additive
Javadoc-hidden method on the existing bytecode-public `SearchExecutionAccess` bridge.

The method consumes one captured `SearchSnapshot`, the existing `SearchRequest`, the
already-resolved internal document ID, and the existing `CandidatePlanner`, and returns
only the supported `SearchExplanation`. Accepting the internal ID is permitted solely
to cross the existing Java package boundary efficiently. The method must not return or
retain that ID, mention it in public descriptions, expose any snapshot, plan, posting,
candidate, position, or score-state handle, or become a general evaluation SPI.

Japicmp reports this one additive method on the already unsupported internal bridge.
No new bridge class or second Phase 7 method is present.
The supported `SearchEngine.explain(...)`, `SearchExplanation`, and `ExplanationNode`
API shapes were frozen in Phase 0 and do not change. Japicmp additionally reports the
required concrete `SnapshotSearchEngine.explain(...)` override; that override is the
only supported class descriptor addition in Phase 7. Normal and isolated comparisons
against 1.0.0, 2.0.0, and 2.1.0 confirm this exact boundary. Third-party
`SearchEngine` implementations continue to inherit the existing default unsupported
behavior.

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

## Published 3.0.0 public API freeze

The final 3.0.0 Japicmp reports against 1.0.0, 2.0.0, and 2.1.0 contain no
binary or source incompatibility. The supported additive V3 surface is exactly:

- `AnalyzedToken` and the default `Analyzer.analyzeWithPositions(String)` method;
- `SearchRequest` and its builder;
- the final `SearchQuery` façade, `SearchQueries`, and its BOOL builder;
- `SearchResult`, `SearchExplanation`, and `ExplanationNode`;
- the default `SearchEngine.search(SearchRequest)` and `SearchEngine.explain` methods;
- the corresponding concrete overrides on `SnapshotSearchEngine`.

The review confirms that the supported request/query/result/explanation types expose no
query node, planner, plan, posting, vocabulary, position, candidate bitmap, score state,
snapshot handle, or internal document ID. Their generic descriptors, construction
validation, immutable collection boundaries, defaults, and exception behavior match the
Phase 0–7 contracts. Public Javadocs state the builder thread-safety boundary, analyzer
concurrency requirement, invocation-local snapshot behavior, top-K-independent Explain
semantics, and diagnostic—not parseable—description contract.

Japicmp also reports the three already reviewed Javadoc-hidden package bridges:
`SearchExecutionAccess`, `PhrasePositionAccess`, and `FuzzyVocabularyAccess`. Their
exact Phase 3/5/6/7 boundaries above remain unchanged. They are bytecode-public only to
cross Java sibling packages and remain unsupported application infrastructure.

Changes reported on `PostingList`, `TextIndexBuilder`, `RankedSearcher`, and
`TextScoringQuery` do not add or remove public descriptors; they reflect private
positional and canonical-execution implementation changes. No other accidental public
V3 type or method is accepted into the published 3.0.0 compatibility contract.
