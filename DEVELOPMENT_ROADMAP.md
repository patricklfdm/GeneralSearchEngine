# GeneralSearchEngine development roadmap

## v4.0 active development contract

V4.0 opens the opt-in durable single-node line from the published `3.4.0` in-memory
reference. It preserves immutable snapshots, lock-free readers, one authoritative
writer, atomic publication, and all frozen retrieval semantics while adding explicit
key/document codecs, local storage ownership, contiguous durable sequences, a framed
checksummed WAL, atomic checkpoints, deterministic recovery, bounded retention, and
real crash evidence.

Phase 0 is a documentation-only contract freeze. It resolves the successful-Future
order, group commit, incomplete-Future semantics, canonical slot/`nextDocId` recovery,
built-in durable index classification, storage/schema/codec identity, exact tail versus
corruption behavior, authoritative-checkpoint policy, terminal runtime I/O behavior,
platform assumptions, disk bounds, additive API shape, and the independent
`v4.0-durable-single-node-v1` evidence family. Phase 0 also freezes the local
parent/child crash protocol, stable barriers, artifact schema, persistent-disk cloud
failure drill, budget, retention, and cleanup rules as first-class architecture. No
`4.0.0-SNAPSHOT`, executable harness, or production persistence implementation belongs
in Phase 0.

After protected acceptance, Phase 1 establishes `4.0.0-SNAPSHOT`, the published-3.4
compatibility baseline, independent history/recovery oracles, crash/corruption harness
scaffolding, executable artifact validation, a fake cloud lane, and pre-change evidence.
Production WAL begins only in Phase 2 and must add named crash barriers alongside each
storage transition. Recovery, checkpoints, lifecycle/crash hardening,
performance/cloud evidence, release candidate, and publication then proceed in ordered
phases 3–8. The authoritative map is under
[`docs/v4/`](docs/v4/README.md).

Phase 0 merged through protected PR #77 as `d5a3253`. Phase 1 is accepted at
protected-master commit `8758106d30223cc1ad6c2faf66a2f0d1131d507c`; exact-master
CI run `33578036261` passed. It establishes `4.0.0-SNAPSHOT`, the eighth published
compatibility baseline at exact `3.4.0`, the independent history oracle, separate-JVM
abrupt-crash scaffold, checksummed evidence validator, storage inspector, and fake
persistent-disk cloud lane.

Phase 2 merged through protected PR #79 at
`7056a5ad00d1f38757f984c51ad21d83ee922443`. It added only opt-in production durable
mode: deterministic codecs, exclusive fresh-store ownership, immutable storage
metadata, a forced generation header, bounded CRC32C logical-unit frames, contiguous
sequences, group force-before-publication, terminal ambiguous-I/O handling, and stable
production crash barriers exercised by the local harness. Its exact-master CI run ID
`33583721019` passed on that merge commit.

Phase 3 merged through protected PR #80 at `2664638`; exact-master CI run
`33589193180` passed. It implements authoritative
WAL-only reopen, strict startup validation, permitted incomplete-tail truncation,
two-pass bounded replay, canonical slot and `nextDocId` restoration, derived-index
rebuild, stable recovery crash barriers, recovered-versus-uninterrupted differential
tests, and the Phase 3 local/fake-cloud failure-drill lane.

Phase 4 is active from that merged recovery boundary. It implements the versioned
checkpoint and manifest formats, writer-coordinated WAL generation cuts, asynchronous
explicit and automatic checkpoints, single-authority recovery, conservative cleanup,
checkpoint-plus-WAL replay, independent byte inspection, eleven production crash
barriers and the fake-cloud checkpoint failure drill. Lifecycle/concurrency loops,
disk-full and cleanup-failure stress remain ordered Phase 5 scope.

## v3.x completed development line

V3.x is the completed post-3.0 in-memory development line. It matured ranked semantics,
text-search experience, application-facing retrieval APIs, and final in-memory
engineering without changing the immutable-snapshot or single-writer publication
boundary. Its version scope and versioned contract maps are maintained under
[`docs/v3x/`](docs/v3x/README.md).

V3.1 Phases 0–8 are complete. Ordered phrase slop, `minimumShouldMatch`, profile-guided
phrase hardening, the semantics-preserving persistent fuzzy dictionary, and 1M
concurrency evidence passed their contracts. The frozen regression comparison and the
distinct ranked feature family are reviewed, and `v3.1.0-ranked-cloud` is registered
immutably. Signed `v3.1.0`, Maven Central publication, clean remote verification, and
the GitHub Release are accepted. Published 1.0.0, 2.0.0, 2.1.0, 3.0.0, 3.1.0,
3.2.0, 3.3.0, and 3.4.0 APIs are mandatory compatibility baselines for later
development.

