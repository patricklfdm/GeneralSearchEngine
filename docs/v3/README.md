# GeneralSearchEngine v3.0

Version `3.0.0` is the current stable release. It adds a higher-level ranked text
retrieval API while preserving the structured and ranked APIs published through 2.1.0.

## Phase map

| Phase | Scope | Status |
|---|---|---|
| Phase 0 | API, architecture, semantics, and compatibility contracts | Complete |
| Phase 1 | position-aware Analyzer API and legacy adapter | Complete |
| Phase 2 | positional posting storage and consistent positioned-term consumption | Complete |
| Phase 3 | SearchRequest planning and execution pipeline | Complete |
| Phase 4 | bool, boost, and cross-field ranked composition | Complete |
| Phase 5 | exact phrase search | Complete |
| Phase 6 | single-term fuzzy search | Complete |
| Phase 7 | Explain execution | Complete |
| Phase 8 | hardening and release | Complete |

Phase 0 deliberately adds no new ranked-search execution. Its purpose is to make the
later implementation auditable and difficult to change accidentally.

Phase 1 adds only the position-aware Analyzer model and backward-compatible default
adapter. Existing text execution still uses legacy tokens; positional consumption and
storage remain deferred.

Phase 2 is the first positioned-analysis consumer. Index, scan, and BM25 term
projection now consistently use validated positioned output, while internal primitive
position storage retains the facts needed by later phrase execution.

Phase 3 implements one snapshot-bound pipeline for direct V3 text requests and the
legacy V2 ranked adapter. It preserves frozen legacy terms, configured filter planning,
BM25 arithmetic, bounded top-K retention, and deterministic ordering.

Phase 4 implements recursive TEXT/BOOL/BOOST plans, whole-tree shape validation,
empty-leaf and missing-index precedence, field-local cross-field BM25, checked
deterministic arithmetic, and matched zero-score retention. Physical candidate
composition remains separate from logical scoring order.

Phase 5 implements positioned phrase normalization, posting-based safe candidates,
deterministic anchor verification, exact relative-position matching, distinct-term
BM25, recursive composition, and failure precedence through one narrow hidden
positional bridge. Focused, randomized, lifecycle, consumer, compatibility, release,
reproducibility, and performance-smoke gates cover the completed implementation.

Phase 6 implements single-emitted-token fuzzy analysis, Unicode code-point AUTO
thresholds, bounded Optimal String Alignment distance, deterministic full vocabulary
expansion, exact-term priority, best-expansion BM25, and recursive composition through
one narrow hidden vocabulary bridge. Randomized differential and lifecycle tests,
independent-consumer coverage, compatibility/release gates, and focused JMH evidence
cover the completed implementation.

Phase 7 implements missing-ID precedence, snapshot-local canonical-plan reuse,
top-K-independent per-document evaluation, deterministic
TEXT/PHRASE/FUZZY/BOOL/BOOST/filter diagnostics, shared scoring arithmetic, and no
explanation allocation on the normal search path. Focused and randomized invariants,
lifecycle/concurrency coverage, independent consumers, compatibility, release, and
reproducibility gates cover the completed implementation.

Phase 8 adds no search capability. It freezes the supported V3 surface, closes only
release-critical validation gaps, records bounded performance and memory evidence,
finalizes migration/newcomer/release documentation, and follows the protected
tag-triggered 3.0.0 publication and post-publication verification state machine.

## Contracts

- [API compatibility](API_COMPATIBILITY.md)
- [2.1-to-3.0 migration guide](MIGRATION_GUIDE.md)
- [V3.0 performance and memory baseline](PERFORMANCE_BASELINE.md)
- [Production performance testing](PRODUCTION_PERFORMANCE_TESTING.md)
- [Reproducible GCP performance testing](CLOUD_PERFORMANCE_TESTING.md)
- [Cloud Benchmark V2 Phase 0 evidence model](CLOUD_BENCHMARK_V2_PHASE_0.md)
- [Cloud soak diagnostics contract](CLOUD_SOAK_DIAGNOSTICS.md)
- [Cloud soak diagnostic results](CLOUD_SOAK_DIAGNOSTIC_RESULTS.md)
- [Cloud soak root-cause investigation contract](CLOUD_SOAK_ROOT_CAUSE_INVESTIGATION.md)
- [Cloud soak root-cause investigation results](CLOUD_SOAK_ROOT_CAUSE_RESULTS.md)
- [Cloud soak early-window stabilization contract](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION.md)
- [Cloud soak early-window stabilization results](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION_RESULTS.md)
- [Production performance follow-up results](PRODUCTION_PERFORMANCE_RESULTS.md)
- [V3.0 release checklist](RELEASE_CHECKLIST.md)
- [Canonical V3 roadmap](ROADMAP.md)
- [Architecture](phases/p0/ARCHITECTURE.md)
- [Ranked-search semantics](phases/p0/SEARCH_SEMANTICS.md)
- [Positional semantics](phases/p0/POSITIONAL_SEMANTICS.md)
- [Fuzzy semantics](phases/p0/FUZZY_SEMANTICS.md)
- [Phase 0 checklist](phases/p0/PHASE_0_CHECKLIST.md)
- [Phase 1 position-aware analysis contract](phases/p1/POSITION_AWARE_ANALYSIS.md)
- [Phase 1 implementation checklist](phases/p1/PHASE_1_CHECKLIST.md)
- [Phase 2 positional storage contract](phases/p2/POSITIONAL_STORAGE.md)
- [Phase 2 implementation checklist](phases/p2/PHASE_2_CHECKLIST.md)
- [Phase 2 performance baseline](phases/p2/PERFORMANCE_BASELINE.md)
- [Phase 3 search pipeline contract](phases/p3/SEARCH_PIPELINE.md)
- [Phase 3 implementation checklist](phases/p3/PHASE_3_CHECKLIST.md)
- [Phase 4 ranked composition contract](phases/p4/RANKED_COMPOSITION.md)
- [Phase 4 implementation checklist](phases/p4/PHASE_4_CHECKLIST.md)
- [Phase 4 performance smoke](phases/p4/PERFORMANCE_BASELINE.md)
- [Phase 5 exact phrase search contract](phases/p5/EXACT_PHRASE_SEARCH.md)
- [Phase 5 implementation checklist](phases/p5/PHASE_5_CHECKLIST.md)
- [Phase 5 performance smoke](phases/p5/PERFORMANCE_BASELINE.md)
- [Phase 6 single-term fuzzy search contract](phases/p6/FUZZY_SEARCH.md)
- [Phase 6 implementation checklist](phases/p6/PHASE_6_CHECKLIST.md)
- [Phase 6 performance smoke](phases/p6/PERFORMANCE_BASELINE.md)
- [Phase 7 Explain execution contract](phases/p7/EXPLAIN_EXECUTION.md)
- [Phase 7 implementation checklist](phases/p7/PHASE_7_CHECKLIST.md)
- [Phase 8 hardening and release contract](phases/p8/HARDENING_AND_RELEASE.md)
- [Phase 8 checklist](phases/p8/PHASE_8_CHECKLIST.md)

The v1 and v2 documents remain frozen historical records. V3 documents describe only
the published additive V3 line and must not be read as changing existing query truth,
ordering, mutation, snapshot, or `searchTopK` behavior.
