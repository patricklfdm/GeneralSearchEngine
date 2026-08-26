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

- [x] Override `explain(SearchRequest<T>, K)` only in `SnapshotSearchEngine`.
- [x] Preserve third-party `SearchEngine` default unsupported behavior and null order.
- [x] Null-check request then ID before capturing state.
- [x] Capture one `PublishedState` and resolve ID, snapshot, and document only from it.
- [x] Return `Optional.empty()` immediately for a missing business ID.
- [x] Give missing ID precedence over Analyzer, missing-index, and filter planning work.
- [x] Return `Optional.of` for every existing matching or non-matching document.
- [x] Emit unmatched canonical `+0.0` for an existing request non-match.
- [x] Make Explain independent of top-K membership and request limit.
- [x] Do not execute a complete bounded search to explain one document.

## Canonical plan and hot-path architecture

- [x] Reuse `RankedSearchInput`, `SearchPlanner`, and one snapshot-bound `SearchPlan`.
- [x] Evaluate one resolved document directly rather than using top-level candidates.
- [x] Use candidate membership only as a correctness-safe internal leaf shortcut.
- [x] Retain an explainable scoring tree for the all-ranked-leaves-empty fast path.
- [x] Preserve early return before index/filter candidate planning for that fast path.
- [x] Retain only immutable normalized/planned diagnostic facts in plan nodes.
- [x] Build no `ExplanationNode`, description, or per-document diagnostic list in planning.
- [x] Keep normal `evaluate(docId)` free of explanation allocation and string creation.
- [x] Reuse `Bm25Scorer`, `ScoreArithmetic`, phrase truth, and fuzzy selection primitives.
- [x] Add no second planner, analyzer, index resolver, scorer, or ranking formula.
- [x] Compare plan normal evaluation with Explain through package-private tests.

## Root request and structured filter

- [x] Give the request root one ranked child and an optional second filter child.
- [x] Mirror ranked match/score at the root when no filter exists.
- [x] Use `Query.matches(document)` as structured-filter semantic truth.
- [x] Keep filter nodes at score `+0.0` whether matching or not.
- [x] Require ranked and filter match when a filter exists.
- [x] Zero the failed request root while retaining ranked-child diagnostic score.
- [x] Add no recursive structured-`Query<T>` explanation hierarchy.
- [x] Describe semantic filter outcome rather than candidate membership.

## TEXT and BM25 diagnostics

- [x] Name the canonical field and show total TEXT match/score.
- [x] Retain distinct normalized terms in Analyzer first-encounter order.
- [x] Include one child for every distinct term, including absent vocabulary terms.
- [x] Make an empty analyzed TEXT an explainable unmatched zero without an index.
- [x] Record term, field, tf, df, N, dl, avgdl, k1, b, idf, and contribution.
- [x] Use the exact shared BM25 normalization and term-score arithmetic.
- [x] Sum matching term children in frozen order through checked addition.
- [x] Cover single, partial, full, repeated, unknown, empty, and custom-BM25 cases.
- [x] Manually verify representative BM25 facts and contribution values.

## PHRASE diagnostics

- [x] Name the field and exact analyzed relative-position requirement.
- [x] Reuse exact Phase 5 positional truth without exposing raw positions.
- [x] Score only a matching phrase and expose distinct-term BM25 children.
- [x] Keep phrase term children in first-encounter distinct order.
- [x] Explain repeated occurrence requirements without double-counting scoring terms.
- [x] Explain position gaps and same-position alternatives semantically.
- [x] Bound the tree by query complexity rather than document occurrence count.
- [x] Make an empty phrase explainable without requiring an index.
- [x] Cover exact, wrong-order, non-consecutive, repeated, gap, and single-slot cases.

## FUZZY diagnostics

- [x] Name field, normalized term, code-point length, and AUTO maximum edits.
- [x] Reuse Phase 6 exact-priority and deterministic best-expansion selection.
- [x] Emit exactly one selected-expansion child for a match.
- [x] Record selected term, distance, similarity, BM25, and weighted contribution.
- [x] Record selected expansion tf, df, N, dl, avgdl, k1, b, and idf.
- [x] Identify exact normalized-term priority explicitly.
- [x] Distinguish no expansion from no matching expansion without vocabulary dumping.
- [x] Make empty FUZZY explainable without requiring an index.
- [x] Keep tree size independent of total expansion count.
- [x] Cover exact, edit, transposition, best-of-many, no-expansion, and empty cases.

## BOOL, BOOST, cross-field, and ordering

