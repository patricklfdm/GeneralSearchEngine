# V3 Phase 5 implementation checklist

## Preparation and frozen boundary

- [x] Phase 4 is merged to `master` with every Phase 4 gate passing.
- [x] Work starts from `feat/v3-phase5-phrase` at the merged Phase 4 commit.
- [x] Phase 0 phrase semantics, positioned analysis/storage, recursive ranked plans,
  dynamic-index lifecycle, compatibility fixtures, consumers, and release gates are
  audited.
- [x] Phrase normalization, position access, validation precedence, candidate safety,
  exact matching, scoring, arithmetic, snapshot ownership, compatibility, and non-goals
  are frozen in [EXACT_PHRASE_SEARCH.md](EXACT_PHRASE_SEARCH.md).
- [x] The root Phase 5 Codex prompt remains an untracked implementation input.

## Internal representation and visibility

- [x] Add an immutable package-private normalized PHRASE node.
- [x] Represent ordered occupied slots with normalized relative logical positions.
- [x] Retain distinct same-position alternatives in Analyzer first-encounter order.
- [x] Preserve the same term when it appears in different phrase slots.
- [x] Retain one distinct scoring-term list in global Analyzer first-encounter order.
- [x] Add a package-private `PhrasePlan` equivalent to the recursive scoring tree.
- [x] Keep phrase slots, normalized nodes, plan nodes, postings, candidates, anchors,
  scores, and internal document IDs out of the supported public API.
- [x] Add only the frozen Javadoc-hidden `PhrasePositionAccess` visibility bridge.
- [x] Make that bridge final, non-instantiable, stateless, and explicitly unsupported.
- [x] Let the bridge return exact match truth only; expose no `IntPositions`, arrays,
  collections, iterators, streams, callbacks, or retained position handles.
- [x] Add no position method to supported `PostingList` or `TextIndexSnapshot` APIs.
- [x] Add no reflection decoder, duplicate phrase search path, or second Phase 5 bridge.

## Whole-tree validation and deterministic normalization

- [x] Null-check public engine/searcher arguments according to existing contracts.
- [x] Preflight the complete public query shape before Analyzer, index, position, or
  structured-filter work.
- [x] Accept TEXT, PHRASE, BOOL, and BOOST during Phase 5 preflight.
- [x] Reject any nested FUZZY before every sibling side effect or planning operation.
- [x] Preserve MUST-then-SHOULD logical traversal and in-place BOOST traversal.
- [x] Analyze every V3 PHRASE occurrence exactly once through positioned analysis.
- [x] Preserve independent visits for repeated query-object/clause occurrences.
- [x] Validate the complete returned positioned sequence before committing slots or
  scoring terms.
- [x] Enforce non-null list/elements, positive first increment, non-negative later
  increments, and checked logical-position accumulation.
- [x] Propagate Analyzer-thrown exceptions unchanged and keep contextual field/token
  details on contract failures.
- [x] Compile every child occurrence after earlier match-none or empty-candidate leaves.
- [x] Prove Analyzer and index failures follow deterministic logical traversal order.

## Phrase slots, gaps, and leaf preparation

- [x] Normalize every valid query position relative to the first occupied position.
- [x] Validate but normalize away the initial query gap.
- [x] Preserve every subsequent relative gap exactly.
- [x] Group equal logical positions into one ordered OR-alternative slot.
- [x] Deduplicate alternatives only within one slot and by first encounter.
- [x] Preserve repeated terms across distinct slots for exact matching.
- [x] Deduplicate scoring terms across the leaf in global first-encounter order.
- [x] Represent a zero-slot PHRASE as match-none with empty candidates and zero score.
- [x] Require no text index for a zero-slot PHRASE.
- [x] Support one-slot phrases, including a slot with multiple alternatives.
- [x] Require the identity-equal canonical text index for every non-empty PHRASE.
- [x] Preserve the contextual missing-index `IllegalStateException` naming the field.
- [x] Treat unknown terms as valid empty postings only after canonical-index resolution.
- [x] Require later non-empty MUST/SHOULD indexes even after an earlier match-none leaf.
- [x] Return empty before index and filter planning only when every TEXT/PHRASE leaf is
  empty after valid analysis.

## Prepared candidates and deterministic anchor

