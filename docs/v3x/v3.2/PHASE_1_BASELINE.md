# V3.2 Phase 1 pre-change baseline

## Scope and comparison eligibility

This record captures the V3.2 foundation baseline before any production offset or
highlighting implementation. The production source is exactly the accepted V3.2
Phase 0 merge commit `9f4825976cb0c6e9c3c8862efabd9e648bc315a4`.
The Phase 1 branch changes project identity, compatibility gates, independent test
oracles, benchmark coverage, and documentation, but changes no file under
`src/main/java`.

The short, single-fork WSL2 measurements below are local diagnostics for repeatable
same-machine comparison. They are not canonical evidence, do not replace either
registered cloud family, and must not be used as a cross-machine regression gate.
Raw JMH JSON belongs under `target/` and is disposable.

## Environment

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- benchmark mode: average time, one thread, one fork, two 500 ms warmups, three
  500 ms measurements, GC profiler.

## Ordinary analyzer baseline

The Phase 1 benchmark exercises existing `Analyzer.simple()` term and positional
analysis without deriving offsets. Each cell uses 256 logical tokens.

```bash
java -jar target/benchmarks.jar 'V32AnalyzerBaselineBenchmark.*' \
  -p shape=ascii,bmp,supplementary,nfkc -p tokenCount=256 \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v32-phase1-analyzer.json -foe true
```

| Operation | Shape | Mean time | Normalized allocation |
|---|---|---:|---:|
| terms | ASCII | 9.612 us/op | 25,520 B/op |
| terms | BMP | 14.933 us/op | 31,416 B/op |
| terms | supplementary | 11.456 us/op | 41,984 B/op |
| terms | NFKC length-changing | 12.375 us/op | 26,904 B/op |
| positions | ASCII | 10.549 us/op | 32,920 B/op |
| positions | BMP | 15.869 us/op | 38,816 B/op |
| positions | supplementary | 12.423 us/op | 49,384 B/op |
| positions | NFKC length-changing | 13.592 us/op | 34,304 B/op |

These are the ordinary-path controls for Phase 2. Offset-aware analysis will receive
separate cells; it may not hide new offset work inside either operation above.

## Index, search, and Explain controls

```bash
java -jar target/benchmarks.jar \
  'PositionalTextIndexBenchmark.(buildPositionalTextIndex|publishPositionSensitiveMutationBatch)' \
  -p analysisMode=default-adapter -p documentCount=10000 \
  -p mutationBatchSize=1 -p tokenCount=16 \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v32-phase1-index.json -foe true

java -jar target/benchmarks.jar 'V3TextCompatibilityBenchmark.v3TextTop10' \
  -p documentCount=10000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v32-phase1-search.json -foe true

java -jar target/benchmarks.jar 'ExplainSearchBenchmark.normalSearchTop10' \
  -p documentCount=10000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v32-phase1-explain-control.json -foe true
```

| Control | Mean time | Normalized allocation |
|---|---:|---:|
| positional text-index build, 10k documents | 218.959 ms/op | 274,304,699 B/op |
| one position-sensitive publication | 0.013 ms/op | 29,600 B/op |
| V3 TEXT top 10, 10k documents | 0.368 ms/op | 163,593 B/op |
| normal-search Explain control, 10k documents | 469.446 us/op | 290,504 B/op |

The short confidence intervals are not stable enough for absolute release claims.
Later comparisons require the same host, JVM, parameters, JMH options, and idle-system
conditions, and must report the full distribution rather than only these means.

## Retained-memory and canonical anchors

No new paid cloud run is required for Phase 1. The index representation is unchanged,
so the durable V3.1 evidence remains the exact pre-offset anchor:

- protected run `33306780388 / 1` used
  `canonical / all / 3 / standard / c3d-standard-30 / 30m / gcs` at source
  `9d4c43c230abb260ac1736cc3dd4d29d4f29fbe9`; its 357-metric candidate is directly
  comparable with `v3.0.0-cloud` and records 1M search, build, allocation, concurrency,
  GC, and 30-minute heap-band behavior;
- the candidate's 30-minute soak retained zero errors, a drained writer queue, and
  100,000 final documents; its median average heap-band growth was about 659 MB and
  remained a reviewed no-plateau diagnostic rather than a leak or SLA conclusion; and
- protected run `33299490397 / 1` established the separate 84-configuration ranked
  family now registered as `v3.1.0-ranked-cloud`. Its 1M initial-build allocation was
  stable at approximately 8.629 GB/op across three independent members.

The complete identities and review boundaries remain in
[the frozen regression review](../v3.1/PHASE_7_REGRESSION_REVIEW.md) and
[the ranked feature review](../v3.1/PHASE_7_CANONICAL_REVIEW.md). Phase 5 must compare
ordinary paths with these unchanged representation anchors. Any stored-offset or
sidecar proposal would invalidate this inheritance and require a separately contracted
before/after cloud family.

## Reproduction boundary

Build and smoke the benchmark JAR with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke gate includes one bounded V3.2 analyzer cell in addition to the existing V3
and V3.1 cells. It proves benchmark discovery and execution only; it is not a latency
or allocation threshold.
