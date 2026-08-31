# Changelog

All notable changes to GeneralSearchEngine are recorded here. The project follows
Semantic Versioning once the first stable artifact is published.

## 3.2.0-SNAPSHOT — Unreleased

### Added

- Additive `OffsetAnalyzer` and `OffsetAnalyzedToken` APIs for deterministic logical
  positions and exact half-open UTF-16 source ranges without changing the published
  `Analyzer` SAM or `AnalyzedToken` record.
- Snapshot-bound structured highlighting through immutable request, hit, field,
  fragment, and span values. Highlighted hits preserve canonical documents, score
  bits, ordering, limits, filters, failures, and Explain semantics.
- Deterministic highlight evidence for TEXT, ordered PHRASE witnesses,
  scoring-selected FUZZY expansions, and recursive BOOL/BOOST composition.
- Focused and randomized Unicode mapping, independent differential oracles, mutation,
  dynamic-index, lifecycle, mixed-concurrency, storage-boundary, allocation, latency,
  scale, and retained-memory coverage.

### Changed

- The built-in `SimpleAnalyzer` implements the offset capability while preserving its
  existing ordinary term and positioned-output paths.
- Explicit highlighting re-analyzes only requested fields of returned top-K documents;
  no offset, evidence, highlight, or sidecar payload is stored in text snapshots.

This development heading does not claim publication. Published `3.1.0` remains the
current stable release until the signed V3.2 release workflow and remote verification
complete.

## 3.1.0 — 2026-08-30

### Added

- Ordered phrase slop through `SearchQueries.phrase(field, text, slop)`, preserving
  exact phrase behavior at slop zero and existing distinct-term BM25 scoring.
- Explicit ranked BOOL thresholds through `BoolBuilder.minimumShouldMatch(int)`, while
  preserving V3.0 matching and scoring when no threshold is configured.
- Focused, randomized, differential, lifecycle, mutation, concurrency, and Explain
  coverage for the V3.1 ranked-query additions.
- A separately identified `ranked-v31` benchmark lane with reviewed 1M concurrency,
  publication, dynamic-index, failure, and soak evidence.

### Changed

- Fuzzy vocabulary expansion now uses an exact persistent Unicode code-point trie with
  bounded OSA traversal while retaining the complete V3.0 full-scan result semantics.
- Phrase planning and verification reduce measured allocation without changing match,
  score, order, validation, snapshot, or Explain behavior.

## 3.0.0 — 2026-08-26

### Added

- Phase 8 release hardening with bounded BOOL/phrase/fuzzy stress coverage, a named V3
  JMH and retained-memory baseline, a 2.1-to-3.0 migration guide, a state-aware release
  checklist, and a complete supported-public-API travel scenario.
- CI JMH forked smoke validation and post-publication verification of remote POM/main/
  sources/Javadoc artifacts, detached signatures, checksums, service entries,
  manifests, and a clean published V3 consumer.
- V3 per-business-document Explain execution through the canonical snapshot-bound
  ranked plan, with top-K-independent match/score parity and deterministic generic
  diagnostics for TEXT, PHRASE, FUZZY, BOOL, BOOST, cross-field BM25, and structured
  filter outcomes.
- Explain coverage for missing and non-matching IDs, BM25 facts, empty analysis,
  malformed Analyzer output, exact phrase and fuzzy selection, recursive randomized
  invariants, concurrent publication, dynamic indexes, mutations, and an executable
  independent V3 consumer example.
- V3 single-term fuzzy execution with complete positioned-output validation, Unicode
  code-point AUTO edit bounds, bounded Optimal String Alignment, deterministic full
  vocabulary expansion, exact candidates, exact-term priority, and best-expansion
  similarity-weighted BM25 scoring inside recursive BOOL/BOOST plans.
- Fuzzy randomized distance, expansion, match/score/order, mutation, snapshot, and
  dynamic-index lifecycle coverage; an executable independent V3 consumer typo query;
  and focused JMH planning/execution evidence across multiple vocabulary sizes.
