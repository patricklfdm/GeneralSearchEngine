# V3 Phase 3 implementation checklist

## Preparation and frozen boundary

- [x] Phase 2 is merged to `master` with all Phase 2 gates passing.
- [x] Work starts from `feat/v3-phase3-search-pipeline` at the merged Phase 2 commit.
- [x] Existing V3 façades, query nodes, `RankedSearcher`, `CandidatePlanner`, engine
  integration, snapshots, compatibility fixtures, and phase contracts are audited.
- [x] Query decoding, package visibility, normalized input, validation order, snapshot
  ownership, legacy adaptation, filter semantics, compatibility, and non-goals are
  frozen in [SEARCH_PIPELINE.md](SEARCH_PIPELINE.md).
- [x] The root Phase 3 Codex prompt remains an untracked implementation input.

## Internal architecture and visibility

- [x] Add package-private immutable normalized text-search input.
- [x] Keep the exact frozen `TextField`, term order, optional filter, limit, and BM25
  configuration in that input.
- [x] Add package-private `SearchPlanner`, immutable `SearchPlan`, and `SearchExecutor`
  in the search package.
- [x] Keep every existing `SearchQueryNode` and its accessor package-private.
- [x] Add only the frozen bytecode-public `SearchExecutionAccess` sibling-package
  bridge.
- [x] Mark the bridge `@hidden`, document it unsupported, and prevent construction.
- [x] Expose no node, plan, posting, bitmap, position, or internal document ID through
  the bridge or supported public API.
- [x] Use no reflection or method-handle access to decode `SearchQuery`.
- [x] Confirm no other Phase 3 implementation type becomes public.

## V3 query decoding and analysis

- [x] Accept only a direct `SearchQueries.text(...)` leaf in Phase 3.
- [x] Reject bool, boost, phrase, and fuzzy shapes with clear
  `UnsupportedOperationException`.
- [x] Reject unsupported shapes before Analyzer and text-index work.
- [x] Analyze V3 raw query text exactly once per request through positioned analysis.
- [x] Apply the complete Phase 2 null/increment/overflow validation contract.
- [x] Propagate Analyzer-thrown exceptions unchanged.
- [x] Deduplicate V3 terms in first-encounter order.
- [x] Keep valid position increments semantically irrelevant to term-only scoring.
- [x] Prove default-adapted and native positioned Analyzers use the expected query
  terms.

## Validation and planning order

- [x] Null-check public request and snapshot arguments according to existing contracts.
- [x] Produce an empty plan/result for zero frozen terms.
- [x] Return empty for zero terms without requiring a text index.
- [x] Require an identity-equal canonical text index for every non-empty request.
- [x] Preserve the V2-style missing-index `IllegalStateException` and field context.
- [x] Treat unknown terms as valid absent postings.
- [x] Return empty when every non-empty term is unknown, after index resolution.
- [x] Resolve the text index, document count, and average length once per request.
- [x] Prepare each known posting, document frequency, and IDF once per request.
- [x] Retain scoring terms in frozen logical encounter order.

## Snapshot-bound plan and candidates

- [x] Store the exact `SearchSnapshot<T>` reference in every plan.
- [x] Do not accept a second snapshot at execution time.
- [x] Make plan fields and collections immutable.
- [x] Prepare text candidates as the union of known-term postings.
- [x] Reuse the configured `CandidatePlanner<T>` for structured filters.
- [x] Preserve injected `PlannerConfig` semantics for both engine ranked paths.
- [x] Preserve caller-injected `CandidatePlanner` semantics in direct
  `RankedSearcher` use.
- [x] Intersect only safe exact/superset filter candidates.
- [x] Evaluate final `filter.matches(document)` for every surviving candidate.
- [x] Evaluate an unindexed filter only against text candidates.
- [x] Never substitute a ranked full-document scan for a missing text index.
- [x] Add no candidate false negative.

## Canonical execution and scoring

