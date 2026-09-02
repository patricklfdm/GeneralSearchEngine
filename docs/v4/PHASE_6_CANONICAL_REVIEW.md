# V4.0 Phase 6 durable canonical review

## Decision

Protected workflow run `33682157985`, attempt 1, produced the accepted three-member
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
| Workflow run / attempt | `33682157985 / 1` |
| Source commit | `fe2060b9a872e66ff0067be6e8b7c900f0099708` |
| Request | `canonical / 3 / standard / c3d-standard-30 / 30m / gcs` |
| Suite / preset | `v4.0-durable-single-node-suite-v1 / v4.0-durable-single-node-v1` |
| Image / zone | `ubuntu-2404-noble-amd64-v20260826 / us-west4-a` |
| Data disk / filesystem | `pd-balanced 200 GiB / ext4 defaults` |
| Codec / schema / storage | `v40-performance-codec-v1 / v40-performance-schema-v1 / v40-performance-store-v1` |
| Set status | `PASS / canonicalEligible=true / members=3` |
| Set SHA-256 | `5e71ae200f94f5713278db7312057c4454fb73e18d159f78e71c31a92c44abbf` |
| GCS layout | `v4-durable/33682157985-1/{1,2,3,set}/` |
| Registry name | `v4.0.0-durable-cloud` |

The downloaded Actions mirrors, every member checksum inventory, the assembled set
and all three cleanup receipts passed independent local review. Successful aggregate
completion also confirms the required GCS member and set retention steps.

## Independent-member controls

| Slot | Evidence SHA-256 | Run | Cleanup |
|---:|---|---|---|
| 1 | `6800296483d24f48a417e1e3c0acf8d0b7702da5aef2b22fc219415d9244f0b5` | PASS | PASS |
| 2 | `461b4362679dd74798352e53bcc81df641bf6775e3d8cddcaaaa5707f0ea075b` | PASS | PASS |
| 3 | `e435d47f06252f9a4c9b9a610c3456edb4e4a8f258d6b473d58043365a631113` | PASS | PASS |

Every member used the same source, machine, pinned image, zone, filesystem, duration
and codec/schema/storage identities. Serial scheduling changed only allocation overlap:
each member still received a fresh Standard VM and independent persistent data disk.

## Measurement review

Values below are the three-member median, full member range and relative range around
the median. Latencies are milliseconds.

| Metric | Median | Member range | Relative range |
|---|---:|---:|---:|
| Durable single p50 | 9.743 ms | 9.425-9.948 ms | 5.36% |
| Durable single p95 | 23.711 ms | 23.353-24.420 ms | 4.50% |
| Durable single p99 | 25.840 ms | 24.867-29.153 ms | 16.59% |
| Durable 100-element bulk p50 | 4.984 ms | 4.718-4.997 ms | 5.60% |
| Durable 100-element bulk p95 | 19.014 ms | 18.491-19.289 ms | 4.19% |
| Explicit checkpoint | 878.679 ms | 876.533-895.448 ms | 2.15% |
| WAL-only open | 169.047 ms | 165.617-169.483 ms | 2.29% |
| Checkpoint-only open | 164.078 ms | 160.618-166.697 ms | 3.71% |
| Checkpoint-plus-WAL open | 173.353 ms | 166.822-174.454 ms | 4.40% |
| 30-minute reads | 45.644 billion | 45.235-46.820 billion | 3.47% |
| 30-minute durable writes | 1,064,048 | 1,056,408-1,079,424 | 2.16% |
| Maximum retained bytes | 4,985,560 | 4,913,803-5,019,863 | 2.13% |

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
