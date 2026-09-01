# GeneralSearchEngine V3.x roadmap

## Status

Current stable release: `3.3.0`

V3.1 Phases 0–8 are complete. The signed `v3.1.0` tag points to protected master,
core and processor artifacts are published to Maven Central, clean remote verification
passes, and the GitHub Release is available. The ranked feature family remains
registered as `v3.1.0-ranked-cloud`; the unchanged regression lane remains anchored to
`v3.0.0-cloud`.

V3.2 Phases 0–5 are accepted on protected `master`. Phase 5 completed mutation and
dynamic-index publication, close admission, mixed highlighted/ordinary/Explain reader
concurrency, retained storage boundaries, and top-K/field/source/corpus scale evidence.
Profiling justified no production optimization: ordinary search and canonical hits
remain unchanged, and no stored offset payload or cloud-family change was introduced.
Phase 6 is complete. Snapshot and final release validation passed; signed tag
`v3.2.0`, Maven Central publication, clean remote verification, the protected
production deployment, and the GitHub Release all resolve to protected-master commit
`c96a15e41719cac8d7c1ee8f3c064338ef20ac61`. Published `3.2.0` is now an immutable
compatibility baseline for later candidates.

V3.3 Phases 0–5 are complete on protected `master`. Phase 1 established the
`3.3.0-SNAPSHOT` six-baseline and pre-change foundation; Phase 2 added the frozen page
API and disabled/exact first-page execution; Phase 3 added the private constant-sized
cursor and deterministic strict current-snapshot continuation. Phase 4 completed
publication, concurrency, retention, scale, and decision hardening without a
production-source change and was accepted as merge commit
`9b1b880ddc947b5b4747e0251d0bd42708f94bfc`. Phase 5 final `3.3.0` conversion and
release gates completed through PR #64 and the calendar-correction PR #65. Signed tag
`v3.3.0`, Maven Central publication, clean remote verification, the protected
production deployment, and the GitHub Release all resolve to protected-master commit
`b399ee999e65ca363e68503720dedd4ddd2b3c2e`. Published `3.3.0` is now an immutable
compatibility baseline for later candidates.

V3.4 Phase 0 is accepted through PR #67 at `5d1d108` and freezes the Final In-Memory
Hardening line before V4 durability. Phase 1 is accepted through PR #68 at
`331284bd70b0234b97bb43cf693dd10af8e9b7e1`; it establishes `3.4.0-SNAPSHOT`, the
pinned published-3.3 seventh baseline,
zero-addition fixtures, exact-V3.3 references, and pre-change evidence without a
production or cloud change. Phase 2 is accepted through PR #69 at
`07b885790acbc8455db7bbc9a284173a05a19f56`: its cold 100k/1M and nine-axis
extreme-corpus evidence passes, while the required heap matrix is correctly rejected
as ineligible on the current swap-active 15.53 GiB host and remains an open final gate.
Phase 3 is accepted through PR #70 at
`34760b326fda6da31a0463d7b4765d6c6da5921c`. Its full producer/batch burst
matrix and 30-minute calibration pass writer-progress, completion, queue-drainage,
mixed-reader, lifecycle, final-oracle, and artifact-integrity gates. Phase 4 is accepted
through PR #71 at `0433de39a318a1885322ee22377e3b8a76738c62`: the isolated final
cloud family, exact workload, bounded plan, evidence analysis, and fake/synthetic
lifecycle gates pass without paid execution. Final coordinates are accepted through
PR #72 at `52be441f70e7f23195b8b4a0024444d315ee8eaa`. Phase 5 final-source evidence is
accepted through PR #73 at `fea1547accf896c3a8111ac9cfbb4080a25c5ed5`: the
eligible heap matrix, controlled two-hour experiment, and three-member canonical set
all pass. The reviewed set is registered on the current branch as
`v3.4.0-in-memory-cloud`; protected registry review and exact-merge CI remain required
before Phase 6.
Production source remains unchanged by default; a reproducible release blocker needs
an accepted amendment.

V3.x completes the in-memory search-engine shape before V4 introduces durability.
The authoritative architecture remains immutable snapshots with structural sharing,
lock-free reads, one asynchronous writer, background dynamic-index construction, and
atomic publication.

## Global rules

- `Query<T>` remains deterministic eligibility; `SearchQuery<T>` remains ranked
  relevance. Neither becomes a subtype of the other.
- The supported ranked-query model remains a final façade built through
  `SearchQueries`; planner, plan, posting, position, dictionary, candidate bitmap,
  snapshot, and internal document-ID types remain unsupported internals.
- Existing V1, V2, V3.0, V3.1, V3.2, and V3.3 behavior changes only for a documented
  correctness fix.
  New functionality is opt-in and existing factory defaults remain unchanged.
- Physical optimization must preserve match truth, score arithmetic, ordering,
  failure precedence, Explain equivalence, snapshot isolation, and lifecycle behavior.
- Every performance claim identifies its workload, evidence profile, configuration
  fingerprint, environment fingerprint, and comparison eligibility.

