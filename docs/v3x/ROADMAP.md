# GeneralSearchEngine V3.x roadmap

## Status

Current stable release: `3.1.0`

V3.1 Phases 0–8 are complete. The signed `v3.1.0` tag points to protected master,
core and processor artifacts are published to Maven Central, clean remote verification
passes, and the GitHub Release is available. The ranked feature family remains
registered as `v3.1.0-ranked-cloud`; the unchanged regression lane remains anchored to
`v3.0.0-cloud`.

V3.2 Phases 0 and 1 are accepted on protected `master`. Phase 2 implements the frozen
`OffsetAnalyzer` and `OffsetAnalyzedToken` family, exact built-in Unicode source
mapping, and package-private sequence validation. Ordinary analysis remains direct and
equivalent; no highlighting API, stored offset payload, or cloud-family change is part
of Phase 2.

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
- Existing V1, V2, V3.0, and V3.1 behavior changes only for a documented correctness fix.
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
| 3.4 or 3.3.x | final in-memory soak, burst-writer, heap, cold-build, extreme-corpus, and canonical evidence | new search features |
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

## V3.3 boundary

Search-after must either reject a cursor when its snapshot version is stale or first
introduce an explicit snapshot-pinning lifecycle. It must not silently promise stable
pagination across mutation. Cursor internals remain opaque and query-bound.

The initial total-hits surface should support disabled and exact modes. The current
executor already evaluates all scoring candidates; lower-bound semantics become useful
only with a future early-termination strategy. Timeout and cancellation are
cooperative and cannot promise preemption inside arbitrary user `Analyzer` or
`Query.matches` code. A prepared object may cache logical normalization, never a
physical plan bound to a stale snapshot.

## Final in-memory hardening

Two-hour investigation is supported by the current protected workflow. Six-, twelve-,
or twenty-four-hour evidence requires a separately frozen Cloud Benchmark extension
with bounded cost, recovery, cleanup, and retention behavior; it is not an automatic
release blocker. Cross-hardware results use separate environment fingerprints and
baseline families.

## V4 entry gate

V4 begins only after ranked BOOL and phrase semantics are stable, fuzzy execution has
no known architecture-level query hotspot, the analyzer/highlighting scope has been
decided, pagination behavior is explicit, 1M capacity and concurrency have evidence,
long-run publication behavior is understood, cold build has a baseline, and a final
V3.x canonical in-memory comparison anchor is registered.
