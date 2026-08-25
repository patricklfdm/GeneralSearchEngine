# GeneralSearchEngine v2 architecture contracts

## Status and scope

This document records the architecture contracts accepted during roadmap phase P0.
It constrains later implementation phases without adding v2 production behavior by
itself.

- Status: accepted P0 architecture baseline
- Accepted by the project owner: 2026-08-23
- Current development coordinates:
  `io.github.patricklfdm:general-search-engine:2.0.0`
- Published compatibility baseline: `io.github.patricklfdm:general-search-engine:1.0.0`
- Java package root: `io.github.patricklfdm.generalsearch`
- Detailed phase tracking: [`DEVELOPMENT_ROADMAP.md`](../../../../DEVELOPMENT_ROADMAP.md)
- P1 performance evidence:
  [`../p1/PERFORMANCE_BASELINE.md`](../p1/PERFORMANCE_BASELINE.md)
- P2 performance evidence:
  [`../p2/PERFORMANCE_BASELINE.md`](../p2/PERFORMANCE_BASELINE.md)
- P3 performance evidence:
  [`../p3/PERFORMANCE_BASELINE.md`](../p3/PERFORMANCE_BASELINE.md)
- P4 analyzed-text contract:
  [`../p4/TEXT_SEMANTICS.md`](../p4/TEXT_SEMANTICS.md)
- P4 accepted performance evidence:
  [`../p4/PERFORMANCE_BASELINE.md`](../p4/PERFORMANCE_BASELINE.md)
- P5 ranked-retrieval contract:
  [`../p5/RANKING_SEMANTICS.md`](../p5/RANKING_SEMANTICS.md)
- P5 accepted performance evidence:
  [`../p5/PERFORMANCE_BASELINE.md`](../p5/PERFORMANCE_BASELINE.md)
- P6 developer-experience contract:
  [`../p6/DEVELOPER_EXPERIENCE.md`](../p6/DEVELOPER_EXPERIENCE.md)
- P6 accepted explicit-bulk performance evidence:
  [`../p6/PERFORMANCE_BASELINE.md`](../p6/PERFORMANCE_BASELINE.md)

The contracts below preserve v1 correctness, immutable snapshots, lock-free readers,
single-writer ordering, dynamic index mutation replay, and atomic publication. Exact
class names that are marked conceptual remain internal design names until their owning
phase validates and introduces them.

## Accepted decisions

| ID | Accepted decision | Consequence |
|---|---|---|
| D1 | Preserve the v1 public API additively | Existing descriptors and behavior remain the default compatibility boundary |
| D2 | Add estimation through a separate optional capability | Existing `IndexSnapshot<T>` implementations do not gain a new abstract method |
| D3 | Select bounded dirty overlay or persistent structural sharing using P2 evidence | Full-map copying is not accepted as the steady-state large-dictionary strategy |
| D4 | Bind Analyzer semantics to a canonical schema/text field | Indexed and scan execution cannot choose different analysis per request |
| D5 | Model ranking as a scoring query plus an optional boolean filter | Boolean matching and relevance scoring remain separate responsibilities |
| D6 | Make explicit bulk mutation all-or-nothing | A successful bulk future represents one atomic publication |
| D7 | Package generated-field annotation processing separately | Runtime core users do not implicitly enable compile-time processing |
| D8 | Defer fluent string/session convenience APIs to v2.1 by default | Convenience scope cannot delay v2 search and ranking stabilization |

D3 is an evidence-gated implementation decision, not permission to leave the
large-dictionary problem unresolved. P2 must prototype the viable representations,
apply the benchmark matrix below, select the least complex qualifying design, and
record the evidence in the roadmap. Escalation to the project owner is required if the
measured winner materially changes API semantics, memory ownership, or the v2 scope.

## Confirmed v1 constraints

The following existing behavior shapes the v2 design:

- `IndexSnapshot<T>` is a public extension SPI with `field()`, `candidates(Query<T>)`,
  and `toBuilder()`. Adding an abstract method would break custom implementations.
- `IndexRegistry.candidates()` currently materializes every supporting index result and
  then chooses the smallest bitmap. Cost-aware planning must not reuse that eager flow.
- `CandidatePlanner<T>` treats an absent candidate result as a safe scan fallback.
- AND may retain a SUPERSET when only some children are planned; OR requires every
  child to provide candidates; NOT complements only an EXACT child.
