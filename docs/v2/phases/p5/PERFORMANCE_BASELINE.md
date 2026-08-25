# GeneralSearchEngine v2 P5 performance baseline

## Status

The complete 70-row P5 matrix is accepted. Correctness, API compatibility, release,
reproducibility, benchmark packaging, and every phase-specific performance gate pass.
Every bounded top-K setup agreed with its exhaustive full-sort oracle before
measurement.

These measurements are environment- and workload-specific regression baselines. They
are not universal latency, memory, speedup, top-K scaling, or crossover guarantees.

## Matrix

| Benchmark | Dimensions | Rows |
|---|---|---:|
| `Bm25TopKBenchmark` | bounded/full-sort × 3 document frequencies × 4 K values × 2 filter modes | 48 |
| `Bm25MultiTermBenchmark` | filtered/unfiltered × 1/4/8 scoring terms | 6 |
| `RankedMetadataPublicationBenchmark` | 10K/100K vocabulary × 1/10/100/1000 mutations | 8 |
| `TextIndexBuildBenchmark` | raw/dynamic × 4/16 tokens × 1K/10K vocabulary | 8 |
| **Total** | | **70** |

The ranking workloads use 100,000 documents. Single-term document-frequency bands are
0.1%, 10%, and 50%; K is 1, 10, 100, or 100,000. `CATEGORY_10` is an indexed structured
filter matching one tenth of document IDs. In the single-term corpus it therefore
reduces eligible hits to approximately one tenth of the scoring posting.

The metadata publication workload changes postings and document length together. The
build matrix reruns the P4 raw/dynamic corpus after immutable P5 length statistics were
added. GC profiling records normalized allocation, not retained heap size.

## Environment

- JMH 1.37
- OpenJDK 64-Bit Server VM 22.0.2+9-70
- one benchmark thread and two forks
- no explicit JVM arguments
- ranking benchmarks: three one-second warmups and five one-second measurements
- build/publication benchmarks: two one-second warmups and five one-second measurements

## Results

### Bounded top-K versus exhaustive full sort

Latency is average milliseconds per operation. Allocation is normalized per operation
and shown in decimal KB or MB. `K=100000` returns all eligible hits in every corpus.

Unfiltered scoring:

| Document frequency | K | Bounded ms | Full-sort ms | Bounded allocation | Full-sort allocation |
|---:|---:|---:|---:|---:|---:|
| 0.1% | 1 | 0.0090 | 0.0139 | 3.87 KB | 3.34 KB |
| 0.1% | 10 | 0.0108 | 0.0143 | 4.22 KB | 3.41 KB |
| 0.1% | 100 | 0.0241 | 0.0145 | 8.18 KB | 4.13 KB |
| 0.1% | 100,000 | 0.0243 | 0.0147 | 8.18 KB | 4.15 KB |
| 10% | 1 | 2.849 | 3.020 | 0.637 MB | 0.628 MB |
| 10% | 10 | 2.756 | 2.986 | 0.637 MB | 0.628 MB |
| 10% | 100 | 2.712 | 3.364 | 0.641 MB | 0.629 MB |
| 10% | 100,000 | 5.442 | 3.399 | 1.089 MB | 0.708 MB |
| 50% | 1 | 14.736 | 14.430 | 3.197 MB | 3.127 MB |
| 50% | 10 | 15.579 | 14.400 | 3.197 MB | 3.127 MB |
| 50% | 100 | 14.725 | 16.055 | 3.201 MB | 3.128 MB |
| 50% | 100,000 | 25.768 | 16.971 | 5.427 MB | 3.527 MB |

Scoring with the indexed 10% category filter:

| Document frequency | K | Bounded ms | Full-sort ms | Bounded allocation | Full-sort allocation |
|---:|---:|---:|---:|---:|---:|
| 0.1% | 1 | 0.0031 | 0.0036 | 2.46 KB | 0.84 KB |
| 0.1% | 10 | 0.0038 | 0.0036 | 2.84 KB | 0.93 KB |
| 0.1% | 100 | 0.0038 | 0.0036 | 2.84 KB | 0.91 KB |
| 0.1% | 100,000 | 0.0038 | 0.0040 | 2.86 KB | 0.93 KB |
| 10% | 1 | 0.425 | 0.528 | 0.093 MB | 0.099 MB |
| 10% | 10 | 0.435 | 0.538 | 0.093 MB | 0.099 MB |
| 10% | 100 | 0.490 | 0.544 | 0.098 MB | 0.100 MB |
| 10% | 100,000 | 0.676 | 0.577 | 0.136 MB | 0.107 MB |
| 50% | 1 | 2.015 | 2.903 | 0.465 MB | 0.496 MB |
| 50% | 10 | 2.047 | 2.901 | 0.465 MB | 0.496 MB |
| 50% | 100 | 2.021 | 2.921 | 0.469 MB | 0.496 MB |
| 50% | 100,000 | 3.217 | 3.082 | 0.691 MB | 0.536 MB |

The bounded heap is useful when K is small relative to a sufficiently large eligible
set and sorting dominates. The clearest case here is the filtered 50%-frequency corpus,
where K=1/10/100 remains around 2.0 ms while full sort remains around 2.9 ms. Several
unfiltered cases are close enough, or variable enough, that their means are not a basis
for exact speedup claims. At 0.1% frequency there are only 100 unfiltered hits and about
10 filtered hits, so fixed costs dominate.

