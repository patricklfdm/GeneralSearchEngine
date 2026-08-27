# V3 production performance follow-up results

## Decision

The bounded V3 production-performance gate passes for the workloads and environment
recorded below. The complete document-scale, top-K, corpus-shape, mixed-concurrency,
and 30-minute soak runs completed without an engine error, out-of-memory failure,
persistent writer backlog, or unbounded committed-heap growth.

This is workload-specific evidence, not a portable SLA. Applications should retain
their own latency, allocation, corpus, and concurrency acceptance thresholds.

## Evidence identity and environment

The reviewed local result directories are:

- `20260827T030340Z-6d4de04e2109-full`;
- `20260827T044519Z-6d4de04e2109-concurrency`;
- `20260827T044820Z-6d4de04e2109-soak`.

Every directory reports `status=PASS`, and every listed SHA-256 checksum verifies.
The runs used base commit `6d4de04e2109c201a1fd0d1cbfa53974db03279a`
plus the performance-suite working-tree changes captured by this document. The host
was WSL2 Linux on an Intel Core i7-12700F with 10 physical cores, 20 logical CPUs,
15 GiB RAM, OpenJDK 21.0.12, JMH 1.37, and `-Xms2g -Xmx6g`.

The full JMH matrix used two forks, three one-second warmups, and five one-second
measurements. Confidence intervals remain relevant; small differences are not
treated as regressions.

## Document and top-K scaling

The controlled uniform English single-field corpus produced these top-10 average
latencies and normalized allocations:

| Query | 10k | 100k | 1M | 1M allocation |
|---|---:|---:|---:|---:|
| TEXT | 0.422 ms | 5.505 ms | 56.584 ms | 28.1 MiB/op |
| BOOL | 0.280 ms | 4.086 ms | 47.384 ms | 17.0 MiB/op |
| PHRASE | 0.586 ms | 7.132 ms | 82.226 ms | 57.6 MiB/op |
| FUZZY | 0.431 ms | 5.232 ms | 62.231 ms | 35.8 MiB/op |

The 100k-to-1M latency ratios were 10.3–11.9x. No capacity cliff occurred, but the 1M
PHRASE, FUZZY, and TEXT allocation rates are the leading optimization candidates for
high-query-rate deployments.

At 100k documents, increasing the limit from 10 to 1,000 changed average latency by
approximately +3.8% for TEXT, +14.3% for BOOL, +10.8% for PHRASE, and +5.9% for FUZZY.
The BOOL and TEXT confidence intervals overlap; the evidence does not show explosive
top-K retention cost.

## Corpus shape

Relative to the 10k uniform short single-field corpus, the Zipf-like bilingual long
four-field profile measured 2.83x TEXT, 5.93x BOOL, 12.25x PHRASE, and 2.73x FUZZY
latency. PHRASE is the workload most sensitive to the combined longer document,
field-count, language, and term-distribution shape.

Because the profile changes those dimensions together, these ratios describe a
production-shaped scenario and must not be interpreted as isolated language or field
effects.

## Concurrent latency and throughput

The 100k Zipf-like English medium four-field corpus produced:

| Readers:writers | Read p50 / p95 / p99 | Write p50 / p95 / p99 | Read ops/s | Write ops/s |
|---|---:|---:|---:|---:|
| 1:1 | 17.96 / 52.26 / 58.57 ms | 8.04 / 9.71 / 13.16 ms | 38.96 | 123.79 |
| 4:1 | 18.42 / 55.97 / 64.02 ms | 8.26 / 9.95 / 15.12 ms | 147.47 | 115.47 |
| 16:1 | 31.72 / 100.14 / 107.17 ms | 13.17 / 16.58 / 21.18 ms | 344.96 | 77.30 |

Total throughput rose from 162.76 ops/s at 1:1 to 422.26 ops/s at 16:1, while read
throughput scaled 8.85x from one to sixteen readers. The sublinear scaling and roughly
doubled read tail at 16:1 show CPU saturation near the host's physical/logical capacity.
Writer throughput declined 37.6% between 1:1 and 16:1 but remained free of persistent
queue growth in the long run.

## Thirty-minute soak

The passing soak used 100,000 documents, 16 readers, one synchronous writer, top 10,
and continuous create/drop cycles for a dynamic range index. It completed 1,800.889
seconds with zero errors:

- 605,460 reads at 336.20 ops/s;
- 125,063 writes at 69.45 ops/s;
- 1,635 dynamic-index cycles at approximately 0.91 cycles/s;
- read p50/p95/p99 of 33.51/99.49/107.52 ms;
- write p50/p95/p99 of 14.09/17.45/21.33 ms;
- read/write observed maxima of 390.25/63.28 ms;
- unchanged final document count of 100,000;
- final snapshot version 128,433 and final writer queue depth zero.

Sampled used heap ranged from 0.65 to 2.18 GiB and averaged about 1.50 GiB. The JVM
kept committed heap fixed at about 2.32 GiB against the 6 GiB maximum. Five-minute heap
maxima plateaued at about 2.18 GiB; they did not rise throughout the run. GC consumed
approximately 21.2 seconds during the sampled 1,800.6-second interval, or 1.18% of wall
time. Writer queue depth was zero in 1,767 of 1,799 samples and one in the remaining 32;
the configured capacity was 100,000.

The first and last five-minute read rates were approximately 345 and 327 ops/s, while
write rate remained near 69–70 ops/s and GC time remained near 11–12 ms/s. This modest
late-run read drift is not accompanied by heap-capacity or queue growth, but longer
multi-hour application-specific runs should monitor it when tail latency is critical.

The 16:1 JMH and soak p99 values agree within about 1% for both reads and writes. Soak
read/write throughput is lower than the short JMH run as expected because it also runs
continuous dynamic-index lifecycle work.

## Excluded diagnostic run

The earlier directory `20260827T032050Z-6d4de04e2109-soak` is retained but excluded
from the passing evidence. Its fixture coupled a global revision to sequential document
IDs, eventually making one valid BOOL query empty and incorrectly treating that result
as a failure. The corrected runner uses per-document revision cycles and validates the
request limit without requiring a non-empty result. The failure did not indicate an
engine exception, leak, deadlock, or queue saturation.
