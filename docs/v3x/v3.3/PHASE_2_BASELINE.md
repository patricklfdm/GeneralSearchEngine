# V3.3 Phase 2 first-page and exact-total baseline

## Scope and interpretation

This record compares the Phase 2 built-in first-page paths with retained ordinary
ranked controls on the same branch and host. It is a local diagnostic, not canonical
cloud evidence or a universal regression threshold. Raw JMH JSON belongs under
`target/` and is disposable.

Phase 2 implements only no-cursor first pages. Built-in cursor emission, ownership,
request/snapshot validation, and continuation begin in Phase 3, so this evidence makes
no deep-page claim.

## Environment

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37; and
- benchmark mode: average time, one thread, three forks, three 500 ms warmups, five
  500 ms measurements, GC profiler.

## Reviewed same-run comparison

Sparse cells match 100 of 10,000 documents. Dense-tie cells match all 10,000 with
equal text and score; filtered cells admit the `eligible` half before ranked retention.
Every operation returns top 10 and consumes document/score/count checksums.

```bash
java -jar target/benchmarks.jar \
  'V33PaginationBaselineBenchmark.(ordinaryRankedSearch|firstPageDisabled|firstPageExact|filteredRankedSearch|filteredFirstPageExact)' \
  -p documentCount=10000 -p topK=10 \
  -p corpusShape=sparse,dense-ties \
  -f 3 -wi 3 -i 5 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase2-page-reviewed.json -foe true
```

The error columns are JMH's reported 99.9% confidence-interval half-widths.

| Operation | Corpus | Mean time | Error | Allocation | Error |
|---|---|---:|---:|---:|---:|
| ordinary ranked | sparse | 7.927 us/op | 0.094 | 10,989 B/op | 11 |
| first page, disabled | sparse | 7.921 us/op | 0.109 | 11,003 B/op | 4 |
| first page, exact | sparse | 7.929 us/op | 0.107 | 11,056 B/op | 26 |
| filtered ordinary | sparse | 10.165 us/op | 0.319 | 15,845 B/op | 23 |
| filtered first page, exact | sparse | 10.165 us/op | 0.126 | 15,923 B/op | 8 |
| ordinary ranked | dense equal-score | 1,233.245 us/op | 20.806 | 878,423 B/op | 15 |
| first page, disabled | dense equal-score | 1,241.418 us/op | 10.210 | 878,432 B/op | 16 |
| first page, exact | dense equal-score | 1,232.655 us/op | 11.898 | 878,463 B/op | 20 |
| filtered ordinary | dense equal-score | 803.255 us/op | 13.629 | 445,458 B/op | 19 |
| filtered first page, exact | dense equal-score | 801.089 us/op | 8.560 | 445,529 B/op | 11 |

The relevant latency intervals overlap. These short local runs therefore show no
resolved Phase 2 latency regression or improvement. First-page disabled allocation is
within 14 B/op of ordinary in sparse and 9 B/op in dense cells. Exact mode is within
67 B/op of ordinary in sparse and 40 B/op in dense; the filtered exact delta is about
77 B/op sparse and 71 B/op dense. The delta is fixed result/count wrapping, not a
per-match allocation: the dense fixture evaluates roughly 100 times more matches
without a proportional delta.

The ordinary implementation still passes no counter into candidate evaluation.
Disabled page execution likewise creates no counter. Exact mode creates one internal
primitive holder and increments it in the existing post-filter matched-candidate path.
A callback-counting correctness test independently proves there is no second filter
evaluation pass.

## Phase 1 comparison boundary

The reviewed ordinary controls agree with the Phase 1 local baseline at the workload
scale expected from short WSL2 runs. Same-run controls are authoritative for evaluating
the Phase 2 façade; cross-run Phase 1 means are retained only as a pre-change anchor.
No unrelated cells are averaged together and no claim is made across machines.

## Smoke and cloud boundary

Build the JMH artifact and execute the retained bounded discovery gate with:

```bash
./mvnw -q -Pjmh -DskipTests package
scripts/verify-jmh-smoke.sh
```

The smoke gate proves discovery and bounded execution, not latency. Phase 2 requires no
paid cloud run. `v3.0.0-cloud` and `v3.1.0-ranked-cloud` remain immutable; pagination
cannot be inserted into either family. A future page cloud lane still requires a
separate accepted identity, cost, retention, and comparison contract.
