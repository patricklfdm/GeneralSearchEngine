# GeneralSearchEngine v2 P2 performance baseline

## Purpose and status

This document records the accepted P2 bitmap and immutable-publication baseline. The
measurements are environment- and workload-specific regression evidence, not universal
performance guarantees. P2 changes internal representations only; it does not add
cost-based planning or new query behavior.

The complete JMH matrices and setup assertions passed. The evidence accepts the D3
hybrid representation and closes P2, with one explicit P3 handoff: broad Range estimates
remain proportional to matched distinct buckets and can themselves cost more than a
scan.

## Environment

- Documents: 100,000 for Bitmap, Range, and mutation batching
- Dictionary entries: 10,000 and 100,000
- Dirty dictionary entries: 1, 10, 100, and 1,000
- JMH: 1.37
- JVM: OpenJDK 22.0.2, no explicit JVM options
- Hardware: Apple M2 MacBook Air, 8 CPU cores, 8 GB memory
- OS: Darwin 24.6.0, arm64
- Threads: 1
- Forks: 2
- Warmup/measurement: 3 × 1 second / 5 × 1 second, except dictionary
  publication and index publication, which use 2 warmup iterations
- Profiler: JMH `gc`

Raw results are retained locally under `target/jmh-p2-*.json`. All seven result files
were present and complete: 112 Bitmap rows, 64 dictionary-publication rows, 16
dictionary-lookup rows, 14 Range-estimate rows, 21 Range-comparison rows, 2 direct
publication rows, and 4 batching rows.

## Bitmap accumulation

Range, Prefix, and composite OR use block-level bulk union and freeze at most once.
Single-source paths return the existing immutable bitmap directly.

The table uses disjoint sources and 1,000 requested sources. When fewer documents match
than requested sources, setup caps the actual source count at the matched-document
count. Times are µs/op; allocation is B/op.

| Selectivity | Repeated union | Single freeze | Repeated allocation | Single-freeze allocation |
|---:|---:|---:|---:|---:|
| 0.01% | 1.575 ± 0.020 | 0.997 ± 0.054 | 6,448 | 1,048 |
| 0.1% | 21.121 ± 0.079 | 11.164 ± 0.141 | 62,608 | 3,208 |
| 1% | 150.250 ± 0.363 | 118.495 ± 0.731 | 624,209 | 24,809 |
| 10% | 1,139.108 ± 1.954 | 497.236 ± 25.250 | 4,364,632 | 255,227 |
| 25% | 2,812.929 ± 91.609 | 1,161.383 ± 56.180 | 10,716,003 | 613,008 |
| 50% | 7,970.216 ± 23.013 | 2,488.715 ± 150.903 | 29,154,535 | 1,212,201 |
| 100% | 15,760.926 ± 78.516 | 5,078.106 ± 501.583 | 58,894,684 | 2,412,475 |

Duplicated-source membership shows the same allocation conclusion. One 1%-selective,
10-source duplicated case has nominally lower repeated-union time, but the single-freeze
confidence interval is very wide and overlaps the repeated result; it is not evidence
of a sparse-query regression. Single-source reuse measures about 0.002 µs/op with
effectively zero normalized allocation in this benchmark.

Conclusion: multi-source candidate construction no longer creates one immutable bitmap
per source. Allocation still grows with the final bitmap and dirty block count, as
expected, but no longer grows through repeated frozen intermediates.

## D3 immutable dictionary decision

The accepted representation is workload-shaped:

- Equality uses a dirty hash overlay capped at 12 layers, preserving arbitrary key
  types without adding an ordering requirement. A large dirty set or a thirteenth layer
  compacts into an immutable root.
- Range and Prefix use a persistent AVL dictionary because natural ordering is already
  part of their semantics. Updates and removals path-copy only affected nodes.
- Full HashMap and TreeMap copying remain benchmark controls only.

### Publication latency

The table shows UPDATE workloads in µs/op. REMOVE/RESTORE histories produced the same
overall ordering and exercised overlay tombstones and compaction.

| Entries | Dirty | Overlay | Persistent AVL | Full Hash copy | Full Tree copy |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 1 | 27.896 | 0.181 | 347.303 | 127.551 |
| 10,000 | 10 | 21.973 | 1.454 | 238.683 | 127.801 |
| 10,000 | 100 | 25.808 | 13.975 | 240.844 | 130.852 |
| 10,000 | 1,000 | 81.070 | 176.202 | 253.707 | 208.114 |
| 100,000 | 1 | 524.736 | 0.256 | 7,916.985 | 1,301.967 |
| 100,000 | 10 | 437.304 | 1.965 | 6,651.676 | 1,303.638 |
| 100,000 | 100 | 465.845 | 20.880 | 6,636.186 | 1,316.548 |
| 100,000 | 1,000 | 591.690 | 272.186 | 6,142.029 | 1,380.128 |

Representative normalized allocation confirms the trade-off:

| Entries | Dirty | Overlay B/op | Persistent AVL B/op | Full Hash B/op | Full Tree B/op |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 1 | 70,059 | 552 | 905,826 | 400,193 |
| 10,000 | 1,000 | 127,945 | 496,257 | 665,714 | 400,193 |
| 100,000 | 1 | 727,322 | 712 | 9,448,966 | 4,000,249 |
| 100,000 | 1,000 | 618,987 | 656,258 | 7,048,842 | 4,000,201 |

