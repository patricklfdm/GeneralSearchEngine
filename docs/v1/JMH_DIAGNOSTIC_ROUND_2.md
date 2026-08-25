# JMH diagnostic round 2

This round investigates the first 100,000-product baseline without changing engine
behavior. Run it on the same JDK, heap, collector, operating system, and hardware as
the first baseline.

## Build

From the IntelliJ terminal:

```bash
mvn -Pjmh -DskipTests clean package
java -jar target/benchmarks.jar -l
```

Use the forked `benchmarks.jar` process for recorded results. Running a benchmark
class directly from the IDE is suitable only for debugging setup.

## Range index versus scan

`RangeIndexComparisonBenchmark` runs indexed and scanned queries over the same price
field with identical bounds and verifies that both return the same number of products.
The selectivity parameter covers 0.01%, 0.1%, 1%, 10%, 25%, 50%, and 100%.

`rangeCandidateOnly` measures index candidate construction without search-result List
materialization. Compare it with `indexedPriceRange` to estimate the additional cost
of candidate verification and result collection; do not directly compare its absolute
throughput with `scannedPriceRange` as if they performed the same work.

```bash
java -jar target/benchmarks.jar 'RangeIndexComparisonBenchmark.*' \
  -p productCount=100000 \
  -p selectivityPercent=0.01,0.1,1.0,10.0,25.0,50.0,100.0 \
  -prof gc \
  -rf json -rff target/jmh-range-round-2.json
```

Record throughput and `gc.alloc.rate.norm` for every benchmark/selectivity pair. The
indexed-versus-scanned comparison is valid only within the same selectivity row.

## Mutation batch scaling

`MutationBatchScalingBenchmark` reports total milliseconds and allocation per batch,
not normalized per document. It tests batches of 1, 10, 100, and 1,000 updates. The
benchmark checks the snapshot version around every measured invocation and fails if
the engine publishes more than once, preventing an accidentally split batch from being
reported as a single-publication result. The reported time and allocation include the
two lightweight metrics snapshots used for this assertion; this is a fixed diagnostic
overhead and should be retained consistently across every batch-size comparison.

```bash
java -jar target/benchmarks.jar 'MutationBatchScalingBenchmark.*' \
  -p productCount=100000 \
  -p batchSize=1,10,100,1000 \
  -prof gc \
  -rf json -rff target/jmh-mutation-scaling-round-2.json
```

For interpretation, divide the reported batch time and bytes per batch by `batchSize`
to derive per-document amortized values. Preserve both the original batch totals and
the derived values in the report.

## Optional profiler pass

After the normal measurement succeeds, run a narrower profiler pass for the suspicious
cases rather than profiling the entire matrix:

```bash
java -jar target/benchmarks.jar \
  'RangeIndexComparisonBenchmark.(indexedPriceRange|rangeCandidateOnly)' \
  -p productCount=100000 -p selectivityPercent=25.0,100.0 \
  -prof jfr \
  -f 1 -wi 2 -i 3 -r 2s
```

## Result record

Keep the following with both JSON files:

- exact command line and Git commit;
- JDK vendor and full version;
- operating system and architecture;
- CPU model and available cores;
- heap size, collector, and any JVM options;
- JMH score, error/confidence interval, units, and normalized allocation;
- profiler output when collected.

These remain diagnostic baselines, not user-facing performance guarantees.
