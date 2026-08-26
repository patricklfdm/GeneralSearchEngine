# V3 Phase 0 architecture contract

## Boundary

V3 separates structured eligibility from ranked relevance:

```text
Query<T>       -> deterministic boolean eligibility/filtering
SearchQuery<T> -> ranked retrieval and relevance
```

`SearchQuery<T>` is a final public façade, not a public subtype hierarchy. Users create
queries through `SearchQueries`; internal text, phrase, fuzzy, bool, and boost nodes stay
private or package-private and carry no compatibility guarantee.

## Public request path

```text
SearchRequest<T>
├── required SearchQuery<T>
├── optional Query<T> filter
├── positive limit
└── Bm25Config
        │
        ▼
SearchEngine.search(SearchRequest<T>)
        │
        ▼ later phases
SearchPlanner -> immutable SearchPlan -> SearchExecutor -> SearchResult<T>
```

Planning and execution will bind to the immutable snapshot observed at invocation
start. Candidate planning may reuse the existing structured `CandidatePlanner`, but a
structured filter contributes no score. `SearchResult` does not pin a snapshot.

## Explain

`SearchEngine.explain(request, id)` is an optional additive capability. Later execution
must reuse the same plan and scoring operations as normal ranked search so match and
score cannot drift. An existing non-matching document receives an explanation;
a missing business ID produces `Optional.empty()`.

## Legacy ranking

The published V2 `searchTopK(RankedSearchRequest<T>)` path remains supported. A future
internal adapter may route it through new internals only after equivalence is proven.
Phase 0 neither adds that adapter nor changes current ranking execution.

## Phase 0 boundary

Phase 0 adds only public model/factory contracts, default unsupported capabilities,
documentation, fixtures, and compatibility gates. It does not add position storage,
phrase or fuzzy execution, `SearchPlanner`, `SearchPlan`, `SearchExecutor`, Explain
execution, or new `SnapshotSearchEngine` behavior.
