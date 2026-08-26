# V3 Phase 7 implementation checklist

## Preparation and frozen boundary

- [x] Phase 6 is merged to `master` with every Phase 6 gate passing.
- [x] Work starts from `feat/v3-phase7-explain` at the merged Phase 6 commit.
- [x] Phase 0–6 public, analysis, storage, planning, scoring, phrase, fuzzy, lifecycle,
  compatibility, consumer, packaging, and reproducibility contracts are audited.
- [x] Explain behavior, failure precedence, tree shape, visibility, lifecycle, tests,
  compatibility, and non-goals are frozen in [EXPLAIN_EXECUTION.md](EXPLAIN_EXECUTION.md).
- [x] The root Phase 7 Codex prompt remains an untracked implementation input.

## Public behavior and failure precedence

- [ ] Override `explain(SearchRequest<T>, K)` only in `SnapshotSearchEngine`.
- [ ] Preserve third-party `SearchEngine` default unsupported behavior and null order.
- [ ] Null-check request then ID before capturing state.
- [ ] Capture one `PublishedState` and resolve ID, snapshot, and document only from it.
- [ ] Return `Optional.empty()` immediately for a missing business ID.
- [ ] Give missing ID precedence over Analyzer, missing-index, and filter planning work.
- [ ] Return `Optional.of` for every existing matching or non-matching document.
- [ ] Emit unmatched canonical `+0.0` for an existing request non-match.
- [ ] Make Explain independent of top-K membership and request limit.
- [ ] Do not execute a complete bounded search to explain one document.

## Canonical plan and hot-path architecture

- [ ] Reuse `RankedSearchInput`, `SearchPlanner`, and one snapshot-bound `SearchPlan`.
- [ ] Evaluate one resolved document directly rather than using top-level candidates.
- [ ] Use candidate membership only as a correctness-safe internal leaf shortcut.
- [ ] Retain an explainable scoring tree for the all-ranked-leaves-empty fast path.
- [ ] Preserve early return before index/filter candidate planning for that fast path.
- [ ] Retain only immutable normalized/planned diagnostic facts in plan nodes.
- [ ] Build no `ExplanationNode`, description, or per-document diagnostic list in planning.
- [ ] Keep normal `evaluate(docId)` free of explanation allocation and string creation.
- [ ] Reuse `Bm25Scorer`, `ScoreArithmetic`, phrase truth, and fuzzy selection primitives.
- [ ] Add no second planner, analyzer, index resolver, scorer, or ranking formula.
- [ ] Compare plan normal evaluation with Explain through package-private tests.

## Root request and structured filter

- [ ] Give the request root one ranked child and an optional second filter child.
- [ ] Mirror ranked match/score at the root when no filter exists.
- [ ] Use `Query.matches(document)` as structured-filter semantic truth.
- [ ] Keep filter nodes at score `+0.0` whether matching or not.
- [ ] Require ranked and filter match when a filter exists.
- [ ] Zero the failed request root while retaining ranked-child diagnostic score.
- [ ] Add no recursive structured-`Query<T>` explanation hierarchy.
- [ ] Describe semantic filter outcome rather than candidate membership.

## TEXT and BM25 diagnostics

- [ ] Name the canonical field and show total TEXT match/score.
- [ ] Retain distinct normalized terms in Analyzer first-encounter order.
- [ ] Include one child for every distinct term, including absent vocabulary terms.
- [ ] Make an empty analyzed TEXT an explainable unmatched zero without an index.
- [ ] Record term, field, tf, df, N, dl, avgdl, k1, b, idf, and contribution.
- [ ] Use the exact shared BM25 normalization and term-score arithmetic.
- [ ] Sum matching term children in frozen order through checked addition.
- [ ] Cover single, partial, full, repeated, unknown, empty, and custom-BM25 cases.
- [ ] Manually verify representative BM25 facts and contribution values.

## PHRASE diagnostics

- [ ] Name the field and exact analyzed relative-position requirement.
- [ ] Reuse exact Phase 5 positional truth without exposing raw positions.
- [ ] Score only a matching phrase and expose distinct-term BM25 children.
- [ ] Keep phrase term children in first-encounter distinct order.
- [ ] Explain repeated occurrence requirements without double-counting scoring terms.
- [ ] Explain position gaps and same-position alternatives semantically.
- [ ] Bound the tree by query complexity rather than document occurrence count.
- [ ] Make an empty phrase explainable without requiring an index.
- [ ] Cover exact, wrong-order, non-consecutive, repeated, gap, and single-slot cases.

## FUZZY diagnostics

- [ ] Name field, normalized term, code-point length, and AUTO maximum edits.
- [ ] Reuse Phase 6 exact-priority and deterministic best-expansion selection.
- [ ] Emit exactly one selected-expansion child for a match.
- [ ] Record selected term, distance, similarity, BM25, and weighted contribution.
- [ ] Record selected expansion tf, df, N, dl, avgdl, k1, b, and idf.
- [ ] Identify exact normalized-term priority explicitly.
- [ ] Distinguish no expansion from no matching expansion without vocabulary dumping.
- [ ] Make empty FUZZY explainable without requiring an index.
- [ ] Keep tree size independent of total expansion count.
- [ ] Cover exact, edit, transposition, best-of-many, no-expansion, and empty cases.

## BOOL, BOOST, cross-field, and ordering

