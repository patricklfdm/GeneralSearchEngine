# V3 Phase 6 implementation checklist

## Preparation and frozen boundary

- [x] Phase 5 is merged to `master` with every Phase 5 gate passing.
- [x] Work starts from `feat/v3-phase6-fuzzy` at the merged Phase 5 commit.
- [x] Phase 0 fuzzy semantics and Phase 1–5 analysis, storage, pipeline, composition,
  phrase, lifecycle, compatibility, consumer, and release behavior are audited.
- [x] Visibility, validation, traversal, expansion, OSA, scoring, snapshot, lifecycle,
  compatibility, performance, and non-goals are frozen in
  [FUZZY_SEARCH.md](FUZZY_SEARCH.md).
- [x] The root Phase 6 Codex prompt remains an untracked implementation input.

## Representation and visibility

- [x] Add an immutable package-private normalized FUZZY node.
- [x] Add a package-private `FuzzyPlan` under the recursive scoring-node contract.
- [x] Add package-private fuzzy expansion values and `FuzzyTermExpander` abstraction.
- [x] Implement the initial bounded vocabulary-scan expander without another index.
- [x] Add only the frozen Javadoc-hidden `FuzzyVocabularyAccess` bridge.
- [x] Make the bridge final, non-instantiable, stateless, synchronous, and unsupported.
- [x] Let the bridge visit normalized terms only; expose no postings, maps, arrays,
  collections, iterators, streams, snapshots, plans, scores, or internal document IDs.
- [x] Retain no callback or snapshot and add no method to supported index/query APIs.
- [x] Add no reflection decoder, duplicate vocabulary, or second Phase 6 bridge.
- [x] Keep every fuzzy plan, expansion, distance, candidate, and selected term internal.

## Analysis and failure precedence

- [x] Accept TEXT, PHRASE, FUZZY, BOOL, and BOOST in whole-tree preflight.
- [x] Perform no Analyzer, index, vocabulary, distance, or filter work during preflight.
- [x] Analyze every FUZZY occurrence exactly once through positioned analysis.
- [x] Validate the complete positioned sequence before deciding fuzzy cardinality.
- [x] Preserve non-null, increment, and checked logical-position validation.
- [x] Propagate Analyzer exceptions unchanged and contextualize contract failures.
- [x] Count emitted token occurrences, not distinct terms or occupied positions.
- [x] Map zero tokens to match-none without requiring an index or scanning vocabulary.
- [x] Accept exactly one emitted token and reject two or more clearly.
- [x] Reject repeated equal tokens and same-position alternatives as multi-token input.
- [x] Preserve independent Analyzer/expansion work for reused query occurrences.
- [x] Preserve MUST-then-SHOULD depth-first logical traversal.
- [x] Compile later occurrences after earlier empty or empty-candidate leaves.
- [x] Return before index/filter planning only when every ranked leaf is empty.
- [x] Resolve the identity-equal canonical index for every non-empty fuzzy leaf.
- [x] Preserve contextual root/MUST/SHOULD missing-index failures.
- [x] Plan filters after non-empty ranked preparation even when candidates are empty.

## Unicode AUTO and bounded OSA

- [x] Compute semantic lengths from Unicode code points, never UTF-16 code units.
- [x] Use AUTO 0 edits for lengths 1–2, 1 edit for 3–5, and 2 edits for 6+.
- [x] Cap every AUTO query at two edits with no public or hidden override.
- [x] Implement insertion, deletion, substitution, and adjacent transposition at cost 1.
- [x] Implement Optimal String Alignment, not unrestricted Damerau or Levenshtein.
- [x] Operate on code-point arrays and support supplementary characters.
- [x] Reject length differences greater than the bound before dynamic programming.
- [x] Return exact in-bound distance and one out-of-range sentinel.
- [x] Use bounded primitive work arrays and only correctness-safe early exits.
- [x] Add no third-party fuzzy dependency or boxed full matrix in production.
- [x] Differential-test bounds 0/1/2 against a full trusted OSA reference.
- [x] Cover exact, threshold, threshold-plus-one, multi-edit, and transposition-heavy pairs.

## Expansion and candidates

- [x] Scan the canonical immutable snapshot vocabulary once per non-empty occurrence.
- [x] Permit an exact-lookup shortcut for bound zero with identical semantics.
- [x] Include every and only vocabulary term whose OSA distance is within AUTO.
- [x] Include an existing exact normalized query term at distance zero.
- [x] Deduplicate identical normalized vocabulary terms naturally/exactly once.
- [x] Add no expansion truncation, DF cutoff, prefix heuristic, or approximate match.
- [x] Sort by distance, then numeric Unicode code-point lexicographic order.
- [x] Do not rely on AVL UTF-16 traversal order for the frozen ordering.
- [x] Prepare term, posting, distance, lengths, similarity, IDF, N, and avgdl once.
- [x] Union every expansion posting into an exact fuzzy candidate bitmap.
- [x] Return empty candidates without error when there are no expansions.
- [x] Perform no per-document analysis, term enumeration, edit distance, or preparation.
- [x] Differential-test production expansion sets/order against brute-force reference.
- [x] Use explicit deterministic seeds and include supplementary-code-point ordering.

## Scoring and recursive composition

