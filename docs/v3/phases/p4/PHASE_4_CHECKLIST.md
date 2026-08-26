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

- [ ] Add an immutable package-private normalized ranked-query tree for TEXT, BOOL,
  and BOOST.
- [ ] Retain ordered frozen terms in each normalized TEXT occurrence.
- [ ] Retain MUST then SHOULD builder encounter order in each normalized BOOL.
- [ ] Retain every nested BOOST node and multiplier separately.
- [ ] Preserve repeated query-object and clause occurrences without memoization,
  merging, or structural deduplication.
- [ ] Keep normalized nodes, plan nodes, `ScoreMatch`, and accessors package-private.
- [ ] Keep `SearchExecutionAccess` as the only Javadoc-hidden bytecode-public bridge.
- [ ] Expose no query tree, plan, posting, bitmap, snapshot, score state, or internal
  document ID through the supported public API or bridge.
- [ ] Add no second execution path, reflection decoder, or second visibility bridge.
- [ ] Confirm no Phase 4 implementation type becomes a supported public type.

## Whole-tree validation and deterministic normalization

- [ ] Null-check public engine/searcher arguments according to existing contracts.
- [ ] Preflight the entire public query shape before Analyzer, index, or filter work.
- [ ] Accept only TEXT, BOOL, and BOOST during Phase 4 preflight.
- [ ] Reject nested PHRASE and FUZZY clearly before any sibling side effect or work.
- [ ] Traverse BOOL MUST occurrences first, then SHOULD occurrences, each in encounter
  order; traverse a BOOST child in place.
- [ ] Analyze every V3 TEXT occurrence exactly once through positioned analysis.
- [ ] Apply the complete positioned list/element/increment/overflow validation contract.
- [ ] Propagate Analyzer-thrown exceptions unchanged.
- [ ] Deduplicate terms only within one V3 leaf and in first-encounter order.
- [ ] Compile every child occurrence even after an earlier match-none or
  empty-candidate MUST.
- [ ] Prove analysis and index-failure precedence follows frozen logical traversal.

## Empty leaves, indexes, and legacy input

- [ ] Represent a zero-term TEXT leaf as match-none with empty candidates and zero
  score.
- [ ] Require no text index for a zero-term leaf.
- [ ] Return empty before text-index and structured-filter planning when every leaf is
  empty.
- [ ] Require the identity-equal canonical text index for every non-empty leaf.
- [ ] Preserve the contextual Phase 3/V2-style missing-index `IllegalStateException`.
- [ ] Require missing non-empty SHOULD indexes even when MUST candidates are empty.
- [ ] Treat unknown terms as valid absent postings after canonical-index resolution.
- [ ] Plan the structured filter after ranked preparation when any non-empty leaf
  exists, even when all ranked terms are unknown.
- [ ] Build the V2 adapter as one direct normalized TEXT leaf.
- [ ] Copy V2 `TextScoringQuery.terms()` exactly without Analyzer calls,
  rededuplication, reordering, or `queryText()` reinterpretation.
- [ ] Preserve V2 empty-term/missing-index precedence.

## Recursive snapshot-bound plans

- [ ] Generalize the Phase 3 plan to own one immutable root scoring node.
- [ ] Store the exact `SearchSnapshot<T>` reference in every `SearchPlan<T>`.
- [ ] Accept no second snapshot at execution time.
- [ ] Add internal `TextPlan`, `BoolPlan`, and `BoostPlan` equivalents.
- [ ] Give every scoring node one safe candidate bitmap and exact
  matched-plus-score evaluation.
- [ ] Prepare node candidates once per request, not per document.
- [ ] Resolve every field index and posting once per leaf occurrence, not per document.
- [ ] Compute document count, average length, document frequency, and IDF once per
  prepared leaf/term as appropriate.
- [ ] Make every plan collection an immutable copy preserving logical order.
- [ ] Read documents, indexes, postings, lengths, and statistics from the one plan
  snapshot.

## TEXT and cross-field scoring

