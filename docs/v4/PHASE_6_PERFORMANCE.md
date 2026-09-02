# V4.0 Phase 6 performance and operational hardening

## Scope

Phase 6 measures the accepted format `1.0` implementation without changing public API,
storage bytes, force authority, recovery classification or completion semantics. The
only production-source addition is a package-private observation snapshot for actual
successful WAL force groups and recovery-stage timing. It cannot be reached through a
supported public type.

The evidence family remains:

- suite `v4.0-durable-single-node-suite-v1`;
- preset `v4.0-durable-single-node-v1`; and
- eventual baseline `v4.0.0-durable-cloud`.

Published `v3.4.0-in-memory-cloud` remains immutable comparison input. V4 evidence is
stored in a separate registry and never overwrites, relabels or joins a V3 set.

## Local measurement layers

`V40DurableMutationBenchmark` uses JMH sample time. It separates current-source
in-memory and force-backed durable single and bulk completion. Production evidence uses
the GC profiler so allocation and p50/p95/p99/max remain visible; throughput is not a
substitute for completion latency.

`V40DurableOperationalProbe` is a standalone process in the benchmark artifact. One
run records:

- identical in-memory/durable logical checksums;
- single and bulk completion distributions;
- actual force count, forced logical units, average and maximum group size;
- explicit checkpoint elapsed time, process CPU, retained bytes and temporary peak;
- WAL-only, checkpoint-only and checkpoint-plus-WAL total open, storage open,
  checkpoint decode, replay/rebuild and index rebuild times;
- encoded-corpus, WAL and retained-byte amplification; and
- a controlled mixed reader/writer/checkpoint long run with progress and retained-byte
  bounds.

The smoke profile is a correctness and plumbing gate only. The production profile
freezes 100,000 documents, 1,000 single mutations, 100 bulks of 100 elements, sixteen
group-commit producers, all three recovery sources and a caller-selected 30-minute or
two-hour long run. Corpus preloading is deliberately excluded from measured mutation
latency and is split into deterministic batches no larger than the engine's 1,000-item
atomic mutation bound. The evidence records that load-batch identity explicitly.

## Evidence validation

`scripts/v4/durable_performance.py` runs the standalone process, validates every
identity and invariant, retains bounded stdout/stderr, embeds all raw properties in a
checksummed evidence bundle, and removes its engine workspace. It rejects unordered
latency percentiles, checksum disagreement, missing progress, inconsistent force
units, incomplete recovery sources and invalid checkpoint byte measurements.

`scripts/v4/durable_cloud_set.py` accepts one experiment member or three comparable
canonical members. Canonical eligibility requires three paid GCP members on the same
exact source, machine, image, zone, filesystem, codec/schema/storage identity and
duration. Registration is append-only and permits only the frozen name
`v4.0.0-durable-cloud`.

## Paid cloud lanes

The user manually starts either workflow after its exact source is accepted on
protected `master`:

- `V4 durable performance` creates one independent Standard VM and one independent
  200-GiB `pd-balanced` data disk per member. The production probe runs on the data
  disk. Experiment is one member; canonical is three comparable members. Canonical
  evidence and the assembled set require GCS retention.
- `V4 durable preserved-disk failure drill` hard-halts a writer JVM at
  `v4-wal-before-future-completion-v1`, deletes the writer VM without deleting the
  data disk, attaches that same disk to a replacement VM, independently inspects the
  bytes, recovers and reopens again.

Both paths use short-lived Workload Identity Federation, an exact image, Standard
provisioning, no VM service account, bounded runtime, non-auto-deleted evidence disks,
checksummed artifacts, and explicit VM/disk cleanup receipts. Success and failure both
run cleanup and retain a bounded GitHub artifact; GCS profiles also attempt durable
partial-evidence retention. CI exercises only their dry-run, fake-cloud and local split
writer/recovery paths; it never provisions paid resources.

The shared WIF provider keeps repository, immutable owner/repository IDs, protected
`master`, `cloud-benchmark` Environment and an exact three-workflow allowlist. Its
custom role adds only `compute.disks.use` and `compute.disks.delete` for the V4 retained
disk lifecycle. Remote cold-start prerequisites explicitly include `unzip`, so the
Maven Wrapper downloads and validates the pinned ZIP rather than falling back to a
tarball under the ZIP checksum. The GCS variable follows the existing repository
contract and is one complete `gs://bucket` URI. A replacement VM normalizes ownership
only on the dedicated failure-drill workspace before the byte inspector runs, because
its ephemeral SSH account may not reuse the writer VM's numeric UID.

## Optimization decision

The first local smoke shows the expected forced-storage cost and confirms group force
is active. It is not stable hardware evidence and justifies no production optimization.
Any optimization requires reproducible production-profile evidence and must preserve
every Phase 2–5 correctness gate. Persisted indexes, multiple writers, relaxed force or
new retrieval semantics remain out of scope.
