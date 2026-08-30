# V3.1 Phase 7 frozen regression review

## Decision

Protected workflow run `33306780388`, attempt 1, produced the required three-member
candidate on the unchanged V3 production lane. Its exact configuration fingerprint,
environment fingerprint, suite, preset, and 357 metric identities match the registered
`v3.0.0-cloud` baseline. The ordered baseline-to-candidate comparison is
`DIRECTLY_COMPARABLE` and completes the Phase 7 regression-evidence gate.

The candidate is accepted with review signals, not as a claim that every metric
improved. The report contains no material regression in an existing search mean,
mixed mean, throughput, or soak latency/throughput metric. Its five
`POSSIBLE_REGRESSION` rows are five percentile views of one sparse 4-reader/1-writer
write-tail observation. That cell's write mean, p50, throughput, and allocation remain
neutral or better, and the sustained soak writer surface does not reproduce a harmful
shift. No score-based replacement or additional paid rerun is justified by this
evidence.

The known V3 revision-update soak signal remains: all candidate members require review
for read-rate drift and heap-band behavior. This is retained as a later hardening
investigation and is not reclassified as a V3.1 correctness failure or hidden by the
favorable search results.

## Candidate identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33306780388 / 1` |
| Source commit | `9d4c43c230abb260ac1736cc3dd4d29d4f29fbe9` |
| Request | `canonical / all / 3 / standard / c3d-standard-30 / 30m / gcs` |
| Suite / preset | `v3-production / v3-production-all-v1` |
| Set status | `VALID_CANONICAL_SET` |
| Set ID | `gse-set-v1-1356e9d46425c3730f4bd8d5ce61dcfbf2f7f3fcbaf11d1cf3af2f26faa51a60` |
| Set manifest SHA-256 | `sha256:eab521f67fa81702997c2280ea09247ccdc903d5c6b86f372581db1a4ea4dcac` |
| Configuration fingerprint | `sha256:fd1935ce328d45b0e626bb1474c6454220b861fabdee79b5601a5c8061989ad5` |
| Environment fingerprint | `sha256:39c7a09cb62458e55c1ec749d5fd48f894f7cd19879532ce1ad7ecc0f3ead0cd` |
| Upload receipt | `gse-upload-receipt-v1-935c1ba4dbf40b9d31638280b8c1dcfbab4e1ff65c5ddc7f3805d3f31a515049` |
| Receipt SHA-256 | `sha256:d98434d69e4db36c05c142a3835e830c2d91d498c1293019c8a23057477852db` |
| Durable objects | 103 |
| Durable manifest generation | `1788095594187560` |

All artifact, derived-member, set, comparison, and receipt checksums verify. Every
member is a first-attempt `VALID_CANONICAL_MEMBER`; there are no replacements,
preemptions, restarts, warnings, or missing metric identities. The receipt inventories
84 raw, nine derived-run, six orchestration, and four set objects with immutable object
identity and integrity metadata.

| Slot | Run ID | VM lifetime | Result |
|---:|---|---:|---|
| 1 | `20260830T103615Z-9d4c43c230ab-all` | 50m 44s | pass and cleaned |
| 2 | `20260830T112701Z-9d4c43c230ab-all` | 50m 42s | pass and cleaned |
| 3 | `20260830T121752Z-9d4c43c230ab-all` | 50m 43s | pass and cleaned |

## Registered-baseline binding and comparison identity

The locally materialized baseline artifact independently verifies against the tracked
`v3.0.0-cloud` entry:

- set `gse-set-v1-4767465528d42ea635ea7f1ed9a6d42b244f2c4e49acc8addc45eba180d06cfb`;
- source commit `4e446ba9bccebe8f9c3c848738ec9f27f18e1288`;
- set-manifest SHA-256
  `sha256:2c67749151a932008d7d282302d08f4003ee97dfb3eee40ca5d791f74db37122`;
- receipt SHA-256
  `sha256:d227382d6c85116dcdd448c8c680ce7c0decdcc87b6d6209c19a10ab6a4d64f9`;
- durable manifest generation `1788004730266975`.

The official comparison is:

```text
gse-comparison-v1-03c8bedca5ebbc24898134fa3da30b0c31ee9856e7a252f2a8c5e025be878a3b
baseline  = v3.0.0-cloud
candidate = gse-set-v1-1356e9d46425c3730f4bd8d5ce61dcfbf2f7f3fcbaf11d1cf3af2f26faa51a60
status    = DIRECTLY_COMPARABLE
metrics   = 357
```