- `SnapshotSearcher<T>` evaluates `Query.matches(T)` for every candidate. Candidate
  indexes therefore cannot change query truth.
- `SnapshotEngineConfig` and `SearchEngineMetrics` are public records. Adding record
  components changes their canonical JVM descriptors.
- Search results are in ascending internal document-ID order. Ranked retrieval must be
  a separate operation and must not change this unranked order.
- Built-in index builders and registry publication currently copy value maps. This is a
  write-amplification risk for a large text vocabulary.

The frozen v1 behavior remains defined by
[`../../../v1/SEMANTICS.md`](../../../v1/SEMANTICS.md), and its supported API by
[`../../../v1/API_COMPATIBILITY.md`](../../../v1/API_COMPATIBILITY.md).

## Contract A — Access-path discovery and delayed materialization

Planning is a two-step operation:

1. Discover which indexes can safely serve a query and obtain immutable estimates.
2. Choose an access path, then materialize only the selected candidate bitmap.

An access path conceptually carries:

- the producing index snapshot;
- the query it can serve;
- candidate accuracy (`EXACT` or `SUPERSET`);
- a candidate-cardinality estimate;
- estimated source/bucket merge work;
- estimate quality;
- a materialization operation invoked only after selection.

The concrete access-path type remains package-private unless a later phase demonstrates
a third-party SPI requirement. Public custom indexes opt into estimation through a new
capability interface introduced in P1; the existing `IndexSnapshot<T>` descriptor does
not change.

### Legacy index behavior

An existing custom index that implements only `IndexSnapshot<T>` remains valid:

- current `IndexRegistry.candidates(Query<T>)` behavior remains available for
  compatibility;
- built-in v2 indexes use the estimation capability;
- when no estimating path claims a query, the planner may use the legacy registry path
  or scan, subject to the phase's compatibility policy;
- a legacy path must never be treated as EXACT unless its returned `CandidateResult`
  says so;
- ignoring an unknown legacy optimization is allowed only when scan/final verification
  preserves the result set.

The cost-aware P3 planner must not call `candidates()` merely to learn whether an
estimating path is cheap. Instrumented tests will verify rejected estimating paths are
not materialized.

## Contract B — Statistics and estimates

Statistics visible to readers are immutable members of the same published snapshot as
the index data they describe. They are updated through the normal index builder and are
published atomically after startup build, mutation batches, and dynamic build/replay.

### Snapshot facts

The initial index statistics model may expose applicable exact facts such as:

- indexed-document count;
- distinct-value or distinct-term count;
- source bucket/posting count;
- algorithm-specific immutable metadata.

Active-document count belongs to the search snapshot and must not be duplicated in
each index unless a measured implementation requires a validated cached value.

### Query estimate

The initial estimate contract contains enough information to compare work without
building the bitmap:

- estimated candidate cardinality;
- estimated number of source buckets/postings to visit or merge;
- estimate quality, initially `EXACT` or `APPROXIMATE`;
- candidate accuracy, which is independent of estimate quality.

Selectivity is derived as candidate cardinality divided by active-document count. It is
not stored as separately mutable state. Unsupported queries return no estimate rather
than a fabricated high-cost estimate.

Estimate quality and candidate accuracy must not be conflated:

- an exact estimate can describe the size of a SUPERSET candidate bitmap;
- an approximate estimate can still describe an EXACT candidate source;
- neither allows the planner to omit final verification required by current semantics.

Equality cardinality can be read exactly from one bitmap. Since P3, Range/Prefix AVL
nodes also retain immutable subtree candidate weights and entry counts. Their estimates
use ordered prefix aggregates in O(tree height); candidate materialization still visits
and merges the matching distinct buckets.

### P3 selected planner

The P3 planner implements the delayed access-path contract as follows:

- an internal path pairs one estimating index snapshot, its immutable estimate, the
  query, and a materializer;
- path discovery invokes estimates only, then invokes `candidates()` on the selected
  estimating path;
- direct Range planning supports cost-aware, forced-index, and forced-scan modes through
  the additive `PlannerConfig` builder option;
- the internal relative-work model includes active documents, estimated candidate
  documents, source buckets, and an approximate-estimate penalty. Its weights remain
  internal and subject to the recorded P3 JMH evidence;
- conservative AND selects one useful path first and only constructs another exact path
  when its cardinality guarantees enough reduced final verification to pay for it;
