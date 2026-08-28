# GeneralSearchEngine documentation

- [CI/CD and release operations](CI_CD.md)

This directory preserves the published v1, v2, and v3 records together with completed
development phases. The repository root [`README.md`](../README.md) remains the
user-facing entry point, and [`DEVELOPMENT_ROADMAP.md`](../DEVELOPMENT_ROADMAP.md)
remains the phase history and decision source of truth.

## v3 — current stable release

- [Development overview and contract map](v3/README.md)
- [API compatibility](v3/API_COMPATIBILITY.md)
- [2.1-to-3.0 migration guide](v3/MIGRATION_GUIDE.md)
- [V3.0 performance and memory baseline](v3/PERFORMANCE_BASELINE.md)
- [Reproducible GCP performance testing](v3/CLOUD_PERFORMANCE_TESTING.md)
- [Cloud soak diagnostics contract](v3/CLOUD_SOAK_DIAGNOSTICS.md)
- [Cloud soak root-cause investigation results](v3/CLOUD_SOAK_ROOT_CAUSE_RESULTS.md)
- [Cloud soak early-window stabilization contract](v3/CLOUD_SOAK_EARLY_WINDOW_STABILIZATION.md)
- [V3.0 release checklist](v3/RELEASE_CHECKLIST.md)
- [Phase 0 architecture](v3/phases/p0/ARCHITECTURE.md)
- [Ranked-search semantics](v3/phases/p0/SEARCH_SEMANTICS.md)
- [Positional semantics](v3/phases/p0/POSITIONAL_SEMANTICS.md)
- [Fuzzy semantics](v3/phases/p0/FUZZY_SEMANTICS.md)
- [Phase 0 checklist](v3/phases/p0/PHASE_0_CHECKLIST.md)
- [Phase 8 hardening and release contract](v3/phases/p8/HARDENING_AND_RELEASE.md)
- [Phase 8 checklist](v3/phases/p8/PHASE_8_CHECKLIST.md)

## v1 — published and frozen

- [Semantics](v1/SEMANTICS.md)
- [Supported API and compatibility contract](v1/API_COMPATIBILITY.md)
- [Performance baseline](v1/PERFORMANCE_BASELINE.md)
- [JMH diagnostic round 2](v1/JMH_DIAGNOSTIC_ROUND_2.md)
- [Historical v1 release checklist](v1/RELEASE_CHECKLIST.md)

## v2 — published and frozen

- [Migration guide](v2/MIGRATION_GUIDE.md)
- [API compatibility audit](v2/API_COMPATIBILITY.md)
- [Published release record](v2/RELEASE_CHECKLIST.md)

## v2.1 — previous stable release

- [Release checklist](v2.1/RELEASE_CHECKLIST.md)

## v2 phase evidence

| Phase | Scope | Documentation |
|---|---|---|
| P0 | architecture and guardrails | [Architecture](v2/phases/p0/ARCHITECTURE.md) |
| P1 | statistics and estimates | [Performance baseline](v2/phases/p1/PERFORMANCE_BASELINE.md) |
| P2 | bitmap/publication groundwork | [Performance baseline](v2/phases/p2/PERFORMANCE_BASELINE.md) |
| P3 | cost-aware planner | [Performance baseline](v2/phases/p3/PERFORMANCE_BASELINE.md) |
| P4 | analyzed full-text search | [Semantics](v2/phases/p4/TEXT_SEMANTICS.md), [performance](v2/phases/p4/PERFORMANCE_BASELINE.md) |
| P5 | BM25 ranked top-K | [Semantics](v2/phases/p5/RANKING_SEMANTICS.md), [performance](v2/phases/p5/PERFORMANCE_BASELINE.md) |
| P6 | bulk mutation and typed-field processor | [Developer experience](v2/phases/p6/DEVELOPER_EXPERIENCE.md), [performance](v2/phases/p6/PERFORMANCE_BASELINE.md) |
| P7 | stabilization and release readiness | [Validation record](v2/phases/p7/RELEASE_VALIDATION.md), [performance](v2/phases/p7/PERFORMANCE_BASELINE.md) |

Raw JMH JSON, soak logs, compiled classes, generated reports, and release artifacts
belong under `target/`. They are disposable validation output and are not repository
documentation.
