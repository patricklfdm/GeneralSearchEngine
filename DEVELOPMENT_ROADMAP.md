# GeneralSearchEngine development roadmap

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

## v2.0.0

Version 2.0.0 is the current published stable release. Its release artifacts are:

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
