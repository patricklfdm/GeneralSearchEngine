# V3 Phase 4 ranked composition contract

## Status

This contract is frozen before implementation. Phase 4 implementation has not started.

Phase 0 ranked-search semantics, Phase 1 positioned analysis, Phase 2 positional
storage, the completed Phase 3 search pipeline, and the V3 API compatibility contract
remain authoritative. This document resolves Phase 4-specific composition and failure
precedence without changing those earlier public contracts.

## Delivery boundary

Phase 4 implements execution for the existing public query shapes:

```text
SearchQueries.text(...)
SearchQueries.bool().must(...).should(...).build()
SearchQuery.boost(double)
```

TEXT, BOOL, and BOOST may be nested. Text leaves may reference different canonical
`TextField<T>` values, which provides cross-field ranked search through ordinary query
composition.

Phase 4 adds no public query type, AST accessor, plan type, scoring extension point, or
result metadata. Phrase, fuzzy, Explain, `minimumShouldMatch`, ranked `mustNot`, ranked
filter clauses, BM25F, DisMax, function scoring, WAND, plan caching, prepared queries,
pagination, highlighting, persistence, vector search, and unrelated refactoring remain
outside this phase.

## Canonical internal architecture

The Phase 3 request pipeline remains the only ranked execution path:

```text
SearchRequest / frozen V2 RankedSearchRequest
    -> normalized ranked tree
    -> SearchPlanner
    -> immutable snapshot-bound SearchPlan
    -> recursive scoring plan
    -> SearchExecutor
    -> SearchResult / legacy hit list
```

The normalized tree is an immutable package-private representation equivalent to:

```text
Text(TextField<T>, ordered frozen terms)
Bool(ordered MUST children, ordered SHOULD children)
Boost(child, positive finite multiplier)
```

The prepared scoring tree is an immutable package-private representation equivalent
to:

