# V3 Phase 7 Explain execution contract

## Status

This contract is implemented and validated. Phase 7 is complete.

The Phase 0 public explanation model and ranked semantics, Phase 1 positioned analysis,
Phase 2 positional storage, Phase 3 snapshot-bound pipeline, Phase 4 recursive
composition, Phase 5 exact phrase execution, Phase 6 single-term fuzzy execution, and
V3 compatibility policy remain authoritative. This document resolves Phase 7-specific
planning, evaluation, diagnostics, visibility, lifecycle, and failure precedence.

## Delivery boundary

Phase 7 implements the existing additive capability on the built-in engine:

```java
Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id)
```

Explain answers whether one existing business document matches the complete request,
what score a match receives, and how ranked-query and structured-filter components
produce that outcome. It is independent of top-K membership and is not a new scoring
model.

Phase 7 adds no automatic explanations to `SearchResult` or `SearchHit`, legacy V2
Explain API, public explanation subtype, type enum, attributes map, raw positions,
internal document ID, snapshot/plan/posting handle, text renderer API, or Phase 8
hardening/release behavior.

## Public model remains frozen

`SearchExplanation<T>` and `ExplanationNode` retain their Phase 0 classes,
constructors, methods, validation, and immutable child-list behavior. No record
conversion or public descriptor change is permitted.

Every produced node has a non-null description and immutable non-null children. Scores
are finite and non-negative. Every unmatched node has canonical `+0.0`; matched nodes
may also validly score `+0.0`. `SearchExplanation.document()` is the exact document
observed in the captured state, and its match and score mirror the root detail node.

Descriptions are deterministic, concise diagnostics. They may contain field, term,
phrase relation, fuzzy selection, BM25, boost, and filter facts, but their complete
prose is not an exhaustive machine-readable protocol. Required numeric rendering is
locale-independent. Public data and descriptions never contain internal document IDs,
raw posting/index identities, candidate bitmaps, raw position arrays, snapshots, or
plan nodes.

## Invocation and failure precedence

One built-in invocation follows this order:

```text
1. null-check request
2. null-check business ID
3. capture current PublishedState exactly once
4. resolve the business ID in that same state
5. return Optional.empty() immediately when the ID is absent
6. normalize and plan the request against that state's SearchSnapshot
7. explain the resolved internal document against that same plan and document
8. return Optional.of(SearchExplanation)
```

Consequently, a missing business ID wins over Analyzer, missing-index, and filter
planning failures. For an existing ID, malformed analysis, missing identity-equal text
indexes, unsupported shapes, and arithmetic failures have the same type, context, and
logical traversal precedence as normal V3 request planning/evaluation.

An existing non-matching document returns an explanation with `matched=false` and
score `+0.0`. Explain never throws `DocumentNotFoundException` for a missing ID and
never fabricates an explanation for a document absent from the captured state.

## Canonical planning and snapshot boundary

Explain uses `RankedSearchInput`, `SearchPlanner`, and `SearchPlan`; it does not have an
independent planner, analyzer, index resolver, vocabulary expansion, phrase compiler,
or filter planner. One plan is bound to the exact immutable snapshot captured with the
business-ID map.

`SearchRequest.limit()` and the plan's top-level candidate bitmap do not decide whether
the resolved document can be explained. Explain evaluates the prepared scoring root
for that document directly. Exact leaf candidate membership may remain an internal
safe shortcut, but public diagnostics state semantic match reasons rather than planner
membership.

The all-ranked-leaves-empty fast path retains an explainable internal scoring tree.
It still performs no canonical-index resolution for an empty leaf and returns before
structured-filter candidate planning, preserving the frozen search failure precedence.

Each Explain call observes the state current when that call begins. `SearchResult`
does not pin a snapshot, and a later Explain call is not required to reproduce an
earlier search call's state.

## One source of match and score truth

For the same snapshot, request, and active document:

```text
normal prepared root/filter evaluation matched == explained matched
normal prepared root/filter evaluation score   == explained score
```

The invariant concerns semantic per-document evaluation, not inclusion in a bounded
`SearchResult`.

