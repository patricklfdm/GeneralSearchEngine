# V3.4 Phase 1 local pre-change baseline

Status: local diagnostic evidence complete on
`feat/v3.4-phase1-foundation`. These measurements describe existing V3.3 behavior
compiled as `3.4.0-SNAPSHOT`; they are not a release gate, cloud result, or comparison
to a later implementation.

## Purpose

The baseline gives later V3.4 hardening work a same-machine reference without
implementing the future cold-build, extreme-corpus, heap, burst, long-run, or cloud
workloads early. `V34FinalHardeningBaselineBenchmark` covers four already-published
read paths:

- ordinary ranked search;
- structured highlighted search with one field and one fragment;
- first-page search with default-disabled totals;
- first-page search with exact totals.

Sparse and dense equal-score corpora expose both selective and broad match shapes.
Each trial verifies canonical parity before timing and each invocation returns a
consumed checksum.

## Environment

| Property | Value |
|---|---|
| Base source | `5d1d10840c5bf818c54c3226de1413e7e28786cd` plus the Phase 1 working tree |
| OS | Linux `6.6.87.2-microsoft-standard-WSL2`, x86-64 |
| CPU | Intel Core i7-12700F, 10 cores / 20 logical CPUs |
| Memory visible to WSL2 | 15 GiB; swap configured, no resource-gate claim |
| JVM | OpenJDK 21.0.12, Ubuntu build `21.0.12+8-1-22.04-Ubuntu` |
| Maven / JMH | Maven 3.9.11 / JMH 1.37 |
| Forks / threads | 1 / 1 |
| Warmup | 2 iterations × 300 ms |
| Measurement | 3 iterations × 300 ms |

Command:

```bash
java -jar target/benchmarks.jar \
  'V34FinalHardeningBaselineBenchmark.(ordinaryRankedSearch|highlightedSearch|firstPageExact)' \
  -p documentCount=10000 -p topK=10 \
  -p corpusShape=sparse,dense-ties \
  -f 1 -wi 2 -w 300ms -i 3 -r 300ms -foe true
```

Results from another environment are not directly comparable merely because benchmark
parameters match.

## Measurement table

| Operation | Corpus | Documents | top K | Mean | Units |
|---|---:|---:|---:|---:|---|
| ordinary ranked search | sparse | 10,000 | 10 | 8.136 | us/op |
| ordinary ranked search | dense ties | 10,000 | 10 | 1,183.140 | us/op |
| highlighted search | sparse | 10,000 | 10 | 28.859 | us/op |
| highlighted search | dense ties | 10,000 | 10 | 1,278.326 | us/op |
| first page exact | sparse | 10,000 | 10 | 8.344 | us/op |
| first page exact | dense ties | 10,000 | 10 | 1,251.956 | us/op |

No threshold is frozen from these diagnostics. Phase 2 must preserve deterministic
correctness and bounded-resource gates before any performance interpretation.

The short three-sample confidence intervals are intentionally wide, especially for
fast sparse cells. These numbers are a same-machine orientation point, not a stable
latency claim. Dense exact totals remain complete-match work; sparse highlighted search
also includes explicit top-K source re-analysis, as already defined by V3.2/V3.3.

## Interpretation boundary

- This file records pre-change local diagnostics, not a regression verdict.
- Cross-phase comparisons require identical source-independent workload parameters,
  JDK/JVM, forks, warmups, measurements, and machine state.
- The later two-hour and canonical cloud evidence use separate contracted identities
  and cannot be replaced by this run.
- No production optimization is justified by Phase 1 evidence alone.