- [x] Read documents, postings, lengths, and statistics from the plan's one snapshot.
- [x] Skip inactive/null documents defensively.
- [x] Preserve the exact V2 BM25 formula and arithmetic operation order.
- [x] Accumulate scores in frozen term order.
- [x] Preserve zero contribution for structured filters.
- [x] Preserve non-positive score skipping.
- [x] Retain at most `limit` candidates in a bounded top-K heap.
- [x] Order final hits by score descending, then internal document ID ascending.
- [x] Return existing `SearchHit<T>` values inside existing `SearchResult<T>`.
- [x] Add no position, phrase, field, coordination, or normalization bonus.
- [x] Maintain only one BM25, top-K, and final-ordering implementation.

## Engine and legacy integration

- [x] Override `SnapshotSearchEngine.search(SearchRequest<T>)`.
- [x] Capture `current.get()` exactly once per V3 ranked request.
- [x] Keep third-party `SearchEngine` default unsupported behavior unchanged.
- [x] Route `SnapshotSearchEngine.searchTopK(...)` through the canonical pipeline.
- [x] Keep `RankedSearcher` as a thin compatibility façade over that pipeline.
- [x] Preserve both public `RankedSearcher` constructors and its search descriptor.
- [x] Copy `TextScoringQuery.terms()` exactly for legacy requests.
- [x] Never re-analyze legacy `TextScoringQuery.queryText()` during execution.
- [x] Preserve legacy empty-query/missing-index precedence.
- [x] Preserve legacy documents, filter truth, exact scores, order, and limits.

## Focused and differential tests

- [x] Cover single-term, multi-term, repeated-term, unknown-term, and empty queries.
- [x] Cover limit 1, exact match count, oversized limit, and custom BM25 configuration.
- [x] Cover indexed and unindexed filters, match-all, match-none, and final predicate
  verification.
- [x] Cover missing index, competing `TextField`, and canonical identity.
- [x] Cover empty query with no text index.
- [x] Cover equal-score internal-ID tie ordering.
- [x] Cover direct TEXT success and bool/boost/phrase/fuzzy rejection.
- [x] Cover native positioned query terms and malformed positioned output.
- [x] Prove V3 query analysis occurs once per invocation.
- [x] Prove legacy execution performs no Analyzer call after query construction.
- [x] Cover direct `RankedSearcher` and injected planner compatibility.
- [x] Add a blocking/concurrent regression proving one-snapshot planning/execution.
- [x] Compare equivalent V2 and V3 requests for exact document, score, and order.
- [x] Add deterministic randomized differential coverage across mutations, documents,
  repeated terms, filters, limits, and valid BM25 configurations.
- [x] Keep the independent exhaustive BM25 oracle passing.

## Compatibility and scope audit

- [x] Extend the v3 independent consumer with a supported text-only SearchRequest call.
- [x] Keep v1- and v2-style consumers unchanged and passing.
- [x] Frozen v1 source/reflection fixture passes.
- [x] Japicmp passes against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [x] Public inspection finds no query-tree, plan, executor, posting, bitmap, position,
  or internal-document-ID leak.
- [x] Public inspection finds only the documented hidden bridge visibility exception.
- [x] No bool, boost, cross-field, phrase, fuzzy, or Explain execution is added.
- [x] No WAND, plan cache, prepared query, pagination, total hits, or unrelated refactor
  is added.
- [x] Bitmap representation, writer concurrency, and snapshot publication remain
  unchanged.

## Performance evidence

- [x] JMH sources compile after the pipeline refactor.
- [x] Run a focused existing BM25 top-K smoke benchmark.
- [x] Confirm no obvious full scan, unbounded hit retention, per-document analysis, or
  per-document IDF calculation.
- [x] Record observations without claiming a universal speedup or freezing a numeric
  release threshold.

## Documentation and full validation

- [x] Update `CHANGELOG.md` after implementation.
- [x] Mark Phase 3 complete in the roadmap and V3 phase map only after every gate passes.
- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes.
- [x] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [x] `./mvnw clean -Papi-compat test` passes.
- [x] `./mvnw clean -Partifact-compat verify` passes in normal and isolated repositories.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] Strict core and processor Javadocs pass.
- [x] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] No generated artifact, local repository, credential, IDE file, or root Codex
  prompt is tracked.

Phase 3 is complete only when built-in V3 text requests execute through one
snapshot-bound pipeline and the legacy V2 path uses that same execution core with exact
observable equivalence. Implementing a Phase 4+ query shape is scope failure, not extra
progress.
