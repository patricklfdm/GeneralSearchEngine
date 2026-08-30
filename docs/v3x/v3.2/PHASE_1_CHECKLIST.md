# V3.2 Phase 1 checklist

Status: implementation foundation and local evidence are complete on an independent
branch; protected PR/master acceptance remains pending. No production offset or
highlighting implementation is present.

## Accepted entry boundary

- [x] Phase 0 merged to protected `master` as
  `9f4825976cb0c6e9c3c8862efabd9e648bc315a4`.
- [x] The independent `feat/v3.2-phase1-foundation` branch starts from that exact
  merge commit.
- [x] All active project, reactor, processor, example, and compatibility-consumer
  coordinates switch atomically from `3.1.0` to `3.2.0-SNAPSHOT`.
- [x] Published baseline coordinates and pinned artifact SHA-256 values remain
  unchanged.
- [x] No file under `src/main/java`, no public API, no search behavior, and no cloud
  workflow or preset changes in Phase 1.

## Compatibility foundation

- [x] Japicmp continues to require published `1.0.0`, `2.0.0`, `2.1.0`, pinned
  `3.0.0`, and pinned `3.1.0` independently.
- [x] A normal clean-home artifact-compat verify passes with all five baselines.
- [x] A second fresh-isolated artifact repository downloads and verifies all five
  baselines rather than inheriting local artifacts.
- [x] Local default-repository SHA mismatch fails closed; it is not silently accepted
  as a published baseline.
- [x] Version alignment verifies exact `3.2.0-SNAPSHOT` across every active module and
  consumer.

## Independent semantic oracles

- [x] The Phase 1 offset oracle validates explicit UTF-16 source ranges, same-position
  alternatives, position gaps, surrogate boundaries, and NFKC length-changing input
  without calling a production offset helper.
- [x] The phrase witness oracle exhaustively enumerates valid ordered witnesses and
  selects least slop, earliest first offset, then the subsequent offset tuple.
- [x] The fuzzy-selection oracle uses the independent full-matrix OSA reference,
  exact-match priority, score ordering, and deterministic tie resolution.
- [x] BOOL/BOOST evidence composition, deduplication, overlap-only merging, fragment
  context, fragment caps, and surrogate-safe window boundaries have independent
  fixtures.
- [x] The oracle layer resides only under `src/test` and does not depend on future
  production offset, witness, interval, or fragment implementation.

## Public API fixtures

- [x] Reflection fixtures preserve `Analyzer` as a SAM and preserve the exact two
  components of `AnalyzedToken`.
- [x] The offset API family may be wholly absent in Phase 1, but any partial or
  descriptor-incompatible introduction fails the fixture.
- [x] The highlighting API family may be wholly absent in Phase 1, but any partial or
  descriptor-incompatible introduction fails the fixture.
- [x] Once both frozen families exist, the test dynamically compiles a real Java
  consumer source fixture against their exact public descriptors.
- [x] The fixture does not add placeholder production types merely to make Phase 1
  compile.

## Evidence and validation

- [x] Ordinary SimpleAnalyzer terms/positions, positional index build/publication,
  TEXT top-K, and normal-search Explain controls are captured from the exact Phase 0
  production source.
- [x] Existing V3.1 canonical regression and ranked-family evidence is retained as
  the pre-offset memory/capacity anchor; Phase 1 spends no additional cloud budget.
- [x] The JMH smoke gate discovers and executes the new analyzer baseline plus all
  retained V3/V3.1 smoke cells.
- [x] Focused oracle and public-API fixtures pass before production implementation.
- [x] All 290 core tests pass; reactor/processor tests, travel example, compatibility
  consumers, five-baseline artifact compatibility, version alignment, and diff hygiene
  also pass.
- [x] The baseline command, environment, result, limitation, canonical inheritance,
  and reproduction boundaries are recorded in
  [the Phase 1 baseline](PHASE_1_BASELINE.md).

## Phase 2 handoff

- [x] Phase 2 may introduce only the separately frozen `OffsetAnalyzer` and
  `OffsetAnalyzedToken` family plus built-in SimpleAnalyzer offset support.
- [x] Phase 2 must keep ordinary term/position projections exactly equivalent and
  must prove that ordinary paths do not allocate offset-token results.
- [x] Highlighted requests/results, query evidence capture, and fragment construction
  remain prohibited until their ordered implementation phases.
- [x] Any change to coordinate semantics, sequence validation, public descriptors, or
  stored-offset policy requires a contract amendment before implementation.

Phase 1 is complete only after this branch passes required CI and merges to protected
`master`. Phase 2 must start from that accepted merge commit on a new independent
branch.
