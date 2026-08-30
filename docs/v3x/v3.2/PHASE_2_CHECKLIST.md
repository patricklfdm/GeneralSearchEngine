# V3.2 Phase 2 checklist

Status: offset-analysis implementation, local evidence, and all required local gates
are complete on an independent branch; protected PR/master acceptance remains pending.
Highlight request, result, evidence, fragment, and engine APIs remain absent.

## Accepted entry boundary

- [x] Phase 1 merged to protected `master` as the Phase 2 source commit `65ea455`.
- [x] The independent `feat/v3.2-phase2-offset-analysis` branch starts from that
  accepted merge.
- [x] Active coordinates remain `3.2.0-SNAPSHOT`; all five published compatibility
  baselines remain unchanged.
- [x] Phase 2 adds no highlighted-search overload, public highlighting model, query
  evidence capture, fragment construction, stored offset, or cloud preset.

## Contract clarification

- [x] Unicode NFKC witnesses prove that one source range can expand to several logical
  positions and that successive source ranges can monotonically overlap.
- [x] The frozen sequence rule now requires both start and end boundaries to be
  nondecreasing across later logical positions; either boundary moving backward is
  rejected.
- [x] Same-position alternatives still require exactly equal ranges.
- [x] The clarification is recorded before acceptance in the token, validation, and
  Phase 0 contract documents.

## Public offset API

- [x] `OffsetAnalyzedToken` is a public immutable four-component record with nonempty
  term, nonnegative position increment, and positive half-open UTF-16 range checks.
- [x] `OffsetAnalyzer` extends `Analyzer`, adds exactly one offset-aware abstract
  method, and supplies immutable ordinary term/position projections.
- [x] `Analyzer` remains a functional interface and `AnalyzedToken` retains its exact
  published two-component descriptor.
- [x] The public consumer fixture compiles against the complete offset family; a
  partial or descriptor-incompatible family fails closed.

## Built-in analyzer and validation

- [x] `SimpleAnalyzer` implements `OffsetAnalyzer` while retaining its direct ordinary
  analysis implementation.
- [x] Ordinary term and position output remains bit-for-bit equal to its Phase 1
  behavior and does not derive or allocate offset-token results.
- [x] Offset terms and positions are exact projections of ordinary analysis for ASCII,
  BMP, supplementary, combining, contextual-lowercase, and NFKC expansion inputs.
- [x] Every emitted range indexes the exact original Java string, is half-open, and
  never splits a surrogate pair.
- [x] Compatibility characters that produce several terms, including shared and
  monotonically overlapping source ranges, remain deterministic.
- [x] The package-private sequence validator rejects null output/elements, invalid
  first increments, out-of-bounds and split-surrogate ranges, mismatched alternatives,
  decreasing boundaries, and logical-position overflow.
- [x] Validated output is a defensive immutable copy and diagnostics identify the
  field and failing token index.

## Correctness, concurrency, and evidence

- [x] Focused offset value, interface projection, built-in Unicode, and sequence
  validator fixtures pass.
- [x] A fixed-seed 2,000-trial randomized Unicode suite proves ordinary projection
  equality, source-range safety, and sequence validity with replayable failures.
- [x] Bounded parallel invocation proves `SimpleAnalyzer` offset output is stateless
  and deterministic.
- [x] The Phase 2 JMH matrix records ordinary and explicit offset analysis across
  ASCII, BMP, supplementary, combining, and NFKC shapes.
- [x] Four directly comparable ordinary shapes remain within -4.8% to +4.9% of the
  Phase 1 local timing controls; normalized allocation is unchanged or differs by only
  24 bytes per invocation.
- [x] Combining-sequence offset cost is retained as an explicit Phase 5 optimization
  observation rather than hidden or averaged with ordinary paths.
- [x] No paid cloud run is required because index representation, retained offsets,
  workflows, and canonical metric families are unchanged.
- [x] Commands, environment, values, limitations, and canonical inheritance are
  recorded in [the Phase 2 baseline](PHASE_2_BASELINE.md).

## Required gates

- [x] The focused offset/API suite passes with 24 tests.
- [x] All 310 core tests pass with zero failures, errors, or skips.
- [x] Five-baseline artifact compatibility and strict Javadocs pass.
- [x] Reactor/processor, travel example, and V1/V2/V3 consumer gates pass.
- [x] Fresh-isolated dependency resolution and compatibility verification pass.
- [x] Version alignment, JMH smoke, diff hygiene, and highlighting-family absence pass.

## Phase 3 handoff

- [x] Phase 3 may introduce only the frozen immutable highlighted request/result family,
  one-snapshot integrated execution, and TEXT evidence/highlighting.
- [x] Canonical hits must remain bit-for-bit equal to ordinary search, and legacy
  analyzers must fail requested-field capability checks deterministically.
- [x] PHRASE/FUZZY witness reconstruction and recursive BOOL/BOOST evidence remain
  prohibited until Phase 4.
- [x] Stored offsets, sidecars, HTML output, and analyzer composition remain outside
  the accepted boundary.

Phase 2 is complete only after all required gates pass and this branch merges through a
protected PR. Phase 3 must start from that accepted merge commit on a new independent
branch.
