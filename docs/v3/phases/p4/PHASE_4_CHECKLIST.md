# V3 Phase 4 implementation checklist

## Preparation and frozen boundary

- [x] Phase 3 is merged to `master` with every Phase 3 gate passing.
- [x] Work starts from `feat/v3-phase4-composition` at the merged Phase 3 commit.
- [x] Phase 0 semantics, Phase 3 pipeline, query nodes, bitmaps, field-local BM25,
  consumers, compatibility fixtures, and release gates are audited.
- [x] Recursive architecture, validation order, empty-leaf behavior, missing indexes,
  arithmetic, snapshot ownership, compatibility, and non-goals are frozen in
  [RANKED_COMPOSITION.md](RANKED_COMPOSITION.md).
- [x] The root Phase 4 Codex prompt remains an untracked implementation input.

## Internal query normalization and visibility

- [x] Add an immutable package-private normalized ranked-query tree for TEXT, BOOL,
  and BOOST.
- [x] Retain ordered frozen terms in each normalized TEXT occurrence.
- [x] Retain MUST then SHOULD builder encounter order in each normalized BOOL.
- [x] Retain every nested BOOST node and multiplier separately.
- [x] Preserve repeated query-object and clause occurrences without memoization,
  merging, or structural deduplication.
- [x] Keep normalized nodes, plan nodes, `ScoreMatch`, and accessors package-private.
- [x] Keep `SearchExecutionAccess` as the only Javadoc-hidden bytecode-public bridge.
- [x] Expose no query tree, plan, posting, bitmap, snapshot, score state, or internal
  document ID through the supported public API or bridge.
- [x] Add no second execution path, reflection decoder, or second visibility bridge.
- [x] Confirm no Phase 4 implementation type becomes a supported public type.

## Whole-tree validation and deterministic normalization

- [x] Null-check public engine/searcher arguments according to existing contracts.
- [x] Preflight the entire public query shape before Analyzer, index, or filter work.
- [x] Accept only TEXT, BOOL, and BOOST during Phase 4 preflight.
- [x] Reject nested PHRASE and FUZZY clearly before any sibling side effect or work.
- [x] Traverse BOOL MUST occurrences first, then SHOULD occurrences, each in encounter
  order; traverse a BOOST child in place.
- [x] Analyze every V3 TEXT occurrence exactly once through positioned analysis.
- [x] Apply the complete positioned list/element/increment/overflow validation contract.
- [x] Propagate Analyzer-thrown exceptions unchanged.
- [x] Deduplicate terms only within one V3 leaf and in first-encounter order.
- [x] Compile every child occurrence even after an earlier match-none or
  empty-candidate MUST.
- [x] Prove analysis and index-failure precedence follows frozen logical traversal.

## Empty leaves, indexes, and legacy input

- [x] Represent a zero-term TEXT leaf as match-none with empty candidates and zero
  score.
- [x] Require no text index for a zero-term leaf.
- [x] Return empty before text-index and structured-filter planning when every leaf is
  empty.
- [x] Require the identity-equal canonical text index for every non-empty leaf.
- [x] Preserve the contextual Phase 3/V2-style missing-index `IllegalStateException`.
- [x] Require missing non-empty SHOULD indexes even when MUST candidates are empty.
- [x] Treat unknown terms as valid absent postings after canonical-index resolution.
- [x] Plan the structured filter after ranked preparation when any non-empty leaf
  exists, even when all ranked terms are unknown.
- [x] Build the V2 adapter as one direct normalized TEXT leaf.
- [x] Copy V2 `TextScoringQuery.terms()` exactly without Analyzer calls,
  rededuplication, reordering, or `queryText()` reinterpretation.
- [x] Preserve V2 empty-term/missing-index precedence.

## Recursive snapshot-bound plans

- [x] Generalize the Phase 3 plan to own one immutable root scoring node.
- [x] Store the exact `SearchSnapshot<T>` reference in every `SearchPlan<T>`.
- [x] Accept no second snapshot at execution time.
- [x] Add internal `TextPlan`, `BoolPlan`, and `BoostPlan` equivalents.
- [x] Give every scoring node one safe candidate bitmap and exact
  matched-plus-score evaluation.
