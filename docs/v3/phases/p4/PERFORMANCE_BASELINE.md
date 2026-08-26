# V3 Phase 4 ranked composition performance smoke

## Scope

This is a focused implementation smoke, not a portable performance promise or release
threshold. It checks that recursive BOOL/BOOST and cross-field preparation execute on
posting-derived candidates without obvious per-document analysis, index resolution,
IDF recomputation, candidate recomposition, full-result retention, or an unnecessary
full collection scan.

## Environment

Recorded on 2026-08-26:

```text
OS: Linux 6.6.87.2-microsoft-standard-WSL2 x86_64
CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs
JVM: OpenJDK 64-Bit Server VM 21.0.12
JMH: 1.37
```

The focused fixture contains 10,000 documents, two independent text indexes, one
structured equality index, explicit BOOST, and bounded top 10 retention.

## Commands

JMH source and generated-code compilation:

```bash
./mvnw -Pjmh -DskipTests package
```

Short functional smoke:

```bash
java -jar target/benchmarks.jar '.*RankedCompositionBenchmark.*' \
  -wi 1 -i 1 -f 1 -w 100ms -r 100ms
```

## Observations

| Benchmark | Documents | Smoke result |
|---|---:|---:|
| all-SHOULD cross-field top 10 | 10,000 | 2.755 ms/op |
| MUST + SHOULD + indexed filter cross-field top 10 | 10,000 | 0.328 ms/op |

Both cases produced ten deterministically ordered hits and completed without an
obvious pathological regression. The filtered MUST case visits a substantially smaller
candidate set in this fixture, which explains its lower observed smoke time; this is a
fixture-specific inference, not a universal speedup claim.

The run used one short warmup and one short measurement iteration. These numbers are
diagnostic only and must not be compared across machines or treated as a frozen Phase 4
performance budget.