- [ ] Preserve direct TEXT any-distinct-term match semantics.
- [ ] Preserve the exact Phase 3/V2 BM25 formula and term operation order.
- [ ] Use each leaf's own canonical `TextIndexSnapshot`.
- [ ] Use field-local `N`, `df`, `dl`, and `avgdl` for every contribution.
- [ ] Keep only `Bm25Config` request-global.
- [ ] Support TEXT leaves from different fields in one recursive tree.
- [ ] Add child scores directly with only explicit BOOST multipliers.
- [ ] Add no BM25F, DisMax, coordination factor, implicit field weight,
  normalization, or max-score selection.

## BOOL candidates and exact evaluation

- [ ] Intersect every MUST child candidate bitmap when MUST children exist.
- [ ] Do not enlarge a MUST BOOL candidate set with SHOULD candidates.
- [ ] Union every SHOULD child candidate bitmap for an all-SHOULD BOOL.
- [ ] Permit physical candidate intersection reordering without changing stored
  logical child order.
- [ ] Prove every BOOL candidate bitmap is a safe superset with no false negatives.
- [ ] Evaluate MUST children in encounter order and short-circuit exact evaluation on
  the first non-match.
- [ ] Evaluate SHOULD children in encounter order after every MUST matches.
- [ ] Make matching SHOULD children score-only when a MUST exists.
- [ ] Require at least one matching SHOULD for an all-SHOULD BOOL.
- [ ] Preserve pure recursive semantics for nested BOOL/BOOST combinations.
- [ ] Do not flatten BOOL trees in a way that changes ordering or occurrences.

## BOOST and checked arithmetic

- [ ] Reuse the child candidate bitmap for BOOST.
- [ ] Preserve child match truth for every valid positive finite multiplier.
- [ ] Multiply each BOOST node separately in public-tree order.
- [ ] Prohibit nested multiplier flattening.
- [ ] Track match truth independently from score positivity throughout execution.
- [ ] Check every score addition immediately in exact logical order.
- [ ] Check every score multiplication immediately at its BOOST node.
- [ ] Throw `ArithmeticException` for NaN, infinite, or negative arithmetic results.
- [ ] Accept and canonicalize valid positive underflow to `+0.0`.
- [ ] Retain matched zero-score documents in bounded top-K and final output.
- [ ] Order zero/equal-score hits by internal document ID ascending after score.

## Structured filter, execution, and snapshot behavior

- [ ] Keep `SearchRequest.filter(Query<T>)` separate from ranked BOOL.
- [ ] Reuse the configured `CandidatePlanner<T>` against the same snapshot.
- [ ] Intersect only exact or safe-superset structured candidate bitmaps.
- [ ] Evaluate final `filter.matches(document)` for each surviving candidate.
- [ ] Evaluate an unindexed filter only over ranked candidates, never a full scan.
- [ ] Keep structured filters eligibility-only with exactly zero score contribution.
- [ ] Preserve a surviving document's score with and without an equivalent permissive
  filter.
- [ ] Capture `current.get()` exactly once for built-in V2 and V3 ranked calls.
- [ ] Preserve direct `RankedSearcher` caller-supplied snapshot/planner behavior.
- [ ] Retain at most `limit` matched documents in the existing bounded heap.
- [ ] Preserve score-descending then internal-document-ID-ascending final ordering.

## Focused, edge-case, and differential tests