- [ ] Preserve MUST encounter order followed by SHOULD encounter order.
- [ ] Retain duplicate clause occurrences and nested tree shape.
- [ ] Explain all children for diagnostics even after a failed MUST.
- [ ] Preserve MUST/SHOULD and SHOULD-only match rules exactly.
- [ ] Add only matching clause scores in frozen checked order.
- [ ] Keep every failed BOOL node at canonical `+0.0`.
- [ ] Give BOOST one child and record its multiplier.
- [ ] Reuse checked multiplication and preserve matched zero.
- [ ] Cover boosted TEXT, PHRASE, FUZZY, BOOL, and nested boosts.
- [ ] Report independent field-local BM25 facts for cross-field leaves.
- [ ] Keep all explanation child ordering deterministic.

## Public data and hidden visibility

- [ ] Preserve all `SearchExplanation` and `ExplanationNode` public descriptors.
- [ ] Preserve immutable, non-null children and existing constructor validation.
- [ ] Use deterministic locale-independent descriptions without defining a parser format.
- [ ] Expose no internal document ID in nodes, descriptions, or returned objects.
- [ ] Expose no posting, index, candidate, raw position, snapshot, or plan handle.
- [ ] Add no public subtype, type enum, attributes map, BM25 getters, or renderer API.
- [ ] Add exactly one Javadoc-hidden Explain method to `SearchExecutionAccess`.
- [ ] Let that bridge consume but never return/retain/describe the resolved internal ID.
- [ ] Add no second Phase 7 bridge or general per-document evaluation SPI.
- [ ] Review the additive hidden bridge method in all Japicmp reports.
- [ ] Update V3 compatibility policy with the exact unsupported bridge boundary.

## Snapshot, mutation, and dynamic-index lifecycle

- [ ] Mix no ID-map, document, posting, vocabulary, statistic, filter, or plan versions.
- [ ] Preserve invocation-local state during concurrent publication.
- [ ] Document that later Explain does not reuse a prior search snapshot.
- [ ] Reflect add, update, reorder, filter changes, and bulk publication.
- [ ] Return empty after remove publication.
- [ ] Cover phrase truth and fuzzy selected-expansion changes after update.
- [ ] Cover dynamic TEXT/PHRASE/FUZZY index build and replay publication.
- [ ] Keep pending builds invisible to the old captured state.
- [ ] Cover subsequent mutations against a newly published dynamic index.
- [ ] Fail existing-document Explain consistently after required index drop.
- [ ] Pin no snapshot or Explain session beyond the synchronous invocation.

## Focused and randomized tests

- [ ] Cover matching, non-matching, and missing business IDs through public API.
- [ ] Cover matching documents outside limit 1 and limits 1/10/100 equivalence.
- [ ] Cover no filter, passing/failing indexed filter, and passing/failing scan filter.
- [ ] Cover ranked-match/filter-fail child and root score distinction.
- [ ] Cover empty whole-tree and contextual root/MUST/SHOULD missing-index precedence.
- [ ] Cover Analyzer invocation counts, malformed output, and exception propagation.
- [ ] Cover matched `+0.0`, underflow, addition overflow, and boost overflow.
- [ ] Add direct plan evaluation versus explanation invariant tests for every node kind.
- [ ] Add deterministic randomized recursive match/score differential tests with filters.
- [ ] Recursively validate node scores, match-zero rules, descriptions, and child order.
- [ ] Verify child lists remain immutable and contain no internal handle text.
- [ ] Preserve Phase 3 TEXT, Phase 4 composition, Phase 5 phrase, and Phase 6 fuzzy tests.
- [ ] Preserve V2 `searchTopK`, direct `RankedSearcher`, and structured search behavior.

## Consumer, documentation, compatibility, and scope

- [ ] Extend the independent V3 consumer with executable Explain usage.
- [ ] Keep v1/v2 consumers unchanged and passing.
- [ ] Add only a concise travel Explain example if it improves the existing demo.
- [ ] Keep frozen v1 source/reflection fixture passing.
- [ ] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 normally and in isolation.
- [ ] Confirm no supported public descriptor is added or changed.
- [ ] Update `CHANGELOG.md` only after implementation is accurate.
- [ ] Mark Phase 7 complete in roadmap/phase map only after every gate passes.
- [ ] Add no automatic/result/legacy Explain API or structured-filter hierarchy.
- [ ] Add no Phase 8 optimization, version conversion, signing, deployment, or release.
- [ ] Add no post-V3 phrase, fuzzy, ranking, pagination, persistence, vector, or distributed work.

## Full validation

- [ ] `git diff --check` passes.
- [ ] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [ ] `./mvnw -f reactor/pom.xml clean test` passes.
- [ ] `scripts/run-travel-example.sh` passes.
- [ ] `./mvnw clean -Papi-compat test` passes.
- [ ] `./mvnw clean -Partifact-compat verify` passes normally.
- [ ] The artifact-compat command passes with an isolated Maven repository.
- [ ] `scripts/verify-consumer-projects.sh` passes.
- [ ] Strict core and processor Javadocs pass.
- [ ] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [ ] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [ ] `scripts/verify-reproducible-build.sh` passes.
- [ ] No artifact, isolated repository, credential, IDE file, or root Codex prompt is tracked.

Phase 7 is complete only when Explain faithfully reports the existing snapshot-bound
plan's match and score for one business document, exposes useful deterministic
diagnostics without internal handles, leaves normal search allocation-light, preserves
legacy behavior and supported descriptors, and passes every gate above. Phase 8 and
post-V3 work are scope failure, not extra progress.
