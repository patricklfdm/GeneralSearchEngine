# V3.1 Phase 2 local diagnostic baseline

## Scope and comparison eligibility

This short local profile checks that adding phrase slop does not materially disturb
the existing exact-phrase path and records a first diagnostic cost for the new path.
It uses the same machine, JVM, document count, fork count, warmup, measurement, and GC
profiler settings as the Phase 1 phrase profile.

The results are developer diagnostics, not canonical evidence or a release regression
gate. The exact and sloppy benchmark cells use different queries and therefore are not
a direct feature-cost comparison. Raw JMH JSON remains disposable output under
`target/`.

## Environment

- captured: 2026-08-29, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- benchmark mode: average time, one thread, one fork, two 500 ms warmups, three
  500 ms measurements, GC profiler.

## Phrase profile

Command:

```bash
java -jar target/benchmarks.jar \
  'PhraseSearchBenchmark.(exactPhraseTop10|sloppyPhraseTop10|commonPhraseTop10)' \
  -p documentCount=100000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v31-phase2-phrase.json -foe true
```

| Benchmark | Mean time | Normalized allocation |
|---|---:|---:|
| common exact phrase top 10 | 25.350 ms/op | 21,994,109 B/op |
| focused exact phrase top 10 | 14.301 ms/op | 13,523,909 B/op |
| focused sloppy phrase top 10 | 18.445 ms/op | 15,442,670 B/op |

The directly comparable common exact cell was 24.409 ms/op and 21,994,098 B/op in
Phase 1. This short run measured a 3.86% latency increase and 11 B/op additional
allocation. That is within the noise expected from this diagnostic-sized run and does
not establish either a regression or a performance improvement. Allocation is
effectively unchanged; Phase 5 remains responsible for profile-guided phrase
optimization and canonical claims remain reserved for the frozen evidence lanes.

The benchmark setup also executes both exact factory forms and fails before
measurement if their result lists differ.

## Reproduction boundary

Build the benchmark JAR with:

```bash
./mvnw clean -Pjmh -DskipTests package
```

A useful repeat requires the same environment and JMH parameters. Release evidence
must still use the unchanged regression lane and the separately versioned V3.1 feature
lane defined in [the performance contract](PERFORMANCE_AND_EVIDENCE.md).
