# Cloud soak diagnostics contract

Status: frozen before implementation on 2026-08-27.

## Trigger and objective

The first Standard `c3d-standard-30` cloud evidence for commit
`72dff777834c2b863a595c42d9666c0f8872e5d1` completed correctness and lifecycle
validation. The 30-minute run
`20260827T234820Z-72dff777834c-soak` reported zero errors, stable document count,
continuous snapshot progress, a final writer queue depth of zero, verified checksums,
and successful VM cleanup.

It also exposed two signals that the existing summary cannot explain:

- five-minute read throughput declined from approximately `592.4` to `498.8 ops/s`;
- the sampled heap band continued moving upward, with five-minute average used heap
  increasing from approximately `3.13` to `3.81 GiB` and the corresponding minima
  increasing from approximately `0.70` to `1.44 GiB`.

Write throughput remained near `85-87 ops/s`, maximum writer queue depth was one, and
GC time remained below one percent of wall time. These observations do not establish a
memory leak or a product regression. This diagnostic phase separates heap ergonomics,
dynamic-index lifecycle work, workload evolution, and run-to-run noise before any engine
change is proposed.

## Scope and non-goals

This phase may change only benchmark configuration, analysis tooling, tests, and
documentation. It must not change search truth, scoring, ordering, snapshot publication,
index implementation, public API, or release coordinates.

The diagnostic flags defined here are investigation thresholds, not a portable SLA and
not an automatic release failure. A single faster cell must not be selected as the new
baseline. Raw generated evidence remains ignored by Git and must not be rewritten after
its `checksums.sha256` has been created.

## Frozen configuration surface

Add `GSE_SOAK_INDEX_CYCLES`, accepting only `true` or `false` and defaulting to `true`.
The local production runner and cloud orchestrator must validate and propagate it without
changing the existing default. The effective value must appear in `metadata.txt`, the
remote command, and `soak-config.properties`.

Existing variables retain their current meaning. In particular, heap cells continue to
use `GSE_PERF_JVM_OPTIONS`; this phase does not add a second heap configuration mechanism.
Invalid booleans fail before a VM is created.

## Per-run analysis contract

Add `scripts/analyze-v3-soak.sh SOAK_DIRECTORY`. The command reads
`soak-samples.csv`, `soak-summary.properties`, and `soak-config.properties` and writes a
deterministic properties report to standard output. It does not mutate its input. The
production runner captures that output to a temporary file and atomically renames it to
`soak/soak-analysis.properties` before the run-level checksum manifest is generated. A
failed analyzer must not leave a partial report bearing the final name.

The analyzer must use locale-independent decimal parsing and reject malformed headers,
missing required properties, non-monotonic cumulative counters, changing document count,
insufficient elapsed coverage, non-finite values, and a summary that reports failure or
errors. A hard validation failure returns non-zero and therefore fails the containing
performance run. Investigation flags return zero with `review_required=true`.

Sufficient coverage requires the first sample no later than two configured sample
intervals after start, the final elapsed value to reach the configured duration, and a
sample count of at least
`floor(seconds / sample_seconds * 0.95) + 1`. Extra final samples and small scheduler
delays are permitted.

The sample interval is divided into six equal elapsed-time buckets. Bucket boundaries
derive from the configured duration rather than row count. A boundary sample belongs to
the later bucket, except that the final sample remains in bucket six. Each bucket records:

- actual first/last elapsed time and sample count;
- read, write, and index-cycle rates from cumulative deltas;
- used-heap average, minimum, and maximum;
- GC count delta and GC milliseconds per second;
- maximum and non-zero sample count for writer queue depth;
- maximum error count and document-count mismatch count.

Bucket one is retained as startup evidence. Trend comparisons use bucket two as the early
steady window and bucket six as the late window. The report also records whole-run
p50/p95/p99/max latency and final counters from the summary.

The first implementation freezes these review flags:

| Flag | Condition |
|---|---|
| `read_rate_drift` | late read rate is at least 10% below early read rate |
| `write_rate_drift` | late write rate is at least 10% below early write rate |
| `heap_band_growth` | late minimum or average used heap exceeds early by at least 512 MiB |
| `heap_no_plateau` | each of the final three bucket averages exceeds the preceding one and total early-to-late growth is at least 512 MiB |
| `gc_time_high` | late GC time exceeds 50 ms per elapsed second |
| `writer_queue_sustained` | queue is non-zero in at least 10% of samples or reaches 1% of configured capacity |

The report records raw values as well as booleans. `review_required` is true when any
review flag is true. Passing the analyzer means that evidence is structurally valid; it
does not mean the performance is acceptable.

The properties schema begins with `analysis_version=1`, `analysis_status=VALID`, and
`review_required`. It includes every flag, whole-run values, early/late derived values,
and bucket keys prefixed `bucket_1_` through `bucket_6_`. Keys are emitted in a stable
order without a generated timestamp so identical inputs produce byte-identical output.

## Screening experiment

Run one fresh Standard VM for each cell of this 2x2 matrix:

| Cell | JVM | Dynamic index cycles |
|---|---|---|
| `elastic-on` | `-Xms8g -Xmx16g` | `true` |
| `elastic-off` | `-Xms8g -Xmx16g` | `false` |
| `fixed-on` | `-Xms8g -Xmx8g` | `true` |
| `fixed-off` | `-Xms8g -Xmx8g` | `false` |

Every cell freezes all other controls:

- exact Git commit and a clean working tree;
- exact `ubuntu-2404-noble-amd64-v20260826` image and recorded JDK package;
- `c3d-standard-30`, Standard provisioning, and one independent ephemeral VM;
- 600 seconds, one-second samples, 100,000 documents, 16 readers, one writer;
- top K 10 and `zipf-en-medium-4` corpus;
- no overlapping cloud benchmark VM and no code/configuration change between cells.

Execute the screening cells in the documented order `elastic-on`, `fixed-off`,
`fixed-on`, `elastic-off`. This interleaves both factors but does not make a single run
per cell statistically conclusive. Retain all four runs, including unfavorable results.

## Interpretation and confirmation

Compare factor effects rather than absolute fastest scores:

- improvement in both fixed-heap cells suggests GC/heap ergonomics;
- degradation in both lifecycle-on cells relative to the matching lifecycle-off cells
  suggests dynamic-index lifecycle contribution;
- similar drift in all four cells suggests the mixed update/query workload or another
  shared mechanism;
- inconsistent cells or differences comparable to run-to-run variation require repeats
  before attribution.

The screening matrix cannot freeze a new baseline. After review, select the minimum
contrasting cells required to test the leading hypothesis and bring each selected cell
to at least three independent Standard runs, reversing execution order across repeats.
Only then run a 30-minute confirmation with the proposed production configuration.

No engine optimization begins until the evidence identifies a reproducible factor. Any
engine change requires a separate branch, correctness gates, and pre/post runs using the
same experiment contract.

## Required tests and completion gate

Implementation is complete only when all of the following pass:

- shell syntax validation for every changed script;
- stable, drifting, queue-pressure, malformed, and counter-regression analyzer fixtures;
- `GSE_SOAK_INDEX_CYCLES=false` propagation through local metadata/configuration;
- fake-gcloud verification of remote propagation and pre-provision rejection of an
  invalid boolean;
- existing fake-gcloud lifecycle suite and reactor tests;
- one no-cost local reduced soak whose analysis is included in `checksums.sha256`;
- dry runs for all four cloud cells showing Standard provisioning and the frozen image;
- manual execution and review of the four paid screening cells.

The phase closes with a reviewed report that references every retained run, records the
factor comparison and uncertainty, and states whether a 30-minute confirmation or an
engine investigation is justified.