- [ ] Cover one/multiple MUST, SHOULD-with-MUST, all-SHOULD, and empty BOOL construction.
- [ ] Cover nested BOOL, BOOST-over-BOOL, BOOL-under-BOOST, and repeated nested boosts.
- [ ] Cover cross-field MUST, SHOULD-with-MUST, and all-SHOULD queries.
- [ ] Prove each field uses independent `N`, `df`, `dl`, and `avgdl` statistics.
- [ ] Cover duplicate terms within one leaf versus across independent clauses.
- [ ] Cover the same query object reused in multiple clause positions.
- [ ] Cover zero-term leaf as MUST, SHOULD, boosted child, and all-empty tree.
- [ ] Cover missing canonical indexes in nested MUST/SHOULD and competing field identity.
- [ ] Cover a later missing SHOULD index after an earlier match-none MUST.
- [ ] Cover unknown terms and all-unknown ranked candidates with filter planning.
- [ ] Cover malformed positioned output and per-occurrence Analyzer invocation counts.
- [ ] Cover PHRASE/FUZZY preflight before Analyzer, index, and filter work.
- [ ] Cover candidate-superset safety for every supported recursive shape.
- [ ] Cover logical score accumulation independent of physical bitmap order.
- [ ] Cover valid BOOST underflow yielding a matched zero-score hit.
- [ ] Cover checked BOOL addition overflow and BOOST multiplication overflow.
- [ ] Cover an encounter-order floating-point case that would expose reordering or
  boost flattening.
- [ ] Cover indexed/unindexed filters, match-all, match-none, subset, and final
  predicate verification.
- [ ] Add a blocking/concurrent regression proving one-snapshot cross-field execution.
- [ ] Preserve exact Phase 3 direct-TEXT documents, scores, order, limit, and errors.
- [ ] Preserve exact V2 `searchTopK` and direct `RankedSearcher` behavior.
- [ ] Add deterministic randomized differential tests against a trusted recursive
  BOOL/BOOST/cross-field evaluator.
- [ ] Keep PHRASE, FUZZY, and Explain execution unsupported.

## Compatibility and scope audit

- [ ] Extend the independent V3 consumer with executable BOOL/BOOST/cross-field usage
  using its real `city` and `description` fields and `Query.eq`.
- [ ] Keep v1- and v2-style consumers unchanged and passing.
- [ ] Keep the frozen v1 source/reflection fixture passing.
- [ ] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [ ] Confirm Phase 4 adds no supported public type, method, or descriptor.
- [ ] Confirm the hidden Phase 3 bridge is unchanged in role and visibility.
- [ ] Add no phrase, fuzzy, Explain, `minimumShouldMatch`, ranked `mustNot`, ranked
  filter, BM25F, DisMax, WAND, plan cache, prepared query, or pagination execution.
- [ ] Leave bitmap representation, writer concurrency, and snapshot publication
  architecture unchanged.

## Performance evidence

- [ ] Add or select a focused nested BOOL/BOOST/cross-field JMH case.
- [ ] Compile all JMH sources after the recursive-plan refactor.
- [ ] Run a focused composition smoke and record environment and observations.
- [ ] Confirm no per-document analysis, index resolution, IDF calculation, candidate
  union/intersection, or unbounded result retention.
- [ ] Make no universal speedup claim and freeze no numeric release threshold.

## Documentation and full validation

- [ ] Update `CHANGELOG.md` only after implementation accurately describes Phase 4.
- [ ] Mark Phase 4 complete in the roadmap and phase map only after every gate passes.
- [ ] Keep this contract and checklist synchronized with the implementation.
- [ ] `git diff --check` passes.
- [ ] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [ ] `./mvnw -f reactor/pom.xml clean test` passes.
- [ ] `scripts/run-travel-example.sh` passes.
- [ ] `./mvnw clean -Papi-compat test` passes.
- [ ] `./mvnw clean -Partifact-compat verify` passes in the normal repository.
- [ ] The same artifact-compat command passes with an isolated Maven repository.
- [ ] `scripts/verify-consumer-projects.sh` passes.
- [ ] Strict core and processor Javadocs pass.
- [ ] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [ ] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [ ] `scripts/verify-reproducible-build.sh` passes.
- [ ] `./mvnw -Pjmh -DskipTests package` passes.
- [ ] No generated artifact, isolated repository, credential, IDE file, benchmark
  output, or root Codex prompt is tracked.

Phase 4 is complete only when TEXT, BOOL, and BOOST execute as one deterministic,
snapshot-bound recursive ranked plan; cross-field BM25 remains field-local; matched
state survives valid zero-score underflow; legacy behavior is unchanged; and every
gate above passes. Phase 5+ work is scope failure, not extra progress.