- [x] Resolve every alternative posting once per phrase occurrence, not per document.
- [x] Build each slot candidate bitmap as the union of its alternative postings.
- [x] Intersect every occupied slot candidate bitmap into a phrase safe superset.
- [x] Allow candidate false positives before positional verification and forbid false
  negatives.
- [x] Permit safe repeated posting/source intersection deduplication without removing
  repeated exact-match slots.
- [x] Permit ascending-cardinality physical intersection with original slot order as
  the deterministic tie-break.
- [x] Select the anchor using the smallest fully unioned slot candidate cardinality.
- [x] Break equal-cardinality anchor ties by earliest phrase slot.
- [x] Do not choose an anchor from only one alternative's document frequency.
- [x] Retain alternatives and positions in deterministic encounter/ascending order.
- [x] Prepare candidates, anchor, postings, IDF, document count, and average length once
  per request-level leaf.
- [x] Rebuild none of those facts per candidate document.

## Exact positional verification

- [x] Verify only documents in the prepared phrase candidate bitmap.
- [x] Iterate anchor occurrences through the internal text-index bridge.
- [x] Compute required positions with `long` intermediate arithmetic.
- [x] Treat negative or greater-than-`Integer.MAX_VALUE` required positions as a
  non-matching anchor occurrence rather than throwing or wrapping.
- [x] Require one alternative from every slot at its exact required position.
- [x] Preserve exact gaps, repeated-term requirements, and phrase-at-any-base behavior.
- [x] Support same-position OR alternatives without requiring all alternatives.
- [x] Perform sorted primitive `contains`-style checks against Phase 2 positions.
- [x] Do not re-analyze document text during query execution.
- [x] Do not allocate boxed position sets/lists or materialize position arrays per doc.
- [x] Do not add a duplicate phrase-specific positional index or occurrence store.

## Phrase scoring and recursive composition

- [x] Use exact phrase truth only as a match gate; add no phrase/proximity bonus.
- [x] Score distinct analyzed phrase terms once in global first-encounter order.
- [x] Require repeated terms at every phrase slot without multiplying query weight.
- [x] After a phrase matches, score every distinct analyzed term occurring in the
  document, not only the alternative that first proved a slot.
- [x] When multiple distinct same-slot alternatives occur, score each exactly once.
- [x] Use each phrase field's prepared posting, `N`, `df`, `dl`, and `avgdl`.
- [x] Keep document length equal to emitted token count; gaps do not increase `dl`.
- [x] Reuse the existing BM25 formula and request `Bm25Config` unchanged.
- [x] Reuse `ScoreMatch` and track match truth independently from score positivity.
- [x] Check every phrase-term score addition immediately in logical order.
- [x] Preserve valid underflow as matched `+0.0` and throw for invalid arithmetic.
- [x] Compose PHRASE correctly under MUST, SHOULD, nested BOOL, and nested BOOST.
- [x] Preserve node-by-node checked BOOST multiplication and BOOL addition.
- [x] Compose different TEXT/PHRASE fields using independent field-local statistics.
- [x] Add no BM25F, DisMax, coordination, field normalization, or implicit phrase weight.

## Filters, execution, snapshot, and lifecycle

- [x] Keep structured filters eligibility-only with zero score contribution.
- [x] Plan filters after ranked preparation whenever any non-empty ranked leaf exists.
- [x] Intersect only exact or safe-superset filter candidates and run the final filter
  predicate over surviving phrase candidates.
- [x] Preserve phrase score with and without an equivalent permissive filter.
- [x] Keep `SearchExecutor` generic over the root scoring node with no phrase branch.
- [x] Bind every phrase plan to exactly one immutable `SearchSnapshot<T>`.
- [x] Mix no document, posting, position, length, statistic, candidate, or filter facts
  across snapshot versions.
- [x] Preserve score-descending then internal-document-ID-ascending result ordering.
- [x] Keep bounded top-K retention, including matched zero-score phrases.
- [x] Make add/update/reorder/remove/bulk publication update phrase truth correctly.
- [x] Preserve old phrase truth in old immutable snapshots after publication.
- [x] Support replay-correct positions for dynamically created text indexes.
- [x] Cover mutation while dynamic build is pending, publication, and subsequent drop.
- [x] Make a non-empty phrase fail with missing index after its canonical index is dropped.

## Focused, edge-case, and differential tests