- [x] Preserve MUST encounter order followed by SHOULD encounter order.
- [x] Retain duplicate clause occurrences and nested tree shape.
- [x] Explain all children for diagnostics even after a failed MUST.
- [x] Preserve MUST/SHOULD and SHOULD-only match rules exactly.
- [x] Add only matching clause scores in frozen checked order.
- [x] Keep every failed BOOL node at canonical `+0.0`.
- [x] Give BOOST one child and record its multiplier.
- [x] Reuse checked multiplication and preserve matched zero.
- [x] Cover boosted TEXT, PHRASE, FUZZY, BOOL, and nested boosts.
- [x] Report independent field-local BM25 facts for cross-field leaves.
- [x] Keep all explanation child ordering deterministic.

## Public data and hidden visibility

- [x] Preserve all `SearchExplanation` and `ExplanationNode` public descriptors.
- [x] Preserve immutable, non-null children and existing constructor validation.
- [x] Use deterministic locale-independent descriptions without defining a parser format.
- [x] Expose no internal document ID in nodes, descriptions, or returned objects.
- [x] Expose no posting, index, candidate, raw position, snapshot, or plan handle.
- [x] Add no public subtype, type enum, attributes map, BM25 getters, or renderer API.
- [x] Add exactly one Javadoc-hidden Explain method to `SearchExecutionAccess`.
- [x] Let that bridge consume but never return/retain/describe the resolved internal ID.
- [x] Add no second Phase 7 bridge or general per-document evaluation SPI.
- [x] Review the additive hidden bridge method in all Japicmp reports.
- [x] Update V3 compatibility policy with the exact unsupported bridge boundary.

## Snapshot, mutation, and dynamic-index lifecycle

- [x] Mix no ID-map, document, posting, vocabulary, statistic, filter, or plan versions.
- [x] Preserve invocation-local state during concurrent publication.
- [x] Document that later Explain does not reuse a prior search snapshot.
- [x] Reflect add, update, reorder, filter changes, and bulk publication.
- [x] Return empty after remove publication.
- [x] Cover phrase truth and fuzzy selected-expansion changes after update.
- [x] Cover dynamic TEXT/PHRASE/FUZZY index build and replay publication.
- [x] Keep pending builds invisible to the old captured state.
- [x] Cover subsequent mutations against a newly published dynamic index.
- [x] Fail existing-document Explain consistently after required index drop.
- [x] Pin no snapshot or Explain session beyond the synchronous invocation.

## Focused and randomized tests

- [x] Cover matching, non-matching, and missing business IDs through public API.
- [x] Cover matching documents outside limit 1 and limits 1/10/100 equivalence.
- [x] Cover no filter, passing/failing indexed filter, and passing/failing scan filter.
- [x] Cover ranked-match/filter-fail child and root score distinction.
- [x] Cover empty whole-tree and contextual root/MUST/SHOULD missing-index precedence.
- [x] Cover Analyzer invocation counts, malformed output, and exception propagation.
- [x] Cover matched `+0.0`, underflow, addition overflow, and boost overflow.
- [x] Add direct plan evaluation versus explanation invariant tests for every node kind.
- [x] Add deterministic randomized recursive match/score differential tests with filters.
- [x] Recursively validate node scores, match-zero rules, descriptions, and child order.
- [x] Verify child lists remain immutable and contain no internal handle text.
- [x] Preserve Phase 3 TEXT, Phase 4 composition, Phase 5 phrase, and Phase 6 fuzzy tests.
- [x] Preserve V2 `searchTopK`, direct `RankedSearcher`, and structured search behavior.

## Consumer, documentation, compatibility, and scope

- [x] Extend the independent V3 consumer with executable Explain usage.
- [x] Keep v1/v2 consumers unchanged and passing.
- [x] Add only a concise travel Explain example if it improves the existing demo.
- [x] Keep frozen v1 source/reflection fixture passing.
- [x] Pass Japicmp against 1.0.0, 2.0.0, and 2.1.0 normally and in isolation.
- [x] Confirm the concrete built-in override is the only supported descriptor addition.
- [x] Update `CHANGELOG.md` only after implementation is accurate.
- [x] Mark Phase 7 complete in roadmap/phase map only after every gate passes.
- [x] Add no automatic/result/legacy Explain API or structured-filter hierarchy.
- [x] Add no Phase 8 optimization, version conversion, signing, deployment, or release.
- [x] Add no post-V3 phrase, fuzzy, ranking, pagination, persistence, vector, or distributed work.

## Full validation

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
- [x] No artifact, isolated repository, credential, IDE file, or root Codex prompt is tracked.

Phase 7 is complete only when Explain faithfully reports the existing snapshot-bound
plan's match and score for one business document, exposes useful deterministic
diagnostics without internal handles, leaves normal search allocation-light, preserves
legacy behavior and supported descriptors, and passes every gate above. Phase 8 and
post-V3 work are scope failure, not extra progress.
