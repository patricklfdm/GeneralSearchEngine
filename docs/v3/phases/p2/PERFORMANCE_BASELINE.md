# V3 Phase 2 positional storage performance baseline

These measurements are a workload- and environment-specific regression record for the
Phase 2 representation. They are not a universal throughput guarantee or a claim that
one Analyzer mode is faster than another.

## Environment

- Date: 2026-08-25
- Base commit: `dbbd09f` plus the Phase 2 implementation working tree
- OS: Linux 6.6.87.2 under WSL2, x86-64
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs
- Available VM memory: 15 GiB
- JVM: OpenJDK 21.0.12
- JMH: 1.37, one benchmark thread, two forks
- Measurement: two 1-second warmups and five 1-second measurements per fork
- Profiler: JMH `gc`, with normalized allocation reported per operation

The benchmark can be rebuilt and rerun with:

```bash
./mvnw -Pjmh -DskipTests package
java -jar target/benchmarks.jar PositionalTextIndexBenchmark -prof gc
```

## Workload and results

Each build indexes 10,000 documents with 16 emitted tokens per document. Each mutation
invocation reorders the terms in 100 documents and publishes one new immutable
snapshot. The default-adapter mode represents existing Analyzer implementations. The
native-positioned mode emits an initial gap and periodic same-position alternatives.

| Operation | Analyzer mode | Average latency | Normalized allocation |
|---|---|---:|---:|
| Build 10,000 documents | default adapter | 174.610 ms/op | 262.14 MB/op |
| Build 10,000 documents | native positioned | 175.681 ms/op | 265.33 MB/op |
| Reorder and publish 100 documents | default adapter | 2.730 ms/op | 2.968 MB/op |
| Reorder and publish 100 documents | native positioned | 2.754 ms/op | 2.961 MB/op |

The latency confidence intervals overlap for both corresponding modes. Normalized
allocation is also in the same narrow range for each operation. This run therefore
shows no obvious mode-specific pathological allocation or latency behavior in the
representative workload; it does not establish equivalence for all workloads.

Production occurrence payloads use a private primitive `int[]` inside package-private
`IntPositions`. No boxed `List<Integer>` is retained per occurrence and no mutable
array crosses the snapshot boundary. The allocation numbers include analysis,
temporary builders, persistent-map publication, and benchmark document processing;
they are not a direct retained-heap measurement of position arrays alone.

Compression, delta encoding, packed blocks, off-heap storage, and representation tuning
remain outside Phase 2. Later work should compare against this exact benchmark before
changing the positional representation.