The widest top-K relative score error is 18.5% in the unfiltered 0.1%/K=10 bounded
row. The widest relative errors in the multi-term, publication, and build matrices are
4.8%, 2.6%, and 9.5%, respectively. Close means, especially in the fastest and widest-
interval rows, are treated as approximately equal rather than as stable winners.

Returning all hits removes the bounded-retention advantage and makes heap maintenance
more expensive than the control's array sort in most rows. This is an expected
workload boundary, not a correctness defect. P5 does not choose between heap and full
sort using a cost model.

The heap retains at most K candidates, but the current scorer still creates a
short-lived candidate object for each eligible scored document. Normalized allocation
therefore tracks candidate count and is often close to the exhaustive control for
small K; it does not fall in proportion to K. Eliminating that transient allocation is
possible future optimization work, not a P5 acceptance requirement or performance
guarantee.

### Multi-term scoring and structured filtering

| Query terms | Unfiltered ms/op | Filtered ms/op | Unfiltered allocation | Filtered allocation |
|---:|---:|---:|---:|---:|
| 1 | 15.24 | 3.48 | 3.20 MB | 0.93 MB |
| 4 | 43.44 | 7.38 | 8.27 MB | 1.48 MB |
| 8 | 73.33 | 12.36 | 13.64 MB | 2.13 MB |

Latency and allocation grow as more postings contribute candidates and scores. Growth
is not strictly proportional to query-term count because postings overlap. The indexed
category filter materially reduces eligible scoring work in this corpus, and its
benefit grows with the unfiltered union, but these ratios are specific to the synthetic
10% filter and term distributions.

### Immutable ranking-metadata publication

| Vocabulary | Mutation batch | Publication us/op | Allocation B/op |
|---:|---:|---:|---:|
| 10K | 1 | 2.53 | 7,476 |
| 10K | 10 | 24.40 | 63,524 |
| 10K | 100 | 316.10 | 642,716 |
| 10K | 1,000 | 3,678.84 | 6,694,435 |
| 100K | 1 | 2.92 | 8,420 |
| 100K | 10 | 28.58 | 70,612 |
| 100K | 100 | 359.38 | 711,383 |
| 100K | 1,000 | 4,310.62 | 7,344,267 |

Publication grows primarily with the number of changed documents/terms. Increasing
vocabulary by ten times raises latency by roughly 14-17% and allocation by roughly
10-13% at equal batch sizes in this workload. This is consistent with persistent-tree
path copying for both postings and document lengths and shows no unexplained full-
vocabulary copy. The values must not be extrapolated as universal mutation scaling.

### Text-index build with length metadata

All cases build 10,000 documents.

| Tokens/document | Vocabulary | Raw ms/op | Dynamic ms/op | Raw allocation | Dynamic allocation |
|---:|---:|---:|---:|---:|---:|
| 4 | 1K | 28.38 | 28.37 | 60.53 MB | 60.66 MB |
| 4 | 10K | 37.37 | 37.35 | 60.70 MB | 60.95 MB |
| 16 | 1K | 113.14 | 113.92 | 214.12 MB | 214.12 MB |
| 16 | 10K | 148.94 | 150.06 | 188.41 MB | 188.42 MB |

Build cost remains driven by analyzed token and posting work. Dynamic lifecycle builds
track raw builds closely, so publishing immutable document-length metadata does not
introduce a separate lifecycle bottleneck in this matrix. The 16-token/10K timing rows
have wider confidence intervals and are interpreted by scale, not their exact means.

## Reproduction commands

```bash
mvn -Pjmh -DskipTests clean package

java -jar target/benchmarks.jar '.*Bm25TopKBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p5-top-k.json

java -jar target/benchmarks.jar '.*Bm25MultiTermBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p5-multi-term.json

java -jar target/benchmarks.jar '.*RankedMetadataPublicationBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p5-publication.json

java -jar target/benchmarks.jar '.*TextIndexBuildBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p5-build.json
```

## Validation

- all 70 expected JMH rows are present and successful;
- every setup's bounded result matched the exhaustive document and score oracle;
- `mvn clean test`: PASS, 106 tests;
- `mvn clean -Papi-compat test`: PASS, 3 frozen-v1 fixture tests;
- `mvn clean -Prelease verify`: PASS, including strict Javadocs and signed artifacts;
- reproducible main, sources, and Javadoc JARs: PASS;
- benchmark package, discovery, and reduced smoke runs: PASS.

## Acceptance checklist

- [x] All 70 expected rows are present and successful.
- [x] Every bounded top-K setup matches the full-sort control.
- [x] K=1/10/100/all behavior is reviewed at low, medium, and high document frequency.
- [x] Structured filter behavior and multi-term scaling are recorded.
- [x] Heap retention and total allocation are compared with exhaustive full sort.
- [x] Posting plus document-length publication remains bounded across vocabulary sizes.
- [x] Raw and dynamic metadata build costs are recorded.
- [x] Environment, variance, latency, allocation, and workload limitations are stated.
- [x] No universal speedup or scalability claim is made.

No correctness issue was discovered. P5 is accepted. Cost-based heap-versus-full-sort
selection, candidate-allocation reduction, and retained-heap capacity sizing remain
future performance work. Phrase/position queries, fuzzy search, persistence/WAL, and
distributed score merging remain explicitly out of scope.