```text
ScoringPlanNode<T>
|- TextPlan
|- BoolPlan
`- BoostPlan
```

Each prepared node provides a safe candidate bitmap and exact evaluation conceptually
equivalent to:

```text
candidates()
evaluate(docId) -> ScoreMatch(matched, score)
```

`SearchPlan<T>` owns the exact `SearchSnapshot<T>` reference and the root scoring node.
Execution accepts no second snapshot. Query nodes, normalized nodes, plan nodes,
`ScoreMatch`, postings, bitmaps, snapshot handles, and internal document IDs remain
hidden from the supported public API.

The Phase 3 Javadoc-hidden `SearchExecutionAccess` class remains the only permitted
bytecode-public cross-package bridge. Phase 4 does not widen it to expose internal
representations and adds no second bridge.

## Query occurrences and legacy adaptation

Every public query-node occurrence is semantically significant. The same
`SearchQuery<T>` object appearing twice is visited, normalized, planned, and scored
twice. Implementations must not use object identity or structural equality to memoize,
merge, or deduplicate query or clause occurrences.

Deduplication remains local to a single V3 TEXT leaf: its analyzed terms are
deduplicated in first-encounter order. Equal terms in separate leaves are independent
contributions.

The V2 adapter does not manufacture BOOL or BOOST. It creates one normalized TEXT leaf
from the exact `TextScoringQuery.textField()` and already-frozen
`TextScoringQuery.terms()`. It copies term order and must not invoke either Analyzer
method, read `queryText()` to recreate terms, deduplicate, reorder, or reinterpret the
list.

## Validation, normalization, and planning precedence

One invocation follows this order:

```text
1. null-check public engine/searcher arguments
2. traverse and validate the complete public ranked-query shape
3. normalize and prepare occurrences in deterministic logical depth-first order
4. if the whole tree has no non-empty TEXT leaf, return an empty plan/result
5. finish ranked candidate composition
6. plan the optional structured filter against the same snapshot
7. intersect safe ranked/filter candidates and execute the immutable plan
```

Step 2 performs no Analyzer, text-index, or structured-filter work. It accepts only
TEXT, BOOL, and BOOST. Any PHRASE or FUZZY node anywhere in the tree throws a clear
`UnsupportedOperationException` before such work, including when an earlier sibling
would later be match-none. Public construction-time null, empty-BOOL, and boost-value
validation remains unchanged.

Step 3 uses this logical traversal order:

```text
BOOL:  all MUST children in builder encounter order, then all SHOULD children
BOOST: its child
TEXT:  the occurrence itself
```

Each V3 TEXT occurrence is analyzed exactly once through
`Analyzer.analyzeWithPositions(String)`. Before a term is consumed, the full Phase 2
contract is validated: non-null list, non-null elements, first increment at least one,
later increments non-negative, and no logical-position overflow. Analyzer-thrown
exceptions propagate unchanged; contextual positioned-output failures retain field and
token context.

After analysis, terms are deduplicated in first-encounter order. If terms remain, that
occurrence immediately resolves its identity-equal canonical `TextIndexSnapshot` from
the request snapshot and prepares field-local facts. A missing canonical index throws
the Phase 3/V2-style `IllegalStateException` naming the field.

All child occurrences are compiled even if a previously compiled MUST leaf is
match-none or already has empty candidates. Planning never uses match short-circuiting
to skip a later non-empty MUST or SHOULD leaf, malformed Analyzer output, or missing
index. Within the fully valid shape, Analyzer and index failures therefore follow the
deterministic traversal order above.

If at least one non-empty leaf exists, optional structured-filter candidate planning
occurs after ranked preparation even when the root ranked candidates are empty because
all terms are unknown. This preserves Phase 3 unknown-term failure and side-effect
precedence. If every leaf is empty, the request returns empty before text-index and
filter planning.

## TEXT leaf semantics

A zero-term TEXT leaf is match-none:

```text
candidates = empty
matched(docId) = false
score(docId) = 0.0
text index required = no
```

A non-empty TEXT leaf requires its canonical field index even if every frozen term is
unknown. Its candidates are the union of known-term posting bitmaps. It matches a
document when at least one distinct frozen term occurs and scores the matching distinct
terms in frozen encounter order using the unchanged Phase 3/V2 BM25 formula.

Each prepared leaf owns field-local facts from its own canonical
`TextIndexSnapshot`:

```text
indexed-document count N
document frequency df
document length dl
average document length avgdl
prepared posting references and IDF values
```

No statistic is shared across different fields. `Bm25Config` is the only request-wide
BM25 input. Phase 4 adds no BM25F, field normalization, implicit weight, coordination
factor, or max/DisMax selection.

## BOOL candidate composition

With one or more MUST children:

```text
candidates = intersection of every MUST child candidate bitmap
```

SHOULD candidates do not enlarge eligibility. Physical bitmap intersection may use a
cost-effective order, including smallest-first, but the plan retains children in their
logical order for exact evaluation and scoring.

With no MUST children:

```text
candidates = union of every SHOULD child candidate bitmap
```

Candidate bitmaps are request-level immutable values and are not rebuilt per document.
Every node candidate set must be a safe superset of exact matches; false negatives are
forbidden.

## BOOL exact match and score

For a BOOL containing MUST children:

```text
match = every MUST child matches
score = ordered sum of all MUST scores
      + ordered sum of scores from matching SHOULD children
