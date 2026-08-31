# V3.3 Phase 2 checklist

Status: accepted on protected `master` through PR #61 at
`e444d40bd265c6ca855d788b75b25623ec892b50`.

Phase 2 deliberately stops before built-in cursor creation or continuation. It exposes
the complete frozen public family now so Phase 3 can add only a private cursor and
continuation execution rather than changing application descriptors.

## Accepted entry boundary

- [x] Phase 1 is accepted on protected `master` through PR #60 at
  `750691eb4bc070e83f76dab7e84e01f1f6fa4a6a`.
- [x] Exact-commit protected-master `CI / Required` passes in
  [run 33357515013](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33357515013).
- [x] The independent Phase 2 branch starts from that exact merge commit.
- [x] Coordinates remain `3.3.0-SNAPSHOT`; no cloud preset, workflow, release, or
  published-baseline identity changes.

## Frozen public page family

- [x] `SearchAfterCursor` is a public zero-method marker with no exposed built-in
  implementation.
- [x] `TotalHitsMode` contains exactly `DISABLED` and `EXACT`.
- [x] Final immutable `SearchPageRequest` wraps one exact `SearchRequest`, defaults to
  no cursor and disabled totals, and snapshots reusable builder state.
- [x] Final immutable `SearchPageResult` copies its non-null ordered hits and exposes
  exactly the four frozen disabled/exact and final/continuable factories.
- [x] Exact totals are present, non-negative `long` values; disabled totals are absent
  rather than represented by a sentinel.
- [x] Final `SearchCursorException` exposes only the frozen reason enum and message.
- [x] `SearchEngine.search(SearchPageRequest)` is an additive default capability:
  third-party engines compile unchanged and reject non-null page requests by default.
- [x] Reflection and a real compiled consumer freeze the complete descriptor family;
  the Phase 1 partial-appearance fail-closed fixture is now active.

## Built-in first-page execution

- [x] `SnapshotSearchEngine` admits the read, rejects `CLOSED`, captures exactly one
  immutable snapshot, then performs page planning and execution from that snapshot.
- [x] A request admitted before close finishes entirely from its captured snapshot;
  mutation after capture cannot leak a mixed state into hits or exact totals.
- [x] No-cursor `DISABLED` hits equal ordinary ranked hits in document identity, raw
  score bits, ordering, and cardinality.
- [x] Deterministic matrices cover no match, fewer/exactly/more-than-limit shapes;
  limits 1/2/10/100; TEXT, exact/sloppy PHRASE, FUZZY, nested BOOL/BOOST; filters; and
  default/non-default BM25.
- [x] Open-engine planning failures preserve ordinary exception type and message.
- [x] At the Phase 2 boundary, the built-in engine emitted no cursor and every supplied
  cursor failed after lifecycle admission as `UNSUPPORTED_CURSOR`; `CLOSED` retained
  precedence. Phase 3 replaces that deliberate intermediate behavior.

## Exact and disabled totals

- [x] `DISABLED` remains the default and allocates no count holder.
- [x] `EXACT` counts the complete query/filter matched set before page limit while the
  existing candidate loop is already evaluating matches.
- [x] Exact zero is present as zero; exact mode cannot change hits.
- [x] A callback-counting filter proves exact mode performs no second filter pass.
- [x] Ordinary execution continues through its existing result path and receives no
  page result or count object.

## Evidence and regression boundary

- [x] The V3.3 benchmark retains ordinary/filtered controls and adds first-page
  disabled, first-page exact, and filtered first-page exact cells.
- [x] A reviewed three-fork local comparison covers sparse and dense equal-score
  10,000-document corpora with allocation/GC profiling.
- [x] Ordinary, first-page disabled, and first-page exact latency intervals overlap;
  filtered ordinary and filtered exact intervals also overlap.
- [x] Exact counting adds only a small fixed result/count allocation delta in these
  cells and does not allocate per match.
- [x] JMH smoke retains all earlier cells and adds one bounded Phase 2 exact-total cell.
- [x] Raw JSON remains disposable under `target/`; commands, means, errors, allocation,
  limitations, and conclusions are recorded in
  [the Phase 2 baseline](PHASE_2_BASELINE.md).
- [x] Phase 2 requires no paid cloud run and mutates neither frozen cloud family.

## Local gates

- [x] All 363 core tests pass, including the public model, default capability,
  first-page matrix, one-pass exact total, failure precedence, and lifecycle tests.
- [x] Reactor core, five processor tests, travel example, version alignment,
  independent consumers, and isolated six-baseline artifact compatibility pass.
- [x] Release-profile strict Javadocs/source packaging passes with signing disabled.
- [x] JMH packaging and the complete retained smoke gate pass.
- [x] Diff whitespace validation passes and the locally excluded master roadmap is not
  staged.

## Phase 3 handoff

- [x] Phase 3 may add one private constant-sized built-in cursor, first-page cursor
  emission, continuation filtering, exact request identity, owner, and snapshot-version
  validation.
- [x] Phase 3 must preserve the Phase 2 public descriptors and first-page/total
  behavior while replacing Phase 2's deliberate no-cursor intermediate behavior.
- [x] Exhaustive dense-tie page walks, cursor precedence, publication staleness,
  idempotent reuse, branching, and retention inspection become Phase 3 hard gates.
- [x] Highlighted pagination, cursor serialization, snapshot pinning, timeout API,
  prepared queries, facets, aggregations, and deep-offset promises remain excluded.

Phase 2 was an intentionally non-releasable pagination endpoint because it could not
continue beyond the first page. Exact-commit protected-master `CI / Required` passed
in [run 33359591742](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33359591742).
Phase 3 begins from that accepted merge and supplies the private continuation
implementation.
