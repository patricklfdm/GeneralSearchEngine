# V3 Phase 3 search pipeline contract

## Status

The Phase 3 contract is frozen and implementation has not started. Phase 3 introduces
the built-in V3 `SearchRequest` execution path and replaces duplicate single-field
ranking logic with one snapshot-bound planning and execution pipeline.

Phase 0 ranked-search semantics, Phase 1 positioned analysis, Phase 2 positional
storage, and the V3 compatibility contract remain authoritative.

## Delivery boundary

Phase 3 implements only:

```text
SearchQueries.text(one canonical TextField, raw query text)
optional SearchRequest.filter(Query<T>)
SearchRequest.limit()
SearchRequest.bm25()
SnapshotSearchEngine.search(SearchRequest<T>)
legacy RankedSearchRequest adaptation to the same execution core
```

The result is the existing `SearchResult<T>` containing the existing
`SearchHit<T>` values. Phase 3 adds no new hit metadata.

Bool, boost, cross-field, phrase, fuzzy, Explain, pagination, total hits, plan caching,
prepared queries, WAND, and unrelated optimization remain outside this phase.

## Internal architecture

The canonical flow is:

```text
public request
    -> normalized TextSearchInput
    -> SearchPlanner
    -> immutable snapshot-bound SearchPlan
    -> SearchExecutor
    -> ordered SearchHit values
```

`TextSearchInput`, `SearchPlanner`, `SearchPlan`, `SearchExecutor`, query decoding,
prepared scoring terms, and ranked candidates are package-private implementation
types in `io.github.patricklfdm.generalsearch.search`.

`SearchQuery.node()` and every `SearchQueryNode` implementation remain package-private.
No supported public accessor exposes the query tree.

### Cross-package execution bridge

Java sibling packages cannot invoke package-private implementation classes. Phase 3
therefore permits exactly one narrow bytecode-public bridge:

```text
io.github.patricklfdm.generalsearch.search.SearchExecutionAccess
```

The bridge exists only for `SnapshotSearchEngine` and `RankedSearcher`. It is marked
with Javadoc `@hidden`, documented as unsupported internal infrastructure, cannot be
instantiated, and exposes only complete execution operations using existing public
request, result, snapshot, and planner types.

It never exposes or accepts a query node, search plan, posting reference, candidate
bitmap, or internal document ID. Reflection, method-handle access to `SearchQuery`, a
public `SearchQuery.internalNode()` method, and public plan/node types are prohibited.

The bridge is an implementation visibility concession, not a new supported application
API. No other Phase 3 implementation type may become bytecode-public merely to cross a
package boundary.

## Normalized ranked input

Both request styles become one immutable package-private input:

```text
TextField<T> textField
List<String> frozenTerms
Query<T> filter or null
int limit
Bm25Config config
```

The list is copied and retains exact scoring order.

For a V3 request, the decoder accepts only a direct `TEXT` leaf. It analyzes the raw
query text exactly once, validates the complete positioned output, and deduplicates
terms in first-encounter order.

For a V2 request, the adapter copies `TextScoringQuery.textField()` and
`TextScoringQuery.terms()` exactly. It must not read `queryText()` to recreate terms,
invoke either Analyzer method, rededuplicate, reorder, or otherwise reinterpret the
already-frozen term list.

After normalization, V2 and V3 use the same planner, plan, scoring operation, bounded
heap, and final ordering logic.

## V3 positioned analysis

V3 text leaves consume `Analyzer.analyzeWithPositions(String)`. They apply the complete
Phase 2 validation contract before using any term:

```text
non-null token list
non-null elements
first increment >= 1
later increments >= 0
logical position does not overflow Integer.MAX_VALUE
```

Malformed output fails with contextual `IllegalArgumentException` naming the text
field and relevant token detail. Analyzer-thrown exceptions propagate unchanged.
Term-only planning ignores valid increments after validation.

Default-adapted legacy Analyzers therefore retain their existing terms. Native
positioned overrides affect V3 query planning consistently with Phase 2 indexing,
scan, and BM25 term projection.

## Validation and failure precedence

