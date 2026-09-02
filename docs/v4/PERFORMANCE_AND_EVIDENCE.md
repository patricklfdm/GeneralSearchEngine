# V4.0 performance and evidence contract

Cloud control, preserved-disk failure drills, artifact structure, cost, and cleanup
obey the independent
[crash harness and cloud durable lane contract](CRASH_HARNESS_AND_CLOUD_LANE.md).

## Measurement principle

Correct recovery and bounded operation are release gates. V4.0 does not promise V3.4
mutation latency or startup parity. Reports keep durability cost visible rather than
combining incompatible paths.

## Required cells

Evidence reports separately:

- published V3.4 in-memory reference;
- V4.0 in-memory compatibility path;
- V4.0 durable single and bulk mutations;
- force-group sizes and per-operation latency distribution;
- explicit and automatic checkpoint time, CPU, allocation, and temporary bytes;
- WAL-only replay, checkpoint load, document decode, index rebuild, and total open;
- steady retained bytes, temporary peak, WAL/checkpoint amplification, and cleanup;
- capacity-limit and cleanup-failure behavior; and
- repeated crash/reopen and long-run durable workloads.

Throughput never substitutes for p50/p95/p99/max latency and completion count. Recovery
numbers state document count, encoded bytes, WAL units/bytes, indexes, analyzer kinds,
heap, filesystem/device, force policy, and cold/warm cache status.

## Baseline and cloud isolation

`v3.4.0-in-memory-cloud` remains immutable and is a comparison input only. V4 creates
a distinct suite/preset/baseline family:

- suite: `v4.0-durable-single-node-suite-v1`;
- preset: `v4.0-durable-single-node-v1`;
- eventual registration: `v4.0.0-durable-cloud`.

The V4 family must never overwrite or relabel V3.4 results. Canonical members use one
final source, Standard provisioning, fixed machine/image/runtime/filesystem/device,
identical codec/corpus/configuration, durable artifact retention, checksums, and
mandatory resource cleanup. At least three eligible members are required.

## Required release evidence

- local functional, crash, corruption, and fault-injection gates;
- exact-V3.4 versus V4 in-memory compatibility evidence;
- large WAL-only and checkpoint-plus-WAL recovery profiles;
- disk-bound and cleanup-failure tests;
- multi-producer group-commit and mixed-reader/writer stress;
- a repeated process-crash loop;
- one preserved-disk VM failure/recovery exercise;
- a controlled durable long run; and
- the three-member canonical cloud set on final source.

Paid cloud execution occurs only after local/fake orchestration, budget, timeout,
retention, checksum, failure, and cleanup gates pass. The user initiates cloud runs.

## Optimization rule

No speculative cache, persisted index, multi-writer path, unsafe force relaxation, or
semantic change is justified by a benchmark. Optimization follows a reproduced
bottleneck and must pass the full durability and V3.4 equivalence matrix.

## Phase 6 executable realization

Phase 6 implements this contract through `V40DurableMutationBenchmark`, the standalone
`V40DurableOperationalProbe`, `scripts/v4/durable_performance.py`, and the independent
cloud set validator. Package-private counters report actual successful force groups and
recovery stages without expanding supported API. The manual performance and
preserved-disk failure workflows are separate from `cloud-performance.yml` and all V3
registries. See [the Phase 6 contract](PHASE_6_PERFORMANCE.md) for the frozen profiles,
resource lifecycle and evidence order.