- [x] Use exact-term BM25 exclusively when the exact query term occurs in a document.
- [x] Preserve exact priority even when another weighted expansion is larger.
- [x] Preserve exact priority when exact BM25 validly underflows to matched zero.
- [x] Otherwise compute expansion-specific BM25 multiplied by frozen similarity.
- [x] Use floating-point `1 - distance / max(queryLength, termLength)`.
- [x] Use expansion-specific TF/DF and field-local N/dl/avgdl with request BM25 config.
- [x] Select the maximum weighted matching expansion and never sum expansions.
- [x] Evaluate expansions in frozen order and replace only on strictly greater score.
- [x] Resolve equal weighted scores by lower distance then code-point lexical term.
- [x] Keep selected expansion internal while allowing a package-private test hook.
- [x] Check BM25, similarity, multiplication, BOOL addition, and BOOST arithmetic.
- [x] Preserve valid underflow as matched canonical `+0.0`.
- [x] Track match truth independently from score positivity.
- [x] Compose FUZZY under MUST, SHOULD, nested BOOL, and nested BOOST unchanged.
- [x] Compose fuzzy with TEXT/PHRASE and across independent fields.
- [x] Keep structured filters eligibility-only with unchanged surviving scores.
- [x] Preserve score-descending then internal-document-ID-ascending bounded top-K.

## Snapshot and lifecycle

- [x] Bind each fuzzy plan to exactly one immutable `SearchSnapshot`.
- [x] Mix no vocabulary, posting, statistic, candidate, filter, or document versions.
- [x] Preserve old fuzzy truth/scores in old snapshots after publication.
- [x] Cover add, update, remove, reorder, and bulk add/update/remove publication.
- [x] Cover typo-like to exact-term updates and their exact-priority ranking change.
- [x] Cover concurrent publication during query analysis/execution.
- [x] Cover dynamic text-index build over existing documents.
- [x] Cover pending mutations, replay, publication, subsequent mutations, and drop.
- [x] Fail a later non-empty fuzzy request after its canonical index is dropped.

## Focused and differential tests

- [x] Cover zero, one, repeated, same-position, and multiple analyzed tokens.
- [x] Cover complete malformed positioned output and Analyzer invocation counts.
- [x] Cover AUTO lengths 1, 2, 3, 5, 6, long, and supplementary-code-point cases.
- [x] Cover controlled exact expansion sets, exclusions, empty vocabulary, and no match.
- [x] Cover exact-term priority, max-not-sum, deterministic tie, and similarity formula.
- [x] Cover default/custom BM25, expansion TF/DF, equal order, zero, and overflow.
- [x] Cover fuzzy root/MUST/SHOULD/nested/boosted composition with TEXT and PHRASE.
- [x] Cover two fields with different field-local corpus statistics.
- [x] Cover indexed, unindexed, and boolean structured filters.
- [x] Cover root/MUST/SHOULD missing canonical indexes and competing field identity.
- [x] Cover later failures after an earlier empty or no-expansion leaf.
- [x] Cover exact candidate union and candidate equality/superset assertions.
- [x] Add randomized bounded-distance differential tests.
- [x] Add randomized expansion-set/order differential tests.
- [x] Add recursive end-to-end match/score/order differential tests across mutations.
- [x] Preserve direct TEXT, exact PHRASE, BOOL/BOOST, V2 `searchTopK`, and direct
  `RankedSearcher` behavior.
- [x] Keep Explain unsupported.

## Consumer, compatibility, performance, and scope

- [x] Extend the independent V3 consumer with executable single-term fuzzy usage.
- [x] Keep v1/v2 consumers unchanged and passing.
- [x] Keep the travel example unchanged unless a small fuzzy example is preferable.
- [x] Keep the frozen v1 source/reflection fixture passing.
- [x] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 normally and in isolation.
- [x] Confirm no supported public descriptor is added or changed.
- [x] Review the one hidden vocabulary bridge and update compatibility policy.
- [x] Keep existing execution/position bridges otherwise unchanged.
- [x] Add no multi-token automatic fuzzy, fuzzy phrase, suggestions, or correction.
- [x] Add no public fuzzy options, expansion cap, trie, BK-tree, automaton, or n-gram index.
- [x] Add no Explain, phrase slop, highlighting, stemming, synonym, ranking, cache,
  pagination, persistence, vector, distributed, or unrelated behavior.
- [x] Add focused JMH planning/execution cases at multiple vocabulary sizes.
- [x] Include one composed fuzzy workload and compile all JMH sources.
- [x] Record environment, workload, commands, observations, and limitations.
- [x] Make no universal speedup claim or numeric release threshold.

## Documentation and full validation

- [x] Add Phase 6 performance evidence after measurements exist.
- [x] Update `CHANGELOG.md` only after implementation is accurate.
- [x] Mark Phase 6 complete in roadmap and phase map only after every gate passes.
- [x] Keep contract, prompt, checklist, implementation, and compatibility policy aligned.
- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes.
- [x] `scripts/run-travel-example.sh` passes.
- [x] `./mvnw clean -Papi-compat test` passes.
- [x] `./mvnw clean -Partifact-compat verify` passes normally.
- [x] The artifact-compat command passes with an isolated Maven repository.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] Strict core and processor Javadocs pass.
- [x] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] `./mvnw -Pjmh -DskipTests package` passes.
- [x] No artifact, isolated repository, credential, IDE file, benchmark output, or root
  Codex prompt is tracked.

Phase 6 is complete only when FUZZY executes as one analyzed-term, exact-priority,
best-expansion ranked leaf inside the existing snapshot-bound recursive plan; the
vocabulary remains internally encapsulated; legacy behavior is unchanged; and every
gate above passes. Phase 7+ work is scope failure, not extra progress.