- [x] Prepare node candidates once per request, not per document.
- [x] Resolve every field index and posting once per leaf occurrence, not per document.
- [x] Compute document count, average length, document frequency, and IDF once per
  prepared leaf/term as appropriate.
- [x] Make every plan collection an immutable copy preserving logical order.
- [x] Read documents, indexes, postings, lengths, and statistics from the one plan
  snapshot.

## TEXT and cross-field scoring

- [x] Preserve direct TEXT any-distinct-term match semantics.
- [x] Preserve the exact Phase 3/V2 BM25 formula and term operation order.
- [x] Use each leaf's own canonical `TextIndexSnapshot`.
- [x] Use field-local `N`, `df`, `dl`, and `avgdl` for every contribution.
- [x] Keep only `Bm25Config` request-global.
- [x] Support TEXT leaves from different fields in one recursive tree.
- [x] Add child scores directly with only explicit BOOST multipliers.
- [x] Add no BM25F, DisMax, coordination factor, implicit field weight,
  normalization, or max-score selection.

## BOOL candidates and exact evaluation

- [x] Intersect every MUST child candidate bitmap when MUST children exist.
- [x] Do not enlarge a MUST BOOL candidate set with SHOULD candidates.
- [x] Union every SHOULD child candidate bitmap for an all-SHOULD BOOL.
- [x] Permit physical candidate intersection reordering without changing stored
  logical child order.
- [x] Prove every BOOL candidate bitmap is a safe superset with no false negatives.
- [x] Evaluate MUST children in encounter order and short-circuit exact evaluation on
  the first non-match.
- [x] Evaluate SHOULD children in encounter order after every MUST matches.
- [x] Make matching SHOULD children score-only when a MUST exists.
- [x] Require at least one matching SHOULD for an all-SHOULD BOOL.
- [x] Preserve pure recursive semantics for nested BOOL/BOOST combinations.
- [x] Do not flatten BOOL trees in a way that changes ordering or occurrences.

## BOOST and checked arithmetic

- [x] Reuse the child candidate bitmap for BOOST.
- [x] Preserve child match truth for every valid positive finite multiplier.
- [x] Multiply each BOOST node separately in public-tree order.
- [x] Prohibit nested multiplier flattening.
- [x] Track match truth independently from score positivity throughout execution.
- [x] Check every score addition immediately in exact logical order.
- [x] Check every score multiplication immediately at its BOOST node.
- [x] Throw `ArithmeticException` for NaN, infinite, or negative arithmetic results.
- [x] Accept and canonicalize valid positive underflow to `+0.0`.
- [x] Retain matched zero-score documents in bounded top-K and final output.
- [x] Order zero/equal-score hits by internal document ID ascending after score.

## Structured filter, execution, and snapshot behavior

- [x] Keep `SearchRequest.filter(Query<T>)` separate from ranked BOOL.
- [x] Reuse the configured `CandidatePlanner<T>` against the same snapshot.
- [x] Intersect only exact or safe-superset structured candidate bitmaps.
- [x] Evaluate final `filter.matches(document)` for each surviving candidate.
- [x] Evaluate an unindexed filter only over ranked candidates, never a full scan.
- [x] Keep structured filters eligibility-only with exactly zero score contribution.
- [x] Preserve a surviving document's score with and without an equivalent permissive
  filter.
- [x] Capture `current.get()` exactly once for built-in V2 and V3 ranked calls.
- [x] Preserve direct `RankedSearcher` caller-supplied snapshot/planner behavior.
- [x] Retain at most `limit` matched documents in the existing bounded heap.
- [x] Preserve score-descending then internal-document-ID-ascending final ordering.

## Focused, edge-case, and differential tests