- V3 exact phrase execution with normalized relative-position slots, same-position
  alternatives, repeated-term matching, posting-based safe candidates, deterministic
  anchor verification, and ordinary distinct-term field-local BM25 scoring.
- Whole-tree PHRASE/FUZZY failure precedence, snapshot and dynamic-index lifecycle
  coverage, randomized exact-match/score/order differential tests, an executable V3
  consumer phrase example, and a focused exact-phrase JMH smoke.
- V3 recursive ranked BOOL and BOOST execution with MUST/SHOULD candidate composition,
  nested query support, cross-field field-local BM25 statistics, checked deterministic
  score arithmetic, and matched zero-score retention.
- Whole-tree ranked-query validation, per-occurrence positioned analysis, empty-leaf
  and missing-index precedence coverage, randomized recursive differential tests, a
  cross-field independent consumer, and a focused ranked-composition JMH smoke.
- V3 direct text `SearchRequest` execution with one immutable snapshot-bound planning
  and BM25 pipeline, including optional structured filters, custom BM25 configuration,
  deterministic bounded top-K ordering, and positioned query analysis.
- Focused request-pipeline, visibility, frozen-term, configured-planner, concurrent
  snapshot, and randomized V2/V3 exact-equivalence coverage; the independent V3
  consumer now executes a supported text request against the built-in engine.
- Internal primitive-backed positional posting storage, position-sensitive immutable
  text-index mutations, deterministic randomized differential coverage, and a focused
  Phase 2 build/publication allocation baseline.
- Position-aware analysis through the immutable `AnalyzedToken` record and the
  backward-compatible default `Analyzer.analyzeWithPositions(String)` adapter, while
  preserving existing Analyzer lambdas and all legacy text execution paths.
- V3 Phase 0 request, ranked-query, result, and explanation model contracts under
  `io.github.patricklfdm.generalsearch.search`, plus additive default request-search and
  Explain capabilities on `SearchEngine`.
- Frozen V3 architecture, ranked-search, positional, fuzzy, and API compatibility
  documents; a v3-style independent consumer; and a direct Japicmp baseline against
  published `2.1.0`.

### Changed

- Bounded OSA fuzzy expansion now reuses its code-point and dynamic-programming
  workspace across vocabulary terms, preserving complete Unicode expansion semantics
  while removing the measured per-term temporary-array allocation pathology.
- The Phase 3 single-text plan is now an internal immutable recursive scoring tree while
  preserving direct V3 text and frozen-term V2 scores, filters, limits, ordering,
  snapshot behavior, and public descriptors.
- Legacy `RankedSearcher` and built-in `searchTopK` now adapt frozen V2 terms into the
  same canonical execution core as V3 without re-analysis, while preserving all V2
  scores, filters, limits, ordering, constructors, and planner configuration.
- Text indexing, indexed and scan text-query projection, and legacy BM25 query
  projection now consistently consume validated position-aware Analyzer output. Legacy
  analyzers retain their default-adapted terms, frequencies, lengths, and ranking.
- Opened the `3.0.0` development line after the 2.1.0 release, beginning with
  additive request/query/result contracts and frozen semantics before new execution.

### Fixed

- JMH packaging now overwrites invalid first-pass generated harness classes with the
  explicitly recompiled output; the required smoke case proves the shaded harness can
  fork and execute instead of treating package success as sufficient.

## 2.1.0 — 2026-08-25

### Added

- `@SearchField` for registering ordinary class fields/getters without creating a
  startup index, enabling consistent dynamic-index and analyzed-text configuration.
- `SearchEngineBuilder.textIndex(fieldName, analyzer)` for direct runtime-annotation
  and generated-schema text configuration without manual `TextField` assembly.
- `SearchEngine.field(...)` and `SearchEngine.textField(...)` default methods for
  concise access to canonical query fields without traversing `engine.schema()`.
- External travel-domain consumer coverage for generated structured fields, analyzed
  text, filtered BM25, atomic bulk mutation, and a dynamic Range index.
