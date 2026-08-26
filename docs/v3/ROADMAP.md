# GeneralSearchEngine V3 development roadmap

## Status

Current stable release: `2.1.0`

Current V3 development line: `3.0.0-SNAPSHOT`

V3 develops high-quality ranked text retrieval with stable public APIs, exact phrase
search, fuzzy term tolerance, cross-field relevance, and Explain.

| Phase | Scope | Status |
|---|---|---|
| Phase 0 | public API, architecture, semantics, and compatibility freeze | Complete |
| Phase 1 | position-aware Analyzer API and legacy adapter | Complete |
| Phase 2 | positional posting storage and consistent positioned-term consumption | Complete |
| Phase 3 | SearchRequest planning and execution pipeline | Complete |
| Phase 4 | bool, boost, and cross-field ranked search | Complete |
| Phase 5 | exact phrase search | Complete |
| Phase 6 | fuzzy term search | Contract frozen |
| Phase 7 | Explain execution | Planned |
| Phase 8 | hardening and 3.0.0 release | Planned |

Each phase starts from the previous phase merged to `master`. A phase is complete only
after its focused tests, full correctness suite, compatibility baselines, independent
consumers, documentation, release packaging, and reproducibility gates pass. Later
phase work must not be pulled forward merely for convenience.

## Global principles

`Query<T>` remains deterministic filtering and eligibility. `SearchQuery<T>` represents
ranked retrieval and relevance and does not extend `Query<T>`.

The public ranked-query model remains a façade. Users construct queries through
`SearchQueries.text(...)`, `phrase(...)`, `fuzzy(...)`, and `bool()`. Planner and
execution node hierarchies remain internal.

V3.0 ranking uses BM25 leaf scoring, deterministic addition, and explicit
multiplicative boost. It does not introduce hidden field normalization, coordination
factors, BM25F, DisMax, function scoring, or custom script scoring.

The existing immutable-snapshot architecture remains authoritative: lock-free reads,
asynchronous single-writer mutation, structural sharing, and atomic publication. V3
does not redesign writer concurrency or snapshot publication.

Application compatibility remains additive against published 1.0.0, 2.0.0, and 2.1.0.
Internal representations may change only while their existing public descriptors and
observable behavior remain supported.

## Phase 0 — Contract freeze

Phase 0 established `SearchRequest<T>`, `SearchQuery<T>`, `SearchQueries`,
`SearchResult<T>`, `SearchExplanation<T>`, and `ExplanationNode`; additive default
request-search and Explain capabilities on `SearchEngine`; and the frozen architecture,
ranked-search, positional, fuzzy, and compatibility contracts.

It added no positional storage, ranked request execution, phrase/fuzzy execution,
planner/executor, or Explain implementation.

## Phase 1 — Position-aware analysis

Phase 1 introduced `AnalyzedToken` and the backward-compatible default
`Analyzer.analyzeWithPositions(...)` adapter. Existing Analyzer implementations and
lambdas remain compatible, the interface remains a SAM, and the default adapter emits
the legacy term sequence with increment `1`.

It added no positional consumer, posting storage, or ranked execution behavior.

## Phase 2 — Positional posting storage

Phase 2 makes the text index retain logical term-occurrence positions. It introduces
internal immutable primitive-backed `IntPositions`, changes posting payloads from
`docId -> frequency` to `docId -> positions`, derives term frequency from stored
positions, and makes token-order changes index-visible.

Phase 2 is also the first positioned-analysis consumer. All internal document indexing,
scan verification, legacy text-query term extraction, and legacy BM25 term extraction
must use a consistent positioned-token term projection. Analyzers inheriting the
default adapter retain their exact published behavior; V3-native positional overrides
become active consistently rather than producing index-versus-scan drift.

Existing `PostingList` public methods and descriptors remain supported. Existing term,
any-terms, all-terms, BM25, document-length, candidate-accuracy, dynamic-index, mutation,
and snapshot behavior remains unchanged for legacy analyzers.

Phase 2 adds no phrase execution, new request pipeline, cross-field execution, fuzzy
execution, Explain execution, position compression, or unrelated public API.

A focused positional build/mutation and allocation baseline records no obvious
pathological regression for the representative workload. Compression and
evidence-driven optimization remain later work.

## Phase 3 — SearchRequest execution pipeline

Phase 3 implements internal `SearchPlanner`, immutable snapshot-bound `SearchPlan`, and
`SearchExecutor`. It initially supports `SearchQueries.text(...)`, the structured
request filter, limit, and BM25 configuration, and implements the built-in
`SearchEngine.search(SearchRequest<T>)` capability.

The package-private query representation and pipeline remain hidden behind one narrow
Javadoc-hidden cross-package execution bridge required by Java visibility. V3 raw text
is normalized once through positioned analysis; V2 requests pass their already-frozen
`TextScoringQuery.terms()` into the same planner without re-analysis. Empty terms return
before text-index resolution, preserving existing V2 failure precedence.

The legacy V2 ranked request path may route through the canonical internal pipeline only
after equivalence is proven and without re-analyzing the terms already frozen in a
`TextScoringQuery`. Equivalent legacy and V3 text requests must return the same hit set,
scores, and order.

Phase 3 adds no bool, boost, cross-field, phrase, fuzzy, Explain, plan cache, prepared
query, or WAND behavior.

The complete frozen boundary is recorded in
[`phases/p3/SEARCH_PIPELINE.md`](phases/p3/SEARCH_PIPELINE.md).

## Phase 4 — Bool, boost, and cross-field ranked search

Phase 4 implements internal bool and boost plan nodes, nested composition, and
cross-field text clauses. When MUST clauses exist, every MUST matches and the score is
the sum of MUST contributions plus matching SHOULD contributions. Without MUST clauses,
at least one SHOULD matches. Boost multiplies its child score without changing match
semantics.