- skipped AND children retain `SUPERSET`; final `Query.matches(...)` remains truth;
- OR and NOT use compatibility planning and are not cost-planned in P3.

Legacy indexes without estimates remain on the eager registry compatibility fallback
only when no estimating path claims that query. `SnapshotEngineConfig` and
`SearchEngineMetrics` descriptors remain unchanged.

## Contract C — Immutable dictionary ownership

The v2 text vocabulary can be much larger than the v1 structured-value maps. The
selected representation must satisfy all of these properties:

- immutable snapshots and lock-free lookup;
- query results cannot observe builder mutations;
- an unchanged builder may reuse the base snapshot;
- a small dirty set should not require copying the full dictionary on every publication;
- lookup and publication cost remain bounded over long mutation histories;
- removals/tombstones cannot retain unreachable postings indefinitely;
- dynamic build/replay produces the same representation and truth as startup build;
- deterministic iteration is used anywhere it affects artifacts, tests, or tie behavior.

### P2 evidence-gated selection

P2 will compare at least:

1. **Bounded dirty overlay/copy-on-write**
   - tracks changed keys over an immutable base;
   - returns the base when unchanged;
   - compacts when depth, dirty ratio, or tombstones cross a documented bound.
2. **Persistent structurally shared dictionary**
   - path-copies only affected nodes;
   - keeps lookup depth predictably bounded;
   - introduces a larger custom data-structure correctness surface.

The current full-copy map remains a benchmark control, not an acceptable default for
the final large-vocabulary path. Selection considers query latency, publication
latency, allocation, retained memory, implementation complexity, snapshot isolation,
and pathological long-running update behavior. If both alternatives miss the phase
gates, P2 becomes technically blocked rather than silently accepting full copying.

### P2 selected representation

P2 implements the accepted D3 recommendation as a workload-shaped hybrid:

- Equality uses a dirty overlay because equality keys need not be naturally ordered.
  The chain is capped at 12 layers and compacts earlier when one publication changes at
  least 64 entries and at least one quarter of the prior dictionary.
- Range and Prefix use a persistent AVL dictionary because they already require natural
  ordering. Publication path-copies affected nodes and range/prefix traversal remains
  deterministic.
- No-op builders return the base bitmap/index/registry snapshot by identity.

The identical-workload JMH controls, removal histories, lookup-depth measurements, and
post-P2 Range baselines are accepted in [`../p2/PERFORMANCE_BASELINE.md`](../p2/PERFORMANCE_BASELINE.md). Periodic
Equality overlay compaction is an explicit bounded trade-off; naturally ordered
dictionaries use persistent structural sharing.

## Contract D — Bitmap accumulation

The existing `ImmutableBitmapBuilder` is the canonical query-local mutable accumulator.
P2 extends it rather than creating a parallel bitmap builder hierarchy.

Multi-source candidate construction follows this lifecycle:

1. create one query-local builder;
2. bulk-OR or bulk-intersect applicable immutable source bitmaps;
3. update cardinality consistently;
4. freeze once;
5. never retain the mutable builder in a snapshot or cache.

Range, Prefix, OR, and future multi-term queries share this primitive. A direct
single-source result may reuse its immutable bitmap where safe. Bitmap optimizations
must preserve empty, sparse, dense, overlapping, document-ID-hole, and high-ID behavior.

## Contract E — Text analysis and query truth

Analyzer semantics belong to a canonical text-field/schema definition. A query refers
to that canonical field; it cannot supply an unrelated Analyzer that changes truth for
an already-built index.

Every Analyzer accepted by the engine must be:

- immutable or safely stateless;
- deterministic for the same input/configuration;
- thread-safe;
- independent of mutable default locale and time-zone state;
- explicit about case conversion, Unicode normalization, punctuation/token boundaries,
  null input, empty input, and zero-token results.

The first implementation is intentionally simple. Stemming, fuzzy expansion, spelling
correction, phrase positions, and locale-sensitive linguistic analysis are not implied
by the Analyzer abstraction.

The scan oracle and inverted index must invoke the same canonical Analyzer. If a text
field's Analyzer identity cannot be proven compatible with an index, that index is not
a valid access path.

Initial unranked query semantics will use explicit operations rather than an ambiguous
generic match:

- one analyzed term;
- any analyzed query term;
- all analyzed query terms.

Exact naming is frozen in P4 after its API review. Their `Query.matches(T)` behavior is
the truth oracle, including in structured AND/OR/NOT composition.

