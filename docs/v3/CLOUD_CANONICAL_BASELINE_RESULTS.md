# V3 canonical cloud baseline results

## Decision

Protected workflow run
[33245212380](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33245212380)
produced the first reviewed Cloud Benchmark V2 canonical set for V3. All three
independent Standard C3D-30 members completed on their first attempt, passed member and
set validation, uploaded durable checksum-bound evidence, and left no benchmark VM
behind. The set is accepted in the immutable registry as `v3.0.0-cloud`.

This entry is a reproducible comparison anchor for later changes. It is not an SLA,
portable hardware claim, or permission to ignore a future regression. In particular,
the 30-minute soak retains the already documented V3 revision-update review signal;
registration records that behavior rather than declaring it desirable.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33245212380 / 1` |
| Source commit | `4e446ba9bccebe8f9c3c848738ec9f27f18e1288` |
| Request | `canonical / all / 3 / standard / c3d-standard-30 / 30m / gcs` |
| Production preset | `v3-production-all-v1` |
| Set status | `VALID_CANONICAL_SET` |
| Set ID | `gse-set-v1-4767465528d42ea635ea7f1ed9a6d42b244f2c4e49acc8addc45eba180d06cfb` |
| Configuration fingerprint | `sha256:fd1935ce328d45b0e626bb1474c6454220b861fabdee79b5601a5c8061989ad5` |
| Environment fingerprint | `sha256:39c7a09cb62458e55c1ec749d5fd48f894f7cd19879532ce1ad7ecc0f3ead0cd` |
| Set manifest digest | `sha256:2c67749151a932008d7d282302d08f4003ee97dfb3eee40ca5d791f74db37122` |
| Upload receipt | `gse-upload-receipt-v1-f7d64883d6ab478df6da7fab90037aec67ecbe61dac4cdcfaa0f8d816f8384d2` |
| Receipt digest | `sha256:d227382d6c85116dcdd448c8c680ce7c0decdcc87b6d6209c19a10ab6a4d64f9` |
| Durable manifest | `gs://gse-benchmark-evidence-266952534277/general-search-engine/sets/gse-set-v1-4767465528d42ea635ea7f1ed9a6d42b244f2c4e49acc8addc45eba180d06cfb/v1/benchmark-set-manifest.json#1788004730266975` |
| Baseline registry name | `v3.0.0-cloud` |

The source commit is a post-release benchmark-tooling commit on the V3 line. Compared
with signed tag `v3.0.0`, it changes no file under `src/main`; the cloud result therefore
describes the published V3 engine rather than a later product optimization.

The downloaded Actions artifact contained 24 allowlisted payloads plus its checksum
inventory. Every `artifact-checksums.sha256` entry passed. Baseline registration then
independently revalidated all 103 GCS objects, including immutable generations and
recorded integrity metadata, before atomically updating the repository registry.

## Independent-member controls

| Slot | Run ID | Result | Approximate VM lifetime |
|---:|---|---|---:|
| 1 | `20260829T092132Z-4e446ba9bcce-all` | first attempt, valid | 50m 48s |
| 2 | `20260829T101228Z-4e446ba9bcce-all` | first attempt, valid | 50m 50s |
| 3 | `20260829T110321Z-4e446ba9bcce-all` | first attempt, valid | 50m 50s |

No slot was replaced or preempted. Every orchestration record reports completed result
recovery, checksum verification, and successful VM cleanup. Exact guest memory differed
by only 8 KiB across the three C3D-30 instances and normalized to one reviewed
environment fingerprint. All members exposed the same 357 metric identities and the
same benchmark configuration fingerprint.

Total Standard C3D-30 lifetime was about 2.54 VM-hours. At the billing-derived
`$1.535` per VM-hour snapshot used by the selection guide, gross instance compute is
approximately `$3.90`; the Cloud Billing export remains authoritative.

## Search and scale medians

The following values are medians of the three independent member values. They are a
compact review surface; the durable aggregate contains all 357 normalized metrics,
including allocation and GC diagnostics.

### Document scale, uniform English short corpus, top K 10

| Documents | BOOL | TEXT | PHRASE | FUZZY |
|---:|---:|---:|---:|---:|
| 10,000 | 0.280 ms/op | 0.434 ms/op | 0.888 ms/op | 0.601 ms/op |
| 100,000 | 4.225 ms/op | 6.231 ms/op | 10.479 ms/op | 6.768 ms/op |
| 1,000,000 | 60.986 ms/op | 52.915 ms/op | 88.197 ms/op | 59.877 ms/op |

