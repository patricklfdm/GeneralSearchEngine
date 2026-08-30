# V3.2 Phase 2 offset-analysis baseline

## Scope and comparison eligibility

This record captures the first production offset-capable `SimpleAnalyzer` together
with the unchanged ordinary term and positional paths. The Phase 2 branch starts from
the accepted Phase 1 merge commit
`65ea455`. Offset analysis is an explicit opt-in operation: ordinary analysis,
indexing, search, and Explain do not construct `OffsetAnalyzedToken` values.

The short, single-fork WSL2 measurements below are local diagnostics. They are not
canonical evidence, do not replace either registered cloud family, and must not be
used as a cross-machine regression gate. Raw JMH JSON belongs under `target/` and is
disposable.

## Environment and protocol

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- benchmark mode: average time, one thread, one fork, two 500 ms warmups, three
  500 ms measurements, GC profiler; and
- input: 256 whitespace-separated logical tokens per invocation.

```bash
java -jar target/benchmarks.jar 'V32AnalyzerBaselineBenchmark.*' \
  -p shape=ascii,bmp,supplementary,combining,nfkc \
  -p tokenCount=256 \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v32-phase2-analyzer.json -foe true
```

## Ordinary-path control

The four shapes shared with the Phase 1 pre-change baseline remain directly
comparable on the same host and protocol.

| Operation | Shape | Phase 1 | Phase 2 | Change | Phase 2 allocation |
|---|---|---:|---:|---:|---:|
| terms | ASCII | 9.612 us/op | 9.494 us/op | -1.2% | 25,544 B/op |
| terms | BMP | 14.933 us/op | 14.769 us/op | -1.1% | 31,416 B/op |
| terms | supplementary | 11.456 us/op | 11.465 us/op | +0.1% | 41,984 B/op |
| terms | NFKC length-changing | 12.375 us/op | 12.814 us/op | +3.5% | 26,928 B/op |
| positions | ASCII | 10.549 us/op | 10.047 us/op | -4.8% | 32,944 B/op |
| positions | BMP | 15.869 us/op | 16.396 us/op | +3.3% | 38,816 B/op |
| positions | supplementary | 12.423 us/op | 12.626 us/op | +1.6% | 49,384 B/op |
| positions | NFKC length-changing | 13.592 us/op | 14.264 us/op | +4.9% | 34,328 B/op |

The observed range is normal short-run local variation rather than evidence of a
material regression. Ordinary `SimpleAnalyzer.analyze` retains its previous direct
implementation, and `analyzeWithPositions` projects directly from it. Neither method
calls offset mapping. Normalized allocation is unchanged or differs by only 24 bytes
per invocation in these cells.

The new combining-sequence control records 18.043 us/op and 39,304 B/op for terms,
and 19.581 us/op and 46,704 B/op for positions. It has no Phase 1 comparison cell.

## Explicit offset-analysis cost

| Shape | Mean time | Normalized allocation | Approx. time/token |
|---|---:|---:|---:|
| ASCII | 93.343 us/op | 536,657 B/op | 0.365 us |
| BMP | 109.474 us/op | 609,338 B/op | 0.428 us |
| supplementary | 71.972 us/op | 413,249 B/op | 0.281 us |
| combining sequence | 338.795 us/op | 1,297,837 B/op | 1.323 us |
| NFKC length-changing | 89.411 us/op | 461,297 B/op | 0.349 us |

Combining input is the most expensive cell because exact original-source provenance
requires the context-sensitive incremental normalization fallback. The cost is visible
only when `analyzeWithOffsets` is explicitly requested; Phase 2 stores no offset
payload in an index or sidecar. Phase 0 intentionally freezes no numerical threshold
for this new path. The cell is therefore an honest optimization anchor for Phase 5,
not a release claim or permission to weaken Unicode mapping.

## Correctness and evidence boundary

Benchmark setup first proves term and position projection equality for every shape.
Focused fixtures additionally cover composed/decomposed forms, supplementary code
points, Greek contextual lowercase, compatibility expansion to several terms,
punctuation, unpaired surrogates, immutability, and bounded parallel determinism. A
2,000-trial fixed-seed randomized Unicode test validates every range against an
independent oracle and reports replay data on failure.

No paid cloud run is required for Phase 2. The index representation, retained-memory
shape, cloud presets, and protected workflows are unchanged, so the canonical anchors
recorded in the [Phase 1 baseline](PHASE_1_BASELINE.md) remain applicable. A stored
offset or sidecar proposal would invalidate that inheritance and require a separate
contract and evidence family.

## Reproduction boundary

Build and smoke the benchmark JAR with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke gate now includes one bounded explicit offset-analysis cell in addition to
the ordinary V3.2 analyzer control and all retained V3/V3.1 cells. It proves discovery
and execution only; it is not a latency or allocation threshold.