Normal `ScoringPlanNode.evaluate(docId)` remains the allocation-light path. Explain may
add an internal detailed-evaluation method, an `ExplainExecutor`, or a diagnostic
context, but both paths use the same `Bm25Scorer`, `ScoreArithmetic`, phrase-match,
fuzzy-selection, BOOL, and BOOST primitives. No second BM25 formula or alternative
ranking stack is allowed.

Prepared nodes may retain immutable facts already derived during normalization and
planning: canonical field identity/name, normalized scoring terms, phrase relative
slots, fuzzy expansions, BM25 configuration, field-local statistics, and postings.
Planning must not eagerly build `ExplanationNode` instances, diagnostic strings, or
per-document diagnostic collections. Normal `search(request)` never enters explanation
construction.

## Root request tree and structured filter

The root detail represents the complete request and has this deterministic shape:

```text
SEARCH REQUEST
├── ranked query
└── structured filter  // only when request.filter() is present
```

Without a filter, root match and score equal the ranked child. With a filter, root
match is ranked-match AND filter-match. A matching request root carries the ranked
score; any failed component produces root score `+0.0`.

The filter child always scores `+0.0`, whether it passes or fails. Filter truth comes
from `Query.matches(document)`, not candidate membership. When the ranked query matches
but the filter fails, the root is an unmatched zero while the ranked child retains its
positive local score. Phase 7 does not recursively explain structured `Query<T>`
implementations.

## TEXT diagnostics

A TEXT node names its canonical field, states match truth and total leaf score, and has
one ordered child per distinct normalized query term in Analyzer first-encounter order.
This includes terms absent from the field vocabulary, which appear as unmatched
zero-score children.

A matching term child score is its exact BM25 contribution and its description records
term, field, `tf`, `df`, field-local `N`, `dl`, `avgdl`, `k1`, `b`, `idf`, and
contribution. These facts use the same prepared posting/statistics and `Bm25Scorer`
arithmetic as normal evaluation. The sum of matching term-child scores equals the TEXT
node score through `ScoreArithmetic` in logical term order.

An empty analyzed TEXT node is retained as unmatched zero with no term children and a
clear empty-analysis diagnostic. It requires no text index.

## PHRASE diagnostics

A PHRASE node names its field and states whether the exact analyzed relative-position
slot pattern matched. Its tree is proportional to query complexity and never exposes
absolute occurrence arrays or `IntPositions`.

When the phrase fails, the phrase node scores zero. When it matches, one term child per
distinct phrase scoring term appears in first-encounter order and carries the same BM25
facts as TEXT. Repeated slots remain visible in the phrase relation description, while
repeated terms contribute only once to scoring. Position gaps and same-position
alternatives are described semantically without raw arrays. A single-slot phrase uses
the same exact phrase truth and distinct-term scoring rules.

An empty analyzed PHRASE is an unmatched zero, retains its field diagnostic, and
requires no index.

## FUZZY diagnostics

A FUZZY node names its field, normalized query term, Unicode code-point query length,
and frozen AUTO maximum edit distance. It never lists the scanned vocabulary or every
expansion.

For a match, exactly one selected-expansion child records the selected term, edit
distance, similarity, `tf`, `df`, field-local `N`, `dl`, `avgdl`, `k1`, `b`, `idf`,
unweighted BM25, and weighted fuzzy contribution. Exact normalized-term priority is
identified explicitly with distance zero and similarity one even if another expansion
would have a larger weighted value. Otherwise the child describes the deterministic
best expansion selected by the Phase 6 max-not-sum rule.

No expansion or no matching expansion produces an unmatched zero with a concise
reason. Empty analyzed FUZZY retains the field diagnostic, has no selected child, and
requires no index. Explain does not change expansion completeness, ordering, tie
breaking, or scoring.

## BOOL and BOOST diagnostics

BOOL children appear as MUST nodes in builder encounter order followed by SHOULD nodes
in builder encounter order. Clause wrapper nodes score the local child score when that
child matches and zero otherwise. The BOOL node follows the exact Phase 4 rules:

- with MUST clauses, every MUST must match and matching SHOULD scores are added;
- without MUST clauses, at least one SHOULD must match;
- duplicate occurrences remain distinct; and
- failed BOOL nodes always score `+0.0`.

Explain evaluates all logical children for diagnostics even when normal evaluation may
short-circuit a failed MUST. Positive local SHOULD diagnostics never leak into a failed
BOOL score. Accumulation order and checked arithmetic remain MUST then SHOULD.

