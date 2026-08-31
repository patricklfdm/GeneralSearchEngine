# GeneralSearchEngine development roadmap

## v3.x active development line

V3.x is the active post-3.0 development line. It matures ranked semantics, text-search
experience, application-facing retrieval APIs, and final in-memory engineering without
changing the immutable-snapshot or single-writer publication boundary. Its version
scope and versioned contract maps are maintained under
[`docs/v3x/`](docs/v3x/README.md).

V3.1 Phases 0–8 are complete. Ordered phrase slop, `minimumShouldMatch`, profile-guided
phrase hardening, the semantics-preserving persistent fuzzy dictionary, and 1M
concurrency evidence passed their contracts. The frozen regression comparison and the
distinct ranked feature family are reviewed, and `v3.1.0-ranked-cloud` is registered
immutably. Signed `v3.1.0`, Maven Central publication, clean remote verification, and
the GitHub Release are accepted. Published 1.0.0, 2.0.0, 2.1.0, 3.0.0, and 3.1.0 APIs
are mandatory compatibility baselines for subsequent V3.x development.

## v3.2 development contract

V3.2 Phases 0–2 are accepted on protected `master`. Phase 3 implements the frozen
immutable highlighted request/result family, integrated one-snapshot execution, and
TEXT evidence over exact original-source offsets. Canonical hit identity, score bits,
order, filters, and top-K remain unchanged. PHRASE, FUZZY, BOOL, and BOOST evidence are
deferred explicitly to Phase 4; no stored offset payload or cloud-family change is
introduced.

The required V3.2 foundation is an additive `OffsetAnalyzer` capability that preserves
the published `Analyzer` SAM and `AnalyzedToken` shape, followed by opt-in structured
highlighting executed against one captured immutable snapshot. Offsets are half-open
UTF-16 ranges into original field text. The engine re-analyzes only requested fields of
returned top-K hits and stores no offset payload in the 1M-document index shape.
Highlight results expose immutable source fragments and spans rather than HTML, and
cannot change canonical match, score, order, limit, failure, or Explain behavior.

Analyzer composition, single-token synonyms, stemming, and ranked prefix require
separate accepted contracts after the foundation; multi-token token-graph synonyms
remain outside V3.2. The architecture, offset, highlighting, compatibility, validation,
performance, and Phase 0 acceptance contracts are mapped in
[`docs/v3x/v3.2/`](docs/v3x/v3.2/ARCHITECTURE.md).

## v3.1.0 current stable release

Version `3.1.0` was published on August 30, 2026 as the current stable release:

- `io.github.patricklfdm:general-search-engine:3.1.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.1.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.1.0).

V3.1 adds ordered phrase slop and explicit ranked BOOL `minimumShouldMatch`, while
preserving V3.0 defaults. It also replaces full-scan fuzzy vocabulary expansion with a
semantics-equivalent persistent code-point trie and completes the separate ranked
feature evidence lane. Ranked `mustNot` and public fuzzy tuning remain outside V3.1.

## v3.0.0 previous stable release

Version `3.0.0` was published on August 26, 2026 and remains the immediate prior stable
release and compatibility baseline:

- `io.github.patricklfdm:general-search-engine:3.0.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.0.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.0.0).

The V3 theme is high-quality ranked text retrieval. Phase 0 froze the public, semantic,
architecture, and compatibility contracts. Phases 1–7 completed position-aware
analysis, positional postings, the canonical `SearchRequest` pipeline, recursive
BOOL/BOOST and cross-field ranking, exact phrase search, single-term fuzzy search, and
per-document Explain while preserving the published V1/V2 APIs.

Phase 8 is complete. It added no search feature. It performed final
public-API and correctness hardening, compatibility validation, performance and memory
measurement, documentation/example finalization, version conversion, protected
tag-based publication, and post-publication verification. Its normative contract and
checklist are under [`docs/v3/phases/p8/`](docs/v3/phases/p8/); the canonical phase
order remains in [`docs/v3/ROADMAP.md`](docs/v3/ROADMAP.md).

V3.0 deliberately excludes phrase slop, `minimumShouldMatch`, automatic multi-token
fuzzy, fuzzy phrase, spell correction, stemming, synonym dictionaries, highlighting,
offset storage, BM25F, DisMax, custom scoring, WAND, plan caching, prepared queries,
pagination/search-after, aggregations, persistence/WAL, vector search, and distributed
search. The published contract map is in [`docs/v3/README.md`](docs/v3/README.md).

