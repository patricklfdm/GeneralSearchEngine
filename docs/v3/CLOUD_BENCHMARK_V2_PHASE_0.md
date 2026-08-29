# Cloud Benchmark V2 Phase 0 evidence model

## Status and authority

This contract freezes the evidence model for Cloud Benchmark V2 before implementation.
It is normative for V2 manifests, metric normalization, fingerprints, run sets,
comparison, baseline registration, durable upload, and manual workflow automation.
Examples in the root implementation prompt are informative when they do not conflict
with this document.

Phase 0 changes no search behavior, benchmark workload, cloud resource, or stored raw
result. A later implementation that cannot honor a rule here must stop and amend this
contract in a focused review before choosing a different behavior in code.

## Goal and boundary

Cloud Benchmark V1 answers whether one exact pushed commit can run on one ephemeral GCP
VM, return checksum-valid evidence, classify interruption, and clean up safely. V2 adds
an evidence and comparison layer that answers:

- which exact source, workload, hardware, image, JDK, and JVM produced a measurement;
- whether two measurements are scientifically comparable;
- how independent runs aggregate without selecting a convenient result;
- how a candidate differs from a human-reviewed baseline;
- where immutable evidence is retained.

V2 does not duplicate `scripts/run-v3-production-performance.sh`, rewrite the V1 VM
lifecycle, alter search semantics, optimize product code, or hard-fail normal CI on a
suspected performance regression.

## Frozen architecture

The dependency direction is one way:

```text
scripts/run-v3-production-performance.sh
        -> raw run with checksums
run-cloud-benchmark.sh
        -> verified local raw run + finalized orchestration record
scripts/cloud/benchmark_v2.py
        -> run manifest + normalized metrics
run-cloud-benchmark-set.sh
        -> independent V1 runs + checkpointed set manifest
comparison / registry / upload wrappers
        -> reports, reviewed references, and durable receipts
```

`run-cloud-benchmark.sh` remains the single-run V1 orchestrator. V2 does not add
evidence-profile routing to it. One dependency-free Python 3.11+ standard-library
utility owns JSON parsing, canonical serialization, hashing, statistics, and Markdown
report data. Thin Bash wrappers may own shell preflight and user-facing commands.

The analyzer runs after local checksum verification. Remote benchmark execution remains
Java/Bash and does not require Python.

## Terms

| Term | Frozen meaning |
|---|---|
| raw run | One timestamped result directory produced by the canonical workload runner and covered by its `checksums.sha256` |
| orchestration record | The finalized V1 properties record for the VM lifecycle that recovered a cloud raw run |
| derived run | Deterministic manifest, normalized metrics, and report created from one verified raw run plus its orchestration record |
| evidence profile | `experiment` or `canonical`; unrelated to the existing soak JFR profile |
| slot | One predeclared independent run position in a run set |
| attempt | One V1 invocation assigned to a slot, including invalid infrastructure attempts |
| run set | An ordered collection of independent derived runs with one final valid member per completed slot |
| baseline | A human-reviewed immutable canonical set reference in the tracked registry |
| candidate | The run or set being compared with a baseline |
| upload receipt | A separate immutable record binding source digests to verified GCS objects and generations |

The schema spelling is `evidenceProfile`. Shell configuration uses
`GSE_BENCHMARK_EVIDENCE_PROFILE`. Neither reuses `GSE_SOAK_PROFILE`, which continues to
mean `none` or `jfr` for investigation workloads.

## V1 behavior preserved

V2 preserves the existing V1 sequence and exit semantics:

```text
preflight -> provision -> bootstrap -> detached exact checkout -> benchmark
          -> recover -> verify checksum -> classify -> cleanup
```

Existing V1 commands and environment variables retain their behavior, including:

```bash
./run-cloud-benchmark.sh quick
./run-cloud-benchmark.sh full
./run-cloud-benchmark.sh concurrency
./run-cloud-benchmark.sh soak
./run-cloud-benchmark.sh investigation
./run-cloud-benchmark.sh stabilized-investigation
./run-cloud-benchmark.sh all
./run-cloud-benchmark.sh --dry-run full
./run-cloud-benchmark.sh --keep-vm full
```

V1 exit codes `2`, `10`, `20`, `30`, `40`, `50`, `60`, and `70` remain unchanged. V2
wrappers call V1 rather than translating those failures into successful measurements.

## Raw and derived evidence boundary

The local layout is fixed:

