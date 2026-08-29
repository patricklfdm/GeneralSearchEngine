# V3.1 Phase 3 checklist

Status: complete.

## Supported API and immutable model

- [x] Add `BoolBuilder.minimumShouldMatch(int)` as the only supported Phase 3 API
  addition.
- [x] Reject negative values immediately while retaining the builder's previous
  valid value.
- [x] Validate the final BOOL shape at `build()`: the explicit minimum cannot exceed
  the declared SHOULD occurrence count, and explicit zero requires a MUST occurrence.
- [x] Preserve the existing empty-BOOL failure and unset V3.0 defaults.
- [x] Freeze each built query independently from later builder changes.
- [x] Retain the optional explicit value in the immutable query node and resolve one
  effective integer during normalization.

## Candidate planning and execution

- [x] Keep MUST candidates as a cardinality-ordered intersection.
- [x] Leave SHOULD candidates out of eligibility when the effective minimum is zero.
- [x] Build a safe threshold bitmap for positive minima, counting duplicate SHOULD
  occurrences independently.
- [x] Keep final truth in logical child evaluation so positional or fuzzy candidate
  supersets cannot become matches.
- [x] Require all MUST matches and the effective number of SHOULD occurrence matches.
- [x] Score every matching SHOULD child in encounter order after the MUST scores,
  even after the threshold has been reached.
- [x] Count matched zero-score children and never count zero-term leaves.
- [x] Keep nested BOOL thresholds independent and BOOST/filter semantics unchanged.
- [x] Report the effective minimum and matched SHOULD occurrence count in Explain
  while preserving ordered child diagnostics and normal-search truth/score.

## Semantic and compatibility validation

- [x] Cover unset and explicit defaults, zero, one, intermediate and all thresholds.
- [x] Cover negative, above-count, empty, duplicate, same-child MUST/SHOULD, zero-term,
  matched-zero-score, nested, phrase, fuzzy, boost, filter and Explain cases.
- [x] Extend the recursive randomized differential oracle with optional explicit
  minima and compare per-document match, score, candidate safety, filter, Explain,
  top-K order and top-K score.
- [x] Extend randomized Explain trees with valid explicit minima.
- [x] Confirm the public descriptor without exposing query nodes, normalized nodes,
  plans, candidates or matched-count carriers.
- [x] Extend the independent V3-style consumer; leave V1 and V2 consumer sources
  unchanged.
- [x] Add a focused `minimumShouldMatch` JMH workload with setup-time result guards.

## Repository gates

- [x] Core suite: 264 tests, zero failures/errors/skips.
- [x] Processor reactor: 5 tests, zero failures/errors/skips.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass.
- [x] Independent V1/V2/V3 consumer compilation and execution: pass.
- [x] Strict release Javadocs and artifact packaging: pass.
- [x] JMH packaging, repository smoke and focused Phase 3 smoke execution: pass.
- [x] `git diff --check`: pass.

Phase 4 may now broaden semantic, lifecycle, mutation and concurrency hardening
without adding another public ranked-query feature.
