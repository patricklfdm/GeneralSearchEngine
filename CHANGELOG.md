# Changelog

All notable changes to GeneralSearchEngine are recorded here. The project follows
Semantic Versioning once the first stable artifact is published.

## 1.0.0 — 2026-08-21

### Added

- Generic `SearchEngine<K,T>` with builder and annotation-generated configuration.
- Type-safe Equality, inclusive Range, Prefix, AND, OR, NOT, and MatchAll queries.
- Immutable snapshots, persistent bitmaps, asynchronous batched mutations, and dynamic
  index creation/drop with atomic publication.
- Operational metrics, stable asynchronous failure types, concurrent stress runner,
  and thirteen JMH benchmarks.
- Frozen v1 boundary semantics and source/JVM-descriptor compatibility checks.
- Release profile producing main, sources, and Javadoc JARs plus reproducible-build
  verification.
- Maven coordinates `io.github.patricklfdm:general-search-engine:1.0.0` and Java root
  package `io.github.patricklfdm.generalsearch`.
- Apache License 2.0 project and Maven metadata.

### Compatibility

- `SnapshotSearchEngine` constructors remain available, while new applications should
  use `SearchEngine.builder(...)` or annotation factories.
- Deprecated Product filters remain source-compatible throughout the v1 release line.

### Fixed

- Range indexes now preserve correctness for Comparable values whose `compareTo`
  equivalence differs from `equals`, including BigDecimal scale variants.

### Scope

Full-text search/BM25, fuzzy search, WAL/persistence, and distributed search/sharding
are intentionally out of scope for v1.0.0.