Across the 36 primary search mean-time cells, the cross-member relative range had a
2.11% median, 5.11% 90th percentile, and 15.77% maximum. The maximum is the 10,000
document TEXT cell: its absolute range is only 0.068 ms/op, so it is retained as normal
small-duration measurement variation rather than hidden by aggregation.

### Top-K scale, 100,000 documents

| Top K | BOOL | TEXT | PHRASE | FUZZY |
|---:|---:|---:|---:|---:|
| 10 | 4.111 ms/op | 6.217 ms/op | 10.656 ms/op | 6.802 ms/op |
| 100 | 4.188 ms/op | 6.335 ms/op | 10.721 ms/op | 6.836 ms/op |
| 1,000 | 4.712 ms/op | 6.430 ms/op | 10.946 ms/op | 7.332 ms/op |

These values provide the V3 comparison anchor; they do not imply linear complexity or
a universal latency promise for other analyzers, corpora, hardware, or JVM settings.

## Concurrent medians

| Readers / writers | Mixed throughput | Read throughput | Write throughput |
|---|---:|---:|---:|
| 1 / 1 | 145.390 ops/s | 35.296 ops/s | 110.134 ops/s |
| 4 / 1 | 278.767 ops/s | 156.525 ops/s | 121.514 ops/s |
| 16 / 1 | 692.450 ops/s | 600.468 ops/s | 95.036 ops/s |

The nine throughput components have a 1.03% median relative range. Eight remain below
1.77%; the 16-reader write component spans 8.14%, which is expected to be reviewed as a
secondary group rate rather than mistaken for total mixed throughput instability.
Sample-mean concurrency latency ranges have a 1.10% median and 6.42% maximum. Extreme
sample percentiles are retained but are not promoted into an SLA.

## Thirty-minute soak medians

| Metric | Three-member median | Cross-member relative range |
|---|---:|---:|
| Read throughput | 539.308 ops/s | 0.503% |
| Write throughput | 85.388 ops/s | 1.172% |
| Read p50 / p95 / p99 | 23.168 / 57.634 / 77.235 ms | 2.35% / 1.63% / 2.91% |
| Write p50 / p95 / p99 | 11.806 / 12.292 / 14.248 ms | 1.38% / 1.61% / 0.99% |
| GC count / time | 3,162 / 6,919 ms | 0.474% / 1.431% |
| Dynamic-index cycles | 1,663 | 0.481% |
| Writer queue non-zero samples / maximum | 15 / 1 | diagnostic |
| Final document count / errors | 100,000 / 0 | identical |

All three soak runs report `PASS`, `analysis_status=VALID`, zero engine errors, final
writer queue depth zero, stable document count, and no high-GC or sustained-queue flag.
All three also report `review_required=true` because:

- read-rate drift is `-11.743%`, `-11.060%`, and `-11.517%`;
- average heap-band growth is approximately 617, 596, and 510 MiB;
- minimum heap-band growth is approximately 625, 530, and 571 MiB.

This is consistent with the frozen V3 soak investigation. Under revision-changing
replacement and sustained snapshot publication, the 30-minute production cell shows a
duration-dependent read decline and heap-band movement. Earlier controlled work found
stable writes, low GC, negligible queue pressure, and no equivalent decline under
content-stable replacement. The canonical run adds replication and a comparison anchor;
it does not change that causal boundary or justify an unmeasured engine change.

## How to use this baseline

Future comparisons should resolve `v3.0.0-cloud` after its exact set has been verified
and materialized under the configured local results root. The current protected
workflow intentionally does not accept a baseline input or download remote evidence;
it produces the candidate set, while comparison remains a separate reviewed operation.
A candidate must retain the same configuration and environment fingerprints unless the
experiment deliberately defines and reviews a new baseline family. Review both the
generated comparison verdict and the raw metric context; no single percentage from
this report is a substitute for the versioned comparison policy.

V4 persistence work should initially compare unchanged in-memory paths to this entry.
Persistence-specific startup, recovery, write-amplification, disk-footprint, and durable
mutation workloads require a separate frozen benchmark contract and must not be mixed
silently into this V3 registry identity.

Related interpretation is recorded in the
[cloud soak diagnostic results](CLOUD_SOAK_DIAGNOSTIC_RESULTS.md) and
[early-window stabilization results](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION_RESULTS.md).