```text
benchmark-results/v3-production/
  <raw-run-id>/
  cloud-orchestration/
    <instance>.properties
    <instance>.log
  partial/
  quarantine/
  derived/
    runs/<raw-run-id>/v1/
      benchmark-manifest.json
      normalized-metrics.json
      report.json
      report.md
      derived-checksums.sha256
  sets/<set-id>/
  comparisons/<comparison-id>/
  upload-receipts/<receipt-id>/
```

After `checksums.sha256` passes locally, V2 never creates, edits, removes, or regenerates
anything below the raw run directory. Derived artifacts are siblings, not children.
Partial, quarantined, missing-checksum, checksum-invalid, and unfinished evidence may be
retained but is never a valid canonical member.

The orchestration record becomes immutable evidence when `stage=FINISHED`. A derived
cloud run requires exactly one matching record. Matching validates:

- raw `cloud_instance_name` equals orchestration `instance_name`;
- raw commit equals requested and remote commit;
- raw mode equals orchestration benchmark mode;
- orchestration `local_result_path` basename equals raw run ID;
- artifact recovery and checksum verification are true;
- ordinary successful evidence has `run_complete=true` and successful cleanup;
- raw and remote PASS/FAIL state agree.

`--keep-vm` experiment evidence may be analyzed with a warning but is not canonical
eligible until cleanup is separately proven. No orchestration property is copied into a
manifest before this binding succeeds.

Source identities are:

```text
rawChecksumManifestSha256 = SHA-256 of the exact checksums.sha256 bytes
orchestrationRecordSha256 = SHA-256 of the finalized orchestration properties bytes
```

Absolute local paths are never scientific identities and do not appear in canonical
manifests. Raw run ID and relative derived file names are portable identifiers.

## Raw evidence schema

Newly produced raw runs add these backward-compatible metadata properties before the
raw checksum manifest is created:

```text
evidence_schema_version=1
benchmark_suite=v3-production
benchmark_suite_schema_version=1
source_repository=<canonical repository URL>
kernel_release=<uname -r>
memory_bytes=<MemTotal from /proc/meminfo multiplied by 1024>
cpu_vendor=<normalized vendor>
cpu_model=<normalized model>
cpu_sockets=<positive integer>
cpu_cores_per_socket=<positive integer>
cpu_threads_per_core=<positive integer>
java_vendor=<runtime vendor>
java_runtime_version=<exact runtime version>
java_vm_name=<VM name>
java_vm_version=<exact VM build>
```

`kernel_release` comes from `uname -r`. `memory_bytes` comes from the integer `MemTotal`
kilobytes in `/proc/meminfo`, multiplied by 1024 with checked integer arithmetic. CPU
facts come from `LC_ALL=C lscpu`; Java facts come from the stable property keys emitted
by `java -XshowSettings:properties -version`. The implementation records and tests the
exact parsers and rejects missing, duplicate, non-integer, or multiline facts. Existing
`logical_cpus`, exact cloud image facts, JMH settings, JVM options, workload
configuration, commit, status, and working-tree evidence remain.

Any semantic change to benchmark implementation, corpus generation, query mix, timing,
metric meaning, or normalization increments `benchmark_suite_schema_version`. Adding an
optional manifest field without changing workload or metric meaning increments only the
relevant derived schema when necessary.

Historical raw runs with no `evidence_schema_version` are schema 0. V2 supports only
explicitly tested schema-0 shapes. Missing strict fingerprint facts make a legacy run
exploratory or unsupported; V2 never manufactures an image, branch, memory value, JDK
build, benchmark parameter, or orchestration fact. A PASS schema-0 run is not
automatically canonical eligible.

## Canonical serialization

All V2 JSON schemas use:

- UTF-8 without a byte-order mark;
- lexicographically sorted object keys;
- schema-defined array order;
- JSON numbers for finite numeric values only;
- `null` plus an explicit reason for unavailable numeric facts;
- no generated-at timestamp in content-addressed manifests;
- one trailing newline and otherwise compact deterministic serialization for hashes.

Human Markdown may format rounded values, but JSON retains the parsed finite value and
unit. Re-running the same command over identical source bytes produces byte-identical
derived JSON and the same IDs.

## Run manifest schema version 1

`benchmark-manifest.json` has `schemaVersion=1` and `kind=benchmark-run`. Required
logical sections are:

```text
project
runId
status and canonicalEligibility
source(repository, commit, optional branch)
evidenceProfile
suite(name, raw schema, suite schema)
benchmark(mode and configuration summary)
environment(provenance facts)
environmentFingerprint
benchmarkConfigFingerprint
evidence(raw run ID, source digests, checksum and orchestration decisions)
metrics(relative path, schema version, SHA-256, metric count)
warnings
```

