# V4.0 Phase 6 durable canonical review

## Decision

Protected workflow run `33663850586`, attempt 1, produced the accepted three-member
canonical set for the independent V4 durable single-node lane. All three serially
scheduled members completed on their first attempt, passed member and set validation,
retained their evidence in GCS, and reported successful VM and persistent-disk cleanup.
No member was selected, replaced or reused from an earlier run.

The set is accepted for append-only registration as `v4.0.0-durable-cloud`. It is a
durability-specific comparison anchor and is intentionally not interchangeable with
the registered V3 in-memory families. Registration records the measured behavior; it
is not an SLA or a portable hardware claim.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33663850586 / 1` |
| Source commit | `e8fac153996e10af6fd880078106a49c531e7cdc` |
| Request | `canonical / 3 / standard / c3d-standard-30 / 30m / gcs` |
| Suite / preset | `v4.0-durable-single-node-suite-v1 / v4.0-durable-single-node-v1` |
| Image / zone | `ubuntu-2404-noble-amd64-v20260826 / us-west4-a` |
| Data disk / filesystem | `pd-balanced 200 GiB / ext4 defaults` |
| Codec / schema / storage | `v40-performance-codec-v1 / v40-performance-schema-v1 / v40-performance-store-v1` |
| Set status | `PASS / canonicalEligible=true / members=3` |
| Set SHA-256 | `4a33e6193fa3c02b609b7a177b16bf16792d197c1eca45437d225154022d0998` |
| GCS layout | `v4-durable/33663850586-1/{1,2,3,set}/` |
| Registry name | `v4.0.0-durable-cloud` |

The downloaded Actions mirrors, all member checksum inventories, the assembled set,
the GCS directory layout and the six VM/disk absence checks passed independent local
review.

## Independent-member controls

| Slot | Evidence SHA-256 | Run | Cleanup |
|---:|---|---|---|
| 1 | `767f7d7893d1cfd97b6a83ddef8b65bf8296f3ffc7101b725606b55604f22dc6` | PASS | PASS |
| 2 | `f8ed858add76794f25dc8883622a0b28bd2a4ec5f2326e50764795ec5aab46f4` | PASS | PASS |
| 3 | `348f2cc71f3c723bbdf87fee581f345e9c2df158693242c76c481c4eb890a86d` | PASS | PASS |

Every member used the same source, machine, pinned image, zone, filesystem, duration
and codec/schema/storage identities. Serial scheduling changed only allocation overlap:
each member still received a fresh Standard VM and independent persistent data disk.

## Measurement review

Values below are the three-member median, full member range and relative range around
the median. Latencies are milliseconds.

| Metric | Median | Member range | Relative range |
|---|---:|---:|---:|
| Durable single p50 | 9.691 ms | 9.402-9.786 ms | 3.97% |
| Durable single p95 | 24.879 ms | 23.322-26.004 ms | 10.78% |
| Durable single p99 | 27.388 ms | 24.653-28.091 ms | 12.56% |
| Durable 100-element bulk p50 | 4.763 ms | 4.650-4.867 ms | 4.56% |
| Durable 100-element bulk p95 | 20.361 ms | 19.506-21.772 ms | 11.13% |
| Explicit checkpoint | 881.619 ms | 874.579-895.409 ms | 2.36% |
| WAL-only open | 179.834 ms | 177.803-181.292 ms | 1.94% |
| Checkpoint-only open | 159.683 ms | 158.392-159.941 ms | 0.97% |
| Checkpoint-plus-WAL open | 173.834 ms | 173.762-176.352 ms | 1.49% |
| 30-minute reads | 46.143 billion | 45.371-47.325 billion | 4.23% |
| 30-minute durable writes | 1,064,848 | 1,050,440-1,070,348 | 1.87% |
| Maximum retained bytes | 4,946,589 | 4,905,361-4,988,214 | 1.67% |

All members produced the same in-memory and durable logical checksum
`-8452554388534467023`. Each group-commit cell forced 3,200 logical units in 200
groups, with average and maximum group size 16. Retained checkpoint amplification was
`1.163157x` and temporary amplification `2.458854x` in every member. WAL-only,
checkpoint-only and checkpoint-plus-WAL recovery classifications matched their
requested cells.

Every long-run cell remained `OPEN`, completed 31 checkpoints, made positive read and
write progress, and ended with bounded retained storage. The larger tail-latency ranges
remain visible diagnostics; they are neither hidden nor converted into an SLA. The
cross-member shape contains no evidence-integrity, allocation, recovery or lifecycle
outlier and justifies no semantics-changing optimization.

## Registration boundary

The append-only registry binds `v4.0.0-durable-cloud` to this exact source, suite,
preset, three-member count and set digest. Future comparisons must validate and
materialize this independent V4 set before use. They must not silently compare its
durable mutation, checkpoint, recovery or long-run metrics with a V3 in-memory set.

The earlier experiment, staged infrastructure failures, successful preserved-disk
replacement-VM drill and quota-bounded serial scheduling decision remain recorded in
[the Phase 6 baseline](PHASE_6_BASELINE.md).