## Version map

| Version | Required scope | Explicitly optional or deferred |
|---|---|---|
| 3.1 | phrase slop, `minimumShouldMatch`, phrase hardening, semantics-preserving fuzzy dictionary optimization, 1M concurrency evidence | ranked `mustNot`, public fuzzy caps/tuning |
| 3.2 | offset-capable analysis foundation and structured highlighting; bounded analyzer composition after its own contract | multi-token synonym graphs, broad language stemming, completion engine |
| 3.3 | snapshot-safe search-after decision, total-hits contract, cooperative timeout/cancellation decision | prepared queries unless measured, facets/aggregations unless consumer-driven |
| 3.4 | final in-memory soak, burst-writer, heap, cold-build, extreme-corpus, independent canonical evidence, and V4 handoff | new search features and durability implementation |
| 4.0 | WAL, checkpoint, recovery, crash consistency, persisted reopen | distributed or vector search unless separately contracted |

No optional item is a release blocker merely because it appears in this roadmap.
Each later minor version starts with its own contract freeze.

## V3.1 phase order

| Phase | Scope | Entry/exit rule |
|---|---|---|
| 0 | freeze architecture, semantics, compatibility, and evidence contracts | no production implementation |
| 1 | add the published-3.0.0 compatibility gate and focused fixtures; capture pre-change profiles | no ranked behavior change |
| 2 | add phrase-slop public model, normalization, planning, verification, scoring, and Explain | exact phrase remains equivalent at slop zero |
| 3 | add `minimumShouldMatch` model, candidate planning, scoring, and Explain | unspecified BOOL remains V3.0-equivalent |
| 4 | focused, randomized, differential, lifecycle, mutation, and concurrency hardening | all semantic oracles pass |
| 5 | profile-guided phrase allocation and execution optimization | no semantic or evidence-identity drift |
| 6 | add the persistent code-point fuzzy dictionary and exact bounded OSA traversal | full-scan differential oracle remains equivalent |
| 7 | 1M mixed concurrency and two-lane benchmark evidence | regression and feature evidence remain separate |
| 8 | consumers, Japicmp, Javadocs, artifacts, reproducibility, documentation, and release | all release gates pass |

Ranked `mustNot` and public advanced fuzzy controls are not part of V3.1. They require
later independent contracts rather than opportunistic inclusion.

The feature lane uses the separately frozen `ranked-v31` mode and
`v3.1-ranked-v1` preset. Existing `v3-production-<mode>-v1` identities remain the
directly comparable regression lane.

## V3.2 phase order

| Phase | Scope | Entry/exit rule |
|---|---|---|
| 0 | freeze offset metadata, snapshot-bound highlighting, compatibility, validation, and evidence contracts | documentation only; no version or production change |
| 1 | switch atomically to `3.2.0-SNAPSHOT`; add five-baseline compatibility fixtures and independent oracles; capture pre-change profiles | no offset or highlighting implementation |
| 2 | add `OffsetAnalyzer`, `OffsetAnalyzedToken`, sequence validation, and built-in `SimpleAnalyzer` offset equivalence | ordinary analysis/index/search remains allocation- and behavior-equivalent |
| 3 | add the immutable highlighted request/result family, integrated one-snapshot execution, and TEXT highlighting | highlighted hits equal canonical hits bit-for-bit |
| 4 | add deterministic PHRASE and FUZZY evidence plus recursive BOOL/BOOST composition | independent semantic and differential oracles pass |
| 5 | lifecycle, mutation, dynamic-index, concurrency, allocation, latency, and retained-memory hardening | no snapshot mixing or ordinary-path regression |
| 6 | consumers, Japicmp, Javadocs, artifacts, reproducibility, documentation, and release | all release gates pass |

Analyzer composition, single-token synonyms, stemming, and ranked prefix are not
silently included in these phases. Each requires a separate accepted semantic and API
contract; none is required for V3.2 release completion.

## V3.2 boundary

V3.2 first defines an additive token-metadata capability while preserving
`Analyzer` as a SAM and leaving the published `AnalyzedToken` record unchanged. The
frozen coordinate system is zero-based half-open UTF-16 ranges into the exact original
Java string. The built-in engine re-analyzes only explicitly requested fields of the
final top-K hits inside one snapshot-bound highlighted-search invocation; it does not
store offsets in postings or a per-document sidecar. A requested field backed by a
legacy analyzer fails deterministically rather than receiving approximate offsets.

Structured highlighting returns immutable source ranges and fragments, never HTML.
TEXT, one deterministic PHRASE witness, the scoring-selected FUZZY expansion, and all
matching BOOL/BOOST evidence have explicit composition rules. Highlighting cannot
change match truth, scores, order, top-K membership, failure precedence, or Explain.

The initial synonym scope, if separately accepted, is single-token same-position
alternatives. Multi-token synonyms require position length or a token graph and are
outside V3.2. Ranked prefix remains optional and must not become a completion,
popularity, or personalization subsystem. The complete frozen contract map is under
[`v3.2/`](v3.2/ARCHITECTURE.md).

