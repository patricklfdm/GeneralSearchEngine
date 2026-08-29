# V3.1 Phase 5 local pre-change baseline

## Scope and comparison eligibility

This profile is the pre-change evidence required before Phase 5 phrase allocation and
execution optimization. It was captured from merge commit `aabaa0c`, after Phase 4
hardening and before any Phase 5 production change.

The short, single-fork WSL2 results are local diagnostics. They confirm continuity
with the Phase 1 and Phase 2 developer baselines and select narrow optimization
experiments; they are not canonical evidence or a release regression gate. Raw JMH
JSON and JFR recordings remain disposable output under `target/`.

## Environment

- captured: 2026-08-29, America/Los_Angeles;
- source: `aabaa0c`;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- allocation benchmark mode: average time, one thread, one fork, two 500 ms
  warmups, three 500 ms measurements, GC profiler.

## Comparable core profile

Command:

```bash
java -jar target/benchmarks.jar \
  'PhraseSearchBenchmark.(exactPhraseTop10|sloppyPhraseTop10|commonPhraseTop10)' \
  -p documentCount=100000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v31-phase5-prechange-core.json -foe true
```

| Benchmark | Phase 5 mean | Phase 5 allocation | Nearest prior mean | Nearest prior allocation |
|---|---:|---:|---:|---:|
| common exact phrase top 10 | 24.983 ms/op | 21,994,108 B/op | 25.350 ms/op | 21,994,109 B/op |
| focused exact phrase top 10 | 13.427 ms/op | 13,523,891 B/op | 14.301 ms/op | 13,523,909 B/op |
| focused sloppy phrase top 10 | 17.988 ms/op | 15,442,664 B/op | 18.445 ms/op | 15,442,670 B/op |

The nearest values are the Phase 2 profile captured on the same machine and with the
same JMH configuration. Allocation is effectively identical. The short latency cells
are respectively 1.45%, 6.11%, and 2.48% lower, which remains diagnostic run-to-run
variation rather than evidence of an improvement. Phase 4 therefore introduced no
observed phrase allocation or evidence-identity drift.

## Additional phrase shapes

Command:

```bash
java -jar target/benchmarks.jar \
  'PhraseSearchBenchmark.(selectivePhraseTop10|repeatedPhraseTop10|longPhraseTop10|positionGapPhraseTop10|composedPhraseTop10)' \
  -p documentCount=100000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v31-phase5-prechange-shapes.json -foe true
```

| Benchmark | Mean time | Normalized allocation |
|---|---:|---:|
| composed phrase top 10 | 12.958 ms/op | 12,468,068 B/op |
| long phrase top 10 | 21.752 ms/op | 21,445,717 B/op |
| position-gap phrase top 10 | 32.143 ms/op | 28,449,889 B/op |
| repeated phrase top 10 | 2.726 ms/op | 2,951,398 B/op |
| selective phrase top 10 | 13.805 ms/op | 13,523,896 B/op |

The Phase 1 long and repeated cells measured 20.590 ms/op with 21,445,693 B/op and
2.540 ms/op with 2,951,395 B/op. Their allocations remain stable; the latency movement
in these short runs is not a performance conclusion. The position-gap cell has the
largest allocation in the local shape matrix and remains a required after-change
guard.

## JFR profile

Common exact and sloppy phrase cells were separately recorded with one 500 ms warmup
and one 1 s measurement. Those JFR runs locate hotspots only; their instrumented
latency is not included in the comparison tables.

```bash
java -jar target/benchmarks.jar \
  'PhraseSearchBenchmark.commonPhraseTop10' \
  -p documentCount=100000 -f 1 -wi 1 -i 1 -w 500ms -r 1s \
  -prof jfr -foe true

java -jar target/benchmarks.jar \
  'PhraseSearchBenchmark.sloppyPhraseTop10' \
  -p documentCount=100000 -f 1 -wi 1 -i 1 -w 500ms -r 1s \
  -prof jfr -foe true
```

The allocation samples identify the same dominant source in both paths:

| Allocation source | Common exact | Sloppy |
|---|---:|---:|
| `ImmutableBitmapBuilder.mutableBlock` capturing lambda | 84.64% | 85.71% |
| boxed `Integer` lookup keys | 8.95% | 4.64% |
| `byte[]`, primarily eager validation diagnostics | 3.13% | 7.37% |
| `ScoreMatch` | 0.77% | 0.78% |
| immutable-list iterator | 0.72% | 0.75% |

The primary lambda is allocated by `HashMap.computeIfAbsent` for every retained
document while `ImmutableBitmap.and` constructs phrase slot intersections. JFR CPU
samples then place `TextIndexSnapshot.documentLength` at 44.19% for common exact and
43.04% for sloppy, and `PostingList.positions` at 17.44% and 31.65%. The sample is
small but the allocation and execution stacks agree across both phrase paths.

## Selected optimization order

1. Replace the per-document capturing `computeIfAbsent` in the bitmap builder with an
   explicit existing-block lookup and one-time block installation. This is the first
   narrow experiment because it dominates allocation while leaving bitmap contents,
   phrase truth, score, order, and evidence identity unchanged.
2. If the first rerun confirms the profile, separately remove successful-path string
   construction from phrase-position validation while preserving every validation
   failure and message. Repeated structural validation is evaluated independently so
   it cannot hide the first change's effect.
3. Do not redesign positional storage, BM25 document-length access, `ScoreMatch`, or
   top-K objects until the two narrow experiments have isolated evidence. Those are
   broader engine surfaces and are not justified by this profile alone.

Each experiment must run the Phase 4 semantic oracles, focused bitmap and phrase
tests, the complete core suite, this exact local JMH matrix, and the unchanged
regression benchmark smoke before acceptance.

## Baseline gates

- JMH package build: pass.
- Every selected benchmark setup-time cardinality, score-order, and exact-zero
  equivalence guard: pass.
- Focused phrase lifecycle, randomized differential, positioned-token differential,
  and ranked hardening suites: 9 tests, zero failures/errors/skips.
- `git diff --check`: pass.
