# V3 Phase 0 checklist

## Contracts and API

- [x] Development modules and all three consumers resolve `3.0.0-SNAPSHOT`.
- [x] Version 2.1.0 remains documented as the current stable release.
- [x] Architecture, ranked, positional, fuzzy, and compatibility contracts are frozen.
- [x] `SearchRequest`, `SearchQuery`, `SearchQueries`, `SearchResult`,
  `SearchExplanation`, and `ExplanationNode` compile with strict Javadocs.
- [x] `SearchEngine` has additive default request-search and Explain capabilities.
- [x] The v3 independent consumer compiles representative API usage.

## Compatibility and packaging

- [x] Existing tests and the frozen v1 fixture pass.
- [x] Japicmp passes against 1.0.0, 2.0.0, and 2.1.0.
- [x] v1-, v2-, and v3-style consumers pass.
- [x] Core and processor main/source/Javadoc artifact checks pass.
- [x] Release-profile artifacts are reproducible.
- [x] The accepted `search(null)` overload ambiguity is documented.

## Scope

- [x] Existing structured and `searchTopK` observable behavior is unchanged.
- [x] No `AnalyzedToken`, position storage, or `IntPositions` implementation exists.
- [x] No phrase/fuzzy execution exists.
- [x] No new planner, plan, executor, Explain execution, or legacy adapter exists.
- [x] No generated artifacts or accidental build output are tracked.

Phase 0 is complete when the contract is difficult to violate later, not when V3 search
features execute.