Each field computes BM25 from its own `N`, `df`, `dl`, and `avgdl`. Scores are added in
the frozen logical encounter order.

Phase 4 adds no phrase, fuzzy, `minimumShouldMatch`, ranked `mustNot`, BM25F, DisMax, or
hidden normalization.

Phase 4 implements whole-tree unsupported-shape preflight,
deterministic per-occurrence normalization, zero-term match-none leaves, canonical-index
requirements only for non-empty leaves, node-by-node checked BOOST arithmetic, and
matched state independent from score positivity. The complete boundary is recorded in
[`phases/p4/RANKED_COMPOSITION.md`](phases/p4/RANKED_COMPOSITION.md); implementation and
validation are tracked in
[`phases/p4/PHASE_4_CHECKLIST.md`](phases/p4/PHASE_4_CHECKLIST.md).

## Phase 5 — Exact phrase search

Phase 5 implements `SearchQueries.phrase(...)`, an internal phrase plan, posting-based
candidate generation, and exact relative-position verification. V3.0 supports slop zero
only. Repeated terms remain positional and phrase scoring uses distinct phrase terms
with ordinary BM25 contributions.

The completed implementation enforces full positioned-output validation, normalized
relative slots, same-position alternatives, empty-leaf and missing-index precedence,
slot-union/phrase-intersection candidates, deterministic union-cardinality anchor
selection, checked relative-position arithmetic, and exact positional verification
through one narrow Javadoc-hidden internal bridge. Phrase scoring remains ordinary
field-local distinct-term BM25 in Analyzer encounter order and composes through the
existing BOOL/BOOST tree.

It adds no phrase slop, fuzzy phrase, offsets, highlighting, phrase-frequency bonus, or
proximity scoring.

The complete boundary is recorded in
[`phases/p5/EXACT_PHRASE_SEARCH.md`](phases/p5/EXACT_PHRASE_SEARCH.md); implementation
and validation are tracked in
[`phases/p5/PHASE_5_CHECKLIST.md`](phases/p5/PHASE_5_CHECKLIST.md), with focused
performance evidence in
[`phases/p5/PERFORMANCE_BASELINE.md`](phases/p5/PERFORMANCE_BASELINE.md).

## Phase 6 — Fuzzy term search

Phase 6 implements `SearchQueries.fuzzy(...)`, an internal fuzzy plan and expander,
bounded Optimal String Alignment distance over Unicode code points, AUTO edit distance,
candidate union, and the frozen fuzzy scoring rules. The initial expander may scan the
bounded vocabulary behind an internal abstraction.

Before implementation, Phase 6 freezes emitted-token cardinality and positioned-output
validation, empty-leaf and missing-index precedence, exact Unicode code-point ordering,
the bounded OSA sentinel contract, full deterministic expansion without truncation,
exact-term scoring priority, max-not-sum similarity-weighted BM25, checked arithmetic,
snapshot/dynamic-index lifecycle, and one narrow Javadoc-hidden vocabulary traversal
bridge. Planning may scale with vocabulary size but performs no lexical work per
document.

It adds no automatic multi-token fuzzy, fuzzy phrase, spelling correction, magic
max-expansion truncation, persistent fuzzy trie, or Levenshtein automaton.

The complete boundary is recorded in
[`phases/p6/FUZZY_SEARCH.md`](phases/p6/FUZZY_SEARCH.md); implementation and validation
are tracked in
[`phases/p6/PHASE_6_CHECKLIST.md`](phases/p6/PHASE_6_CHECKLIST.md).

## Phase 7 — Explain

Phase 7 implements `SearchEngine.explain(SearchRequest<T>, K)` with the same planning,
matching, arithmetic, and scoring operations as normal ranked search. It explains text,
phrase, selected fuzzy expansion, boost, bool composition, structured-filter outcome,
and BM25 details.

Normal matched state must equal explained matched state, and normal score must equal
explained score. Explain exposes no internal document IDs, posting references, raw
positions, snapshot handles, or public planner nodes.

## Phase 8 — Hardening and 3.0.0 release

Phase 8 adds no features. It completes correctness, randomized/differential, mutation,
snapshot, legacy-equivalence, and Explain-invariant validation; performance baselines
and evidence-driven optimization; compatibility and independent-consumer gates; public
documentation and examples; release artifacts, signing, reproducibility, CI/CD, Maven
Central, and GitHub Release preparation.

The travel example should demonstrate structured filtering, text ranking, cross-field
ranking, exact phrase search, fuzzy typo tolerance, Explain, and dynamic-index behavior.

## V3.0 explicit exclusions

The following are not V3.0 blockers: phrase slop, `minimumShouldMatch`, ranked
`mustNot`, automatic multi-token fuzzy, fuzzy phrase, spell correction, stemming,
synonym dictionaries, highlighting, token offsets, ranked prefix-as-you-type, BM25F,
DisMax, custom/function scoring, learning-to-rank, personalization, WAND, plan caching,
prepared queries, parallel scoring, a global cost optimizer, pagination/search-after,
total-hits contracts, facets/aggregations/grouping/timeouts, persistence/WAL, vector
search, and distributed retrieval.

New ideas belong in a V3.x or V4 backlog unless required for correctness or a frozen
V3.0 contract.

Likely V3.1 candidates are phrase slop, `minimumShouldMatch`, advanced fuzzy controls,
and an optimized fuzzy dictionary. Likely V3.2 candidates are highlighting, offsets,
synonyms, advanced analyzers, and ranked prefix search. A likely V4 theme is durability
through WAL, checkpoints, crash recovery, and reopening persisted indexes.