Phase 3 freezes this order:

```text
1. public engine/searcher arguments are null-checked
2. V3 SearchQuery shape is decoded and rejected if unsupported
3. V3 raw text is analyzed once, or V2 frozen terms are copied
4. zero frozen terms produce an empty result
5. a non-empty request resolves the exact canonical text index
6. candidates, filter planning, and scoring are prepared
7. the immutable plan executes
```

Consequences:

- bool, boost, phrase, and fuzzy shapes fail with `UnsupportedOperationException`
  explaining that Phase 3 supports only a direct text leaf;
- unsupported shape rejection occurs before Analyzer or index work;
- empty analyzed text returns an empty result even if the text index is absent;
- a non-empty request without the identity-equal canonical text index throws the
  existing V2-style `IllegalStateException` naming the field;
- unknown terms are valid; they have no prepared posting and contribute no candidate or
  score;
- if every non-empty term is unknown, the result is empty after index resolution;
- filter and Analyzer exceptions are not wrapped or replaced unless an existing public
  engine boundary already specifies wrapping.

No ranked full-document scan substitutes for a missing text index.

## Snapshot-bound planning

`SnapshotSearchEngine` captures `current.get()` once per V2 or V3 ranked invocation and
passes that exact `SearchSnapshot<T>` into planning. Direct `RankedSearcher` calls use
the caller-supplied snapshot.

`SearchPlan<T>` owns the exact `SearchSnapshot<T>` reference, not only its version. It
is immutable and contains all request-level facts required for execution, including:

```text
the snapshot
the canonical TextIndexSnapshot
prepared scoring terms with posting references and IDF
the final candidate bitmap
the optional final Query<T> predicate
the positive limit
the Bm25Config
the average indexed document length
```

An empty plan may omit index/scoring state but still belongs to the captured snapshot.
Execution is conceptually `execute(SearchPlan<T>)` and accepts no second snapshot. This
prevents mixing documents, postings, lengths, or statistics from different versions.

All collections in the plan are immutable copies. Candidate bitmaps, postings, and the
snapshot are already immutable values.

## Text and structured candidates

For non-empty terms, text candidates are the union of their existing posting bitmaps.
Unknown terms do not add candidates.

When a structured filter exists, the same configured `CandidatePlanner<T>` used by the
engine or direct `RankedSearcher` is invoked against the same snapshot. If it returns a
candidate result, its bitmap may be intersected with text candidates. Both exact and
superset candidate results are safe restrictions under the existing candidate
contract; final predicate verification is still mandatory.

If structured planning returns empty, the implementation does not scan the complete
document collection. It evaluates `filter.matches(document)` only for text candidates.
The filter always contributes zero score.

No candidate plan may introduce false negatives. Candidate accuracy metadata is not a
substitute for final predicate truth.

## Execution and BM25

Planning computes each known term's document frequency and IDF once using the canonical
text snapshot's indexed-document count. Execution reads document length, term
frequencies, and the prepared postings from that same snapshot.

The existing V2 formula and operation order remain unchanged:

```text
idf = log1p((N - df + 0.5) / (df + 0.5))

normalization = k1 * (1 - b + b * dl / avgdl)

termScore = idf * (tf * (k1 + 1)) / (tf + normalization)

documentScore = ordered sum of matching distinct termScore values
```

Scoring terms remain in Analyzer first-encounter order for V3 and frozen
`TextScoringQuery.terms()` order for V2. Physical candidate work may be reordered;
floating-point accumulation may not.

For each candidate, execution:

1. reads the document from the plan's snapshot;
2. skips inactive/null documents defensively;
3. evaluates the final filter predicate when present;
4. computes BM25 in frozen term order;
5. skips scores that are not positive, matching V2;
6. retains at most `limit` candidates in the existing bounded worst-first heap;
7. emits hits ordered by score descending, then internal document ID ascending.

Internal document IDs determine ties but are never exposed.

Phase 3 adds no position, phrase, field, coordination, or query-normalization bonus.

## Engine and legacy integration