## v1.0.0 freeze

Version 1.0.0 is published and feature-frozen. Its release identity is
`io.github.patricklfdm:general-search-engine:1.0.0`, with public Java packages rooted at
`io.github.patricklfdm.generalsearch`.

The v1.0.0 feature set consists of typed equality, inclusive range, prefix, AND, OR,
NOT, and MatchAll queries; immutable in-memory snapshots; synchronous reads;
asynchronous batched mutations; runtime index lifecycle management; and operational
metrics. The observable contract is frozen in
[`docs/v1/SEMANTICS.md`](docs/v1/SEMANTICS.md), and the supported application API is
recorded in [`docs/v1/API_COMPATIBILITY.md`](docs/v1/API_COMPATIBILITY.md).

The following remain outside the v1.0.0 scope:

- full-text search and BM25 ranking;
- fuzzy search;
- write-ahead logging (WAL) and persistence;
- distributed search and sharding.

## v2.1.0 (previous stable)

Version 2.1.0 is the previous stable release. Its release artifacts are:

- `io.github.patricklfdm:general-search-engine:2.1.0`;
- `io.github.patricklfdm:general-search-engine-processor:2.1.0`.

Version 2.1.0 preserves the v1 and v2 supported application APIs while improving the
newcomer configuration path with runtime `@SearchField` discovery,
`textIndex(fieldName, analyzer)`, direct canonical field accessors, actionable lookup
diagnostics, an optional generated-field path, and a reactor-compiled travel example.
Its compatibility and release gates are recorded in
[`docs/v2/API_COMPATIBILITY.md`](docs/v2/API_COMPATIBILITY.md) and
[`docs/v2.1/RELEASE_CHECKLIST.md`](docs/v2.1/RELEASE_CHECKLIST.md).

## v2.0.0 (earlier stable)

Version 2.0.0 is an earlier stable release and retained compatibility baseline.
Its release artifacts are:

- `io.github.patricklfdm:general-search-engine:2.0.0`;
- `io.github.patricklfdm:general-search-engine-processor:2.0.0`.

The Java package root remains `io.github.patricklfdm.generalsearch`. Version 2.0.0
preserves the supported v1 application API while expanding the engine with:

- immutable index statistics and materialization-free access-path estimates;
- cost-aware Range index-versus-scan planning;
- lower-allocation bitmap construction and structurally shared index publication;
- deterministic analyzed full-text search backed by an immutable inverted index;
- BM25-ranked top-K retrieval with deterministic tie-breaking;
- atomic collection mutations through `addAll`, `updateAll`, and `removeAll`;
- an optional annotation processor for generated typed fields and schemas;
- continued lock-free reads, snapshot isolation, dynamic index lifecycle management,
  and atomic publication across structured and text indexes.

Existing v1 applications can adopt v2 by updating the dependency version. Migration
guidance is available in [`docs/v2/MIGRATION_GUIDE.md`](docs/v2/MIGRATION_GUIDE.md),
and the compatibility boundary is recorded in
[`docs/v2/API_COMPATIBILITY.md`](docs/v2/API_COMPATIBILITY.md).

The v2.0.0 release completed correctness, compatibility, consumer, concurrency,
performance, Javadoc, signing, artifact, and reproducible-build validation before its
August 25, 2026 publication. The frozen release record is maintained in
[`docs/v2/RELEASE_CHECKLIST.md`](docs/v2/RELEASE_CHECKLIST.md), and the public release is
available from the
[`v2.0.0` GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v2.0.0).

## v2.0.0 scope boundaries

Version 2.0.0 deliberately does not include:

- fuzzy, phonetic, spelling-correction, phrase, or positional search;
- disk persistence, WAL, checkpoints, or crash recovery;
- distributed search, sharding, replication, consensus, or cross-node score merging;
- vector search, embeddings, HNSW, or hybrid vector retrieval;
- learning-to-rank, personalization, or neural ranking;
- a string-based fluent query language or `SearchSession` abstraction.

These capabilities are not release blockers. Any future addition requires its own
semantics, compatibility policy, correctness coverage, performance evidence, and
release plan.

## Documentation

The complete documentation map is available in [`docs/README.md`](docs/README.md).
Architecture, semantics, performance baselines, and validation evidence for the v2
release are organized by phase under [`docs/v2/phases/`](docs/v2/phases/).
