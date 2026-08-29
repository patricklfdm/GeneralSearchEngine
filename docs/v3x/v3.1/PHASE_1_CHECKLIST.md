# V3.1 Phase 1 checklist

Status: complete. No production ranked-search behavior changed in this phase.

## Compatibility foundation

- [x] Add the candidate-versus-`3.0.0` Japicmp execution. Phase 2 subsequently pins
  and checksums the published artifact to prevent same-version self-resolution.
- [x] Retain direct published `1.0.0`, `2.0.0`, and `2.1.0` comparisons.
- [x] Preserve the existing public-access, synthetic filtering, and binary/source
  incompatibility failure policy for every comparison.
- [x] Compile independent V1-, V2-, and V3-style consumers.
- [x] Run the core, processor, generated-source, and travel-example reactor.

## Semantic fixtures

- [x] Add a representation-free ordered extra-gap phrase reference model using
  overflow-safe `long` arithmetic.
- [x] Freeze phrase ordering, contraction, repeated-term, same-position-alternative,
  analyzer-gap, minimum-witness, one-slot, and empty-output examples.
- [x] Add a representation-free BOOL reference evaluator for default and explicit
  minimums, occurrence counting, validation, and complete score accumulation.
- [x] Exercise the existing phrase and BOOL factories through the real V3.0 execution
  and Explain pipeline.
- [x] Freeze `Analyzer` as a SAM and the two-component `AnalyzedToken` record shape.
- [x] Keep production Java and public API unchanged.

The reference classes are test-only and deliberately do not call production phrase,
BOOL-planning, or score-aggregation helpers. Phase 2 and later phases extend these
foundations into the full randomized and lifecycle matrix frozen by
[the validation contract](VALIDATION.md).

## Pre-change evidence

- [x] Build the unchanged V3.0 JMH implementation from source commit `a36183e`.
- [x] Capture representative 100,000-document phrase latency and normalized
  allocation.
- [x] Capture representative 100,000-term fuzzy latency and normalized allocation.
- [x] Record environment, commands, limitations, and results in
  [the Phase 1 local baseline](PHASE_1_BASELINE.md).
- [x] Keep this short local diagnostic distinct from the registered cloud baseline
  and from future canonical V3.1 evidence.

## Verification record

- [x] Core suite: 252 tests, zero failures/errors/skips.
- [x] Processor suite: 5 tests, zero failures/errors/skips.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass.
- [x] Independent V1/V2/V3 consumer compilation: pass.
- [x] JMH packaging and smoke execution: pass.

Phase 2 added the phrase-slop public model and execution path while preserving the
exact-phrase defaults and using the independent Phase 1 oracle rather than production
internals as its semantic reference. Its completion record is in
[the Phase 2 checklist](PHASE_2_CHECKLIST.md).