`source.commit` is the 40-character checked-out SHA. `source.branch` is nullable and
never inferred because cloud V1 intentionally uses detached HEAD. A tag or release name
is optional reviewed provenance and never substitutes for the commit.

Manifest status distinguishes at least:

```text
VALID_EXPERIMENT
VALID_CANONICAL_MEMBER
INVALID
UNSUPPORTED
```

Only PASS raw evidence with complete strict identities, clean source, matching finalized
orchestration, verified checksum, no interruption, and successful ordinary cleanup may
be `VALID_CANONICAL_MEMBER`.

## Normalized metric schema version 1

`normalized-metrics.json` has `schemaVersion=1`, the raw run ID, suite identity, and a
sorted `metrics` array. The canonical metric ID is derived from:

```text
suite schema version
workload name
benchmark FQCN
JMH mode
sorted benchmark parameters
thread and thread-group configuration
metric role and source name
statistic kind
unit
```

Each metric records:

```text
id
source file and source field
workload / benchmark / mode
parameters and threads
statistic kind
source value and source unit
canonical value and canonical unit, when a supported exact conversion exists
optimization direction: lower | higher | categorical | diagnostic
confidence/error/percentile metadata when semantically valid
comparison policy ID or null
```

Metric arrays sort by ID. Duplicate IDs with different values are invalid. Required
canonical-set metrics must occur once in every member with identical identities and
units.

### JMH rules

V2 reads JMH JSON, never console logs, for numeric JMH metrics. It supports explicitly
tested primary and secondary fields, including score, score error/confidence when
finite, normalized allocation, GC count/time, sample-mode secondary groups, and known
units.

JMH average-time iteration percentiles are not request-latency percentiles and are not
exported as p50/p95/p99. Sample-mode percentiles may be exported as sampled latency
percentiles. A set aggregate of per-run p99 values is labeled `median_of_run_p99`, not
as a newly pooled p99. JSON string `"NaN"` becomes unavailable with a reason, never zero.

Historical `concurrent-read-write-*` and current `concurrent-latency-*` /
`concurrent-throughput-*` shapes require separate fixtures and adapters. File naming is
not sufficient to assign metric meaning.

### Soak rules

V2 reads stable properties produced by the workload and analyzers. It may normalize:

- read/write operation rates and bounded-reservoir latency percentiles;
- per-query rates and latencies when enabled;
- errors, document/snapshot identity, writer queue, GC, and lifecycle counters;
- frozen drift and stabilization decisions as diagnostic metrics.

CSV is used only when a frozen property is unavailable and a narrow versioned parser is
contracted. Arbitrary log scraping is forbidden. Errors and failed identity checks are
categorical validity facts, not percentage performance metrics.

## Fingerprints

Fingerprints are SHA-256 of canonical JSON payloads with their own schema version.
Commit, run ID, timestamps, branch, instance name, IP, local path, and GCP project are
not inputs because they describe identity or provenance rather than the controlled
environment/configuration.

### Environment fingerprint version 1

Required inputs are:

```text
provider
zone
machine type
provisioning model
CPU vendor, model, logical CPUs, sockets, cores/socket, threads/core
memory bytes
resolved image project, name, and immutable ID
kernel release
exact Java vendor, runtime version, VM name, and VM version
ordered JVM options
```

Image family and creation time remain provenance; resolved image identity is the
control. CPU flags, frequency, BogoMIPS, instance name, and ephemeral resource facts are
excluded as noisy inputs.

Current V1 installs OpenJDK from apt at VM bootstrap. Until a pinned archive or immutable
benchmark image is separately implemented, exact JDK build equality is mandatory. Two
Java 21 builds that differ by patch, package, vendor, runtime, or VM version are not
directly comparable canonical environments.

### Environment fingerprint version 2

Version 2 supersedes version 1 for newly derived evidence after real independent C3D
boots demonstrated an 8 KiB `MemTotal` difference on otherwise identical machines. The
manifest still records exact `memoryBytes` as observed provenance. The fingerprint uses
that value rounded to the nearest MiB as `memoryMiB`; every other version-1 environment
input remains unchanged. This removes boot-reservation noise without treating a
material capacity change as comparable. Benchmark configuration fingerprint version 1
is unchanged.

### Benchmark configuration fingerprint version 1

Required inputs are:

