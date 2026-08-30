# V3.1 Phase 7 ranked feature canonical review

## Decision

Protected workflow run `33299490397`, attempt 1, produced an accepted three-member
canonical set for the isolated V3.1 ranked feature lane. All members completed on their
first attempt, exposed the exact 84-configuration and 460-metric identity, passed
canonical eligibility, and uploaded checksum-bound evidence to GCS. No member was
selected or replaced by score.

The set is registered as the new immutable feature family
`v3.1.0-ranked-cloud`. It is deliberately incomparable with
`v3.0.0-cloud`: the suite, preset, heap, configuration fingerprint, and metric set are
different. The frozen V3 regression lane has now been run and reviewed separately;
the distinct registration completes the final Phase 7 gate.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33299490397 / 1` |
| Source commit | `9d4c43c230abb260ac1736cc3dd4d29d4f29fbe9` |
| Request | `canonical / ranked-v31 / 3 / standard / c3d-standard-30 / 30m / gcs` |
| Suite / preset | `v3.1-ranked-suite-v1 / v3.1-ranked-v1` |
| JVM | OpenJDK `21.0.12`, `-Xms32g -Xmx64g` |
| Set status | `VALID_CANONICAL_SET` |
| Set ID | `gse-set-v1-bff8407c3732fbe914de11baacf6d5368f28597cbb7b0402b5925afd58d532a2` |
| Configuration fingerprint | `sha256:1c9a9ef7e94776ecf34e0bd804f13d386e47440d0f4a6a3e12cff5c0cdeaae91` |
| Environment fingerprint | `sha256:51080e358d847728b6aaedb238f4d873158a1fde09b06c43b95a2b13ce2595f9` |
| Upload receipt | `gse-upload-receipt-v1-eaf81fcee1699ed275f1eb0dbd125ec7b71b7249e650c568b020847751847c50` |
| Receipt SHA-256 | `sha256:772499303b1e63c4faf3334398e2b0ce349c686e562a12b3e2665b9f78db7deb` |
| Durable objects | 76 |
| Durable manifest generation | `1788084628819510` |
| Durable manifest | `gs://gse-benchmark-evidence-266952534277/general-search-engine/sets/gse-set-v1-bff8407c3732fbe914de11baacf6d5368f28597cbb7b0402b5925afd58d532a2/v1/benchmark-set-manifest.json` |
| Registry name | `v3.1.0-ranked-cloud` |

The artifact inventory, every member's derived inventory, the set inventory, and the
upload-receipt checksum all verify. The receipt contains 57 raw, nine derived-run, six
orchestration, and four set objects. Every object has a unique URI and immutable
generation plus SHA-256, CRC32C, MD5, size, role, and relative-path metadata.

## Independent-member controls and runtime

| Slot | Run ID | VM lifetime | JMH time | Margin below cap |
|---:|---|---:|---:|---:|
| 1 | `20260830T073525Z-9d4c43c230ab-ranked-v31` | 55m 17s | 47m 44s | 4m 43s |
| 2 | `20260830T082545Z-9d4c43c230ab-ranked-v31` | 53m 32s | 48m 00s | 6m 28s |
| 3 | `20260830T091624Z-9d4c43c230ab-ranked-v31` | 50m 21s | 47m 51s | 9m 39s |

Every orchestration record reports `BENCHMARK_PASS`, exit zero, recovered artifacts,
verified raw checksums, no interruption or restart, and successful cleanup. All members
used the same C3D-30, Ubuntu image, Java version, preset, suite, and normalized
environment. Guest memory differed by only 4 KiB and remained within the fingerprint's
reviewed tolerance.

## Matrix and feature ranges

Each member contains 22 phrase, 36 BOOL, ten fuzzy, two initial-build, 12 publication,
and two mixed-concurrency entries. Metric identity is identical across all members;
all 460 aggregate metrics have three finite member values and the set has no warnings.

Most primary feature cells have modest independent-VM range. Phrase primary mean-time
ranges have a 2.15% median and 9.90% maximum; fuzzy has a 2.24% median and 3.60%
maximum. BOOL has a 2.87% median and 13.39% maximum. Publication's largest percentage
ranges are 15.95% and 15.12% on unchanged 100k cells whose medians are only 0.229 ms/op
and 0.00229 ms/op.

The 1M initial text build is the material review signal: member means are 3952.527,
4987.990, and 3915.106 ms/op, a 27.14% range. This is not evidence corruption or an
allocation/GC drift. Allocation is effectively identical at about 8.629 GB/op, while
GC time ranges only from 1811 to 1841 ms. The raw JMH iterations show that slot two's
second fork repeated the same early high-latency shape seen in every first fork, while
the other second forks settled near 2.8-3.5 seconds. The resulting per-member
confidence intervals are broad and overlap. The canonical median and full range are
therefore retained as an explicit unstable-cell diagnostic; no score-based member
replacement or unsupported threshold rejection is applied.

## Mixed-concurrency evidence

| Metric | Median | Member range | Relative range |
|---|---:|---:|---:|
| Sample mean | 283.945 ms/op | 280.346-292.812 | 4.39% |
| Read sample mean | 339.108 ms/op | 334.839-362.234 | 8.08% |
| Write sample mean | 79.040 ms/op | 73.947-82.600 | 10.95% |
| Mixed throughput | 58.575 ops/s | 57.706-60.890 | 5.44% |
| Read throughput | 45.972 ops/s | 45.172-48.268 | 6.73% |
| Write throughput | 12.603 ops/s | 12.533-12.622 | 0.70% |
| Sample snapshots | 200 | 189-212 | 11.50% |
| Throughput snapshots | 196 | 192-201 | 4.59% |
| Writer queue maximum | 1 | 1-1 | 0% |

Normalized allocation is stable: the sample cell median is 126,929,251 B/op with a
0.44% range, and throughput is 126,956,928 B/op with a 0.17% range. Allocation rates
are about 6.4 GB/s. Sample GC count/time have medians 20/1353 ms; throughput has
19/1342 ms. Sparse write-sample tail percentiles have visibly larger ranges and remain
diagnostic rather than latency-SLA claims. Positive snapshot counts, queue maximum one,
and successful teardown in all members show continued writer progress and a drained
queue.

## Registration and Phase 7 completion

The separately reviewed regression candidate used the unchanged registered-baseline
shape:

```text
canonical / all / 3 / standard / c3d-standard-30 / 30m / gcs
preset = v3-production-all-v1
```

That candidate is the only Phase 7 lane directly comparable with `v3.0.0-cloud`; its
evidence and comparison are recorded in
[the frozen regression review](PHASE_7_REGRESSION_REVIEW.md). After that review, the
ranked feature set was explicitly registered as `v3.1.0-ranked-cloud`, bound to its
exact GCS generation and receipt. The protected workflow performed neither comparison
nor registration automatically. This separate reviewed change completes Phase 7.