### P4 selected analysis contract

P4 freezes the public names `TextField<T>`, `Analyzer`, `Token`, `TermQuery`,
`AnyTermsQuery`, and `AllTermsQuery`, with matching `Query` factories. One logical
schema field name accepts one canonical `TextField` instance. Startup and dynamic text
index definitions must reference that instance by identity; different analysis of one
source property requires different logical field names.

The built-in simple Analyzer applies NFKC, `Locale.ROOT` lowercase, and Unicode
letter/digit runs separated by all other code points. Null/empty fields produce zero
tokens. Query terms are deduplicated in encounter order; zero-token any/all queries
match nothing, and a term query requires exactly one distinct analyzed token. Indexed
and scan execution invoke the same Analyzer. Text candidates are always exact, while
multi-term cardinality estimates may be approximate without affecting correctness.

## Contract F — Posting-list readiness

P4 introduces a `PostingList` abstraction instead of committing the permanent design to
`Map<String, ImmutableBitmap>`. The representation must support:

- candidate document membership;
- per-document term frequency required by P5;
- immutable mutation updates and structural sharing;
- document frequency without scanning all documents;
- deterministic iteration where scoring requires it.

Positions and offsets are excluded unless separately approved. P4 may initially use
membership-only execution, but its stored representation must not require a complete
rewrite to add term frequency in P5.

### P4 selected posting representation

P4 uses the P2 persistent AVL map from normalized term String to immutable
`PostingList`. A posting stores a persistent document-membership bitmap plus a
path-copied document-to-term-frequency map. Document frequency is the bitmap
cardinality. Updates analyze old and new documents, modify only changed term paths,
remove empty postings, and reuse the base index when nothing changes.

Any-terms candidates accumulate posting unions through one bitmap builder and freeze
once. All-terms candidates visit the smallest posting first and intersect remaining
immutable bitmaps. Positions, offsets, scoring, and document-length statistics remain
outside P4. The representation carries P5 term frequency without exposing BM25 or
changing the v1 index SPI.

## Contract G — Ranked retrieval

Boolean eligibility and relevance scoring are separate concepts:

- a scoring text query defines which analyzed terms contribute a score;
- an optional existing `Query<T>` filter defines additional eligibility;
- top-K bounds the requested result count;
- immutable scoring configuration defines BM25 parameters;
- each result is represented as a `SearchHit<T>`-style value containing the document
  and score, with any additional fields justified during P5.

The conceptual execution flow is:

1. obtain text candidates from postings;
2. intersect or verify the optional boolean filter;
3. calculate BM25 for eligible documents;
4. retain only K best hits in a bounded min-heap;
5. return descending score order with a stable documented tie-break.

The default tie-break is ascending internal document ID. BM25 formula, IDF variant,
`k1`, `b`, repeated query terms, zero-length fields, and multi-field behavior are frozen
and tested in P5.

Existing `search(Query<T>)` keeps v1 matching and insertion-order semantics. P5 must not
add a new abstract method to `SearchEngine<K,T>` without a compatibility-safe default
or separate capability boundary. The final method placement is selected during P5 API
review while preserving D1 and the accepted ranked request shape.

### P5 selected ranked implementation

P5 adds `searchTopK(RankedSearchRequest<T>)` as a default `SearchEngine` method; the
built-in snapshot engine overrides it, while existing third-party implementations keep
binary compatibility and reject the unsupported capability. `TextScoringQuery<T>` is
separate from boolean `Query<T>`, and the optional request filter remains final
eligibility truth.

BM25 uses `ln(1 + (N-df+0.5)/(df+0.5))`, default `k1=1.2` and `b=0.75`, exact P4 TF/DF,
and immutable P5 document length/average length. Repeated query terms are deduplicated;
one request scores one canonical text field. Zero-token queries return empty, a positive
K is required, and non-empty scoring without the canonical text index fails explicitly.

Scoring candidates are the union of scoring-term postings. An optional planner result
may reduce them, but the filter predicate is still evaluated before scoring. A bounded
min-heap retains at most K candidates. Final ordering is descending score then ascending
internal document ID. `SearchHit<T>` deliberately exposes document and score but not
the internal tie-break key.

Document length, total length, indexed-document count, postings, TF, and DF publish in
the same immutable text snapshot across mutation and dynamic-build replay. Cross-field
score combination, boosts, explanations, positions, fuzzy expansion, and distributed
score merging remain outside P5.