```text
benchmark suite and suite schema version
mode and workload list
JMH version
forks, warmups, iterations, warmup time, measurement time, batch sizes
threads and ordered thread groups
sorted benchmark parameters for every workload
soak documents/readers/writers/seconds/sample interval/top K/corpus/update/lifecycle
stabilization and profile configuration when applicable
```

The candidate source commit is intentionally excluded: comparing different commits is
the purpose of the system. Workload implementation changes must increment suite schema.

## Evidence profiles and mode eligibility

| Evidence profile | Purpose | Provisioning | Repeats | Canonical registry eligible |
|---|---|---|---:|---:|
| `experiment` | cheap exploration or scientific investigation | Spot or Standard | one by default | no |
| `canonical` | release/version performance evidence | Standard only | at least three | yes, after review/upload |

The existing V1 single-run command is an experiment. The set wrapper accepts
`--evidence-profile`; it never adds `--profile` to V1.

Canonical regression modes are `full`, `concurrency`, `soak`, and `all`, each with a
versioned frozen preset. `quick` is always experimental. `investigation` and
`stabilized-investigation` remain controlled scientific experiments and cannot become a
canonical regression baseline.

Before a canonical set starts, the wrapper resolves one exact image and passes it to
every slot. It freezes project, zone, machine, Standard provisioning, JVM, workload
preset, and commit. Independent slots run sequentially by default:

```text
slot 1 -> fresh VM -> verify -> delete
slot 2 -> fresh VM -> verify -> delete
slot 3 -> fresh VM -> verify -> delete
```

Running repeated measurements inside one VM does not satisfy independence. A canonical
paid run requires an explicit `--confirm-paid-run`; `--dry-run` performs every possible
local/GCP read-only validation and prints VM count, mode, frozen inputs, maximum runtime,
cleanup commands, and derived destinations without mutation.

## Run-set state and aggregation

An in-progress set uses a temporary attempt directory and an atomic checkpoint after
every attempt. It predeclares profile, target commit, mode, preset, repeat count, slot
order, and expected controls before the first VM.

Each slot retains every attempt. Resume skips completed valid slots. Infrastructure
invalidity may be replaced only with an explicit replacement command and recorded
reason before benchmark scores are used for a scientific decision. The invalid attempt
remains referenced. Benchmark/correctness failure is evidence and leaves the set
incomplete; it is not automatically replaceable.

A complete canonical set requires:

- at least three slots and one valid final member per slot;
- distinct raw run IDs, instance IDs, and independent VM lifecycles;
- identical source commit, mode, suite schema, evidence profile, and both fingerprints;
- `VALID_CANONICAL_MEMBER` for every selected member;
- an identical required metric-ID/unit set across members;
- no hidden member or metric exclusion.

The final set ID is SHA-256-derived from set schema version, evidence profile, commit,
mode, fingerprints, ordered slot identities, and ordered member-manifest hashes.

For every metric, aggregation records count, ordered member values, minimum, median,
maximum, absolute range, and relative range:

```text
relativeRangePct = (max - min) / abs(median) * 100
```

When the median is zero, relative range is unavailable and absolute range remains.
Median for an even count is the arithmetic mean of the two central finite values. V2
does not select the fastest run, discard a valid slow run, pool JMH forks across VMs,
or invent a cross-run confidence interval.

## Comparability

Compatibility status is separate from performance classification:

```text
DIRECTLY_COMPARABLE
COMPARABLE_WITH_WARNINGS
INCOMPARABLE
INVALID
```

`DIRECTLY_COMPARABLE` requires complete canonical sets, identical supported schema
versions, identical environment fingerprints, identical benchmark configuration
fingerprints, and the same metric identities/units.

`COMPARABLE_WITH_WARNINGS` is available only through an explicit exploratory override,
for example one Spot and one Standard run with otherwise matching facts or a run-to-set
view. It can never support canonical registration or a regression gate.

Machine, zone, CPU/topology, memory, provisioning, resolved image, kernel, exact JDK/VM,
JVM options, suite schema, workload configuration, or unit mismatch is
`INCOMPARABLE` for direct regression. Missing, contradictory, checksum-invalid, or
corrupt evidence is `INVALID`, not merely incomparable.

## Comparison policy version 1

V2 reports performance findings but returns success for a suspected regression. It
returns nonzero only for command/configuration errors, invalid evidence, unsupported or
incompatible schema, or a direct-comparison request that is not directly comparable.

The fixed classification vocabulary is:

