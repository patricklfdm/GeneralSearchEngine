# GeneralSearchEngine v2 P4 performance baseline

## Status

The complete 58-row P4 matrix is accepted. Correctness, compatibility, release,
reproducibility, benchmark packaging, and every phase-specific performance gate pass.
Every indexed query setup agreed with its exhaustive analyzed scan oracle.

These measurements are environment- and workload-specific regression baselines, not
universal performance guarantees, exact speedup claims, or portable crossover rules.

## Matrix

The P4 benchmark group separates final search, candidate construction, query analysis,
index publication, and index build costs.

| Benchmark | Dimensions | Expected rows |
|---|---|---:|
| `TextTermQueryBenchmark` | indexed/scanned/posting-only × 7 document-frequency bands | 21 |
| `TextMultiTermQueryBenchmark` | 7 operations × 1/4/8 query terms | 21 |
| `TextIndexPublicationBenchmark` | 10K/100K vocabulary × 1/10/100/1000 mutations | 8 |
| `TextIndexBuildBenchmark` | raw/dynamic × 4/16 tokens × 1K/10K vocabulary | 8 |
| **Total** | | **58** |

Term and multi-term query cases use 100,000 documents. Term frequency bands are
0.01%, 0.1%, 1%, 10%, 25%, 50%, and 100%. Build cases use 10,000 documents. Every setup
self-checks indexed results against exhaustive analyzed scan results before measurement.

The publication matrix changes a small batch in dictionaries with approximately 10,000
or 100,000 distinct terms. Its purpose is to confirm that small-batch publication grows
with changed terms and persistent-tree depth rather than silently copying the entire
vocabulary. GC profiling records allocation; retained-memory sizing is not inferred
from allocation and requires a separate heap analysis if needed for P5 capacity work.

## Environment

- JMH 1.37
- OpenJDK 64-Bit Server VM 22.0.2+9-70
- one benchmark thread and two forks
- no explicit JVM arguments
- query benchmarks: three one-second warmups and five one-second measurements
- build/publication benchmarks: two one-second warmups and five one-second measurements

## Results

### Single-term selectivity

Search latency is derived from measured throughput. Posting-only latency is the direct
term dictionary lookup and immutable bitmap return. Allocation is normalized B/op.

| Document frequency | Indexed ms/op | Scan ms/op | Posting-only µs/op | Indexed allocation | Scan allocation |
|---:|---:|---:|---:|---:|---:|
| 0.01% | 0.0066 | 57.35 | 0.127 | 8.8 KB | 75.1 MB |
| 0.1% | 0.065 | 61.69 | 0.129 | 85.8 KB | 75.1 MB |
| 1% | 0.659 | 58.66 | 0.159 | 0.87 MB | 75.2 MB |
| 10% | 7.23 | 56.65 | 0.128 | 8.64 MB | 76.2 MB |
| 25% | 17.72 | 59.59 | 0.129 | 21.56 MB | 77.9 MB |
| 50% | 35.37 | 61.47 | 0.127 | 43.21 MB | 80.8 MB |
| 100% | 70.03 | 70.96 | 0.159 | 86.00 MB | 86.00 MB |

The dictionary lookup remains essentially flat because a term query reuses one
published posting bitmap without constructing a candidate union. Indexed end-to-end
cost and allocation grow with matched documents because `SnapshotSearcher` deliberately
retains the established final `Query.matches(...)` verification boundary. At 100%
document frequency both paths analyze and retain every document and are approximately
equal in this workload. P4 does not encode a selectivity crossover.

The throughput confidence intervals are wider for several very fast posting-only and
selective cases, so the table is interpreted by scale and trend rather than exact
ratios.

### Any/all query terms

The corpus deterministically changes result cardinality as terms are added. Latency is
derived from measured throughput.

| Query terms | Any results | Indexed any ms/op | Scan any ms/op | All results | Indexed all ms/op | Scan all ms/op |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50,000 | 36.76 | 70.35 | 50,000 | 32.42 | 63.74 |
| 4 | 73,334 | 55.66 | 72.96 | 1,667 | 2.38 | 68.99 |
| 8 | 77,143 | 55.06 | 71.64 | 40 | 0.288 | 67.73 |

Any-term union-only cost was 0.163 µs, 23.43 µs, and 42.33 µs for 1, 4, and 8 terms.
All-term intersection-only cost was 0.175 µs, 517.83 µs, and 228.86 µs. The eight-term
intersection is cheaper than the four-term case here because smallest-posting-first
execution rapidly reduces the intermediate bitmap to only 40 final documents; it is
not a claim that more terms are generally cheaper.

Query analysis itself remained below 0.7 µs/op with at most 868 B/op in this matrix.
Final document analysis and result collection dominate high-cardinality any queries,
while selective all queries benefit strongly from exact posting intersection.

