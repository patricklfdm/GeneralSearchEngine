# V3 cloud soak diagnostic results

## Decision

The cloud soak diagnostic experiment is complete. Nine Standard C3D-30 runs provide
valid retained evidence: the four-cell screening matrix, four confirmation repeats,
and one final 30-minute production-configuration confirmation. Every run completed
without an engine error, document-count change, persistent writer backlog, checksum
failure, preemption, or cleanup failure.

The experiment does not identify either the 8-versus-16 GiB maximum heap or continuous
dynamic range-index lifecycle work as the primary cause of the long-run signal. Three
independent runs of both maximum-contrast configurations consistently showed about six
percent read-rate decline over ten minutes. The final 30-minute `elastic-on` run then
reproduced the earlier long-run result almost exactly: 536.320 versus 536.368 read ops/s
and -11.291% versus -12.007% early-to-late read drift.

The signal is therefore reproducible and duration-dependent, but this aggregate soak
cannot attribute it to an engine defect. Stable writes, low GC time, negligible queue
depth, and the maximum-contrast result argue against GC saturation, writer backlog, or
dynamic-index lifecycle as the dominant mechanism. No engine optimization is justified
without a separate investigation contract containing read-only, per-query, and update-
shape controls.

## Evidence identity and controls

All new runs used clean pushed commit
`7a6a7539b9d4f736eff34fe56b9f52d76497fc15` and reported:

- GCP project `gse-benchmark`, zone `us-west4-a`;
- Standard `c3d-standard-30` provisioning on one fresh VM per run;
- exact image `ubuntu-2404-noble-amd64-v20260826`, image ID
  `5563818848645508791`;
- OpenJDK `21.0.12+8-1~24.04`;
- 100,000 documents, 16 readers, one synchronous writer, top K 10;
- `zipf-en-medium-4` and one-second sampling;
- no overlapping benchmark VM and an empty working tree.

Every result reports `status=PASS`, `errors=0`, unchanged final document count, a final
writer queue depth of zero, and byte-valid `checksums.sha256`. Every orchestration record
reports `BENCHMARK_PASS`, successful artifact recovery and checksum verification, and
successful VM cleanup without preemption.

Raw result directories remain generated local evidence and are not committed to Git.
This report records their identities and reviewed aggregates without replacing them.

## Four-cell screening

The screening matrix ran in the frozen order:

| Cell | JVM | Index cycles | Result directory |
|---|---|---:|---|
| `elastic-on` | `-Xms8g -Xmx16g` | true | `20260828T011429Z-7a6a7539b9d4-soak` |
| `fixed-off` | `-Xms8g -Xmx8g` | false | `20260828T012733Z-7a6a7539b9d4-soak` |
| `fixed-on` | `-Xms8g -Xmx8g` | true | `20260828T014237Z-7a6a7539b9d4-soak` |
| `elastic-off` | `-Xms8g -Xmx16g` | false | `20260828T015616Z-7a6a7539b9d4-soak` |

Whole-run rates and bounded-reservoir latencies were:

| Cell | Read ops/s | Write ops/s | Read p95 / p99 | Write p95 / p99 | Index cycles |
|---|---:|---:|---:|---:|---:|
| `elastic-on` | 578.809 | 85.339 | 53.488 / 76.029 ms | 12.516 / 14.263 ms | 554 |
| `fixed-off` | 579.950 | 84.793 | 52.777 / 73.265 ms | 12.594 / 14.295 ms | 0 |
| `fixed-on` | 578.051 | 85.852 | 54.010 / 75.249 ms | 12.255 / 14.338 ms | 556 |
| `elastic-off` | 579.847 | 85.086 | 53.447 / 73.047 ms | 12.366 / 14.055 ms | 0 |

The deterministic bucket analysis reported:

| Cell | Read drift | Write drift | Average heap growth | Minimum heap growth | GC ms/s | Queue non-zero / max |
|---|---:|---:|---:|---:|---:|---:|
| `elastic-on` | -5.611% | +2.439% | 141.0 MiB | 190.6 MiB | 4.360 | 3 / 1 |
| `fixed-off` | -5.726% | +4.027% | 187.5 MiB | 229.5 MiB | 4.445 | 1 / 1 |
| `fixed-on` | -5.944% | +0.304% | 213.0 MiB | 217.6 MiB | 4.530 | 2 / 1 |
| `elastic-off` | -6.112% | +1.467% | 253.6 MiB | 171.0 MiB | 3.887 | 3 / 1 |

No screening cell crossed a frozen review threshold. Sampled used heap peaked near
5.6 GiB. Both JVM configurations started with an 8 GiB committed heap, so this workload
did not create sustained pressure that would distinguish an 8 GiB from a 16 GiB maximum.
GC remained far below the 50 ms/s review threshold, and queue capacity was 100,000.

With one observation per screening cell, the factorial contrasts were investigation
hints rather than statistical estimates:

| Contrast | Read throughput | Write throughput | GC time | Average heap growth |
|---|---:|---:|---:|---:|
| Fixed minus elastic heap | -0.327 ops/s (-0.057%) | +0.110 ops/s (+0.129%) | +0.364 ms/s | +3.0 MiB |
| Lifecycle on minus off | -1.468 ops/s (-0.253%) | +0.656 ops/s (+0.772%) | +0.279 ms/s | -43.5 MiB |

Neither contrast was practically large relative to the common within-run read decline.
Heap-growth ordering also changed across the pairs rather than following either factor.

## Maximum-contrast confirmation

The maximum-contrast `elastic-on` and `fixed-off` cells were each brought to three
independent runs. Execution order was reversed across rounds:

| Round | First | Second |
|---|---|---|
| Screening | `elastic-on` (`011429Z`) | `fixed-off` (`012733Z`) |
| Confirmation two | `fixed-off` (`021530Z`) | `elastic-on` (`022841Z`) |
| Confirmation three | `elastic-on` (`025050Z`) | `fixed-off` (`031154Z`) |

The three-run aggregates below show mean plus or minus sample standard deviation:

| Metric | `elastic-on` | `fixed-off` |
|---|---:|---:|
| Read ops/s | 577.336 +/- 2.592 | 581.850 +/- 2.252 |
| Write ops/s | 85.131 +/- 0.269 | 85.273 +/- 0.583 |
| Read p95 | 53.404 +/- 0.321 ms | 52.839 +/- 0.157 ms |
| Read p99 | 74.430 +/- 1.424 ms | 73.501 +/- 1.094 ms |
| Write p95 | 12.371 +/- 0.140 ms | 12.400 +/- 0.170 ms |
| Write p99 | 14.247 +/- 0.040 ms | 14.297 +/- 0.007 ms |
| Read drift | -6.014% +/- 0.410 pp | -5.805% +/- 0.379 pp |
| GC time per 600-second run | 2,588 +/- 27 ms | 2,656 +/- 14 ms |

`fixed-off` averaged 0.776% more read throughput and 1.069% lower read p95. It changed
both experimental factors simultaneously, so that small difference cannot be assigned
to heap maximum or lifecycle independently. Write rate differed by 0.166%, read drift
by 0.209 percentage points, and both cells showed low within-cell variation. Most
importantly, every repeat preserved the same approximately six-percent read trajectory
without a review flag.

Average and minimum heap-growth measurements varied more than throughput and latency,
but remained below 512 MiB in all six confirmation runs. Queue depth was non-zero in at
most four of 601 samples and never exceeded one.

## Thirty-minute confirmation

The final production-configuration result is
`20260828T033628Z-7a6a7539b9d4-soak`. It used `-Xms8g -Xmx16g`, enabled dynamic index
cycles, and completed 1,801.099 seconds with:

- 965,965 reads at 536.320 ops/s;
- 153,043 writes at 84.972 ops/s;
- 1,661 dynamic-index cycles;
- read p50/p95/p99 of 23.563/57.279/77.695 ms;
- write p50/p95/p99 of 11.866/12.378/13.987 ms;
- observed read/write maxima of 195.157/39.762 ms;
- 3,142 GC events and 6,859 ms total GC time, approximately 3.81 ms/s;
- writer queue non-zero in 15 of 1,801 samples, maximum one, and final depth zero;
- final document count 100,000 and final snapshot version 156,465.

The report is structurally valid with `review_required=true`. Read rate declined
11.291% from bucket two to bucket six. Average heap grew 474.1 MiB and minimum heap grew
569.1 MiB; the minimum-band increase crossed the frozen 512 MiB review threshold.
Write drift was only -1.316%. The no-plateau flag cannot be triggered by the average
growth because it remained below 512 MiB, while GC and queue-pressure flags remain false.

The independent earlier Standard 30-minute run
`20260827T234820Z-72dff777834c-soak` provides a strong replication:

| Metric | Earlier run | Final confirmation |
|---|---:|---:|
| Read ops/s | 536.368 | 536.320 |
| Write ops/s | 86.067 | 84.972 |
| Read drift | -12.007% | -11.291% |
| Average heap growth | 631.4 MiB | 474.1 MiB |
| Minimum heap growth | 625.8 MiB | 569.1 MiB |
| Read p95 / p99 | 57.742 / 79.001 ms | 57.279 / 77.695 ms |
| GC time | 6,739 ms | 6,859 ms |
| Queue non-zero / max | 17 / 1 | 15 / 1 |

Read throughput differs by less than 0.01%, and both runs independently cross the
read-drift and minimum-heap-band review conditions. The change between commits contains
diagnostic runner and documentation work rather than an engine optimization, so the
agreement is relevant evidence while still not being a formal cross-commit benchmark.

## Interpretation and boundary

The four-query read mix is constant, while the writer performs deterministic document
replacements throughout the run. A ten-minute run performs about 51,000 replacements;
the 30-minute confirmations perform about 153,000-155,000. The magnitude of read and
heap movement is correlated with sustained snapshot evolution. The ten-minute lifecycle
controls, queue evidence, and GC evidence do not support dynamic index cycles, writer
backlog, or high GC time as the primary explanation.

Plausible shared mechanisms include accumulated immutable update state, changed term or
candidate distributions after document revisions, and other duration-dependent search
costs. Aggregate counts cannot distinguish those explanations or identify whether TEXT,
BOOL, PHRASE, or FUZZY contributes the drift. Calling this a memory leak would also be
unsupported: minimum heap moves upward, but the evidence contains no post-full-GC live-
set measurement or allocation ownership profile.

This diagnostic phase therefore closes without a product change. Any next phase must
freeze benchmark-only controls before implementation, minimally:

1. a read-only static-snapshot control;
2. per-query bucket throughput and latency for TEXT, BOOL, PHRASE, and FUZZY;
3. content-stable replacement versus revision-changing replacement;
4. bounded allocation/CPU profiling with the same corpus and VM controls;
5. unchanged correctness, checksum, lifecycle, and cleanup gates.

Only those controls can determine whether an engine investigation is justified and
which subsystem it should target. The numbers in this report remain workload-specific
diagnostic evidence, not a portable SLA or a release regression threshold.

The benchmark-only follow-up is frozen in the
[cloud soak root-cause investigation contract](CLOUD_SOAK_ROOT_CAUSE_INVESTIGATION.md).