- Clear generated-source comments and README guidance for annotation processing,
  generated-source locations, and deterministic nested-type naming.

### Changed

- Core, processor, reactor, examples, and compatibility consumers now use the final
  `2.1.0` coordinates.
- The processor-free travel demo is now a reactor-compiled example module, and the
  README puts development installation and the annotated quick start before internals.
- Unknown field lookups now list canonical choices and suggest close spellings; the
  travel example also has a one-command runner.
- `SearchEngine.builder(existingSchema)` can safely extend a copied configuration.
  Adding `IndexDefinition.text(textField)` automatically registers the text field
  without mutating the supplied schema or requiring manual schema reconstruction.
- Configuration failures now explain how to reuse canonical generated fields or
  register analyzed-text definitions.

## 2.0.0 — 2026-08-25

### Added

- P0 architecture contracts, compatibility guardrails, owner decision register, phase
  gates, and v2 benchmark matrix.
- Optional `EstimatingIndexSnapshot<T>` capability with immutable `IndexStatistics`,
  `CandidateEstimate`, and estimate-quality metadata.
- Exact, non-materializing estimates for built-in Equality, Range, and Prefix indexes.
- P1 randomized, snapshot-isolation, legacy-index, and dynamic-build/replay tests.
- JMH baselines separating Range estimation from candidate materialization and measuring
  index publication at low and high distinct-key counts.
- P2 randomized tests and JMH matrices for bulk bitmap union, immutable dictionary
  publication, tombstone histories, post-P2 Range costs, and mutation batching.
- Accepted P2 performance baseline and D3 hybrid representation, with broad Range
  estimate acquisition cost recorded as a P3 planning constraint.
- Additive `PlannerConfig` and `RangePlanningMode` controls for cost-aware,
  forced-index, and forced-scan Range execution.
- P3 delayed access paths, selected-only candidate materialization, conservative AND
  planning, and Range/bucket-spread/AND-correlation JMH matrices.
- Accepted P3 performance baseline with bounded ordered-index estimates and calibrated
  Range index-versus-scan selection.
- P4 canonical `TextField<T>`/`Analyzer` configuration, deterministic NFKC simple
  analysis, and explicit term/any-terms/all-terms boolean queries.
- Immutable inverted indexes using persistent AVL term dictionaries and `PostingList`
  values with exact membership, document frequency, and P5-ready term frequency.
- Text startup and dynamic index lifecycle integration, mutation replay, failure
  recovery, analyzed scan oracles, randomized differential coverage, and P4 JMH
  query/publication/build matrices.
- P5 additive `TextScoringQuery`, `RankedSearchRequest`, `Bm25Config`, `SearchHit`, and
  default `SearchEngine.searchTopK(...)` capability.
- Posting-driven BM25 with immutable document-length statistics, optional existing
  boolean filters, bounded top-K heap retention, and deterministic internal-document-ID
  tie-breaking.
- Hand-computed BM25 golden tests, randomized exhaustive full-sort differential tests,
  engine lifecycle regressions, and P5 ranking/publication/build JMH matrices.
- P6 atomic `addAll`, `updateAll`, and `removeAll` collection mutations with explicit
  size/duplicate failure context, single-publication ordering, and dynamic-index replay.
- Optional `general-search-engine-processor` artifact generating deterministic typed
  `*SearchFields` constants, canonical schemas, and index definitions at compile time.
- P6 javac success/failure/equivalence fixtures and an eight-row explicit-bulk JMH
  matrix covering valid and invalid batches of 1, 10, 100, and 1,000 operations.
- P7 mixed structured/text/BM25 exhaustive oracle, analyzer atomic-failure regression,
  and opt-in concurrent v2 soak runner.
- Published-v1 artifact compatibility profile plus independent v1-style and
  processor-enabled v2-style consumer projects.
- v2 compatibility classification, migration guide, release checklist, and P7
  target-machine validation runbook.
