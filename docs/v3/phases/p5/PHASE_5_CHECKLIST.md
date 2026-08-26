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

- [ ] Add an immutable package-private normalized PHRASE node.
- [ ] Represent ordered occupied slots with normalized relative logical positions.
- [ ] Retain distinct same-position alternatives in Analyzer first-encounter order.
- [ ] Preserve the same term when it appears in different phrase slots.
- [ ] Retain one distinct scoring-term list in global Analyzer first-encounter order.
- [ ] Add a package-private `PhrasePlan` equivalent to the recursive scoring tree.
- [ ] Keep phrase slots, normalized nodes, plan nodes, postings, candidates, anchors,
  scores, and internal document IDs out of the supported public API.
- [ ] Add only the frozen Javadoc-hidden `PhrasePositionAccess` visibility bridge.
- [ ] Make that bridge final, non-instantiable, stateless, and explicitly unsupported.
- [ ] Let the bridge return exact match truth only; expose no `IntPositions`, arrays,
  collections, iterators, streams, callbacks, or retained position handles.
- [ ] Add no position method to supported `PostingList` or `TextIndexSnapshot` APIs.
- [ ] Add no reflection decoder, duplicate phrase search path, or second Phase 5 bridge.

## Whole-tree validation and deterministic normalization

- [ ] Null-check public engine/searcher arguments according to existing contracts.
- [ ] Preflight the complete public query shape before Analyzer, index, position, or
  structured-filter work.
- [ ] Accept TEXT, PHRASE, BOOL, and BOOST during Phase 5 preflight.
- [ ] Reject any nested FUZZY before every sibling side effect or planning operation.
- [ ] Preserve MUST-then-SHOULD logical traversal and in-place BOOST traversal.
- [ ] Analyze every V3 PHRASE occurrence exactly once through positioned analysis.
- [ ] Preserve independent visits for repeated query-object/clause occurrences.
- [ ] Validate the complete returned positioned sequence before committing slots or
  scoring terms.
- [ ] Enforce non-null list/elements, positive first increment, non-negative later
  increments, and checked logical-position accumulation.
- [ ] Propagate Analyzer-thrown exceptions unchanged and keep contextual field/token
  details on contract failures.
- [ ] Compile every child occurrence after earlier match-none or empty-candidate leaves.
- [ ] Prove Analyzer and index failures follow deterministic logical traversal order.

## Phrase slots, gaps, and leaf preparation

- [ ] Normalize every valid query position relative to the first occupied position.
- [ ] Validate but normalize away the initial query gap.
- [ ] Preserve every subsequent relative gap exactly.
- [ ] Group equal logical positions into one ordered OR-alternative slot.
- [ ] Deduplicate alternatives only within one slot and by first encounter.
- [ ] Preserve repeated terms across distinct slots for exact matching.
- [ ] Deduplicate scoring terms across the leaf in global first-encounter order.
- [ ] Represent a zero-slot PHRASE as match-none with empty candidates and zero score.
- [ ] Require no text index for a zero-slot PHRASE.
- [ ] Support one-slot phrases, including a slot with multiple alternatives.
- [ ] Require the identity-equal canonical text index for every non-empty PHRASE.
- [ ] Preserve the contextual missing-index `IllegalStateException` naming the field.
- [ ] Treat unknown terms as valid empty postings only after canonical-index resolution.
- [ ] Require later non-empty MUST/SHOULD indexes even after an earlier match-none leaf.
- [ ] Return empty before index and filter planning only when every TEXT/PHRASE leaf is
  empty after valid analysis.

## Prepared candidates and deterministic anchor

- [ ] Resolve every alternative posting once per phrase occurrence, not per document.
- [ ] Build each slot candidate bitmap as the union of its alternative postings.
- [ ] Intersect every occupied slot candidate bitmap into a phrase safe superset.
- [ ] Allow candidate false positives before positional verification and forbid false
  negatives.
- [ ] Permit safe repeated posting/source intersection deduplication without removing
  repeated exact-match slots.
- [ ] Permit ascending-cardinality physical intersection with original slot order as
  the deterministic tie-break.