## v3.2 development contract

V3.2 Phases 0–5 are accepted on protected `master`. Phase 5 completed add/update/remove
and bulk publication, dynamic text-index replay/drop/create, close admission, mixed
highlighted/ordinary/Explain reader concurrency, storage boundaries, and local scale
evidence. Profiling justified no production optimization: canonical hits and ordinary
paths remain unchanged, offset cost stays bounded to explicit top-K requested-source
analysis, and no stored payload or cloud-family change was introduced. Phase 6
snapshot hardening and final release validation are accepted. Signed `v3.2.0`, Maven
Central publication, clean remote verification, the production deployment, and the
GitHub Release are complete on protected-master commit
`c96a15e41719cac8d7c1ee8f3c064338ef20ac61`.

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
performance, migration, hardening, and release contracts are mapped in
[`docs/v3x/v3.2/`](docs/v3x/v3.2/ARCHITECTURE.md).

## v3.3 development contract

V3.3 Phases 0–5 are complete on protected `master`. Phase 1 converted atomically to
`3.3.0-SNAPSHOT` and established six-baseline compatibility, public descriptor/source
fixtures, independent semantic oracles, and exact-V3.2 pre-change evidence. Phase 2
added the complete frozen page value family, additive default engine capability,
built-in first-page parity, and default-disabled/explicitly-exact total hits. Phase 3
added the private constant-sized built-in cursor, frozen owner/request/snapshot
validation, first-page cursor emission, and deterministic search-after continuation
without changing the public descriptors. Phase 4 completed publication, concurrency,
retention, and scale hardening without changing production code and was accepted as
merge commit `9b1b880ddc947b5b4747e0251d0bd42708f94bfc`. Phase 5 converted all active
coordinates atomically to final `3.3.0` and closed consumers, migration and release
documentation, Japicmp, strict Javadocs, artifacts, reproducibility, performance
smoke, and cloud local gates. The initial candidate merged through PR #64 as
`fd15a8df9600bd98ec0b1926810637f0ee40ade5`; the calendar-corrected candidate merged
through PR #65 as protected-master commit
`b399ee999e65ca363e68503720dedd4ddd2b3c2e`. Signed `v3.3.0`, Maven Central
publication, clean remote verification, the production deployment, and the GitHub
Release are complete at that exact commit.

The required implementation scope remains strict current-snapshot search-after. The
page façade wraps the existing immutable `SearchRequest`; it cannot change query/filter
truth, BM25, score bits, canonical ordering, failure behavior, Explain, or publication
semantics.

The built-in opaque cursor is bound to one engine, the exact request object, one
snapshot version, and the hidden canonical order anchor. It does not pin a snapshot or
expose the internal document ID. Any successful document or dynamic-index publication
makes an earlier cursor stale. Exact total hits count the complete query/filter match
set before cursor and limit during the existing candidate evaluation.

Phase 4 evidence explicitly defers timeout/cancellation and prepared queries: no
consumer SLA or complete safe cross-operation control contract justifies a public
surface, and arbitrary application callbacks cannot be cooperatively preempted. No
speculative cache or production optimization is added. Highlighted pagination,
lower-bound counts, snapshot pinning, deep offsets, facets, and aggregations remain
deferred unless a separate contract amendment is accepted. The executable map is under
[`docs/v3x/v3.3/`](docs/v3x/v3.3/ARCHITECTURE.md).

## v3.4 development contract

V3.4 is the final in-memory hardening line before V4 durability. It is not a feature
release and authorizes no new public API, query semantics, scoring model, writer model,
snapshot model, or persistence behavior. Phase 0 freezes a measurement-first program
over the published `3.3.0` boundary: cold startup and index construction, extreme
corpora, bounded heap diagnostics, multi-producer mutation bursts, a required two-hour
mixed workload, and one independent final cloud evidence family.

