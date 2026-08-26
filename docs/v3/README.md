# GeneralSearchEngine v3 development

Version `3.0.0-SNAPSHOT` develops a higher-level ranked text retrieval API while
preserving the structured and ranked APIs published through 2.1.0. Version 2.1.0
remains the current stable release until 3.0.0 is published.

## Phase map

| Phase | Scope | Status |
|---|---|---|
| Phase 0 | API, architecture, semantics, and compatibility contracts | Complete |
| Phase 1 | position-aware Analyzer API and legacy adapter | Complete |
| Later phases | positional storage, phrase/fuzzy execution, planner, executor, and Explain | Planned |

Phase 0 deliberately adds no new ranked-search execution. Its purpose is to make the
later implementation auditable and difficult to change accidentally.

Phase 1 adds only the position-aware Analyzer model and backward-compatible default
adapter. Existing text execution still uses legacy tokens; positional consumption and
storage remain deferred.

## Contracts

- [API compatibility](API_COMPATIBILITY.md)
- [Architecture](phases/p0/ARCHITECTURE.md)
- [Ranked-search semantics](phases/p0/SEARCH_SEMANTICS.md)
- [Positional semantics](phases/p0/POSITIONAL_SEMANTICS.md)
- [Fuzzy semantics](phases/p0/FUZZY_SEMANTICS.md)
- [Phase 0 checklist](phases/p0/PHASE_0_CHECKLIST.md)
- [Phase 1 position-aware analysis contract](phases/p1/POSITION_AWARE_ANALYSIS.md)
- [Phase 1 implementation checklist](phases/p1/PHASE_1_CHECKLIST.md)

The v1 and v2 documents remain frozen historical records. V3 documents describe only
the additive development line and must not be read as changing existing query truth,
ordering, mutation, snapshot, or `searchTopK` behavior.