- Completed the P7 target-machine soak over 100,000 documents for 300.11 seconds with
  8 readers, 2 writers, 19,888 mutations, 2,701 dynamic-index cycles, and final
  exhaustive state verification.

### Changed

- Release coordinates now use `2.0.0`; the published compatibility
  baseline remains `1.0.0`.
- Mutation failure/rejection metrics are published before their returned futures are
  completed, removing a completion-versus-observability race found by the P7 gate.
- Built-in index builders maintain indexed-document counts in the same immutable
  publication lifecycle as their value buckets.
- Range, Prefix, and composite OR candidates accumulate bitmap blocks and freeze once,
  with a direct single-source reuse path.
- Equality publications use a bounded dirty overlay; ordered Range and Prefix
  dictionaries use persistent AVL path copying. Unchanged builders reuse base index and
  registry snapshots.
- Persistent Range/Prefix AVL nodes maintain immutable subtree candidate weights and
  bucket counts, making estimate acquisition proportional to tree height.
- Direct Range queries can choose scan from snapshot-local cost inputs; OR and NOT keep
  their existing compatibility planning and final predicates remain query truth.
- Text query and index execution share the schema-owned Analyzer. Text candidates are
  exact; multi-term estimate quality remains separate from candidate accuracy.
- Text snapshots atomically publish per-document and average analyzed lengths together
  with P4 TF/DF metadata. Existing unranked searches retain their truth and ordering.
- A separate `reactor/pom.xml` builds the unchanged runtime artifact together with the
  opt-in processor; release and reproducibility behavior now cover both artifacts.

### Compatibility

- The v1 `IndexSnapshot<T>` SPI is unchanged. Estimation is an additive optional
  interface, and legacy non-estimating indexes retain their existing candidate path.
- P1 does not alter normal query-planner choices or v1 query result semantics.
- P2 changes internal representations only. P3 planning APIs are additive, preserve
  v1 results, and do not alter existing record descriptors or the custom-index SPI.
- P4 text APIs are additive and leave the v1 `IndexSnapshot<T>` SPI and public record
  descriptors unchanged. BM25/ranking, phrase/position, fuzzy, persistence, and
  distributed behavior remain deferred or out of scope.
- P5 ranking APIs are additive, `searchTopK(...)` is a default interface method, and
  existing unranked query truth and result ordering remain unchanged.
- P6 bulk methods are additive interface defaults. The core artifact contains no
  annotation-processor service entry, and runtime annotation generation remains
  available without the processor artifact.
- P7 artifact comparison reports no binary or source incompatibility against the
  published v1.0.0 JAR; all supported changes are additive.

### Performance

- Accepted the complete 58-row P4 analyzed-text baseline: seven single-term document
  frequencies, 1/4/8-term any/all queries, 10K/100K vocabulary publication, and raw
  versus dynamic build matrices.
- Direct posting lookup remained effectively independent of document frequency, and
  tenfold vocabulary growth did not cause full-dictionary publication copying.
- Recorded high-selectivity final-verification cost and benchmark variance without
  defining a universal crossover or advertising exact speedups.
- Accepted the complete 70-row P5 matrix covering bounded heap versus full sort, K and
  document frequency, structured filtering, multi-term scoring, ranking metadata
  publication, and raw/dynamic index build cost.
- Recorded that bounded retention helps selected small-K/large-eligible-set workloads,
  while retaining every hit favors full sort and current transient allocation still
  follows eligible-candidate count; no universal speedup or crossover is claimed.
- Accepted the complete eight-row P6 explicit-bulk matrix. Successful collections
  published exactly once and invalid collections published nothing at batch sizes 1,
  10, 100, and 1,000.
- Recorded fixed-cost amortization and rollback allocation/latency as workload-specific
  regression evidence without defining a universal batching multiplier.
- Accepted all 141 representative P7 structured, text, BM25, publication, build, and
  explicit-bulk rows. Targeted review attributed two wide intervals to isolated stalls;
  stable allocation and a clean batch-1,000 confirmation found no repeatable regression.

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