- [x] Cover one/multiple MUST, SHOULD-with-MUST, all-SHOULD, and empty BOOL construction.
- [x] Cover nested BOOL, BOOST-over-BOOL, BOOL-under-BOOST, and repeated nested boosts.
- [x] Cover cross-field MUST, SHOULD-with-MUST, and all-SHOULD queries.
- [x] Prove each field uses independent `N`, `df`, `dl`, and `avgdl` statistics.
- [x] Cover duplicate terms within one leaf versus across independent clauses.
- [x] Cover the same query object reused in multiple clause positions.
- [x] Cover zero-term leaf as MUST, SHOULD, boosted child, and all-empty tree.
- [x] Cover missing canonical indexes in nested MUST/SHOULD and competing field identity.
- [x] Cover a later missing SHOULD index after an earlier match-none MUST.
- [x] Cover unknown terms and all-unknown ranked candidates with filter planning.
- [x] Cover malformed positioned output and per-occurrence Analyzer invocation counts.
- [x] Cover PHRASE/FUZZY preflight before Analyzer, index, and filter work.
- [x] Cover candidate-superset safety for every supported recursive shape.
- [x] Cover logical score accumulation independent of physical bitmap order.
- [x] Cover valid BOOST underflow yielding a matched zero-score hit.
- [x] Cover checked BOOL addition overflow and BOOST multiplication overflow.
- [x] Cover an encounter-order floating-point case that would expose reordering or
  boost flattening.
- [x] Cover indexed/unindexed filters, match-all, match-none, subset, and final
  predicate verification.
- [x] Add a blocking/concurrent regression proving one-snapshot cross-field execution.
- [x] Preserve exact Phase 3 direct-TEXT documents, scores, order, limit, and errors.
- [x] Preserve exact V2 `searchTopK` and direct `RankedSearcher` behavior.
- [x] Add deterministic randomized differential tests against a trusted recursive
  BOOL/BOOST/cross-field evaluator.
- [x] Keep PHRASE, FUZZY, and Explain execution unsupported.

## Compatibility and scope audit

- [x] Extend the independent V3 consumer with executable BOOL/BOOST/cross-field usage
  using its real `city` and `description` fields and `Query.eq`.
- [x] Keep v1- and v2-style consumers unchanged and passing.
- [x] Keep the frozen v1 source/reflection fixture passing.
- [x] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [x] Confirm Phase 4 adds no supported public type, method, or descriptor.
- [x] Confirm the hidden Phase 3 bridge is unchanged in role and visibility.
- [x] Add no phrase, fuzzy, Explain, `minimumShouldMatch`, ranked `mustNot`, ranked
  filter, BM25F, DisMax, WAND, plan cache, prepared query, or pagination execution.
- [x] Leave bitmap representation, writer concurrency, and snapshot publication
  architecture unchanged.

## Performance evidence

The focused evidence is recorded in
[PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md).

- [x] Add or select a focused nested BOOL/BOOST/cross-field JMH case.
- [x] Compile all JMH sources after the recursive-plan refactor.
- [x] Run a focused composition smoke and record environment and observations.
- [x] Confirm no per-document analysis, index resolution, IDF calculation, candidate
  union/intersection, or unbounded result retention.
- [x] Make no universal speedup claim and freeze no numeric release threshold.

## Documentation and full validation

- [x] Update `CHANGELOG.md` only after implementation accurately describes Phase 4.
- [x] Mark Phase 4 complete in the roadmap and phase map only after every gate passes.
- [x] Keep this contract and checklist synchronized with the implementation.
- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes.
- [x] `scripts/run-travel-example.sh` passes.
- [x] `./mvnw clean -Papi-compat test` passes.
- [x] `./mvnw clean -Partifact-compat verify` passes in the normal repository.
- [x] The same artifact-compat command passes with an isolated Maven repository.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] Strict core and processor Javadocs pass.
- [x] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] `./mvnw -Pjmh -DskipTests package` passes.
- [x] No generated artifact, isolated repository, credential, IDE file, benchmark
  output, or root Codex prompt is tracked.

Phase 4 is complete only when TEXT, BOOL, and BOOST execute as one deterministic,
snapshot-bound recursive ranked plan; cross-field BM25 remains field-local; matched
state survives valid zero-score underflow; legacy behavior is unchanged; and every
gate above passes. Phase 5+ work is scope failure, not extra progress.
