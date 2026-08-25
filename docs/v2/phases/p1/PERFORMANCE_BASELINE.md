# GeneralSearchEngine v2 P1 performance baseline

## Purpose

This document records the P1 statistics and materialization-free estimate baseline. It
is an environment- and workload-specific regression reference for P2 bitmap/publication
work and P3 cost planning, not a universal performance guarantee.

No planner behavior changed in P1. The estimate benchmark calls the optional index
capability directly; normal search still follows the v1 candidate planner.

## Environment

- Documents: 100,000 for Range estimation; 10,000 for publication scaling
- JMH: 1.37
- JVM: OpenJDK 22.0.2, no explicit JVM options
- Hardware: Apple M2 MacBook Air, 8 CPU cores, 8 GB memory
- OS: Darwin 24.6.0, arm64
- Threads: 1
- Forks: 2
- Range warmup/measurement: 3 × 1 second / 5 × 1 second per fork
- Publication warmup/measurement: 2 × 1 second / 5 × 1 second per fork
- Profiler: JMH `gc`

Commands:

```bash
mvn -Pjmh -DskipTests clean package

java -jar target/benchmarks.jar 'RangeEstimateBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p1-range-estimate.json

java -jar target/benchmarks.jar 'IndexStatisticsPublicationBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p1-statistics-publication.json
```

Files under `target` are disposable raw output and are not committed.

## Range estimate versus candidate materialization

The dataset uses one distinct ordered value per document. Consequently, matched
documents and visited Range buckets are equal in this workload. Reported errors are the
JMH 99.9% confidence interval.

| Selectivity | Matched documents/buckets | Estimate µs/op | Estimate B/op | Materialize µs/op | Materialize B/op |
|---:|---:|---:|---:|---:|---:|
| 0.01% | 10 | 0.114 ± 0.001 | 144 | 1.611 ± 0.019 | 6,596 |
| 0.1% | 100 | 0.944 ± 0.309 | 200 | 15.704 ± 0.852 | 62,848 |
| 1% | 1,000 | 13.221 ± 0.442 | 256 | 176.632 ± 1.436 | 624,441 |
| 10% | 10,000 | 114.345 ± 1.569 | 257 | 1,779.517 ± 3.934 | 6,240,468 |
| 25% | 25,000 | 314.838 ± 45.659 | 258 | 4,596.218 ± 33.295 | 15,600,488 |
| 50% | 50,000 | 610.248 ± 56.984 | 260 | 11,854.350 ± 228.237 | 35,557,818 |
| 100% | 100,000 | 1,991.233 ± 100.333 | 270 | 25,880.470 ± 341.179 | 76,357,912 |

### Interpretation

- Every Range estimate exactly matched the eventual candidate cardinality.
- Estimate allocation stayed bounded at roughly 144–270 B/op and did not grow with the
  candidate-document count. It contains small result/view/iterator objects, not a
  candidate bitmap.
- Estimate latency still grows with matching distinct buckets because the current
  ordered map sums their disjoint bitmap cardinalities. P1 deliberately records this
  work instead of adding a cumulative structure that could increase write cost.
- Candidate materialization allocation grows strongly with the number of matched
  documents under the current repeated immutable bitmap union. P2 is responsible for
  replacing that accumulation pattern and rerunning this matrix.
- These results do not define an index-versus-scan threshold. P3 must combine estimate
  cost, source count, materialization cost, candidate count, and final verification cost.

## Statistics/index publication scaling

The publication benchmark keeps 10,000 indexed documents constant, swaps the values of
two documents, and publishes a new Range index snapshot. The swap preserves the exact
indexed-document and distinct-key counts.

| Distinct keys | Publication ms/op | Allocation B/op |
|---:|---:|---:|
| 100 | 0.0033 ± 0.0001 | 11,440 |
| 10,000 | 0.3648 ± 0.0377 | 962,267 |

The current snapshot representation copies its ordered value map during publication,
so both time and allocation grow substantially with total distinct-key count even when
only two keys are dirty. This confirms the P0 write-amplification risk and provides the
control result for P2's bounded dirty-overlay versus persistent-structure evaluation.

This microbenchmark measures direct Range index publication, not the complete engine
writer queue, document table, business-ID map, or end-to-end mutation future.

## Correctness conclusion

No correctness issue was discovered. Unit and randomized tests verify exact estimate
parity with materialized candidates, immutable snapshot statistics, null and reversed
range behavior, document-ID holes, legacy non-estimating indexes, and dynamic index
mutation replay.