- [ ] Select the anchor using the smallest fully unioned slot candidate cardinality.
- [ ] Break equal-cardinality anchor ties by earliest phrase slot.
- [ ] Do not choose an anchor from only one alternative's document frequency.
- [ ] Retain alternatives and positions in deterministic encounter/ascending order.
- [ ] Prepare candidates, anchor, postings, IDF, document count, and average length once
  per request-level leaf.
- [ ] Rebuild none of those facts per candidate document.

## Exact positional verification

- [ ] Verify only documents in the prepared phrase candidate bitmap.
- [ ] Iterate anchor occurrences through the internal text-index bridge.
- [ ] Compute required positions with `long` intermediate arithmetic.
- [ ] Treat negative or greater-than-`Integer.MAX_VALUE` required positions as a
  non-matching anchor occurrence rather than throwing or wrapping.
- [ ] Require one alternative from every slot at its exact required position.
- [ ] Preserve exact gaps, repeated-term requirements, and phrase-at-any-base behavior.
- [ ] Support same-position OR alternatives without requiring all alternatives.
- [ ] Perform sorted primitive `contains`-style checks against Phase 2 positions.
- [ ] Do not re-analyze document text during query execution.
- [ ] Do not allocate boxed position sets/lists or materialize position arrays per doc.
- [ ] Do not add a duplicate phrase-specific positional index or occurrence store.

## Phrase scoring and recursive composition

- [ ] Use exact phrase truth only as a match gate; add no phrase/proximity bonus.
- [ ] Score distinct analyzed phrase terms once in global first-encounter order.
- [ ] Require repeated terms at every phrase slot without multiplying query weight.
- [ ] After a phrase matches, score every distinct analyzed term occurring in the
  document, not only the alternative that first proved a slot.
- [ ] When multiple distinct same-slot alternatives occur, score each exactly once.
- [ ] Use each phrase field's prepared posting, `N`, `df`, `dl`, and `avgdl`.
- [ ] Keep document length equal to emitted token count; gaps do not increase `dl`.
- [ ] Reuse the existing BM25 formula and request `Bm25Config` unchanged.
- [ ] Reuse `ScoreMatch` and track match truth independently from score positivity.
- [ ] Check every phrase-term score addition immediately in logical order.
- [ ] Preserve valid underflow as matched `+0.0` and throw for invalid arithmetic.
- [ ] Compose PHRASE correctly under MUST, SHOULD, nested BOOL, and nested BOOST.
- [ ] Preserve node-by-node checked BOOST multiplication and BOOL addition.
- [ ] Compose different TEXT/PHRASE fields using independent field-local statistics.
- [ ] Add no BM25F, DisMax, coordination, field normalization, or implicit phrase weight.

## Filters, execution, snapshot, and lifecycle

- [ ] Keep structured filters eligibility-only with zero score contribution.
- [ ] Plan filters after ranked preparation whenever any non-empty ranked leaf exists.
- [ ] Intersect only exact or safe-superset filter candidates and run the final filter
  predicate over surviving phrase candidates.
- [ ] Preserve phrase score with and without an equivalent permissive filter.
- [ ] Keep `SearchExecutor` generic over the root scoring node with no phrase branch.
- [ ] Bind every phrase plan to exactly one immutable `SearchSnapshot<T>`.
- [ ] Mix no document, posting, position, length, statistic, candidate, or filter facts
  across snapshot versions.
- [ ] Preserve score-descending then internal-document-ID-ascending result ordering.
- [ ] Keep bounded top-K retention, including matched zero-score phrases.
- [ ] Make add/update/reorder/remove/bulk publication update phrase truth correctly.
- [ ] Preserve old phrase truth in old immutable snapshots after publication.
- [ ] Support replay-correct positions for dynamically created text indexes.
- [ ] Cover mutation while dynamic build is pending, publication, and subsequent drop.
- [ ] Make a non-empty phrase fail with missing index after its canonical index is dropped.

## Focused, edge-case, and differential tests

- [ ] Cover empty, one-slot, adjacent multi-slot, reordered, missing, and unknown terms.
- [ ] Cover repeated terms with sufficient and insufficient occurrences.
- [ ] Cover initial gaps, internal gaps, phrase-at-offset, and wrong-gap rejection.
- [ ] Cover same-position alternatives A/B, neither alternative, duplicate alternative,
  and both distinct alternatives present.
