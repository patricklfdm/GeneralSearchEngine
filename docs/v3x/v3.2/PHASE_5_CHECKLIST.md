# V3.2 Phase 5 checklist

Status: complete and accepted on protected `master` through PR #55 as merge commit
`fbbce30`. Profiling found no justified production-code optimization.

## Accepted entry boundary

- [x] Phase 4 merged to protected `master` as source commit `1dd81d1`.
- [x] The independent `feat/v3.2-phase5-hardening` branch starts from that accepted
  merge.
- [x] Active coordinates remain `3.2.0-SNAPSHOT`; all five published compatibility
  baselines remain mandatory.
- [x] Phase 5 adds no public API, query semantics, stored offset payload, sidecar,
  analyzer composition, cloud preset, or release-family mutation.

## Mutation, snapshot, and lifecycle hardening

- [x] Deterministic blocked-offset fixtures publish add, update, remove, and atomic
  bulk update after snapshot capture; every completed result retains only the captured
  hits, documents, source strings, fragments, and spans.
- [x] Dynamic text-index construction replays update/remove/add journal entries before
  publication and immediately supports canonical highlighted search.
- [x] A drop during a blocked dynamic build cancels that build; a later create using
  the same canonical field succeeds and produces the expected highlights.
- [x] A highlighted read admitted before close completes from its captured snapshot;
  calls beginning after close fail with the existing CLOSED reason.
- [x] Failed atomic bulk analysis publishes no partial document/index state, and failed
  offset analysis publishes no state or partial result.
- [x] Existing malformed-output, extractor/analyzer failure, dynamic drop/install, and
  single-publication snapshot tests remain green.

## Mixed concurrency

- [x] Three highlighted readers, two ordinary readers, one Explain reader, and one
  writer complete a deterministic local stress fixture without error or mixed-source
  fragments.
- [x] All 240 writer updates publish, the queue drains, and final highlighted hits
  equal ordinary canonical hits after the writer stops.
- [x] The JMH mixed group combines four highlighted readers, four ordinary readers,
  one Explain reader, and one writer while recording latency distributions, writer
  publications, and queue evidence.
- [x] The bounded local JMH run records 246 publications with no observed queue buildup;
  highlighted and ordinary reader distributions overlap.

## Storage and retained-memory boundary

- [x] An instrumented `OffsetAnalyzer` proves add/update, ordinary search, Explain,
  dynamic text-index build, and ordinary post-build search never invoke
  `analyzeWithOffsets`.
- [x] Only explicit highlighting requests offset output, once per nonempty requested
  field of each returned hit in the focused storage fixture.
- [x] `TextIndexSnapshot` retains exactly its field, postings, fuzzy dictionary,
  document lengths, total length, and statistics; no offset, highlight, evidence, or
  sidecar field exists.
- [x] JFR old-object inspection finds no retained highlight, evidence, analyzer-output,
  or captured-snapshot candidate; the only sampled candidate is JMH/JDK infrastructure.
- [x] No global cache, static invocation state, or unbounded `ThreadLocal` is added.

## Profiling and stopping boundary

- [x] Pre-change JFR is captured from exact Phase 4 production code before any
  production edit.
- [x] BOOL/BOOST allocation samples remain dominated by existing candidate scoring,
  integer lookup, `ScoreMatch`, and fuzzy evaluation; TEXT CPU remains dominated by
  canonical document-length lookup.
- [x] Highlight-specific offset mapping, fragment construction, span construction, and
  phrase witness samples are individually small and do not justify a broader scoring,
  index, or Unicode-mapping change.
- [x] Scaling evidence shows explicit cost follows top-K, requested field count, and
  requested source length, while no-hit work remains bounded and small.
- [x] The 100k and 1M top-10 cells retain approximately 301 KB/op and 337 KB/op of
  highlighting delta respectively, providing no evidence of corpus-sized offset work.
- [x] Stop production optimization: the remaining allocation is either canonical
  search work or the frozen explicit top-K source-analysis/result cost. No point
  estimate is presented as a universal latency improvement.

## Benchmarks and evidence

- [x] `V32HighlightScaleBenchmark` covers top K 1/10/100, one/three requested fields,
  short/medium/long source, every ranked query family, highlighted/unrelated/no-hit
  outcomes, contexts 0/40/160, and fragment caps 1/3/10.
- [x] Setup compares the complete highlighted hit projection with ordinary search and
  fails on any canonical drift.
- [x] `V32HighlightConcurrencyBenchmark` records mixed reader latency and writer
  progress using a single shared immutable-snapshot engine.
- [x] Both new surfaces are included in the bounded JMH discovery/execution gate.
- [x] The Phase 5 baseline records environment, commands, values, limitations, JFR
  observations, retained-memory boundary, and the unchanged cloud decision.
- [x] No paid cloud run is required because no protected workflow, cloud preset,
  immutable baseline family, ordinary index shape, or stored payload changes.

## Required repository gates

- [x] Complete core clean verify passes with 343 tests and no failures/errors/skips.
- [x] Reactor core/processor/example verification passes.
- [x] Five published-version Japicmp comparisons pass in a fresh isolated repository.
- [x] Independent V1-, V2-, and V3-style consumers compile and execute.
- [x] Strict release sources, Javadocs, artifacts, version alignment, travel example,
  JMH smoke, and diff hygiene pass.

## Phase 6 handoff

- [x] Phase 6 inherits the frozen public API, exact evidence semantics, failure order,
  one-snapshot behavior, storage boundary, and Phase 5 lifecycle/concurrency oracles.
- [x] Phase 6 may complete consumers, Japicmp, Javadocs, artifact reproducibility,
  documentation, release-candidate conversion, and publication preparation.
- [x] Stored offsets, HTML, analyzer composition, cloud highlighting families, and new
  search features remain outside the release handoff.

Phase 5 is complete. Phase 6 starts from accepted merge commit `fbbce30` on a new
independent branch.