BOOST has one child, inherits its match truth, and multiplies a matching child score by
the frozen positive multiplier through `ScoreArithmetic`. Its description records the
multiplier. A failed child produces a failed zero-score BOOST node. Nested BOOL/BOOST
structure and duplicate occurrences are not flattened.

Cross-field trees retain one leaf per canonical field. Every BM25 leaf reports its own
field-local statistics; no global or BM25F statistics are synthesized.

## Hidden execution boundary

`SnapshotSearchEngine` owns the atomic `PublishedState<K,T>` and business-ID map, while
planning and explanation internals remain package-private in the search package. Phase
7 therefore permits exactly one additive Javadoc-hidden `SearchExecutionAccess`
Explain method. It consumes the captured `SearchSnapshot`, request, resolved internal
document ID, and existing `CandidatePlanner`, and returns only the supported public
`SearchExplanation<T>`.

This unsupported bridge method may accept the resolved internal ID solely to cross the
existing Java package boundary. It must not return that ID, include it in descriptions,
retain any argument, expose a plan/snapshot/posting/candidate handle, or become a
general per-document evaluation SPI. `SnapshotSearchEngine` performs missing-ID
handling before invoking it. No new bridge class or second Phase 7 method is allowed.

Japicmp may report this method as an addition to the already unsupported bytecode-public
bridge. It may also report the required concrete `SnapshotSearchEngine.explain(...)`
override of the Phase 0 interface method. That override is the only supported class
descriptor addition and introduces no new public API shape. No other supported public
type, method, field, constructor, record component, or descriptor changes in Phase 7;
third-party `SearchEngine` implementations keep the existing default unsupported
behavior.

## Lifecycle and concurrency

Explain reflects every published add, update, remove, reorder, and bulk mutation.
Removed IDs return empty. Each invocation mixes no business-ID map, document,
vocabulary, posting, statistic, filter, or plan version.

Dynamic text-index creation and replay make TEXT, PHRASE, and FUZZY explainable after
publication. Pending builds do not leak into the captured old state. Subsequent
mutations use the newly published index. Dropping a required index makes an existing
document's Explain fail with the same contextual planning error as search.

Concurrent publication during ID lookup, analysis, planning, or explanation cannot
change the captured state. Tests may use package-private hooks, but production stores
no Explain session and pins no snapshot beyond the synchronous invocation.

## Validation evidence

Focused tests cover public missing/matching/non-matching behavior, top-K and limit
independence, root/filter structure, every ranked node, BM25 diagnostics, deterministic
ordering, checked zero/overflow behavior, mutations, snapshot concurrency, and dynamic
indexes. Package-private tests compare prepared normal evaluation directly with
explanation match/score.

Deterministic randomized tests generate TEXT/PHRASE/FUZZY/BOOL/BOOST trees with
optional filters and compare semantic per-document normal evaluation with Explain for
active documents. They recursively validate immutable children, finite non-negative
scores, failed-node zero scores, deterministic order, and absence of internal handles.

The v1 source/reflection fixture, v1/v2/v3 independent consumers, normal and isolated
Japicmp comparisons against 1.0.0/2.0.0/2.1.0, travel example, strict Javadocs, release
profile, release-artifact integrity, reproducibility, and normal test suite remain
mandatory. These are validation gates, not Phase 8 publication work.

## Explicit non-goals

Phase 7 adds no deep structured-filter tree, public BM25 getters, explanation parser or
renderer contract, automatic/batched Explain, stored explanations, snapshot sessions,
query cache, allocation campaign, fuzzy optimization, phrase slop, highlighting,
offsets, synonyms, advanced fuzzy controls, `minimumShouldMatch`, ranked `mustNot`,
BM25F, DisMax, custom scoring, pagination, facets, persistence, vectors, distributed
execution, version conversion, signing, deployment, or release publication.

## Completion rule

Phase 7 is complete only when Explain is a faithful, snapshot-local diagnostic view of
the existing canonical plan; public match and score equal semantic normal evaluation;
normal search allocates no explanation objects or descriptions; legacy and supported
descriptors remain stable; and every item in `PHASE_7_CHECKLIST.md` passes. Phase 8 or
post-V3 work is scope failure, not extra progress.