- [ ] Prove the exact both-alternatives-present BM25 score and accumulation order.
- [ ] Cover zero-slot PHRASE as root, MUST, SHOULD, boosted child, and in all-empty trees.
- [ ] Cover missing canonical indexes for root/MUST/SHOULD and competing field identity.
- [ ] Cover a later missing SHOULD index after an earlier match-none MUST.
- [ ] Cover complete malformed positioned output and Analyzer invocation counts.
- [ ] Cover the same phrase object reused in independent clause occurrences.
- [ ] Cover FUZZY whole-tree preflight before Analyzer/index/position/filter work.
- [ ] Cover slot candidate union, phrase intersection, repeated-source deduplication,
  and candidate-superset safety.
- [ ] Cover anchor selection, equal-cardinality tie-break, unknown/empty candidates, and
  relative-position arithmetic boundaries.
- [ ] Cover exact phrase BM25, custom BM25, field-local statistics, equal-score order,
  matched-zero underflow, checked addition overflow, and checked BOOST overflow.
- [ ] Cover MUST/SHOULD/nested BOOL/BOOST and cross-field TEXT/PHRASE composition.
- [ ] Cover indexed/unindexed filters and final predicate verification.
- [ ] Cover add/update/reorder/remove/bulk, snapshot isolation, and concurrent publication.
- [ ] Cover dynamic index build, pending mutation replay, publication, and drop.
- [ ] Add deterministic randomized reference evaluation for match, score, and order.
- [ ] Add randomized candidate-superset assertions with explicit seeds.
- [ ] Preserve direct TEXT, Phase 4 composition, V2 `searchTopK`, and direct
  `RankedSearcher` observable behavior.
- [ ] Keep FUZZY and Explain unsupported.

## Compatibility and scope audit

- [ ] Extend the independent V3 consumer with executable exact phrase usage using its
  real canonical field.
- [ ] Keep the travel example unchanged unless repository convention makes a small
  observable phrase example preferable.
- [ ] Keep v1- and v2-style consumers unchanged and passing.
- [ ] Keep the frozen v1 source/reflection fixture passing.
- [ ] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [ ] Confirm Phase 5 adds no supported public type, method, field, or descriptor.
- [ ] Document the one additive hidden `PhrasePositionAccess` class in compatibility
  policy and Japicmp review.
- [ ] Inspect the bridge API for every prohibited position/query/plan/snapshot leak.
- [ ] Keep `SearchExecutionAccess` complete-execution-only and otherwise unchanged.
- [ ] Add no fuzzy, Explain, slop, highlighting, offset, phrase-frequency, proximity,
  synonym, advanced ranking, plan-cache, prepared-query, or pagination behavior.
- [ ] Leave bitmap representation, writer concurrency, and snapshot publication
  architecture unchanged.

## Performance evidence

- [ ] Add or select a focused exact-phrase JMH case with representative candidate
  reduction, repeated terms, gaps, and same-position alternatives where practical.
- [ ] Compile all JMH sources after adding the phrase plan and internal bridge.
- [ ] Run a focused phrase smoke and record environment, workload, and observations.
- [ ] Confirm there is no full-document scan, document reanalysis, per-document index,
  posting, IDF, slot, or candidate reconstruction.
- [ ] Confirm there is no per-document boxed position collection or unbounded result
  retention.
- [ ] Make no universal speedup claim and freeze no numeric release threshold.

## Documentation and full validation

- [ ] Add a Phase 5 performance evidence document after measurements exist.
- [ ] Update `CHANGELOG.md` only after implementation accurately describes Phase 5.
- [ ] Mark Phase 5 complete in roadmap and phase map only after every gate passes.
- [ ] Keep this contract, prompt, and checklist synchronized with implementation.
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

Phase 5 is complete only when PHRASE executes as an exact positional gate plus ordinary
distinct-term BM25 inside the existing snapshot-bound recursive plan; internal
positions remain unexposed; legacy behavior is unchanged; and every gate above passes.
Phase 6+ work is scope failure, not extra progress.