## Contract H — Bulk mutations and generated fields

P6 follows these already accepted boundaries:

- explicit `addAll`, `updateAll`, or `removeAll` operations are atomic: validation or
  application failure publishes none of that explicit bulk operation;
- the operation occupies one position in writer ordering and publishes at most once;
- partial-success behavior, if later needed, is a distinct API with a structured result;
- compile-time generated fields live in a separate processor artifact/module;
- the runtime reflection path remains supported;
- string fluent query and SearchSession convenience APIs are deferred to v2.1 unless
  the owner explicitly supersedes D8 using concrete evidence.

### P6 selected implementation

The built-in engine implements additive default `addAll`, `updateAll`, and `removeAll`
methods as distinct writer tasks. One non-empty collection occupies one queue slot,
may contain at most `SnapshotEngineConfig.maxBatchSize()` operations, rejects duplicate
IDs, and publishes exactly once or not at all. Successful/failed mutation metrics count
document operations. Empty collections are immediate no-ops. Existing opportunistic
single-task batching retains its established per-future behavior.

Compile-time field generation is isolated in
`io.github.patricklfdm:general-search-engine-processor`. A separate reactor POM builds
core and processor without changing the root runtime artifact coordinates or source
layout. Generated `*SearchFields` companions own canonical typed constants, schema,
and index definitions; runtime reflection remains the fallback for unsupported source
models. Exact bulk and source-model semantics are frozen in
[`../p6/DEVELOPER_EXPERIENCE.md`](../p6/DEVELOPER_EXPERIENCE.md).

## Lifecycle mapping

| v2 concern | Empty/startup state | Mutation batch | Dynamic build/replay | Published reader state | Drop/close |
|---|---|---|---|---|---|
| Statistics | Created with index snapshot | Updated by index builder | Built from captured snapshot, then replayed | Immutable and version-consistent | Removed with index |
| Access paths | Derived from registered snapshots | No independent mutable state | Unavailable until index publication | Discovered from one published registry | Disappear atomically |
| Dictionary/postings | Empty immutable dictionary | Dirty keys structurally updated | Same builder rules as startup plus replay | Immutable, lock-free | Released with unreachable snapshots |
| Analyzer | Canonical schema/text-field configuration | Never mutated by document writes | Captured canonical configuration | Same identity for index and scan | Released with engine/schema reachability |
| Document length/TF/DF | Empty scoring metadata | Updated in same index builder | Built and replayed with postings | Immutable and mutually consistent | Removed with ranked index |
| Ranked request | Not stored | Not applicable | Not applicable | Reads exactly one published snapshot | Rejected after close under normal read contract |
| Bulk operation | Not applicable | One ordered task, all-or-nothing, at most one publication | Journal records successful document effects | Entire bulk visible or absent | Accepted tasks drain under existing close semantics |

No row introduces an independently published statistics, text, or scoring state.

## Public API compatibility impact

| Existing v1 surface | P0 rule for v2 | Compatibility effect |
|---|---|---|
| `IndexSnapshot<T>` | Do not add abstract estimation/scoring methods | Existing custom implementations continue to link |
| `IndexBuilder<T>` / `IndexDefinition<T>` | Add new capability/types rather than narrow existing methods | Existing algorithms remain valid |
| `IndexRegistry<T>` | Preserve existing candidate method; add internal delayed path flow | Existing callers retain behavior |
| `CandidateResult` / `CandidateAccuracy` | Preserve truth meanings | v1 candidate safety remains unchanged |
| `Query<T>` and built-in queries | Preserve existing factories and matching semantics; add separate text query types | Structured consumer source remains valid |
| `SearchEngine<K,T>` | No new abstract methods; ranked/bulk APIs need defaults or capability boundaries | Third-party implementations are not forced to recompile |
| `SnapshotEngineConfig` | Do not append record components; use additive planner/scoring config types and builder methods | Canonical descriptor remains intact |
| `SearchEngineMetrics` | Do not append record components; use separate planner/ranking metric snapshots if approved | Canonical descriptor remains intact |
| `Field` / `SearchSchema` | Add explicit text-field configuration without changing raw-string v1 field semantics | v1 equality/prefix strings stay case-sensitive/raw |
| `IndexType` annotation enum | Do not assume a `TEXT` constant is sufficient for Analyzer configuration | Avoid premature annotation/API lock-in |
| Product/filter compatibility layer | No v2 core dependency on deprecated Product filters | Existing v1 adapter remains isolated |
| Maven coordinates/package root | Keep artifact/package identity unless separately approved for processor module | Consumers retain namespace continuity |