```

MUST children are evaluated in builder encounter order. The first non-match ends exact
evaluation of that document. Once every MUST matches, SHOULD children are evaluated in
builder encounter order. A non-matching SHOULD contributes nothing and does not affect
eligibility.

For an all-SHOULD BOOL:

```text
match = at least one SHOULD child matches
score = ordered sum of every matching SHOULD score
```

SHOULD children are evaluated in builder encounter order while tracking match truth
separately from score. An all-SHOULD BOOL is never MatchAll. Nested BOOL behavior is
purely recursive; BOOL flattening is unnecessary and must not change logical ordering
or explicit clause occurrences.

## BOOST exact match and score

For a BOOST node with child `q` and its already validated positive finite multiplier
`x`:

```text
candidates(boost(q, x)) = candidates(q)
match(boost(q, x)) = match(q)
score(boost(q, x)) = checkedMultiply(score(q), x)
```

Boost never changes match truth. Nested boosts execute node by node in public-tree
order. For `q.boost(2.0).boost(3.0)`, the operation is:

```text
(score(q) * 2.0) * 3.0
```

It must not be flattened to `score(q) * (2.0 * 3.0)`, because IEEE-754 rounding,
underflow, and intermediate overflow are observable parts of deterministic arithmetic.

## Match state, checked arithmetic, and zero scores

`ScoreMatch.matched` is authoritative. No executor, BOOL node, BOOST node, heap, or
result builder may infer match truth from `score > 0.0`.

Every score addition and multiplication is checked immediately in the frozen logical
operation order. A NaN, infinite, or negative result throws `ArithmeticException` and
is never silently skipped, saturated, or reordered. A positive calculation that
underflows to zero is valid and is canonicalized to `+0.0`.

A matched document whose valid boosted score is `+0.0` remains eligible for bounded
top-K retention and output. Zero-score ties use the ordinary final ordering: score
descending, then internal document ID ascending. Internal document IDs remain hidden.

This generalizes Phase 3's non-positive-score shortcut without changing V2 observable
behavior: ordinary V2 BM25 matches remain positive, while Phase 4 can represent a
valid underflowed BOOST match.

## Structured filters and candidates

`SearchRequest.filter(Query<T>)` remains eligibility-only and contributes zero score.
Ranked BOOL does not gain `filter` or `mustNot` clauses.

After ranked preparation, the configured `CandidatePlanner<T>` plans the structured
filter against the same snapshot. Exact or safe-superset filter candidates may
intersect ranked candidates. Every surviving document still undergoes the final
`filter.matches(document)` predicate. If the filter has no candidate plan, only ranked
candidates are tested; ranked execution does not fall back to a full collection scan.

The implementation may reject a document with the cheap exact filter before recursive
scoring when this cannot change exceptions or public semantics. The filter never
changes the score of a surviving document.

## Snapshot, mutation, and ordering

The built-in engine captures one immutable state exactly once per ranked invocation.
Every document, field index, posting, length, statistic, candidate bitmap, and filter
plan comes from that exact snapshot. Direct `RankedSearcher` calls use the one supplied
snapshot. Concurrent publication cannot mix fields or versions within a request.

Physical candidate work may be reordered. Logical score accumulation may not. The
frozen logical order is recursive query encounter order and, within a TEXT leaf, frozen
term encounter order. No hash iteration or cost order may determine floating-point
addition.

The existing bounded worst-first heap and final ordering remain canonical. At most the
requested limit is retained, with score descending and internal document ID ascending
in final results.

## Compatibility and public surface

All published 1.0.0, 2.0.0, and 2.1.0 descriptors and behaviors remain supported.
Phase 4 introduces no supported public class or method. The public BOOL/BOOST façade
was already frozen in Phase 0; this phase only implements its built-in execution.

Third-party `SearchEngine` implementations retain the existing default unsupported V3
capabilities. Both public `RankedSearcher` constructors, its search descriptor, legacy
`searchTopK`, V2 frozen-term behavior, structured filters, custom BM25 configuration,
limits, exact scores, and tie ordering remain unchanged.

Japicmp should find no Phase 4 public addition. The existing hidden
`SearchExecutionAccess` bridge remains explicitly unsupported infrastructure and gains
no application compatibility guarantee.

## Required verification

Focused tests must cover:

- MUST, SHOULD-with-MUST, all-SHOULD, nested BOOL, BOOST, and mixed nesting;
- cross-field candidates and field-local `N`, `df`, `dl`, and `avgdl`;
- duplicate terms within a leaf versus duplicate terms/query objects across clauses;
- whole-tree unsupported-shape precedence before Analyzer/index/filter work;
- malformed positioned output and Analyzer call counts for nested occurrences;
- empty leaves, all-empty trees, missing indexes, unknown terms, and later missing
  SHOULD indexes after match-none MUST leaves;
- candidate-superset safety and logical score order independent of physical planning;
- valid zero-score underflow, addition overflow, multiplication overflow, and
  encounter-order floating-point cases;
- indexed/unindexed filters, snapshot consistency under concurrent publication, and
  deterministic zero/equal-score ordering;
- exact Phase 3 direct-TEXT and V2 legacy regressions;
- PHRASE, FUZZY, and Explain remaining unsupported; and
- deterministic randomized differential comparison with a trusted recursive evaluator.

JMH sources must compile and a focused composition smoke must demonstrate no obvious
per-document analysis, index resolution, IDF recomputation, candidate recomposition, or
unbounded hit retention. Phase 4 freezes no numeric performance threshold.

The full reactor, travel example, source/reflection fixture, published-artifact
compatibility in normal and isolated repositories, independent consumers, strict
Javadocs, release packaging, artifact inspection, reproducibility, and version
alignment gates remain mandatory.

## Completion rule

Phase 4 is complete only when the implementation and every checklist item pass, the
roadmap and changelog describe the implemented boundary accurately, and no Phase 5+
feature or unsupported public surface has been added. Until then, its status is
`Contract frozen`.