`SnapshotSearchEngine.search(SearchRequest<T>)` overrides the additive default method,
null-checks the request, captures one state, invokes the canonical bridge, and returns
`SearchResult<T>`.

Third-party `SearchEngine` implementations retain the existing default unsupported
method and remain binary compatible.

`SnapshotSearchEngine.searchTopK(RankedSearchRequest<T>)` and public direct
`RankedSearcher.search(SearchSnapshot<T>, RankedSearchRequest<T>)` remain supported.
`RankedSearcher` becomes a thin compatibility façade over the same execution pipeline.

Both existing public `RankedSearcher` constructors and its search descriptor remain
unchanged. A caller-supplied `CandidatePlanner<T>` continues to govern structured
filter planning. Likewise, the `PlannerConfig` supplied to `SnapshotSearchEngine`
governs both V2 and V3 ranked execution; no adapter creates an unrelated default
planner.

There is one BM25 implementation, one bounded top-K implementation, and one final
ordering implementation after Phase 3.

## Compatibility and public surface

Phase 3 preserves:

```text
all published 1.0.0, 2.0.0, and 2.1.0 descriptors
SearchEngine default behavior for third-party implementations
RankedSearcher constructors and direct search method
RankedSearchRequest and TextScoringQuery behavior
legacy empty-query and missing-index precedence
legacy filter truth, scores, hit order, and limits
canonical TextField identity semantics
```

No public query-tree accessor, public plan, public executor, public posting-position
read, or internal-document-ID API is added. Public inspection treats only the hidden
unsupported `SearchExecutionAccess` bridge as the frozen Java visibility exception.

The v3 independent consumer is extended to execute one supported text-only
`SearchRequest`. v1- and v2-style consumers remain unchanged and passing.

## Verification boundary

Focused tests cover supported text requests, limits, custom BM25, known and unknown
terms, empty analysis, missing indexes, identity-equal fields, indexed and unindexed
filters, final predicate truth, ties, positioned analysis, malformed output,
unsupported query shapes, and snapshot consistency.

A frozen-term regression proves legacy execution does not call the Analyzer after
`TextScoringQuery` construction. Direct `RankedSearcher` tests prove constructor and
injected-planner compatibility.

Deterministic randomized differential coverage compares equivalent V2 and V3 requests
across document/mutation histories, repeated query terms, filters, limits, and valid
BM25 configurations. It requires exact document order and exact score equality when
both paths share the canonical operation sequence.

The existing exhaustive BM25 oracle remains independent of the new pipeline and must
continue passing.

Phase 3 adds no performance claim. The JMH profile must compile, and a focused existing
BM25 top-K smoke run should show no obvious full-scan, unbounded-retention, per-document
analysis, or per-document IDF regression. No numeric release threshold is frozen here.

## Full gates

Completion requires:

```text
git diff --check
scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT
./mvnw -f reactor/pom.xml clean test
scripts/run-travel-example.sh
./mvnw clean -Papi-compat test
./mvnw clean -Partifact-compat verify
artifact compatibility from a fresh isolated Maven repository
scripts/verify-consumer-projects.sh
strict core and processor Javadocs through the release profile
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT
scripts/verify-reproducible-build.sh
```

No generated artifact, local repository, credential, IDE file, or root Codex prompt may
be tracked.

## Explicit non-goals

Phase 3 must not implement or expose:

- bool or boost planning/execution;
- cross-field ranked execution;
- phrase matching, scoring, or slop;
- fuzzy expansion, edit distance, or scoring;
- Explain execution;
- position bonuses or public position access;
- `minimumShouldMatch`, ranked `mustNot`, BM25F, or DisMax;
- WAND, Block-Max WAND, global optimization, plan caching, or prepared queries;
- parallel scoring, pagination, search-after, total hits, facets, or aggregations;
- persistence, WAL, vector/ANN, or distributed behavior;
- changes to bitmap representation, writer concurrency, or snapshot publication;
- unrelated refactoring.

Phase 3 is complete only when the V3 text request is independently usable, legacy V2
ranking uses the same canonical execution core without re-analysis, and every focused,
differential, compatibility, consumer, packaging, and reproducibility gate passes.
