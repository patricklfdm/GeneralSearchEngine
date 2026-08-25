# GeneralSearchEngine documentation

This directory preserves the published v1 and v2 records together with the completed
v2 development phases. The repository root [`README.md`](../README.md) remains the
user-facing entry point, and [`DEVELOPMENT_ROADMAP.md`](../DEVELOPMENT_ROADMAP.md)
remains the phase history and decision source of truth.

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
