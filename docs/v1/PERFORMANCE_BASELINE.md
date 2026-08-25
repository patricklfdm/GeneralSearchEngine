# v1 performance baseline

This document records the completed v1 JMH performance investigation. These
measurements are environment- and workload-specific regression baselines, not
universal performance guarantees.

## Benchmark environment

- 100,000 documents
- JMH 1.37
- OpenJDK 22.0.2

## Range-query selectivity

The indexed and scanned benchmarks execute equivalent price-range queries. Throughput
is reported in operations per second; allocation is the JMH normalized allocation per
operation. MB values use 1,000,000 bytes.

| Selectivity | Indexed throughput | Scan throughput | Indexed allocation | Scan allocation |
|---:|---:|---:|---:|---:|
| 0.01% | 316,950 ops/s | 278 ops/s | 0.010 MB/op | 5.60 MB/op |
| 0.1% | 23,234 ops/s | 301 ops/s | 0.090 MB/op | 5.60 MB/op |
| 1% | 2,587 ops/s | 270 ops/s | 0.89 MB/op | 5.62 MB/op |
| 10% | 263 ops/s | 263 ops/s | 8.89 MB/op | 5.77 MB/op |
| 25% | 95 ops/s | 187 ops/s | 22.18 MB/op | 5.98 MB/op |
| 50% | 53 ops/s | 247 ops/s | 44.46 MB/op | 6.45 MB/op |
| 100% | 22 ops/s | 218 ops/s | 88.48 MB/op | 6.88 MB/op |

The current range index strongly benefits selective queries. Around 10% selectivity,
the index and full scan are approximately equal in this workload; at higher
selectivity, the full scan becomes faster. The candidate bitmap allocation grows
roughly with the number of matched documents, which increasingly affects indexed
queries as the range widens.

The 10% observation is neither an exact nor a universal crossover threshold. The
crossover depends on the data distribution, query, index implementation, JVM, and
hardware. Cost-based index-versus-scan planning is not part of v1 and should be
considered future work.

## Mutation batching

Each invocation applies the stated number of updates and publishes one immutable
snapshot. Allocation is reported for the complete batch.

| Batch size | Publication latency | Amortized latency per document | Allocation per batch |
|---:|---:|---:|---:|
| 1 | 27.46 ms | 27.460 ms | 26.25 MB |
| 10 | 29.00 ms | 2.900 ms | 26.13 MB |
| 100 | 28.65 ms | 0.286 ms | 24.96 MB |
| 1,000 | 25.04 ms | 0.025 ms | 21.86 MB |

Total publication latency remains roughly 25–29 ms per batch. This indicates that
batching amortizes the fixed cost of publishing an immutable snapshot across more
mutations. The measurements contain benchmark variance, particularly at the largest
batch size, so they should not be used to advertise exact speedup multipliers.

No correctness issue was discovered during this investigation. The benchmark setup
validated equivalent range-query result counts, and the mutation benchmark verified
one snapshot publication per measured batch.
