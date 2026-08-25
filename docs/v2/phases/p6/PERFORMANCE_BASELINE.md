# GeneralSearchEngine v2 P6 performance baseline

## Status

The complete eight-row P6 explicit-bulk matrix is accepted. Correctness, compatibility,
processor compile tests, release packaging, reproducibility, benchmark packaging, and
every phase-specific gate pass.

Each successful invocation asserted exactly one snapshot-version increment. Each
invalid invocation placed one missing ID at the end of the collection and asserted
exceptional completion, zero publication, and unchanged visible state. Completion of
all rows therefore provides both timing and atomicity evidence.

These measurements are environment- and workload-specific regression baselines. They
are not universal mutation latency, allocation, batching benefit, capacity, or scaling
guarantees.

## Matrix and environment

| Benchmark | Dimensions | Rows |
|---|---|---:|
| `ExplicitBulkMutationBenchmark` | successful/invalid update × batch 1/10/100/1000 | 8 |

- JMH 1.37
- OpenJDK 64-Bit Server VM 22.0.2+9-70
- one benchmark thread and two forks
- no explicit JVM arguments
- two one-second warmups and five one-second measurements
- one existing Range index updated by every valid document

Both methods report total average time and normalized allocation for the complete
collection. Per-document values below are derived only to show fixed-cost amortization.

## Successful atomic publication

| Batch size | Total ms/op | Amortized us/document | Allocation/batch | Allocation/document |
|---:|---:|---:|---:|---:|
| 1 | 0.0112 | 11.224 | 9.18 KB | 9,180 B |
| 10 | 0.0171 | 1.715 | 31.31 KB | 3,131 B |
| 100 | 0.0901 | 0.901 | 284.43 KB | 2,844 B |
| 1,000 | 0.8886 | 0.889 | 3.09 MB | 3,091 B |

Total work grows with the explicit collection, while the one queue task, future, and
immutable-publication fixed costs are amortized. In this workload the 100- and
1,000-document rows have similar per-document latency and allocation scale. The small
batch rows are dominated by fixed costs, so the table must not be used to advertise an
exact batching multiplier.

Every measured successful invocation advanced the snapshot version by exactly one,
including the 1,000-document collection. The result confirms the public operation is
not silently split into multiple publications.

## Invalid collection rollback

The missing ID is the final collection element, so batches above one first perform
private builder work for every preceding valid ID. None of that work becomes visible.

| Batch size | Total ms/op | Amortized us/input | Allocation/batch | Allocation/input |
|---:|---:|---:|---:|---:|
| 1 | 0.0128 | 12.812 | 4.10 KB | 4,104 B |
| 10 | 0.0161 | 1.614 | 20.22 KB | 2,022 B |
| 100 | 0.0499 | 0.499 | 138.74 KB | 1,387 B |
| 1,000 | 0.4846 | 0.485 | 1.32 MB | 1,320 B |

Invalid-batch work grows with how late validation fails, but remains cheaper than a
successful large batch here because it discards the private builder and does not build
or publish the final immutable snapshot. This is not a promise that failures are
always cheaper: duplicate-ID, extractor, existing-ID, and early/late missing-ID paths
perform different amounts of work.

The widest relative primary-score error is 3.16% in the invalid batch-one row. All
other rows remain below 3%, so the matrix is sufficiently stable for regression-scale
comparisons. Exact ratios are still not portable performance claims.

## Reproduction command

```bash
mvn -Pjmh -DskipTests clean package

java -jar target/benchmarks.jar '.*ExplicitBulkMutationBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p6-explicit-bulk.json
```

## Validation

- all eight expected JMH rows are present and successful;
- successful collections publish exactly once at all four sizes;
- invalid collections publish nothing and retain pre-invocation documents;
- `mvn clean test`: PASS, 115 core tests;
- `mvn clean -Papi-compat test`: PASS, 3 frozen-v1 fixture tests;
- `mvn -f reactor/pom.xml test`: PASS, 115 core plus 4 processor compile tests;
- `mvn -f reactor/pom.xml clean -Prelease verify`: PASS, strict Javadocs, six attached
  JARs, two POMs, and signatures;
- `bash scripts/verify-reproducible-build.sh`: PASS for all six core/processor JARs;
- core JAR processor-service isolation and processor JAR service registration: PASS;
- JMH package, discovery, smoke, and formal matrix: PASS.

## Acceptance checklist

- [x] All eight expected rows are present and successful.
- [x] Successful collections publish exactly once at all four sizes.
- [x] Invalid collections publish nothing and retain pre-invocation documents.
- [x] Total batch latency and allocation are recorded separately from amortized values.
- [x] Variance and environment are recorded.
- [x] No universal batching multiplier or capacity claim is made.

No correctness or publication defect was discovered. P6 is accepted. Partial-success
bulk results require a separate structured-result API if later justified. String-based
fluent queries and SearchSession remain deferred to v2.1.