## V3.3 phase order

| Phase | Scope | Entry/exit rule |
|---|---|---|
| 0 | freeze strict cursor, exact-total, API, compatibility, validation, evidence, and decision contracts | documentation only; no version or production change |
| 1 | switch atomically to `3.3.0-SNAPSHOT`; add six-baseline fixtures, independent oracles, and exact-V3.2 baselines | no page/cursor production implementation |
| 2 | add frozen page API values/default engine capability, first-page parity, and disabled/exact total execution | accepted on protected `master`; ordinary ranked and highlighted behavior remains unchanged |
| 3 | add opaque built-in cursor ownership, request/snapshot validation, and deterministic continuation | accepted on protected `master`; exhaustive page walks equal canonical full order |
| 4 | mutation, dynamic-index, lifecycle, concurrency, retention, scale, and timeout/cancellation decision closure | accepted on protected `master`; no production change, snapshot pinning, or speculative cancellation API |
| 5 | consumers, Japicmp, Javadocs, artifacts, reproducibility, documentation, and release | all release and post-publication verification gates pass |

Prepared queries are implemented only after measured logical-normalization evidence
and an accepted amendment. Highlighted pagination, lower-bound totals, snapshot
pin/release, offsets, facets, aggregations, and grouping are not silent additions.

## V3.3 boundary

Search-after uses a separate page façade around one exact immutable `SearchRequest`.
The opaque cursor binds its built-in engine, exact request object, captured snapshot
version, raw score anchor, and hidden internal document ID. A successful publication
before the next page captures its snapshot fails as stale; V3.3 introduces no snapshot
pinning, registry, serialization, or cross-engine/process cursor.

Canonical order remains score descending then internal document ID ascending. First
page hits remain bit-for-bit ordinary-search equivalent. `DISABLED` is the default
total mode; `EXACT` counts the complete full-query/filter match set before cursor and
limit during the existing evaluation. No lower-bound relation exists without a future
accepted early-termination strategy.

Phase 4 profiling explicitly defers timeout/cancellation: no complete safe control
surface or consumer latency budget justifies implementation, and arbitrary user
`Analyzer`, extractor, or `Query.matches` code cannot be preempted. Prepared queries
also remain deferred because logical normalization is not a demonstrated hotspot and a
future prepared object may never cache a physical snapshot-bound plan. The complete
contract and evidence map is under [`v3.3/`](v3.3/ARCHITECTURE.md).

## V3.4 phase order

| Phase | Scope | Entry/exit rule |
|---|---|---|
| 0 | freeze no-feature architecture, seven-baseline compatibility, validation, performance, cloud, and V4 handoff contracts | documentation only; no version, code, workflow, preset, paid-run, or baseline change |
| 1 | switch atomically to `3.4.0-SNAPSHOT`; add published-3.3 compatibility, zero-addition fixtures, exact-V3.3 references, and pre-change evidence | no production or cloud-family implementation |
| 2 | cold-process/index-build, extreme-corpus, and bounded heap diagnostic surfaces | deterministic reduced fixtures, resource caps, and local evidence pass |
| 3 | multi-producer burst/recovery and long-run calibration | single-writer semantics, writer progress, future completion, queue drainage, and final oracles pass |
| 4 | implement and calibrate isolated `final-v34` cloud mode/suite/preset | all existing modes/presets remain frozen; fake/synthetic lifecycle gates pass before paid execution |
| 5 | convert to final `3.4.0`; run/review the required two-hour evidence and 3-or-more-member Standard canonical set; close V4 handoff | exact final source/environment identities and durable evidence pass |
| 6 | final consumers, compatibility, Javadocs, artifacts, reproducibility, documentation, signed release, remote verification, and post-publication evidence | `3.4.0` and `v3.4.0-in-memory-cloud` become immutable final V3.x references |

The V3.4 cloud identities are `final-v34`, `v3.4-final-in-memory-suite-v1`,
`v3.4-final-in-memory-v1`, and `v3.4.0-in-memory-cloud`. They do not alter or aggregate
with `v3.0.0-cloud` or `v3.1.0-ranked-cloud`.

One controlled two-hour run is required. Six-, twelve-, and twenty-four-hour evidence
requires a later durable-orchestration contract and is not a V3.4 release blocker.
Cross-hardware results are optional and use separate environment fingerprints and
families. The complete contract map is under [`v3.4/`](v3.4/ARCHITECTURE.md).

## V4 entry gate

V4 begins only after ranked BOOL and phrase semantics are stable, fuzzy execution has
no known architecture-level query hotspot, the analyzer/highlighting scope has been
decided, pagination behavior is explicit, 1M capacity and concurrency have evidence,
V3.4 cold/burst/heap/extreme/two-hour gates pass, signed `3.4.0` is remotely verified,
and `v3.4.0-in-memory-cloud` is registered as the final comparison anchor.
