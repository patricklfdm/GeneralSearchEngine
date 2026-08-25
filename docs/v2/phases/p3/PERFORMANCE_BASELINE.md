# GeneralSearchEngine v2 P3 performance baseline

## Status

The complete P3 matrix is accepted. An initial diagnostic run exposed one cost-model
tie decision and two integer-overflow defects in the bucket-spread benchmark setup.
After minimal corrections, all affected parameter combinations, correctness gates,
compatibility gates, release validation, and reproducible-build checks pass.

The measurements are environment- and workload-specific regression baselines, not
universal performance guarantees. In particular, no selectivity percentage is an
exact or portable index-versus-scan crossover.

## Accepted planner behavior

- Direct Range queries compare immutable snapshot-local estimates with active-document
  scan work before candidate construction.
- `COST_AWARE`, `FORCE_INDEX`, and `FORCE_SCAN` provide same-environment controls.
- Planner inspection estimates every built-in eligible path but materializes only the
  selected path. Legacy non-estimating indexes retain their compatibility fallback.
- AND starts from one lowest-cost useful estimated path. An additional exact path is
  materialized only when its cardinality gives a guaranteed verification reduction
  larger than its construction/intersection work; skipped children leave a safe
  `SUPERSET` for final predicate verification.
- OR and NOT deliberately retain compatibility planning. Cost-aware OR/NOT remains
  future work.
- Approximate or stale estimates may make execution slower, but final
  `Query.matches(...)` verification preserves correctness.

The accepted relative-work weights are deliberately internal rather than a public
tuning API. They account for estimated candidate documents, matched source buckets,
estimate quality, and active documents. Equal modeled Range index and scan work favors
the already-published index, based on the same-environment control evidence below.

## Bounded estimate acquisition

Persistent Range and Prefix AVL nodes now retain immutable subtree entry counts and
candidate-cardinality weights. Range/prefix estimates use two tree-prefix aggregates,
so estimate acquisition is proportional to tree height instead of matched bucket
count. Candidate bitmap materialization still visits and combines the matching buckets.
Randomized tests cover updates, removals, inclusive/exclusive/unbounded ranges,
reversed bounds, negative-weight rejection, and old-snapshot isolation.

## Results

Environment: JMH 1.37, OpenJDK 22.0.2, 100,000 documents, one thread, two forks,
three one-second warmups, and five one-second measurements. No explicit JVM options
were supplied.

### Range estimate

Estimate acquisition is µs/op; allocation was approximately 32 B/op throughout.

| Selectivity | Estimate µs/op | Materialize µs/op |
|---:|---:|---:|
| 0.01% | 0.141 | 1.255 |
| 0.1% | 0.147 | 12.858 |
| 1% | 0.151 | 81.918 |
| 10% | 0.152 | 1,295.569 |
| 25% | 0.151 | 2,198.020 |
| 50% | 0.151 | 5,494.566 |
| 100% | 0.162 | 15,384.554 |

The estimate is effectively flat across the selectivity matrix. This resolves the P2
handoff where a 100%-selective estimate took milliseconds because it traversed every
matched bucket. Candidate materialization still scales with matched documents and
sources, as expected. The 10% and 100% materialization scores have wide error intervals,
so they are not treated as precise regressions or speedups.

### Calibrated Range path selection

Throughput is ops/s. The selected path is inferred from cost-aware allocation and its
agreement with the forced control.

| Selectivity | Cost-aware | Forced index | Forced scan | Final choice |
|---:|---:|---:|---:|---|
| 0.01% | 250,926 | 285,280 | 232 | index |
| 0.1% | 33,939 | 30,782 | 286 | index |
| 1% | 3,500 | 3,563 | 261 | index |
| 10% | 449 | 461 | 275 | index |
| 25% | 274 | 157 | 252 | scan |
| 50% | 237 | 87 | 283 | scan |
| 100% | 231 | 40 | 252 | scan |

Cost-aware normalized allocation matches forced index through 10% and forced scan from
25%, independently confirming the chosen path. The controls show that index is useful
through 10% in this workload, while scan is preferable from 25%. The initial diagnostic
model rejected 10% only because modeled work was exactly equal and the comparison used
strict `<`; resolving equality in favor of the index (`<=`) corrects that decision and
has a deterministic boundary regression test. No selectivity percentage is encoded in
the model, and this observed crossover is not a portable threshold.