```text
MATERIAL_IMPROVEMENT
IMPROVEMENT
NEUTRAL
WARNING
POSSIBLE_REGRESSION
INCOMPARABLE
INVALID
```

Known latency and allocation metrics use `lower`; throughput uses `higher`. Categorical
and diagnostic metrics have explicit policies and are never passed through generic
percentage logic. Unknown metrics are displayed without classification and do not
affect summary counts.

For known continuous metrics with a nonzero baseline median:

```text
deltaPct = (candidateMedian - baselineMedian) / abs(baselineMedian) * 100
variationPct = max(baselineRelativeRangePct, candidateRelativeRangePct)
neutralLimitPct = max(5, variationPct)
materialLimitPct = max(10, 2 * variationPct)
```

After applying optimization direction:

- absolute delta at or below `neutralLimitPct` is `NEUTRAL`;
- a beneficial delta above neutral is `IMPROVEMENT`;
- it is `MATERIAL_IMPROVEMENT` only at or above `materialLimitPct`;
- a harmful delta above neutral is `WARNING`;
- it is `POSSIBLE_REGRESSION` only at or above `materialLimitPct`.

Threshold equality passes into the more material class. If relative variation is
unavailable, the metric-specific policy must define absolute handling; otherwise it is
reported without performance classification. A baseline of zero never uses percentage
division. Overall reports count classifications but do not collapse dissimilar metrics
into one synthetic score.

## Baseline registry

The tracked registry location is:

```text
docs/v3/cloud-benchmark-baselines.json
```

It is a small deterministic schema, not a database. Each human-reviewed name records:

```text
set ID
set-manifest SHA-256
evidence profile
source commit and optional reviewed release label
environment and benchmark-config fingerprints
immutable GCS set-manifest URI and object generation
upload-receipt ID and SHA-256
```

Local absolute paths and raw metrics are not committed. Registration requires a
complete canonical set, a verified durable upload receipt, and explicit human action.
There is no automatic latest baseline. An existing name is immutable and cannot be
replaced by a force flag; a superseding baseline uses a new name and code review.

The label `v3.0.0-cloud` does not prove that the released tag itself produced the run.
The exact measured commit remains authoritative, and any release association is
reviewed provenance stated honestly.

## GCS retention and upload receipts

GCS is optional for local extraction, experiment reports, local set aggregation, and
local comparison. It is required for a registered canonical baseline and for canonical
execution on an ephemeral GitHub runner.

The user creates the bucket and IAM policy. V2 never creates a bucket, changes IAM,
embeds credentials, or reuses Maven release secrets. The logical layout is:

```text
gs://<bucket>/general-search-engine/
  raw/<commit>/<run-id>/
  orchestration/<commit>/<run-id>/
  derived/runs/<run-id>/v1/
  sets/<set-id>/
  comparisons/<comparison-id>/
  receipts/<receipt-id>/
```

Upload uses create-only/no-clobber semantics. A collision succeeds only after the remote
object is proven byte-identical; otherwise it fails. Verification checks object identity,
generation, size, and available integrity metadata, not only existence. Baseline paths
are references and do not duplicate large raw objects.

Source manifests remain unchanged after upload. A separate canonical
`upload-receipt.json` records source manifest digests, object URIs, generations, sizes,
and verified hashes. It contains no generated timestamp required for identity. Its ID is
derived from its canonical bytes, and it receives its own checksum.

## Manual GitHub workflow

`.github/workflows/cloud-performance.yml` is `workflow_dispatch` only. Normal pull
request and push CI never authenticate to GCP, create a VM, upload to GCS, or run paid
benchmarks.

Workflow inputs are enumerated choices for evidence profile, supported mode/preset,
and machine. A reviewed baseline may be exposed only after the workflow has a frozen,
checksum-verified remote retrieval path; until then the input is omitted rather than
accepted and silently ignored. Inputs are not arbitrary shell fragments.
Canonical workflow execution requires durable GCS configuration and explicit dispatch;
experiment output may use bounded Actions artifacts according to documented size limits.

Authentication uses GitHub OIDC and Google Workload Identity Federation with:

```text
permissions:
  contents: read
  id-token: write
```

The repository stores only provider/service-account/project/zone/bucket identifiers as
variables or non-secret configuration. It stores no service-account JSON key. The
federated principal receives only the documented Compute, network/SSH, and Storage
permissions required by the existing runner and selected upload. GitHub workflow steps
call repository scripts rather than duplicating orchestration in YAML.

