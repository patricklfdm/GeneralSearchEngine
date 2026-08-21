# Changelog

All notable changes to GeneralSearchEngine are recorded here. The project follows
Semantic Versioning once the first stable artifact is published.

## Unreleased — 1.0.0 candidate

### Added

- Generic `SearchEngine<K,T>` with builder and annotation-generated configuration.
- Type-safe Equality, inclusive Range, Prefix, AND, OR, NOT, and MatchAll queries.
- Immutable snapshots, persistent bitmaps, asynchronous batched mutations, and dynamic
  index creation/drop with atomic publication.
- Operational metrics, stable asynchronous failure types, concurrent stress runner,
  and nine JMH benchmarks.
- Frozen v1 boundary semantics and source/JVM-descriptor compatibility checks.
- Release profile producing main, sources, and Javadoc JARs plus reproducible-build
  verification.

### Compatibility

- `SnapshotSearchEngine` constructors remain available, while new applications should
  use `SearchEngine.builder(...)` or annotation factories.
- Deprecated Product filters remain source-compatible throughout the v1 release line.

### Fixed

- Range indexes now preserve correctness for Comparable values whose `compareTo`
  equivalence differs from `equals`, including BigDecimal scale variants.
