# V3.4 Phase 1 checklist

Status: complete locally on `feat/v3.4-phase1-foundation` and pending protected
review. Phase 1 introduces no production source, public API, hardening workload,
cloud identity implementation, workflow mutation, paid run, or baseline registration.

## Entry boundary

- [x] Phase 0 merged through PR #67 as protected-master commit
  `5d1d108`.
- [x] The independent Phase 1 branch starts from that exact merge commit.
- [x] Exact-commit protected-master CI was required before branch creation; the durable
  run identifier remains to be attached during protected review.
- [x] Published `3.3.0` artifacts, signed tag, release, deployment, and every earlier
  baseline remain immutable.
- [x] All seven active core, processor, reactor, example, and consumer coordinates
  switch atomically from `3.3.0` to `3.4.0-SNAPSHOT`.

## Seven-baseline compatibility foundation

- [x] Japicmp compares the candidate independently with published `1.0.0`, `2.0.0`,
  `2.1.0`, pinned `3.0.0`, pinned `3.1.0`, pinned `3.2.0`, and pinned `3.3.0`.
- [x] Published `3.3.0` is copied from Maven Central and must match SHA-256
  `18fb6439be074b39e5f22e2b01fba327ee919a4997e6429551481ef7fb8754f4`.
- [x] A fresh isolated Maven repository downloads and verifies all seven baselines.
- [x] The normal local compatibility gate passes or fails closed on a polluted
  same-coordinate artifact; it never silently substitutes that artifact.
- [x] Exact `3.4.0-SNAPSHOT` alignment and all V1/V2/V3 consumer projects pass.

## Zero-addition public fixture

- [x] `V34PublicApiContractTest` freezes the three V3 search request entry points and
  rejects representative V3.4 hardening façades.
- [x] A real third-party fixture compiles ordinary ranked, highlighted, exact-total,
  and continuation-capable page calls using only the published V3.3 surface.
- [x] Existing V1, V3.2, and V3.3 reflection/source fixtures remain active and retain
  their exact descriptor, builder, result, exception, and default-method contracts.
- [x] No V3.4 production type or placeholder exists merely to satisfy a fixture.

## Exact-V3.3 semantic reference

- [x] The Phase 1 fixture freezes ordinary/page/highlight hit equivalence, canonical
  dense-tie order, exact-total/default-total behavior, and cursor emission.
- [x] Add, update, and remove completion is followed by a deterministic current-
  snapshot oracle and an accepting single-writer state.
- [x] Reference expected IDs and ordered checksums are primitive-only test logic and
  do not call production search, page, highlight, or mutation helpers.
- [x] Existing V3.3 cursor ownership, request identity, snapshot invalidation,
  continuation, and retention oracles remain mandatory.

## Pre-change evidence

- [x] `V34FinalHardeningBaselineBenchmark` measures only existing V3.3 ordinary,
  highlighted, default-page, and exact-page read paths.
- [x] Sparse and dense-tie corpora plus `topK=1/10/100` are explicit parameters.
- [x] Trial setup checks hit counts and bit-for-bit ordinary/highlight/page parity
  before measurement; every method returns a deterministic consumed checksum.
- [x] The bounded JMH smoke runs one ordinary dense-tie cell and one highlighted
  sparse cell.
- [x] Reviewed local pre-change measurements and the exact environment are recorded
  in `PHASE_1_BASELINE.md`.

## Local validation

- [x] Focused V3.4 fixtures pass.
- [x] Core and reactor test suites pass.
- [x] JMH smoke passes, including the two V3.4 cells.
- [x] Consumer, version-alignment, artifact-compatibility, Markdown, and diff-hygiene
  gates pass.
- [x] `src/main/java`, cloud scripts/workflows/presets, and baseline registries are
  unchanged.

## Phase 2 entry

- [ ] Merge this branch through protected review.
- [ ] Require exact-merge protected-master CI success.
- [ ] Create a new Phase 2 branch from that exact merge.
- [ ] Implement only deterministic cold-process/index-build, extreme-corpus, and
  bounded heap diagnostic surfaces contracted by Phase 0.
- [ ] Do not implement burst, long-run, `final-v34`, paid cloud, or release work in
  Phase 2.

Unchecked validation and protected-merge items are required before Phase 1 acceptance.
No Phase 1 evidence is a release claim or a cloud-family member.