Suspected performance regression is visible in `GITHUB_STEP_SUMMARY` but does not fail
the job. Infrastructure, benchmark, checksum, schema, upload, or cleanup failure does.
Derived artifacts may be uploaded to Actions; large raw evidence uses GCS.

## V2 command and exit model

The intended focused commands are:

```bash
./run-cloud-benchmark.sh full

./run-cloud-benchmark-set.sh \
  --evidence-profile canonical \
  --repeats 3 \
  --confirm-paid-run \
  full

./compare-cloud-benchmark.sh BASELINE CANDIDATE
./upload-cloud-benchmark.sh RUN_OR_SET
./register-cloud-baseline.sh NAME SET
```

The Python analysis utility uses stable categories:

| Exit | Meaning |
|---:|---|
| 0 | requested derivation/comparison completed, including reported performance warnings/regressions |
| 2 | CLI or local configuration error |
| 80 | raw/checksum/orchestration evidence invalid |
| 81 | unsupported evidence or schema |
| 82 | contradictory manifest or duplicate metric identity |
| 83 | set incomplete or members incompatible |
| 84 | comparison invalid or not directly comparable when direct comparison was required |
| 85 | registry validation or immutable-name conflict |
| 86 | upload configuration, collision, transfer, or verification failure |

Thin wrappers preserve the underlying V1 exit code when V1 fails and record it in the
set checkpoint. Analysis exits deliberately occupy `80..86` so they cannot be confused
with V1 lifecycle exits.

## No-cost validation gates

No paid implementation work begins until fixtures and local gates cover:

- raw schema-1 PASS, FAIL, contradiction, checksum corruption, and detached branch;
- supported and unsupported legacy schema-0 shapes;
- exact orchestration binding and finalized-record digest;
- byte-stable manifest, metric JSON, fingerprints, set, comparison, and reports;
- JMH average-time, sample-time, throughput, secondary operation, allocation, GC, and
  string-`NaN` fields;
- soak summary, diagnostic analysis, optional per-query fields, and categorical failure;
- duplicate metric rejection and unit/config mismatch;
- fingerprint equality and every included/excluded field;
- three-member median/min/max/range, zero median, missing metric, and fastest-run
  non-selection;
- slot checkpoint/resume, infrastructure replacement audit, benchmark-failure stop, and
  member environment mismatch;
- comparison direction, threshold equality, variation dominance, zero baseline,
  unknown metric, and non-failing suspected regression;
- immutable registry-name behavior;
- fake-GCS missing config, create-only command, identical collision, conflicting
  collision, failure, remote verification, and separate upload receipt;
- workflow trigger, bounded choices, WIF permissions, summary behavior, and absence of
  automatic paid triggers;
- all existing fake-gcloud, soak analyzer, stabilization, JMH-only, reactor,
  compatibility, and release gates.

Tests use synthetic or minimized fixtures and fake cloud/storage commands. Codex does
not create a real VM, bucket, IAM binding, WIF provider, or GCS object during V2
implementation. The user performs bounded manual cloud validation after review.

## Phase 0 completion checklist

Phase 0 is ready for implementation only when all items below are true:

- [x] V1 lifecycle and workload runner remain authoritative.
- [x] Raw and derived evidence have a non-overlapping directory boundary.
- [x] Raw schema 1 and legacy schema-0 behavior are defined.
- [x] Manifest and metric identities are versioned and deterministic.
- [x] Detached branch, exact source commit, and orchestration binding are defined.
- [x] Environment and benchmark configuration fingerprints are separate.
- [x] Exact JDK build compatibility and the current apt limitation are explicit.
- [x] Experiment/canonical profiles and mode eligibility are distinct from JFR profile.
- [x] Independent slot, resume, replacement, and aggregation rules prevent cherry-picking.
- [x] Comparability and variation-aware classification rules are executable.
- [x] Baseline registration is human-reviewed and immutable.
- [x] GCS upload uses separate receipts and never mutates source manifests.
- [x] Manual workflow authentication and no-cost CI boundaries are frozen.
- [x] V2 exit categories and no-cost gates are defined.
- [x] Historical index generation is explicitly deferred to V2.1.

## Deferred work

Cloud Benchmark V2.1 may regenerate a historical JSON/Markdown index from registered
baselines. Cloud Benchmark V3 or a separate project may add policy-approved hard gates,
automatic bisect, dashboards, databases, multi-cloud execution, or multi-node tests.

Neither deferred phase is allowed to weaken the immutable raw evidence, human-reviewed
baseline, exact environment identity, or no-paid-normal-CI rules frozen here.