Phase 0 is accepted through PR #67 at protected-master commit `5d1d108`. Phase 1 is
accepted through PR #68 at protected-master commit
`331284bd70b0234b97bb43cf693dd10af8e9b7e1`: all seven active coordinates are
`3.4.0-SNAPSHOT`; published `3.3.0` is a pinned seventh Japicmp baseline; zero-addition
public, exact-V3.3 semantic, and pre-change JMH fixtures are present. Phase 1 changes no
production source, cloud workflow/preset, paid execution, or baseline registry.
Phase 2 is accepted through PR #69 at protected-master commit
`07b885790acbc8455db7bbc9a284173a05a19f56`; its benchmark-only diagnostics accept
five-run 100k/1M cold construction and all nine extreme-corpus axes. The required heap
cells fail closed on this host because 4g/8g observe active swap and 16g exceeds
physical memory, so the eligible heap exit gate remained open at the Phase 2 boundary.
Phase 3 is accepted
through PR #70 at protected-master commit
`34760b326fda6da31a0463d7b4765d6c6da5921c`: the full producer/batch burst matrix and
bounded 30-minute calibration pass completion, queue drainage, window, mixed-reader,
dynamic-index, final-oracle, and artifact-integrity gates without production changes.
Phase 4 is accepted through PR #71 at protected-master commit
`0433de39a318a1885322ee22377e3b8a76738c62`. It implements the isolated `final-v34`
suite/preset, freezes exact workload and resource bounds, and passes local,
fake-gcloud, synthetic aggregation, failure/recovery, and integrity gates without a
paid run or production change. Final coordinates are accepted through PR #72 at
`52be441f70e7f23195b8b4a0024444d315ee8eaa`. Phase 5 evidence is accepted through
PR #73 at protected-master commit
`fea1547accf896c3a8111ac9cfbb4080a25c5ed5`: the eligible heap matrix, required
two-hour experiment, and three-member canonical set all resolve to that exact source.
The reviewed set is registered as `v3.4.0-in-memory-cloud` through PR #74 at
protected-master commit `f5b573e4a9ed389ff3ec7c9e7edc783a638d82cd`; exact-master
CI run `33532660854` passed. Phase 6 merged through protected PR #75 as
`7077446a3be3ac5eefff78366aa61d6a48e55ee1`; exact-master CI run `33535775072`
passed. Signed `v3.4.0`, Maven Central publication, clean remote verification,
production deployment `6206483105`, GitHub Release `380695065`, and the final
post-publication record complete the V3.x line at that exact release identity.

The new cloud identities are mode `final-v34`, suite
`v3.4-final-in-memory-suite-v1`, preset `v3.4-final-in-memory-v1`, and registration
`v3.4.0-in-memory-cloud`. Existing `v3.0.0-cloud`,
`v3.1.0-ranked-cloud`, and their presets remain immutable. Canonical V3.4 evidence
requires at least three Standard `c3d-standard-30` members with exact source,
environment, preset, GCS retention, and cleanup evidence.

One controlled two-hour run is a V3.4 release gate. Six-, twelve-, and twenty-four-hour
runs remain non-blocking investigations until a separate durable-orchestration contract
freezes resume, failure, budget, retention, and cleanup semantics. Cross-hardware
evidence is optional and uses a separate environment family.

Production source remains unchanged by default. A reproducible correctness, liveness,
bounded-memory, or architecture-level release blocker requires an accepted contract
amendment before a narrow compatibility-preserving fix. The architecture,
compatibility, validation, performance, cloud, handoff, and Phase 0 contracts are under
[`docs/v3x/v3.4/`](docs/v3x/v3.4/ARCHITECTURE.md).

## v3.4.0 current stable release

Version `3.4.0` was published on September 1, 2026 as the current stable release:

- `io.github.patricklfdm:general-search-engine:3.4.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.4.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.4.0).

V3.4 adds no supported application API. It closes the V3.x in-memory line with
reviewed cold-build, extreme-corpus, bounded-heap, burst/recovery, two-hour, canonical
cloud, compatibility, artifact, and publication evidence.

## v3.3.0 previous stable release

Version `3.3.0` was published on August 31, 2026 and remains the immediate prior
stable release and compatibility baseline:

- `io.github.patricklfdm:general-search-engine:3.3.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.3.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.3.0).

V3.3 adds strict current-snapshot search-after pagination and opt-in exact total hits
without changing ordinary ranked search, highlighting, Explain, or publication
semantics.

## v3.2.0 earlier stable release

Version `3.2.0` was published on August 30, 2026 and remains a frozen compatibility
baseline:

- `io.github.patricklfdm:general-search-engine:3.2.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.2.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.2.0).

V3.2 adds exact source offsets and opt-in snapshot-consistent structured highlighting
without changing ordinary query, ranking, index, mutation, or Explain behavior.

## v3.1.0 earlier stable release

Version `3.1.0` was published on August 30, 2026 and remains a frozen compatibility
baseline:

- `io.github.patricklfdm:general-search-engine:3.1.0`;
- `io.github.patricklfdm:general-search-engine-processor:3.1.0`;
- signed tag and [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v3.1.0).

V3.1 adds ordered phrase slop and explicit ranked BOOL `minimumShouldMatch`, while
preserving V3.0 defaults. It also replaces full-scan fuzzy vocabulary expansion with a
semantics-equivalent persistent code-point trie and completes the separate ranked
feature evidence lane. Ranked `mustNot` and public fuzzy tuning remain outside V3.1.

## v3.0.0 earlier stable release

Version `3.0.0` was published on August 26, 2026 and remains a frozen compatibility
baseline:

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
