# V3.1 Phase 5 checklist

Status: complete. The two accepted production changes preserve supported API,
ranked-search semantics, failure behavior, and benchmark identity.

## Evidence protocol and stopping boundary

- [x] Capture the pre-change profile from Phase 4 merge commit `aabaa0c` before any
  Phase 5 production change.
- [x] Keep the 100,000-document, one-fork, two-warmup, three-measurement JMH matrix
  fixed across the pre-change baseline and both experiments.
- [x] Treat all short WSL2 measurements as local diagnostics rather than canonical
  evidence or a release regression gate; keep raw JMH JSON and JFR output disposable
  under `target/`.
- [x] Accept each optimization separately only after its profile cause disappears and
  the frozen semantic gates pass.
- [x] Stop production optimization after the two narrow causes are removed. Remaining
  samples cross positional storage, BM25, persistent maps, top-K, and general query
  execution and do not justify broader representation changes in this phase.

## Optimization 1: bitmap intersection allocation

- [x] Replace the per-document capturing `computeIfAbsent` path in
  `ImmutableBitmapBuilder.mutableBlock` with explicit dirty-block lookup and
  first-miss installation.
- [x] Preserve bitmap contents, cardinality, copy-on-write behavior, structural reuse,
  planner behavior, phrase verification, scoring, and Explain.
- [x] Reduce normalized allocation in all eight phrase shapes by 6.80% to 29.21%
  without an allocation regression in any cell.
- [x] Confirm with after-change JFR that the profiled bitmap-builder lambda allocation
  source no longer appears.

## Optimization 2: validation diagnostics allocation

- [x] Construct indexed null-diagnostic strings in `PhrasePositionAccess.validate`
  only on their failure branches.
- [x] Preserve every validation type, message, and failure-precedence rule; freeze the
  null-slot and null-alternative messages with focused assertions.
- [x] Reduce allocation by another 37.55% to 68.21% across all eight phrase shapes.
  The cumulative reduction from the Phase 5 baseline is 52.15% to 72.69%.
- [x] Confirm with after-change JFR that validation-message `byte[]` allocation no
  longer appears and that the bitmap-builder lambda remains absent.
- [x] Make no latency claim: short-run mean changes versus the original baseline range
  from approximately -4.3% to +5.2% with wide confidence intervals.

## Correctness and repository gates

- [x] Phase 4 phrase, slop, Explain, failure-precedence, lifecycle, mutation,
  randomized differential, and concurrency oracles remain green.
- [x] Final focused optimization suite: 32 tests, zero failures/errors/skips.
- [x] Complete core suite: 274 tests, zero failures/errors/skips.
- [x] Reactor processor suite: 5 tests, zero failures/errors/skips; travel example
  builds successfully.
- [x] Independent V1-, V2-, and V3-style consumer compilation and execution: pass.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass in an isolated Maven
  repository. The V3 diff remains exactly `minimumConsumedSlop`, phrase slop factory,
  and `minimumShouldMatch` additions from Phases 2 and 3.
- [x] Strict release sources, Javadocs, and artifact packaging: pass.
- [x] JMH packaging, all eight phrase setup-time guards, and repository smoke fork:
  pass.
- [x] `git diff --check`: pass.

Phase 6 may now implement the persistent code-point fuzzy dictionary and exact
bounded OSA traversal under its separately frozen semantic and compatibility
contract.
