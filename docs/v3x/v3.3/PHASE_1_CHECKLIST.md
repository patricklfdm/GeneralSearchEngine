# V3.3 Phase 1 checklist

Status: accepted on protected `master` through PR #60 at
`750691eb4bc070e83f76dab7e84e01f1f6fa4a6a`.
Phase 1 introduces no production page, cursor, total-hit, or search behavior.

## Accepted entry boundary

- [x] Phase 0 merged to protected `master` as
  `72f94c063d44fe5d758976e58ae30ab9f24b5439` through PR #59.
- [x] The independent Phase 1 branch starts from that exact merge commit.
- [x] All active core, reactor, processor, example, and compatibility-consumer
  coordinates switch atomically from `3.2.0` to `3.3.0-SNAPSHOT`.
- [x] Published baseline coordinates and pinned V3.0/V3.1/V3.2 SHA-256 identities
  remain unchanged.
- [x] No file under `src/main/java`, no supported API, no search behavior, no cloud
  preset, and no workflow changes in Phase 1.
- [x] Exact-commit Phase 0 protected-master `CI / Required` passes in
  [run 33355405253](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33355405253).

## Six-baseline compatibility foundation

- [x] Japicmp independently compares the candidate with published `1.0.0`, `2.0.0`,
  `2.1.0`, pinned `3.0.0`, pinned `3.1.0`, and pinned `3.2.0`.
- [x] Published `3.2.0` is copied from Maven Central and must match frozen SHA-256
  `8cf029b43bdd57ce93c06d71e007f1404c2d1c02c4d4dc6779461dabcd051c1c`.
- [x] A fresh isolated Maven repository downloads and verifies all six baselines.
- [x] The pre-existing polluted default local repository fails closed on its
  mismatched same-coordinate V3.0 artifact rather than being silently accepted.
- [x] Exact `3.3.0-SNAPSHOT` version alignment passes across every active module and
  independent consumer.
- [x] V1-style, V2-style, and V3-style consumer projects compile without source
  changes.

## Public API fixture

- [x] Existing `SearchRequest`, `SearchResult`, and `SearchHit` page-free descriptors
  are frozen alongside the retained V1 and V3.2 fixtures.
- [x] `SearchAfterCursor`, `TotalHitsMode`, `SearchPageRequest`, `SearchPageResult`,
  `SearchCursorException`, and the engine overload may be wholly absent in Phase 1.
- [x] Any partial appearance of that family fails immediately.
- [x] Once present, reflection freezes the exact public/final types, zero-method cursor,
  enum constants, builders, factories, accessors, exception reasons, and default
  engine method.
- [x] A real third-party consumer fixture compiles only after the complete family is
  present and exercises both request paths and all four result factories.
- [x] No placeholder production type exists merely to make the future fixture compile.

## Independent semantic oracles

- [x] The reference order is score descending by `Double.compare`, then hidden
  document ID ascending, and includes dense equal-score fixtures.
- [x] Independent page slicing excludes the anchor, applies the limit, emits a cursor
  only when a later match exists, and walks every match without gaps or duplicates.
- [x] Exact totals count full query/filter matches before cursor and limit and remain
  identical across pages; disabled totals remain absent without changing hits.
- [x] Unsupported, different-engine, different-request, and stale-snapshot rejection
  precedence is frozen independently of production exception types.
- [x] Successful publication advances the reference snapshot version; failed or
  cancelled non-publication leaves the cursor valid.
- [x] The retention oracle permits only an owner token and exact request reference;
  score bits, snapshot version, and document ID remain primitive cursor state.
- [x] The entire oracle resides under `src/test` and calls no future production page or
  cursor helper.

## Evidence and local validation

- [x] `V33PaginationBaselineBenchmark` captures ordinary and filtered ranked search
  for sparse and dense equal-score corpora before page execution exists.
- [x] Existing ordinary/highlighted TEXT cells are rerun as the V3.2 regression anchor.
- [x] Raw JMH JSON remains disposable under `target/`; reviewed commands, environment,
  means, allocations, and limitations are recorded in
  [the Phase 1 baseline](PHASE_1_BASELINE.md).
- [x] JMH smoke discovers and runs one bounded V3.3 baseline cell plus all retained
  V3.1/V3.2 smoke cells.
- [x] All 351 core tests pass; reactor core, five processor tests, travel example,
  version alignment, independent consumers, and fresh-isolated six-baseline
  compatibility pass.
- [x] Phase 1 uses no paid cloud run and does not mutate either frozen cloud family.

## Phase 2 handoff

- [x] Phase 2 may add only the frozen public page value family, default engine
  capability, built-in first-page execution, and disabled/exact total-hit behavior.
- [x] First-page disabled results must remain bit-for-bit ordinary ranked results on a
  controlled unchanged snapshot.
- [x] Phase 2 must not introduce built-in continuation, cursor ownership validation,
  snapshot pinning, highlighted pagination, timeout/cancellation API, or prepared
  queries.
- [x] Any descriptor, total meaning, evaluation-pass, lifecycle, or ordinary-path
  change requires a contract amendment before production implementation.

Phase 1 is accepted. Exact-commit protected-master `CI / Required` passed in
[run 33357515013](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33357515013).
Phase 2 begins from that accepted merge on a separate branch.
