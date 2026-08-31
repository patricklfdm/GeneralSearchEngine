# V3.3 Phase 4 checklist

Status: locally complete on `feat/v3.3-phase4-hardening`; full local gate results are
recorded below before commit review. No production source or public descriptor changes.

## Accepted entry boundary

- [x] Phase 3 is accepted on protected `master` through PR #62 at merge commit
  `521e65e`.
- [x] The transient Maven plugin-resolution failure in Release artifacts passed on a
  failed-job rerun without a source workaround.
- [x] The independent Phase 4 branch starts from that exact protected-master merge.
- [x] Coordinates remain `3.3.0-SNAPSHOT`; all six published compatibility baselines
  remain mandatory.

## Publication, lifecycle, and failure hardening

- [x] Successful add, update, remove, bulk add/update/remove, dynamic-index create,
  and dynamic-index drop each advance the snapshot and stale an earlier cursor.
- [x] A barrier after continuation capture proves all eight publication kinds leave
  the admitted page wholly on its captured old snapshot.
- [x] Duplicate add, missing update, failed bulk add/update, and duplicate index create
  publish nothing and leave the cursor usable.
- [x] Idempotent drop of a known field with no installed index publishes nothing and
  leaves the cursor usable.
- [x] Existing close-before-admission and admitted-across-close Phase 3 gates remain
  mandatory.

## Cursor reuse, concurrency, and writer progress

- [x] Three controlled readers branch and reuse one cursor across a writer publication;
  all complete from the captured snapshot and later calls reject the old cursor.
- [x] Writer completion and queue drainage occur while the page readers are blocked in
  query analysis, proving retained cursors do not coordinate with writers.
- [x] The JMH mixed group includes ordinary, disabled-page, exact-page, highlighted,
  Explain, and writer operations and counts successful/stale continuations.
- [x] The reviewed local group completes 256 sample-mode and 263 throughput-mode
  publications with zero observed queue buildup.

## Retention boundary

- [x] One, 1,000, and 100,000 live-cursor isolated probes are recorded; the two stable
  larger cells converge near a 44 B/cursor retained envelope on this JVM.
- [x] Full release returns used heap to within 32–192 B of the pre-retention baseline.
- [x] Reflection continues to prove exactly two direct references and three primitive
  fields, with no engine, snapshot, index, posting, result, plan, or document graph.
- [x] Keeping 100,000 distinct cursors live changes no engine metrics or registry and
  does not prevent a writer publication or queue drainage.

## Scale and decision closure

- [x] Depth-100 phrase, fuzzy, dense BOOL/BOOST, and expensive-filter disabled/exact
  cells record latency, allocation, and GC evidence.
- [x] A 20,000-document, depth-1,000 dense BOOL cell confirms complete-candidate
  evaluation and preserves the no-O(page-size)/no-seek claim.
- [x] Exact counting adds no per-match object in the stable paired depth-100 cells.
- [x] Timeout/cancellation is explicitly deferred: no consumer SLA or complete safe
  public control contract justifies implementation, and arbitrary callbacks remain
  outside cooperative preemption.
- [x] Prepared queries are explicitly deferred: profiling does not identify logical
  normalization as a material hotspot and no physical snapshot plan may be cached.
- [x] No production optimization is accepted; the Phase 3 executor remains unchanged.

## Evidence and repository gates

- [x] `V33PaginationHardeningBenchmark` covers the required expensive-query and deep
  continuation cells.
- [x] `V33PaginationConcurrencyBenchmark` records mixed reader/writer distributions,
  stale/success outcomes, publications, and queue evidence.
- [x] `V33CursorRetentionProbe` records the isolated live/released heap envelope.
- [x] All three surfaces are compiled and bounded by the retained JMH smoke gate.
- [x] No paid cloud run is required because production code, protected workflow,
  stored shape, cloud modes, presets, and immutable baseline families are unchanged.
- [x] Complete core, reactor, compatibility, consumer, strict Javadoc/release,
  example, JMH smoke, and diff-hygiene gates pass after documentation closure.

## Phase 5 handoff

- [x] Phase 5 inherits strict current-snapshot cursor semantics, exact totals, failure
  precedence, the constant retained shape, and all Phase 4 publication/concurrency
  oracles.
- [x] Phase 5 closes consumers, Japicmp, Javadocs, artifacts, reproducibility,
  documentation, release-candidate conversion, and publication preparation.
- [x] Timeout/cancellation, prepared queries, highlighted pagination, lower-bound
  totals, snapshot pinning, facets, aggregations, grouping, and deep-offset APIs remain
  outside the release handoff.

Phase 4 is functionally, evidentially, and locally gate-complete and is ready for
commit review.
