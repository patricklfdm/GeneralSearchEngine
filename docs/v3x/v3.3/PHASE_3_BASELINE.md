# V3.3 Phase 3 search-after baseline

## Scope and interpretation

This local diagnostic records strict current-snapshot continuation after the private
built-in cursor implementation. It does not create canonical cloud evidence or a
numerical CI threshold. Raw JMH JSON remains disposable under `target/`.

The implementation evaluates query/filter/scoring candidates on every page. It skips
page-heap admission for candidates at or before the anchor, but does not claim O(page
size), index seeking, early termination, WAND, or a deep-page latency improvement.

## Environment

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37; and
- benchmark mode: average time, one thread, three forks, three 500 ms warmups, five
  500 ms measurements, GC profiler.

## First-page regression after cursor emission

The retained Phase 2 control uses 10,000 documents, top 10, and sparse or dense
equal-score corpora. Phase 3 now emits a cursor when another match exists.

```bash
java -jar target/benchmarks.jar \
  'V33PaginationBaselineBenchmark.(ordinaryRankedSearch|firstPageDisabled|firstPageExact)' \
  -p documentCount=10000 -p topK=10 \
  -p corpusShape=sparse,dense-ties \
  -f 3 -wi 3 -i 5 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase3-first-page-regression.json -foe true
```

| Operation | Corpus | Mean time | Error | Allocation | Error |
|---|---|---:|---:|---:|---:|
| ordinary ranked | sparse | 7.977 us/op | 0.106 | 10,976 B/op | 26 |
| first page, disabled | sparse | 7.955 us/op | 0.094 | 11,075 B/op | 41 |
| first page, exact | sparse | 7.971 us/op | 0.073 | 11,123 B/op | 27 |
| ordinary ranked | dense equal-score | 1,255.999 us/op | 19.736 | 878,416 B/op | 16 |
| first page, disabled | dense equal-score | 1,231.437 us/op | 19.323 | 878,503 B/op | 20 |
| first page, exact | dense equal-score | 1,263.859 us/op | 12.804 | 878,536 B/op | 16 |

JMH reports 99.9% confidence-interval half-widths. The relevant latency intervals
overlap. Cursor emission and page state add about 99 B/op sparse and 87 B/op dense for
disabled pages versus the same-run ordinary control; exact pages add about 147 B/op
sparse and 120 B/op dense. The ordinary executor no longer carries the Phase 2
always-null count branch.

## Continuation depth and exact-count comparison

`V33SearchAfterBenchmark` uses 10,000 matching documents, page size 10, and measures a
continuation after page 1 or page 100. Dense ties share one score; score bands vary term
frequency while retaining many ties.

```bash
java -jar target/benchmarks.jar 'V33SearchAfterBenchmark.*' \
  -p documentCount=10000 -p pageSize=10 \
  -p pageDepth=1,100 -p corpusShape=dense-ties,score-bands \
  -f 3 -wi 3 -i 5 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase3-search-after-reviewed.json -foe true
```

| Total mode | Corpus | Depth | Mean time | Error | Allocation | Error |
|---|---|---:|---:|---:|---:|---:|
| disabled | dense ties | 1 | 1,222.294 us/op | 11.291 | see anomaly below | — |
| disabled | dense ties | 100 | 1,228.438 us/op | 42.079 | 846,542 B/op | 14 |
| exact | dense ties | 1 | 1,226.684 us/op | 10.283 | 878,247 B/op | 15 |
| exact | dense ties | 100 | 1,239.858 us/op | 34.744 | 846,566 B/op | 14 |
| disabled | score bands | 1 | 1,206.320 us/op | 70.355 | 878,222 B/op | 15 |
| disabled | score bands | 100 | 1,237.507 us/op | 46.897 | 846,542 B/op | 14 |
| exact | score bands | 1 | 1,239.043 us/op | 10.758 | 878,248 B/op | 16 |
| exact | score bands | 100 | 1,235.975 us/op | 33.370 | 846,566 B/op | 14 |

Depth intervals overlap within each shape/mode. That is expected: every page still
normalizes, plans, filters, matches, and scores the full candidate set. At depth 100,
the first 1,000 matches fail the anchor predicate before `RankedCandidate` allocation
and page-heap admission, explaining the roughly 31.7 KB/op reduction. Exact versus
disabled differs by about 24 B/op in stable paired depth-100 cells and does not allocate
per match.

### Dense-disabled depth-1 allocation anomaly

One of the original three dense-disabled depth-1 forks reported about 638 KB/op while
the other two reported about 878 KB/op. A separate five-fork rerun retained stable
latency (`1,234.206 ± 7.351 us/op`) but reproduced the JVM allocation bifurcation:
four forks ranged from approximately 878,209 to 878,242 B/op and one ranged from
638,209 to 638,241 B/op.

```bash
java -jar target/benchmarks.jar \
  'V33SearchAfterBenchmark.continuationDisabled' \
  -p documentCount=10000 -p pageSize=10 -p pageDepth=1 \
  -p corpusShape=dense-ties \
  -f 5 -wi 3 -i 5 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase3-search-after-disabled-depth1-review.json \
  -foe true
```

The exact 240 KB difference is consistent with fork-dependent escape/scalar-replacement
of short-lived equal-score candidate objects. Because the compilation outcome is not
stable, this record reports the observed range and does not use the aggregate
`830,223 ± 73,395 B/op` as a regression claim.

## Correctness and evidence boundary

Deterministic tests, not JMH checksums, prove exhaustive no-gap/no-duplicate walks,
raw-score and hidden-ID ordering, exact totals, cursor reason precedence, request and
snapshot identity, publication staleness, admitted-read snapshot behavior, and cursor
retention. The benchmarks consume hit, score, cursor-presence, and total checksums only
to prevent dead-code elimination.

Build and run the retained discovery gate with:

```bash
scripts/verify-jmh-smoke.sh
```

Phase 3 requires no paid cloud run. `v3.0.0-cloud` and
`v3.1.0-ranked-cloud` remain immutable. A page-specific cloud family still requires a
separate accepted identity, provisioning, cost, retention, and comparison contract.
