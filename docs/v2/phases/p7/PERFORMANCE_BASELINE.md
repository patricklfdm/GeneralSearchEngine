# GeneralSearchEngine v2 P7 performance baseline

## Status and scope

The representative P7 JMH regression matrix is accepted: all 141 expected primary
rows completed successfully and every benchmark setup assertion passed. The separate
300-second concurrency soak also passed, completing P7 validation.

These measurements are environment- and workload-specific regression evidence. They
are not universal latency, throughput, allocation, scaling, capacity, speedup, or
index-crossover guarantees.

## Environment and matrix

- JMH 1.37;
- OpenJDK 64-Bit Server VM 22.0.2+9-70;
- Apple arm64 target machine, one benchmark thread, two forks, no explicit JVM options;
- query/ranking: three one-second warmups and five one-second measurements;
- publication/build/bulk: two one-second warmups and five one-second measurements;
- GC profiler enabled;
- 34 structured, 37 text, 62 ranking, and 8 explicit-bulk rows.

All four JSON files contain finite primary and secondary scores. No benchmark failure,
cardinality mismatch, ranking-oracle mismatch, or publication assertion failure was
reported.

## Structured queries and mutation publication

Range throughput is operations/second over 100,000 documents. The selected path was
independently checked through normalized allocation against the forced controls.

| Selectivity | Cost-aware | Forced index | Forced scan | Selected path |
|---:|---:|---:|---:|---|
| 0.01% | 316,175 | 303,637 | 265 | index |
| 0.1% | 31,329 | 28,436 | 299 | index |
| 1% | 3,308 | 3,580 | 278 | index |
| 10% | 430 | 421 | 259 | index |
| 25% | 280 | 169 | 257 | scan |
| 50% | 206 | 88 | 213 | scan |
| 100% | 171 | 40 | 240 | scan |

The P3 decision boundary is preserved: selective queries use the Range index and broad
queries avoid candidate materialization. The 50% and 100% cost-aware throughput means
have wide intervals, but their allocation matches forced scan and the forced-scan
controls remain at the historical scale. No percentage is encoded as a universal
crossover threshold.

The historical opportunistic mutation-batch workload remains dominated by one fixed
immutable-snapshot publication:

| Batch | Total ms/op | Allocation/batch |
|---:|---:|---:|
| 1 | 24.40 | 7.07 MB |
| 10 | 23.35 | 7.14 MB |
| 100 | 26.11 | 7.75 MB |
| 1,000 | 18.09 | 10.50 MB |

The scores retain the expected fixed-cost amortization pattern. Their exact ordering
is not a batching guarantee. Dynamic build/drop measured 1.114 ms/op for Equality and
1.538 ms/op for Range over 10,000 documents.

## Analyzed text

Single-term end-to-end latency remains consistent with the P4 scale. Posting lookup is
approximately 0.14–0.16 microseconds throughout and allocates about 40 B/op.

| Document frequency | Indexed ms/op | Scan ms/op |
|---:|---:|---:|
| 0.01% | 0.0073 | 47.76 |
| 0.1% | 0.0651 | 46.74 |
| 1% | 0.650 | 57.19 |
| 10% | 6.79 | 54.42 |
| 25% | 17.36 | 63.48 |
| 50% | 36.31 | 63.92 |
| 100% | 68.18 | 73.44 |

Text publication continues to grow with the changed batch and persistent-tree depth,
not by copying the complete vocabulary:

| Vocabulary | Batch 1 | Batch 10 | Batch 100 | Batch 1,000 |
|---:|---:|---:|---:|---:|
| 10K | 1.72 us | 19.63 us | 259.01 us | 2.963 ms |
| 100K | 1.93 us | 22.88 us | 290.96 us | 3.585 ms |

Raw and dynamic text-index builds over 10,000 documents remain close in all four
token/vocabulary combinations. Their observed range was 28.34–162.35 ms/op, with
normalized allocation consistent with the P5 length-metadata baseline.

## BM25 ranking and metadata publication

The bounded top-K versus exhaustive-sort relationship is unchanged. Small K remains
useful for sufficiently large eligible sets, especially with the structured filter;
returning all eligible hits retains the expected heap overhead. Every setup matched
the exhaustive score/order oracle.

Multi-term top-10 latency remains at the P5 scale:

| Query terms | Unfiltered ms/op | Structured-filtered ms/op |
|---:|---:|---:|
| 1 | 15.17 | 3.49 |
| 4 | 44.25 | 7.36 |
| 8 | 72.12 | 12.57 |

Ranking-metadata publication allocation is stable at every batch/vocabulary pair. The
100K-vocabulary, batch-100 timing row was noisy, while its 711 KB/op allocation was
stable:

| Vocabulary | Batch 1 | Batch 10 | Batch 100 | Batch 1,000 |
|---:|---:|---:|---:|---:|
| 10K | 2.54 us | 24.72 us | 315.01 us | 4.006 ms |
| 100K | 2.94 us | 29.30 us | 535.45 us* | 4.430 ms |

`*` The formal row was `535.45 ± 420.29 us/op`. Its stable samples overlap the P5
baseline and two runs retained approximately 711 KB/op; isolated scheduler/GC stalls
reached 1.1 ms and 17.7 ms. The wide interval overlaps the historical result, so this
is recorded as environment noise rather than a structural regression.

## Explicit atomic bulk

| Batch | Successful ms/op | Invalid rollback ms/op | Successful allocation |
|---:|---:|---:|---:|
| 1 | 0.0111 | 0.0129 | 9.19 KB |
| 10 | 0.0166 | 0.0161 | 31.31 KB |
| 100 | 0.1030 | 0.0593 | 284.43 KB |
| 1,000 | 0.9345* | 0.4999 | 3.09 MB |

`*` The full-matrix batch-1,000 mean was distorted by one 6.42 ms sample. A targeted
two-fork confirmation measured `0.935 ± 0.071 ms/op`, with a 0.893–1.047 ms range and
the same 3.09 MB allocation. It confirms the P6 scaling and atomic-publication result.

All successful rows published exactly once. All invalid rows retained the previous
version and visible state.

## Acceptance conclusion

- planner choices and structured-query allocation behavior are preserved;
- analyzed-text, ranking, publication, build, and explicit-bulk results remain at the
  accepted P3–P6 scale;
- adverse means above 20% were accompanied by overlapping, very wide intervals and
  stable allocation, and targeted examination found isolated stalls rather than a
  repeatable regression;
- no correctness issue was discovered by the performance matrix;
- no P7 optimization or feature change is justified by these results.

The four formal JSON files and two diagnostic reruns remain disposable files under
`target` and must not be committed.