Any later phase that cannot follow this table must stop at an owner decision gate and
document the exact source, binary, semantic, and migration impact.

## Benchmark matrix

All accepted measurements use JMH 1.37 and record JDK, hardware, heap, GC, forks,
warmup, measurement, seed, and dataset distribution. Results are regression baselines,
not universal guarantees.

| Phase | Subject | Required dimensions | Primary evidence |
|---|---|---|---|
| P1 | Estimate cost | 0.01%, 0.1%, 1%, 10%, 25%, 50%, 100%; low/high distinct values | estimate latency, allocation, buckets visited, estimate error |
| P1 | Statistics publication | document count and distinct-value count | batch latency, allocation, retained state |
| P2 | Bitmap accumulation | selectivity, bucket count, overlap, sparse/dense | candidate latency, bytes/op, frozen bitmap count |
| P2 | Dictionary strategy | total entries, dirty entries, tombstones, history depth | publication latency, lookup latency, allocation, retained memory |
| P2 | Mutation batching | batch sizes 1, 10, 100, 1000 | total publication latency and allocation |
| P3 | Range planning | same selectivity matrix, equal selectivity/different bucket spread | total/index/scan latency, chosen path, bytes/op |
| P3 | AND planning | correlated, independent-like, and anti-correlated children | result parity, path cost, candidate reduction |
| P4 | Text lookup | low/medium/high DF, query token counts, vocabulary sizes | index/scan latency, analysis/candidate allocation |
| P4 | Text lifecycle | documents, tokens/document, vocabulary, dirty terms | startup/dynamic build, replay, publication, retained memory |
| P5 | BM25 top-K | DF bands, 1/many terms, K=1/10/100/all | score latency, heap cost, allocation, exhaustive parity |
| P5 | Scoring mutation | TF/DF/length changes and batch sizes | publication latency, allocation, metadata consistency |
| P6A | Explicit bulk mutation | batch sizes 1, 10, 100, 1000; valid/invalid batches | total latency, publications, atomicity |
| P7 | End-to-end regression | representative v1 and v2 workloads | correctness, throughput/latency, allocation, build/replay cost |

P2 selects the dictionary representation only after comparing identical workloads and
correctness gates. P3 calibrates only against post-P2 bitmap behavior. No phase may turn
the v1 approximately 10% observed crossover into a hard-coded universal threshold.

## Phase handoff boundaries

### P1 may

- introduce immutable statistics, estimate values, and the optional estimation
  capability;
- refactor discovery enough to collect estimates without bitmap allocation;
- add tests and benchmarks.

P1 must not change user-visible planning choices or add text queries.

### P2 may

- optimize bitmap accumulation and immutable dictionary/index publication;
- select and implement D3 using recorded evidence.

P2 must not add cost-based path choices or text search behavior.

### P3 may

- choose Range index versus scan and conservatively plan AND;
- add bounded planner configuration/observability without changing frozen records.

P3 must not hard-code a selectivity crossover or cost-plan OR/NOT without a separately
reviewed correctness and benchmark case.

### P4 may

- add the canonical Analyzer, text-field configuration, posting lists, inverted index,
  and unranked term/any/all queries.

P4 must not expose BM25 ranking, fuzzy matching, or phrase/position behavior.

### P5 may

- add the accepted ranked request model, BM25, deterministic top-K, and scoring metadata.

P5 must not change the result order or truth semantics of existing unranked searches.

### P6 may

- add atomic bulk mutation and separately packaged generated fields.

P6 must not implement D8-deferred convenience APIs without a superseding owner decision.

### P7 may

- stabilize, document, audit compatibility, benchmark, and prepare release artifacts.

P7 must not add features or publish/tag without separate authorization.

## P0 validation record

- Architecture scope review: PASS
- D1–D8 owner decisions: ACCEPTED 2026-08-23
- `mvn clean test`: PASS — 60 tests, 0 failures, 0 errors, 0 skipped
- `mvn clean -Papi-compat test`: PASS — 3 tests, 0 failures, 0 errors, 0 skipped
- Production behavior/code changes: none

P0 completed on 2026-08-23. P1 may begin only as tracked by the roadmap and must retain
the contracts in this document.
