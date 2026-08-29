# V3.1 Phase 1 local diagnostic baseline

## Scope and comparison eligibility

This is the focused pre-change profile required before V3.1 phrase and fuzzy
implementation work. Production search sources are unchanged from commit `a36183e`
(the merged V3.1 Phase 0 contract); the working branch adds only build gates, tests,
and documentation.

These short, single-fork WSL2 results identify local hotspots and provide a repeatable
developer comparison on the same machine. They are not canonical evidence, do not
replace `v3.0.0-cloud`, and must not be compared across environments as a regression
gate. Raw JMH JSON is disposable output under `target/`.

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
  'PhraseSearchBenchmark.(commonPhraseTop10|longPhraseTop10|repeatedPhraseTop10)' \
  -p documentCount=100000 -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v31-phase1-phrase.json -foe true
```

| Benchmark | Mean time | Normalized allocation |
|---|---:|---:|
| common phrase top 10 | 24.409 ms/op | 21,994,098 B/op |
| long phrase top 10 | 20.590 ms/op | 21,445,693 B/op |
| repeated phrase top 10 | 2.540 ms/op | 2,951,395 B/op |

The representative common and long cases allocate about 21 MiB per operation. This
is a profile-guided optimization target, not a Phase 2 permission to change exact
phrase semantics or scoring.

## Fuzzy profile

Command:

```bash
java -jar target/benchmarks.jar \
  'FuzzySearchBenchmark.fuzzyPlanAndTop10' \
  -p vocabularySize=100000 -p scenario=exact,high-expansion,no-match \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms \
  -prof gc -rf json -rff target/v31-phase1-fuzzy.json -foe true
```

| Scenario | Mean time | Normalized allocation |
|---|---:|---:|
| exact | 42.458 ms/op | 10,524,986 B/op |
| high expansion | 5.634 ms/op | 5,191,917 B/op |
| no match | 32.778 ms/op | 2,735 B/op |

The exact and no-match latencies expose the retained whole-vocabulary scan cost; the
exact and high-expansion cells also expose material temporary allocation. The
high-expansion timing had visibly wider iteration variance, so its absolute latency is
diagnostic only. Phase 6 must compare trie traversal with the retained full-scan oracle
before attributing any improvement to the new physical dictionary.

## Reproduction boundary

Build the benchmark JAR with:

```bash
./mvnw clean -Pjmh -DskipTests package
```

A useful local before/after requires the same machine, JVM, parameters, JMH options,
and idle-system conditions. Release claims still require the unchanged frozen
regression lane and the separately versioned V3.1 feature lane defined in
[the performance contract](PERFORMANCE_AND_EVIDENCE.md).
