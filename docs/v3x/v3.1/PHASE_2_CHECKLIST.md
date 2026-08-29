# V3.1 Phase 2 checklist

Status: complete.

## Supported API and immutable model

- [x] Add `SearchQueries.phrase(TextField<T>, String, int slop)` as the only
  supported Phase 2 API addition.
- [x] Reject negative slop immediately and retain existing null validation for field
  and text.
- [x] Keep `phrase(field, text)` exactly equivalent to
  `phrase(field, text, 0)`.
- [x] Retain slop through the immutable query node, normalization, planning, and
  scoring plan without exposing internal positional representations.
- [x] Leave `minimumShouldMatch` and all later V3.1 additions out of this phase.

## Positional execution and scoring

- [x] Implement the ordered extra-gap budget with overflow-safe `long` arithmetic.
- [x] Preserve query gaps as minimum gaps; reject contraction and transposition at
  every slop value.
- [x] Require distinct ordered occurrences for repeated-term slots while treating
  same-position alternatives as one slot.
- [x] Retain the existing exact-position fast path for slop zero.
- [x] Keep candidate generation as the intersection of slot-union postings and a
  safe positional superset.
- [x] Keep phrase scoring equal to the existing distinct-term BM25 sum, independent
  of requested or consumed slop.
- [x] Report requested slop and the minimum consumed slop for matching Explain
  nodes without exposing raw positions.

## Semantic validation

- [x] Cover public validation, immutable retention, and legacy/explicit-zero
  equivalence.
- [x] Cover ordered gaps, analyzer gaps, alternatives, repeated terms, one-slot and
  zero-slot phrases, missing indexes, filters, boosts, nested BOOL queries, and
  integer position boundaries.
- [x] Add deterministic randomized differential testing against the independent
  Phase 1 phrase oracle across mutation, filtering, top-K ordering, score, candidate
  safety, and Explain equivalence.
- [x] Extend the existing Explain differential generator with sloppy phrases.

## Compatibility correction and consumers

- [x] Pin and verify the SHA-256 of the published `3.0.0` baseline before Japicmp.
- [x] Compare the candidate against the copied published artifact by file path, so
  the unchanged `3.0.0` project version cannot resolve the candidate as its own old
  baseline.
- [x] Confirm the V3 diff contains only the supported phrase overload and the narrow
  Javadoc-hidden scalar positional bridge method.
- [x] Compile and execute an independent V3-style consumer using phrase slop while
  preserving the V1 and V2 consumer builds.
- [x] Isolate consumer verification from the user's default local Maven repository.

The Phase 1 profile added a V3 Japicmp execution, but Maven could resolve its
same-version old dependency to the freshly installed candidate. Phase 2 closes that
false-pass path with a pinned published-artifact copy and checksum. A contaminated
repository now fails closed instead of silently self-comparing.

## Performance and build verification

- [x] Package the JMH benchmarks and add a focused sloppy-phrase workload.
- [x] Verify the benchmark setup asserts legacy/explicit-zero result equivalence.
- [x] Capture the short local diagnostic in
  [the Phase 2 local baseline](PHASE_2_BASELINE.md).
- [x] Core suite: 260 tests, zero failures/errors/skips.
- [x] Processor reactor: 5 tests, zero failures/errors/skips.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass using an isolated Maven
  repository and the pinned V3 artifact.
- [x] Independent V1/V2/V3 consumer compilation and execution: pass.
- [x] Strict release Javadocs and artifact packaging: pass.
- [x] JMH smoke execution: pass.

Phase 3 may now add `minimumShouldMatch` under its already frozen contract. It must
not alter the phrase semantics completed here.