### Bucket spread

The corrected matrix demonstrates that equal result cardinality does not imply equal
index work:

| Distinct values | Selectivity | Sources | Estimate µs/op | Materialize µs/op |
|---:|---:|---:|---:|---:|
| 100 | 1% | 1 | 0.044 | 0.106 |
| 100 | 25% | 25 | 0.054 | 3.837 |
| 10,000 | 1% | 100 | 0.097 | 11.864 |
| 10,000 | 25% | 2,500 | 0.099 | 302.055 |
| 100,000 | 1% | 1,000 | 0.151 | 82.064 |
| 100,000 | 25% | 25,000 | 0.151 | 2,169.386 |

For a fixed distinct-value count, estimate time is essentially independent of
selectivity, while materialization grows with source count. Across dictionary sizes,
estimate time grows only with tree height and remains sub-microsecond here. The initial
100,000-distinct setup failures came from two benchmark-only `int` multiplications;
both now use `long`, and all 12 corrected rows pass cardinality assertions.

### Conservative AND

Times are µs/op; allocation is normalized B/op.

| Correlation | Planned | Scan | Planned allocation | Scan allocation |
|---|---:|---:|---:|---:|
| Positive | 811 | 5,219 | 2,088,902 | 19,368,824 |
| Negative | 430 | 5,002 | 1,441,758 | 14,399,866 |
| Independent-like | 473 | 4,553 | 1,456,552 | 14,414,846 |

Every setup compared planned results with the full-scan oracle. Planning is materially
faster and allocates less in all three distributions. Correlation changes final result
work but does not justify adding an independence assumption or speculative additional
bitmap construction.

No correctness issue was found in production code. The only first-run failures were
benchmark setup arithmetic, and estimate/model errors remained performance-only.

## Full local validation commands

Build and inspect the benchmark JAR first:

```bash
mvn -Pjmh -DskipTests clean package
java -jar target/benchmarks.jar -l
```

Run these four commands from the repository root. They use the benchmark annotations'
two forks, three one-second warmups, and five one-second measurements.

```bash
java -jar target/benchmarks.jar '.*RangeEstimateBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-range-estimate.json

java -jar target/benchmarks.jar '.*RangeIndexComparisonBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-range-planner.json

java -jar target/benchmarks.jar '.*RangeBucketSpreadBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-range-buckets.json

java -jar target/benchmarks.jar '.*AndPlannerBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-and-planner.json
```

Expected matrices:

| Result file | Dimensions | Expected rows |
|---|---|---:|
| `jmh-p3-range-estimate.json` | estimate/materialize × 7 selectivities | 14 |
| `jmh-p3-range-planner.json` | cost-aware/forced-index/forced-scan/candidate × 7 selectivities | 28 |
| `jmh-p3-range-buckets.json` | estimate/materialize × 3 distinct counts × 2 selectivities | 12 |
| `jmh-p3-and-planner.json` | planned/scan × 3 correlations | 6 |

The Range selectivity matrix is 0.01%, 0.1%, 1%, 10%, 25%, 50%, and 100% over
100,000 documents. Bucket-spread cases use 100, 10,000, and 100,000 distinct values at
1% and 25%. AND covers positive, negative, and independent-like child correlation.

The corrected affected-matrix rerun used:

```bash
java -jar target/benchmarks.jar '.*RangeIndexComparisonBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-range-planner.json

java -jar target/benchmarks.jar '.*RangeBucketSpreadBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p3-range-buckets.json
```

## Acceptance checklist

- [x] All 60 expected result rows were observed and successful after correction.
- [x] Cost-aware, forced-index, and forced-scan result counts are equal.
- [x] Selective Range cases choose a useful index path in this workload.
- [x] Sufficiently expensive Range cases choose scan in this workload.
- [x] Estimate acquisition stays bounded as matched cardinality grows.
- [x] Bucket spread is reflected in materialization cost and planner interpretation.
- [x] Every AND correlation matches its full-scan oracle.
- [x] Latency, allocation, environment, and model calibration are recorded here.
- [x] No universal crossover or exact speedup claim is made.

No correctness issue was found. `mvn clean test`, the frozen-v1 API fixture, strict
release/Javadoc/signing verification, and reproducible main/sources/Javadoc builds all
pass. Cost-aware OR/NOT, public planner metrics, and any further cost-model expansion
remain deferred; P3 is complete.