The report classifies 45 metric rows as `MATERIAL_IMPROVEMENT`, 32 as
`IMPROVEMENT`, 113 as `NEUTRAL`, five as `WARNING`, and five as
`POSSIBLE_REGRESSION`. Four metric-level `INVALID` rows are the registered baseline's
already unhealthy or non-unanimous soak review flags, not invalid input evidence; 153
diagnostic metrics intentionally have no ordered classification. The comparison
contract does not collapse these heterogeneous rows into a pass/fail score.

## Existing search surface

The 1M uniform-English document-scale medians remain neutral under the variation-aware
policy:

| Query | Baseline | Candidate | Delta | Classification |
|---|---:|---:|---:|---|
| BOOL | 60.986 ms/op | 59.908 ms/op | -1.77% | neutral |
| TEXT | 52.915 ms/op | 52.929 ms/op | +0.03% | neutral |
| PHRASE | 88.197 ms/op | 86.025 ms/op | -2.46% | neutral |
| FUZZY | 59.877 ms/op | 57.086 ms/op | -4.66% | neutral |

The phrase optimization is clearly visible at smaller production cells: 10k and 100k
document PHRASE means improve by 28.81% and 27.29%, while normalized allocation falls
by about 60.33% and 60.40%. At 1M, PHRASE allocation falls by 55.31% with neutral mean
time. The 1M BOOL allocation reduction is 11.25%; TEXT and FUZZY allocation remain
effectively unchanged.

The only search-primary warning is a 10k uniform TEXT corpus-shape cell moving from
0.434 to 0.471 ms/op. Its absolute change is about 0.037 ms/op and the candidate's
three-member range is 8.09%, so it remains a small-duration warning rather than a
material regression. The paired allocation warning is about 40 KiB/op and similarly
variation-dominated. The independently named document-scale 10k TEXT cell is neutral.

## Concurrency and soak review

At 1, 4, and 16 readers, mixed throughput changes by less than 1%. Read throughput
improves by 5.67% at one reader and 5.07% at 16 readers. Normalized mixed allocation
falls by approximately 13.6%, 25.2%, and 32.3% across the three groups.

The review-required 4-reader write sample moves from 8.127 to 8.314 ms/op in mean and
from 8.053 to 8.094 ms/op at p50, both neutral. Write throughput moves from 121.514 to
118.296 ops/s, also neutral. Its p95 and p99 are warnings; p99.9 through maximum are
the five duplicated `POSSIBLE_REGRESSION` rows because the sparse sample tail repeats
the same 21.660 ms maximum. This is retained for future concurrency-tail review.
The remaining concurrency warning is the one-reader read p90 moving from 50.607 to
53.150 ms; its read sample mean improves by 5.63% and read throughput improves by
5.67%, so the isolated p90 shift is retained without promoting it to a broad read-path
regression.

The 30-minute soak remains operationally healthy:

| Metric | Baseline | Candidate | Interpretation |
|---|---:|---:|---|
| Read throughput | 539.308 ops/s | 562.317 ops/s | +4.27%, neutral |
| Write throughput | 85.388 ops/s | 86.632 ops/s | +1.46%, neutral |
| Read p95 / p99 | 57.634 / 77.235 ms | 53.078 / 71.483 ms | improvements |
| Write p50 / p95 / p99 | 11.806 / 12.292 / 14.248 ms | 11.643 / 12.140 / 13.227 ms | neutral |
| GC count / time | 3162 / 6919 ms | 2252 / 5004 ms | diagnostic reduction |
| Writer queue maximum / final | 1 / 0 | 1 / 0 | unchanged and drained |
| Errors / final documents | 0 / 100000 | 0 / 100000 | identical |

All three candidate members are `PASS` and `VALID`, with zero errors, no high-GC,
write-drift, or sustained-queue flag. Median read-rate drift improves from -11.52% to
-10.93%, but remains flagged. Average heap-band growth rises from about 624 MB to
659 MB, minimum growth remains near 593 MB, and all candidate members report no
plateau. These are known diagnostic boundaries, not an SLA or permission to omit later
long-run hardening.

## Registration outcome

Phase 7 now has both required cloud lanes reviewed. The ranked feature set documented
in [the feature canonical review](PHASE_7_CANONICAL_REVIEW.md) was subsequently
registered under the new immutable name `v3.1.0-ranked-cloud`. The explicit registry
change preserves `v3.0.0-cloud` and completes the final Phase 7 gate.