### Immutable publication

| Vocabulary | Mutation batch | Publication µs/op | Allocation B/op |
|---:|---:|---:|---:|
| 10K | 1 | 1.63 | 4,648 |
| 10K | 10 | 17.95 | 44,960 |
| 10K | 100 | 236.20 | 447,662 |
| 10K | 1,000 | 2,792.45 | 4,555,651 |
| 100K | 1 | 2.14 | 5,080 |
| 100K | 10 | 21.01 | 49,264 |
| 100K | 100 | 273.25 | 489,706 |
| 100K | 1,000 | 3,264.88 | 4,949,193 |

Increasing vocabulary by ten times raises normalized allocation by only about 9–10%
at equal batch sizes. Latency changes are similarly bounded in the stable batch rows,
while work grows primarily with the mutation batch. This is consistent with persistent
AVL path copying and rules out an unexplained full-vocabulary copy in this workload.

The 100K/one-mutation latency mean has a 49% relative error because one of ten samples
was 4.09 µs; the other samples cluster around 1.86–2.27 µs. Its allocation is stable at
about 5,080 B/op, and the 10/100/1,000-mutation rows confirm the structural conclusion,
so the outlier does not block P4 acceptance.

### Raw and dynamic index build

All cases use 10,000 documents. Allocation is normalized per completed build.

| Tokens/document | Vocabulary | Raw ms/op | Dynamic ms/op | Raw allocation | Dynamic allocation |
|---:|---:|---:|---:|---:|---:|
| 4 | 1K | 24.83 | 26.08 | 50.5 MB | 50.7 MB |
| 4 | 10K | 32.83 | 33.23 | 50.7 MB | 50.9 MB |
| 16 | 1K | 106.36 | 107.67 | 204.0 MB | 204.1 MB |
| 16 | 10K | 146.19 | 135.90 | 178.3 MB | 178.4 MB |

Build time is driven mainly by analyzed token/posting work. Dynamic lifecycle builds
track raw builds closely and add only a small, stable allocation increment in every
case. The 4-token/1K dynamic row and 16-token/10K raw row contain wider timing
intervals, so their means are not used to advertise exact lifecycle overhead.

The lower allocation of the 16-token/10K case versus 16-token/1K reflects shallower
per-posting term-frequency maps: the same total token count is distributed across more
terms. It is workload structure, not evidence that a larger vocabulary universally
uses less memory.

## Full local commands

From the repository root, first build and inspect the benchmark JAR:

```bash
mvn -Pjmh -DskipTests clean package
java -jar target/benchmarks.jar -l
```

Then run the four matrices. The benchmark annotations use two forks, three one-second
warmups, and five one-second measurements unless a command explicitly overrides them.

```bash
java -jar target/benchmarks.jar '.*TextTermQueryBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p4-text-term.json

java -jar target/benchmarks.jar '.*TextMultiTermQueryBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p4-text-multi.json

java -jar target/benchmarks.jar '.*TextIndexPublicationBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p4-text-publication.json

java -jar target/benchmarks.jar '.*TextIndexBuildBenchmark.*' \
  -prof gc -rf json -rff target/jmh-p4-text-build.json
```

The commands are independent and may be run one at a time. Preserve all four JSON
files for review.

## Validation

The benchmark JAR and reduced smoke runs first verified startup, parameter wiring,
result equality assertions, dynamic build/drop, and output generation. The subsequent
formal run produced all 58 expected result rows with no setup or measurement failures.

The non-performance P4 gates pass:

- `mvn clean test`: 97 tests;
- `mvn clean -Papi-compat test`: 3 frozen-v1 fixture tests;
- `mvn clean -Prelease verify`: tests, strict Javadocs, artifacts, and signatures;
- `bash scripts/verify-reproducible-build.sh`: main, sources, and Javadoc JARs match
  byte-for-byte across clean builds.

## Acceptance checklist

- [x] All 58 expected JMH rows are present and successful.
- [x] Every indexed setup matches its exhaustive analyzed scan oracle.
- [x] Term behavior is reviewed across all seven document-frequency bands.
- [x] Any/all behavior and allocation are reviewed at 1, 4, and 8 query terms.
- [x] 10K versus 100K vocabulary publication shows no unexplained full-copy behavior.
- [x] Raw and dynamic build costs are recorded by token and vocabulary size.
- [x] Environment, JDK, JMH, forks, warmups, measurements, latency, and allocation are
      recorded with the accepted results.
- [x] No universal crossover, speedup, or memory claim is made.

No correctness defect was discovered in P4. The complete phase is accepted; BM25,
ranking, phrase/position queries, fuzzy search, persistence, and distributed search
remain outside P4.