The overlay figures include periodic full compaction, so their steady-state average
still grows with dictionary size. This is an accepted, bounded trade-off for arbitrary
Equality keys: it remains materially below full HashMap copying while avoiding a new
persistent hash-trie correctness surface. Ordered and future naturally ordered term
dictionaries should prefer persistent structural sharing.

### Lookup latency

Times are ns/op; every lookup allocates approximately 16 B/op in this harness.

| Entries | Overlay depth | Overlay | Persistent AVL | Immutable Hash | Immutable Tree |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 0 | 4.869 | 26.288 | 4.543 | 54.166 |
| 10,000 | 12 | 84.237 | 28.415 | 7.158 | 55.590 |
| 100,000 | 0 | 4.881 | 35.329 | 4.555 | 74.911 |
| 100,000 | 12 | 48.182 | 35.464 | 7.206 | 75.551 |

The maximum overlay depth has a visible but bounded lookup cost. Randomized tests also
verify depth never exceeds 12, compaction preserves contents, removals do not reappear,
and old snapshots remain isolated.

## Direct ordered-index publication

This workload keeps 10,000 documents constant and swaps two Range values per
publication.

| Distinct keys | P1 ms/op | P2 ms/op | P1 B/op | P2 B/op |
|---:|---:|---:|---:|---:|
| 100 | 0.0033 | 0.000513 ± 0.000007 | 11,440 | 2,136 |
| 10,000 | 0.3648 | 0.000737 ± 0.000005 | 962,267 | 2,616 |

The P2 result scales with dirty paths rather than copying the complete ordered
dictionary. No exact speedup multiplier is claimed because the old and new
microsecond-scale measurements have different variance profiles.

## Post-P2 Range estimate and materialization

The dataset has one ordered value per document, so matched documents and visited
buckets are equal. Times are µs/op; allocation is B/op.

| Selectivity | Estimate µs/op | Estimate B/op | Materialize µs/op | Materialize B/op |
|---:|---:|---:|---:|---:|
| 0.01% | 0.188 ± 0.010 | 72 | 1.256 ± 0.007 | 880 |
| 0.1% | 0.851 ± 0.005 | 72 | 12.791 ± 0.239 | 3,040 |
| 1% | 12.047 ± 0.078 | 72 | 94.764 ± 20.637 | 32,645 |
| 10% | 122.842 ± 1.233 | 74 | 908.961 ± 30.917 | 404,237 |
| 25% | 296.941 ± 1.708 | 74 | 2,163.626 ± 6.487 | 1,010,671 |
| 50% | 953.755 ± 104.067 | 85 | 5,526.389 ± 206.369 | 2,023,707 |
| 100% | 8,368.443 ± 1,153.023 | 145 | 14,007.182 ± 345.581 | 4,052,267 |

Compared with P1, candidate materialization is faster throughout the matrix and its
allocation is much lower; at 100%, P1 recorded about 25,880 µs and 76.4 MB/op. Estimate
allocation also falls, but persistent-tree traversal increases estimate time at some
points. The 100% estimate rises from roughly 1,991 µs in P1 to 8,368 µs in P2.

This is accepted as a documented P3 constraint, not hidden as a P2 win. P3 must include
estimate acquisition in total path cost and must investigate bounded-cost Range
statistics or an early scan choice; fully walking the matched buckets merely to reject
the index can cost more than scanning.

## Index versus scan after P2

Throughput is ops/s for the same 100,000-document result set.

| Selectivity | Indexed Range | Candidate only | Full scan |
|---:|---:|---:|---:|
| 0.01% | 378,115 | 588,904 | 322 |
| 0.1% | 35,112 | 58,226 | 248 |
| 1% | 4,095 | 5,506 | 277 |
| 10% | 475 | 534 | 306 |
| 25% | 174 | 208 | 287 |
| 50% | 91 | 104 | 289 |
| 100% | 45 | 49 | 271 |

In this workload, the indexed path remains faster at 10%, while scan is faster at 25%
and above. Bitmap changes have therefore shifted the observed crossover from the v1
baseline. This does not establish a universal threshold; P3 must use measured cost
inputs and preserve scan/result parity.

## Mutation batching

Each invocation verifies that one immutable publication covers the complete batch.

| Batch size | Total latency ms/op | Allocation B/op |
|---:|---:|---:|
| 1 | 21.346 ± 1.517 | 7,069,902 |
| 10 | 21.581 ± 2.343 | 7,126,358 |
| 100 | 22.369 ± 3.882 | 7,659,640 |
| 1,000 | 15.899 ± 3.697 | 10,098,189 |

Latency remains dominated by fixed publication and writer-window costs rather than
growing proportionally with batch size. The 1,000-item score has high variance and
overlaps the batch-10 and batch-100 confidence ranges, so it must not be advertised as
an exact speedup.

## Acceptance conclusion

- [x] Every benchmark setup assertion and result matrix completed.
- [x] Bulk union removes repeated frozen intermediates without an evidenced sparse
      regression.
- [x] Small dirty publications avoid full-map copying on every publication; overlay
      compaction is bounded and persistent ordered publication path-copies dirty nodes.
- [x] Overlay update/removal histories and maximum-depth lookup were measured.
- [x] Persistent ordered publication qualifies against the full-copy control.
- [x] P1 Range and v1 index-versus-scan matrices were rerun after P2.
- [x] Batch sizes 1, 10, 100, and 1,000 completed with one publication each.
- [x] Environment, raw result locations, correctness gates, and limitations are recorded.

No correctness issue was discovered. D3 is accepted as the bounded-overlay/persistent-
AVL hybrid, P2 is complete, and broad Range-estimate cost is an explicit P3 follow-up.
