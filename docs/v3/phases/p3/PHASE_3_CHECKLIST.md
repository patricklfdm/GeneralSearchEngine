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

- [ ] Add package-private immutable normalized text-search input.
- [ ] Keep the exact frozen `TextField`, term order, optional filter, limit, and BM25
  configuration in that input.
- [ ] Add package-private `SearchPlanner`, immutable `SearchPlan`, and `SearchExecutor`
  in the search package.
- [ ] Keep every existing `SearchQueryNode` and its accessor package-private.
- [ ] Add only the frozen bytecode-public `SearchExecutionAccess` sibling-package
  bridge.
- [ ] Mark the bridge `@hidden`, document it unsupported, and prevent construction.
- [ ] Expose no node, plan, posting, bitmap, position, or internal document ID through
  the bridge or supported public API.
- [ ] Use no reflection or method-handle access to decode `SearchQuery`.
- [ ] Confirm no other Phase 3 implementation type becomes public.

## V3 query decoding and analysis

- [ ] Accept only a direct `SearchQueries.text(...)` leaf in Phase 3.
- [ ] Reject bool, boost, phrase, and fuzzy shapes with clear
  `UnsupportedOperationException`.
- [ ] Reject unsupported shapes before Analyzer and text-index work.
- [ ] Analyze V3 raw query text exactly once per request through positioned analysis.
- [ ] Apply the complete Phase 2 null/increment/overflow validation contract.
- [ ] Propagate Analyzer-thrown exceptions unchanged.
- [ ] Deduplicate V3 terms in first-encounter order.
- [ ] Keep valid position increments semantically irrelevant to term-only scoring.
- [ ] Prove default-adapted and native positioned Analyzers use the expected query
  terms.

## Validation and planning order

- [ ] Null-check public request and snapshot arguments according to existing contracts.
- [ ] Produce an empty plan/result for zero frozen terms.
- [ ] Return empty for zero terms without requiring a text index.
- [ ] Require an identity-equal canonical text index for every non-empty request.
- [ ] Preserve the V2-style missing-index `IllegalStateException` and field context.
- [ ] Treat unknown terms as valid absent postings.
- [ ] Return empty when every non-empty term is unknown, after index resolution.
- [ ] Resolve the text index, document count, and average length once per request.
- [ ] Prepare each known posting, document frequency, and IDF once per request.
- [ ] Retain scoring terms in frozen logical encounter order.

## Snapshot-bound plan and candidates

- [ ] Store the exact `SearchSnapshot<T>` reference in every plan.
- [ ] Do not accept a second snapshot at execution time.
- [ ] Make plan fields and collections immutable.
- [ ] Prepare text candidates as the union of known-term postings.
- [ ] Reuse the configured `CandidatePlanner<T>` for structured filters.
- [ ] Preserve injected `PlannerConfig` semantics for both engine ranked paths.
- [ ] Preserve caller-injected `CandidatePlanner` semantics in direct
  `RankedSearcher` use.
- [ ] Intersect only safe exact/superset filter candidates.
- [ ] Evaluate final `filter.matches(document)` for every surviving candidate.
- [ ] Evaluate an unindexed filter only against text candidates.
- [ ] Never substitute a ranked full-document scan for a missing text index.
- [ ] Add no candidate false negative.

## Canonical execution and scoring

- [ ] Read documents, postings, lengths, and statistics from the plan's one snapshot.
- [ ] Skip inactive/null documents defensively.
- [ ] Preserve the exact V2 BM25 formula and arithmetic operation order.
- [ ] Accumulate scores in frozen term order.
- [ ] Preserve zero contribution for structured filters.
- [ ] Preserve non-positive score skipping.
- [ ] Retain at most `limit` candidates in a bounded top-K heap.
- [ ] Order final hits by score descending, then internal document ID ascending.
- [ ] Return existing `SearchHit<T>` values inside existing `SearchResult<T>`.
- [ ] Add no position, phrase, field, coordination, or normalization bonus.
- [ ] Maintain only one BM25, top-K, and final-ordering implementation.

## Engine and legacy integration