- [x] Cover empty, one-slot, adjacent multi-slot, reordered, missing, and unknown terms.
- [x] Cover repeated terms with sufficient and insufficient occurrences.
- [x] Cover initial gaps, internal gaps, phrase-at-offset, and wrong-gap rejection.
- [x] Cover same-position alternatives A/B, neither alternative, duplicate alternative,
  and both distinct alternatives present.
- [x] Prove the exact both-alternatives-present BM25 score and accumulation order.
- [x] Cover zero-slot PHRASE as root, MUST, SHOULD, boosted child, and in all-empty trees.
- [x] Cover missing canonical indexes for root/MUST/SHOULD and competing field identity.
- [x] Cover a later missing SHOULD index after an earlier match-none MUST.
- [x] Cover complete malformed positioned output and Analyzer invocation counts.
- [x] Cover the same phrase object reused in independent clause occurrences.
- [x] Cover FUZZY whole-tree preflight before Analyzer/index/position/filter work.
- [x] Cover slot candidate union, phrase intersection, repeated-source deduplication,
  and candidate-superset safety.
- [x] Cover anchor selection, equal-cardinality tie-break, unknown/empty candidates, and
  relative-position arithmetic boundaries.
- [x] Cover exact phrase BM25, custom BM25, field-local statistics, equal-score order,
  matched-zero underflow, checked addition overflow, and checked BOOST overflow.
- [x] Cover MUST/SHOULD/nested BOOL/BOOST and cross-field TEXT/PHRASE composition.
- [x] Cover indexed/unindexed filters and final predicate verification.
- [x] Cover add/update/reorder/remove/bulk, snapshot isolation, and concurrent publication.
- [x] Cover dynamic index build, pending mutation replay, publication, and drop.
- [x] Add deterministic randomized reference evaluation for match, score, and order.
- [x] Add randomized candidate-superset assertions with explicit seeds.
- [x] Preserve direct TEXT, Phase 4 composition, V2 `searchTopK`, and direct
  `RankedSearcher` observable behavior.
- [x] Keep FUZZY and Explain unsupported.

## Compatibility and scope audit

- [x] Extend the independent V3 consumer with executable exact phrase usage using its
  real canonical field.
- [x] Keep the travel example unchanged unless repository convention makes a small
  observable phrase example preferable.
- [x] Keep v1- and v2-style consumers unchanged and passing.
- [x] Keep the frozen v1 source/reflection fixture passing.
- [x] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [x] Confirm Phase 5 adds no supported public type, method, field, or descriptor.
- [x] Document the one additive hidden `PhrasePositionAccess` class in compatibility
  policy and Japicmp review.
- [x] Inspect the bridge API for every prohibited position/query/plan/snapshot leak.
- [x] Keep `SearchExecutionAccess` complete-execution-only and otherwise unchanged.
- [x] Add no fuzzy, Explain, slop, highlighting, offset, phrase-frequency, proximity,
  synonym, advanced ranking, plan-cache, prepared-query, or pagination behavior.
- [x] Leave bitmap representation, writer concurrency, and snapshot publication
  architecture unchanged.

## Performance evidence

- [x] Add or select a focused exact-phrase JMH case with representative candidate
  reduction, repeated terms, gaps, and same-position alternatives where practical.
- [x] Compile all JMH sources after adding the phrase plan and internal bridge.
- [x] Run a focused phrase smoke and record environment, workload, and observations.
- [x] Confirm there is no full-document scan, document reanalysis, per-document index,
  posting, IDF, slot, or candidate reconstruction.
- [x] Confirm there is no per-document boxed position collection or unbounded result
  retention.
- [x] Make no universal speedup claim and freeze no numeric release threshold.

## Documentation and full validation

- [x] Add a Phase 5 performance evidence document after measurements exist.
- [x] Update `CHANGELOG.md` only after implementation accurately describes Phase 5.
- [x] Mark Phase 5 complete in roadmap and phase map only after every gate passes.
- [x] Keep this contract, prompt, and checklist synchronized with implementation.
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

Phase 5 is complete only when PHRASE executes as an exact positional gate plus ordinary
distinct-term BM25 inside the existing snapshot-bound recursive plan; internal
positions remain unexposed; legacy behavior is unchanged; and every gate above passes.
Phase 6+ work is scope failure, not extra progress.