- [ ] Override `SnapshotSearchEngine.search(SearchRequest<T>)`.
- [ ] Capture `current.get()` exactly once per V3 ranked request.
- [ ] Keep third-party `SearchEngine` default unsupported behavior unchanged.
- [ ] Route `SnapshotSearchEngine.searchTopK(...)` through the canonical pipeline.
- [ ] Keep `RankedSearcher` as a thin compatibility façade over that pipeline.
- [ ] Preserve both public `RankedSearcher` constructors and its search descriptor.
- [ ] Copy `TextScoringQuery.terms()` exactly for legacy requests.
- [ ] Never re-analyze legacy `TextScoringQuery.queryText()` during execution.
- [ ] Preserve legacy empty-query/missing-index precedence.
- [ ] Preserve legacy documents, filter truth, exact scores, order, and limits.

## Focused and differential tests

- [ ] Cover single-term, multi-term, repeated-term, unknown-term, and empty queries.
- [ ] Cover limit 1, exact match count, oversized limit, and custom BM25 configuration.
- [ ] Cover indexed and unindexed filters, match-all, match-none, and final predicate
  verification.
- [ ] Cover missing index, competing `TextField`, and canonical identity.
- [ ] Cover empty query with no text index.
- [ ] Cover equal-score internal-ID tie ordering.
- [ ] Cover direct TEXT success and bool/boost/phrase/fuzzy rejection.
- [ ] Cover native positioned query terms and malformed positioned output.
- [ ] Prove V3 query analysis occurs once per invocation.
- [ ] Prove legacy execution performs no Analyzer call after query construction.
- [ ] Cover direct `RankedSearcher` and injected planner compatibility.
- [ ] Add a blocking/concurrent regression proving one-snapshot planning/execution.
- [ ] Compare equivalent V2 and V3 requests for exact document, score, and order.
- [ ] Add deterministic randomized differential coverage across mutations, documents,
  repeated terms, filters, limits, and valid BM25 configurations.
- [ ] Keep the independent exhaustive BM25 oracle passing.

## Compatibility and scope audit

- [ ] Extend the v3 independent consumer with a supported text-only SearchRequest call.
- [ ] Keep v1- and v2-style consumers unchanged and passing.
- [ ] Frozen v1 source/reflection fixture passes.
- [ ] Japicmp passes against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [ ] Public inspection finds no query-tree, plan, executor, posting, bitmap, position,
  or internal-document-ID leak.
- [ ] Public inspection finds only the documented hidden bridge visibility exception.
- [ ] No bool, boost, cross-field, phrase, fuzzy, or Explain execution is added.
- [ ] No WAND, plan cache, prepared query, pagination, total hits, or unrelated refactor
  is added.
- [ ] Bitmap representation, writer concurrency, and snapshot publication remain
  unchanged.

## Performance evidence

- [ ] JMH sources compile after the pipeline refactor.
- [ ] Run a focused existing BM25 top-K smoke benchmark.
- [ ] Confirm no obvious full scan, unbounded hit retention, per-document analysis, or
  per-document IDF calculation.
- [ ] Record observations without claiming a universal speedup or freezing a numeric
  release threshold.

## Documentation and full validation

- [ ] Update `CHANGELOG.md` after implementation.
- [ ] Mark Phase 3 complete in the roadmap and V3 phase map only after every gate passes.
- [ ] `git diff --check` passes.
- [ ] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [ ] `./mvnw -f reactor/pom.xml clean test` passes.
- [ ] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [ ] `./mvnw clean -Papi-compat test` passes.
- [ ] `./mvnw clean -Partifact-compat verify` passes in normal and isolated repositories.
- [ ] `scripts/verify-consumer-projects.sh` passes.
- [ ] Strict core and processor Javadocs pass.
- [ ] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [ ] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [ ] `scripts/verify-reproducible-build.sh` passes.
- [ ] No generated artifact, local repository, credential, IDE file, or root Codex
  prompt is tracked.

Phase 3 is complete only when built-in V3 text requests execute through one
snapshot-bound pipeline and the legacy V2 path uses that same execution core with exact
observable equivalence. Implementing a Phase 4+ query shape is scope failure, not extra
progress.
