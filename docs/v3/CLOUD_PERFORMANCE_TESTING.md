# Reproducible GCP performance testing

## Purpose and safety boundary

`run-cloud-benchmark.sh` provisions one ephemeral Google Compute Engine VM, checks out
the exact pushed Git commit, runs the existing
`scripts/run-v3-production-performance.sh`, retrieves and verifies its evidence, and
deletes the VM. It does not duplicate JMH workloads and does not change search semantics.

The runner never enables APIs, changes billing or IAM, creates networks/firewall rules,
or creates service accounts. Pull-request CI uses a fake `gcloud` implementation and
never authenticates to GCP or creates billable resources.

The frozen evidence, aggregation, comparison, and retention layer planned above this
single-run lifecycle is defined separately in the
[Cloud Benchmark V2 Phase 0 evidence model](CLOUD_BENCHMARK_V2_PHASE_0.md). That
contract does not change the V1 commands documented here.

## One-time prerequisites

Install the Google Cloud CLI, then authenticate and select a project:

```bash
gcloud version
gcloud auth login
gcloud config set project PROJECT_ID
gcloud config set compute/zone C3D_SUPPORTED_ZONE
```

The selected project must already have:

- billing and the Compute Engine API enabled;
- quota for the selected C3D machine type;
- permission to create, inspect, start, SSH/SCP to, and delete Compute Engine VMs;
- an existing network and SSH path;
- outbound internet access for Ubuntu packages, GitHub, and Maven Central.

The script does not perform this setup. A project administrator may enable the API once:

```bash
gcloud services enable compute.googleapis.com --project=PROJECT_ID
```

Confirm machine availability before a paid run:

```bash
gcloud compute machine-types describe c3d-standard-30 \
  --project=PROJECT_ID \
  --zone=C3D_SUPPORTED_ZONE
```

### External-IP SSH

This is the default. The VM receives an ephemeral, not static, external IP. An existing
firewall rule must permit SSH and the authenticated user must be allowed to use OS Login
or the project's existing metadata-key mechanism.

```bash
export GSE_CLOUD_EXTERNAL_IP=true
export GSE_CLOUD_USE_IAP=false
```

If the project has no default VPC, select existing resources:

```bash
export GSE_GCP_NETWORK=NETWORK
export GSE_GCP_SUBNET=SUBNET
```

### IAP SSH without an external IP

IAP mode requires existing IAP IAM and firewall configuration. Because the VM has no
external address, the subnet must also have Cloud NAT or another outbound path before
bootstrap can install packages or clone GitHub.

```bash
export GSE_CLOUD_USE_IAP=true
export GSE_CLOUD_EXTERNAL_IP=false
export GSE_GCP_NETWORK=NETWORK
export GSE_GCP_SUBNET=SUBNET
```

The VM is created with no attached service account and no OAuth scopes. Do not place
release credentials, GitHub write tokens, Maven publishing credentials, or GPG keys on it.

## Preflight and dry run

The local working tree must be clean and the exact `HEAD` commit must already be fetchable
from the configured public remote. A moving branch such as `master` is never used as the
remote benchmark identity.

Start with a read-only dry run:

```bash
export GSE_GCP_PROJECT=PROJECT_ID
export GSE_GCP_ZONE=C3D_SUPPORTED_ZONE
./run-cloud-benchmark.sh --dry-run quick
```

Dry run may authenticate and issue read-only describe/image-resolution calls. It never
creates, starts, stops, deletes, SSHs, SCPs, enables APIs, or changes metadata. `--help`
requires neither `gcloud` nor authentication.

The Ubuntu image family is resolved before provisioning. The create command uses that
exact image name, and evidence records its name, numeric ID, self-link, creation time,
and requested family. `GSE_CLOUD_IMAGE=EXACT_IMAGE_NAME` repeats a run with a previously
resolved image.

Ubuntu's OpenJDK 21 package and `unzip` are installed on the VM. `unzip` is required so
the Maven Wrapper downloads the ZIP pinned by `distributionSha256Sum` rather than falling
back to the differently hashed tarball. The complete Java output and exact installed
package version are recorded. An apt-installed JDK is not claimed to be pinned merely
because its major version is 21; compare those fields before comparing runs.

## Commands

Routine runs use a `c3d-standard-30` Spot VM by default:

```bash
./run-cloud-benchmark.sh quick
./run-cloud-benchmark.sh full
./run-cloud-benchmark.sh concurrency
./run-cloud-benchmark.sh soak
./run-cloud-benchmark.sh investigation
./run-cloud-benchmark.sh stabilized-investigation
./run-cloud-benchmark.sh all
```

The investigation mode requires one frozen cell and should use Standard provisioning
for evidence intended for comparison:

```bash
GSE_CLOUD_PROVISIONING=standard \
GSE_SOAK_INVESTIGATION_CELL=revision-update \
GSE_SOAK_PROFILE=none \
./run-cloud-benchmark.sh investigation
```

Accepted cells are `read-only`, `stable-update`, and `revision-update`. Use
`GSE_SOAK_PROFILE=jfr` only for a separate diagnostic profile after an unprofiled
contrast has been established. See the frozen
[root-cause investigation contract](CLOUD_SOAK_ROOT_CAUSE_INVESTIGATION.md).

The stabilized path requires Standard provisioning, a stable or revision cell, and one
frozen purpose. A screening example is:

```bash
GSE_CLOUD_PROVISIONING=standard \
GSE_GCP_ZONE=us-west4-a \
GSE_CLOUD_IMAGE=ubuntu-2404-noble-amd64-v20260826 \
GSE_SOAK_INVESTIGATION_CELL=stable-update \
GSE_SOAK_STABILIZATION_PURPOSE=screening \
./run-cloud-benchmark.sh --dry-run stabilized-investigation
```

Remove `--dry-run` only after reviewing the immutable plan. Cloud rejects `reduced-test`
before any GCP command. Its mode-derived cap is stabilization plus measurement plus two
hours (8,100 seconds for screening/profile and 9,300 for confirmation). See the frozen
[early-window stabilization contract](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION.md) before
running the paid alternating matrix.

Only the top-level `concurrency` mode receives the stronger cloud default ratios:

```text
1,1 4,1 8,1 16,1 24,1 30,1
```

The existing local runner defaults remain unchanged. Run the 1M concurrency matrix with
an explicitly larger heap on the default 120-GB machine:

```bash
GSE_CONCURRENCY_DOCUMENTS=1000000 \
GSE_CONCURRENCY_THREAD_GROUPS='1,1 4,1 8,1 16,1 24,1 30,1' \
GSE_PERF_JVM_OPTIONS='-Xms32g -Xmx64g' \
./run-cloud-benchmark.sh concurrency
```

Run a two-hour or six-hour soak with:

```bash
GSE_SOAK_SECONDS=7200 ./run-cloud-benchmark.sh soak
GSE_SOAK_SECONDS=21600 ./run-cloud-benchmark.sh soak
```

Use Standard provisioning for release-quality measurements:

```bash
GSE_CLOUD_PROVISIONING=standard ./run-cloud-benchmark.sh all
```

A canonical baseline requires at least three independent ephemeral Standard runs with
the same exact image, machine, JVM, and workload configuration. Use the set wrapper
below so every raw run is retained and medians and run-to-run variation are derived
without selecting the fastest run.

## Independent Cloud Benchmark V2 run sets

Cloud Benchmark V2 Phase 2 automates a sequential set of independent V1 VM lifecycles.
The existing `./run-cloud-benchmark.sh MODE` command remains the shortest exploratory
path. Use the set wrapper when the experiment itself needs checkpointing or multiple
independent slots.

Review a one-slot Spot experiment without creating a workspace or VM:

```bash
GSE_CLOUD_PROVISIONING=spot \
./run-cloud-benchmark-set.sh --dry-run \
  --evidence-profile experiment --repeats 1 quick
```

Run it only after explicitly acknowledging the paid VM lifecycle:

```bash
GSE_CLOUD_PROVISIONING=spot \
./run-cloud-benchmark-set.sh \
  --evidence-profile experiment --repeats 1 \
  --confirm-paid-run quick
```

Experiment sets accept 1 through 10 slots and every V1 mode. A preset is optional; if
provided, it must be a known preset for the selected mode. Experiment evidence remains
exploratory even with Standard provisioning, three members, or a canonical-shaped
workload. It cannot be directly compared or registered as canonical evidence.

Start with a mutation-free plan review:

```bash
GSE_CLOUD_PROVISIONING=standard \
./run-cloud-benchmark-set.sh --dry-run \
  --evidence-profile canonical --repeats 3 full
```

The wrapper resolves one exact image, freezes the production workload preset, and runs
the existing V1 dry-run checks. It creates neither a set workspace nor a VM. After
reviewing the plan, acknowledge the worst-case VM count explicitly:

```bash
GSE_CLOUD_PROVISIONING=standard \
./run-cloud-benchmark-set.sh \
  --evidence-profile canonical --repeats 3 \
  --confirm-paid-run full
```

Canonical modes are `full`, `concurrency`, `soak`, and `all`; canonical sets accept 3
through 10 slots. Each mode selects its versioned `v3-production-<mode>-v1` preset.
Every slot creates and cleans up a separate Standard VM. The wrapper stops on the first
invalid attempt and returns the underlying V1 or Phase 1 exit instead of hiding it.

Resume only untouched pending slots with:

```bash
./run-cloud-benchmark-set.sh \
  --resume benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --confirm-paid-run
```

If the current slot is explicitly classified `INFRASTRUCTURE_INVALID`, authorize one
replacement without inspecting or selecting benchmark scores:

```bash
./run-cloud-benchmark-set.sh \
  --replace benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --slot 2 \
  --reason 'VM terminated before evidence recovery' \
  --confirm-no-score-selection \
  --confirm-paid-run
```

Benchmark, configuration, analyzer/evidence, incompatible-environment, and unresolved
failures are not replacement eligible. A valid slow member is never discarded.
Completed content-addressed artifacts are written under
`benchmark-results/v3-production/sets/gse-set-v1-.../v1/`; the completed in-progress
workspace remains as the attempt and replacement audit trail. The exact schemas and
state transitions are frozen in the
[Phase 2 aggregation contract](CLOUD_BENCHMARK_V2_PHASE_2.md).
The profile matrix and V1 compatibility boundary are audited in the
[Phase 4 profile-hardening contract](CLOUD_BENCHMARK_V2_PHASE_4.md).

## Deterministic local comparison

Compare two completed canonical sets without contacting GCP or GCS:

```bash
./compare-cloud-benchmark.sh \
  benchmark-results/v3-production/sets/BASELINE_SET_ID/v1 \
  benchmark-results/v3-production/sets/CANDIDATE_SET_ID/v1
```

The command validates the complete checksum-bound inputs, requires matching benchmark
and environment fingerprints, and writes deterministic artifacts below
`benchmark-results/v3-production/comparisons/<comparison-id>/v1/`. Suspected
regressions remain review evidence and return exit `0`; valid but incompatible inputs
produce an explicit report and return exit `84`.

A run, experiment set, or provisioning-only Spot/Standard comparison requires the
explicit exploratory mode:

```bash
./compare-cloud-benchmark.sh --allow-exploratory BASELINE CANDIDATE
```

The flag does not permit machine, zone, image, JVM, workload, suite, or metric-schema
mismatches. Single-run comparisons report no independent-run variation and do not
invent confidence intervals.

Validate or list the tracked baseline registry locally with:

```bash
python3 scripts/cloud/benchmark_v2.py registry-validate \
  docs/v3/cloud-benchmark-baselines.json
scripts/cloud/list-baselines.sh
```

Registry names may be used only as the baseline operand and resolve only an exact local
set. Phase 3 never downloads missing evidence. The detailed compatibility and
classification rules are frozen in the
[Phase 3 comparison contract](CLOUD_BENCHMARK_V2_PHASE_3.md).

## Durable GCS retention and baseline registration

Cloud Benchmark V2 Phase 5 retains already verified evidence; it does not create a
bucket, change IAM, run a VM, or make GCS mandatory for local analysis. Configure one
existing bucket and first review a mutation-free upload plan:

```bash
export GSE_BENCHMARK_GCS_BUCKET=gs://my-gse-benchmarks

./upload-cloud-benchmark.sh --dry-run \
  benchmark-results/v3-production/sets/SET_ID/v1
```

The source may be one derived run or one completed set. A set upload retains every
member's checksum-bound raw, orchestration, and derived evidence once, followed by its
set artifacts. Execute only after reviewing the fixed object paths:

```bash
./upload-cloud-benchmark.sh --confirm-upload \
  benchmark-results/v3-production/sets/SET_ID/v1
```

Every object uses a generation-zero create precondition. A retry accepts an existing
object only after URI, generation, size, CRC32C, tool-owned SHA-256 metadata, and any
available MD5 match. The command then writes a separate local and remote receipt under
`upload-receipts/RECEIPT_ID/v1/`; it never edits source manifests.

After human review, preview a canonical baseline registry entry without GCS access or
local mutation:

```bash
./register-cloud-baseline.sh --dry-run \
  --receipt benchmark-results/v3-production/upload-receipts/RECEIPT_ID/v1 \
  --release-label 'v3.0.0 reviewed cloud baseline' \
  v3.0.0-cloud \
  benchmark-results/v3-production/sets/SET_ID/v1
```

Remove `--dry-run` only when ready to re-verify every receipt object and atomically add
the new name to `docs/v3/cloud-benchmark-baselines.json`. Existing names cannot be
replaced, including by an identical entry. The command does not commit or push the
registry; review that small metadata change in a separate PR. If exactly one receipt
binds the set, `--receipt` may be omitted; ambiguity is always rejected.

Phase 5 does not download a missing registered set or upload comparison reports. Its
complete storage, receipt, retry, security, and registration rules are frozen in the
[Phase 5 durable-retention contract](CLOUD_BENCHMARK_V2_PHASE_5.md).

Use the frozen [cloud soak diagnostics contract](CLOUD_SOAK_DIAGNOSTICS.md) for
factor-controlled heap and dynamic-index investigation when a soak does not reach a
stable operating band.

A larger experiment is configurable without changing scripts:

```bash
GSE_CLOUD_MACHINE_TYPE=c3d-standard-60 \
GSE_CONCURRENCY_THREAD_GROUPS='1,1 4,1 8,1 16,1 24,1 30,1 48,1 60,1' \
GSE_PERF_JVM_OPTIONS='-Xms32g -Xmx64g' \
./run-cloud-benchmark.sh concurrency
```

## Configuration reference

| Variable | Default / meaning |
|---|---|
| `GSE_GCP_PROJECT` | Current gcloud project, otherwise required |
| `GSE_GCP_ZONE` | Current gcloud compute zone, otherwise required |
| `GSE_CLOUD_REPO_URL` | Public GeneralSearchEngine GitHub URL |
| `GSE_BENCHMARK_GCS_BUCKET` | No default; exact existing `gs://bucket` used only by explicit Phase 5 upload |
| `GSE_CLOUD_MACHINE_TYPE` | `c3d-standard-30` |
| `GSE_CLOUD_PROVISIONING` | `spot`; accepts `spot` or `standard` |
| `GSE_CLOUD_IMAGE_PROJECT` | `ubuntu-os-cloud` |
| `GSE_CLOUD_IMAGE_FAMILY` | `ubuntu-2404-lts-amd64` |
| `GSE_CLOUD_IMAGE` | Optional exact image override |
| `GSE_CLOUD_BOOT_DISK_SIZE` | `100GB` |
| `GSE_CLOUD_BOOT_DISK_TYPE` | `pd-balanced` |
| `GSE_CLOUD_MAX_RUN_DURATION` | Mode-derived; positive duration up to seven days |
| `GSE_GCP_NETWORK` / `GSE_GCP_SUBNET` | Optional existing resources |
| `GSE_CLOUD_USE_IAP` | `false` |
| `GSE_CLOUD_EXTERNAL_IP` | `true` |
| `GSE_PERF_JVM_OPTIONS` | `-Xms8g -Xmx16g` in cloud runs |
| `GSE_CONCURRENCY_DOCUMENTS` | `100000` |
| `GSE_CONCURRENCY_THREAD_GROUPS` | Cloud concurrency ratios above; local defaults are unchanged |
| `GSE_SOAK_SECONDS` | `1800` |
| `GSE_SOAK_READERS` / `GSE_SOAK_WRITERS` | Existing runner defaults |
| `GSE_SOAK_DOCUMENTS` | Existing runner default |
| `GSE_SOAK_INDEX_CYCLES` | `true`; accepts `true` or `false` |
| `GSE_SOAK_INVESTIGATION_CELL` | Required for investigation modes; stabilized production accepts `stable-update` or `revision-update` |
| `GSE_SOAK_PROFILE` | Purpose-derived for stabilized runs; `jfr` remains opt-in for ordinary investigation |
| `GSE_SOAK_STABILIZATION_PURPOSE` | Required only for `stabilized-investigation`; cloud accepts `screening`, `confirmation`, or `profile` |
| `GSE_SOAK_STABILIZATION_SECONDS` / `GSE_SOAK_STABILIZATION_WINDOW_SECONDS` | Purpose-derived and strictly checked |
| `GSE_JMH_FORKS` / `GSE_JMH_WARMUPS` / `GSE_JMH_ITERATIONS` / `GSE_JMH_DURATION` | Existing runner defaults |

Mode-derived compute caps are two hours for quick, twelve for full, eight for concurrency,
the requested soak or investigation duration plus two hours, and twenty-four hours for
all. The VM also carries
searchable `purpose=gse-benchmark` labels. The cap limits compute after a dead local
orchestrator; it does not replace deletion, and a stopped Spot boot disk can still cost money.

## Results and outcomes

Verified results retain the remote directory name under:

```text
benchmark-results/v3-production/<run>/
```

Separate local lifecycle records and logs are under:

```text
benchmark-results/v3-production/cloud-orchestration/
```

### Derive a Cloud Benchmark V2 run

Phase 1 adds deterministic post-processing without changing the V1 cloud lifecycle.
It requires Python 3.11 or newer locally or in CI; Python is not installed on the
benchmark VM for this purpose. After a verified V1 run, derive experiment evidence with:

```bash
python3 scripts/cloud/benchmark_v2.py manifest \
  benchmark-results/v3-production/RAW_RUN_ID
```

The analyzer finds the matching finalized orchestration record by instance identity,
revalidates every raw checksum and the raw/record relationship, then writes only to:

```text
benchmark-results/v3-production/derived/runs/RAW_RUN_ID/v1/
  benchmark-manifest.json
  normalized-metrics.json
  derived-checksums.sha256
```

Reprocessing identical evidence is byte-stable. An existing derived file with different
bytes is rejected instead of overwritten. The raw run is never modified. Use
`--orchestration-record PATH` only when the record is stored outside its normal sibling
directory, and `--output-dir PATH` for a separate derived destination.

New raw runs carry evidence schema 1 and exact CPU topology, memory, kernel, image,
Java/VM, ordered JVM option, suite, and repository facts. Explicitly supported historical
schema-0 JMH shapes remain usable as `VALID_EXPERIMENT`, but missing strict facts are
left null and no environment fingerprint is invented.

`--evidence-profile canonical` validates one potential canonical set member. It requires
schema 1, a clean source, Standard provisioning, a canonical mode, a complete strict
environment fingerprint, ordinary cleanup proof, and a matching versioned benchmark
preset in raw metadata. Prefer `run-cloud-benchmark-set.sh` for canonical evidence; it
sets and validates that preset automatically. One run never becomes a canonical
baseline by itself.

Interrupted evidence is placed below `partial/`; checksum-invalid evidence is placed
below `quarantine/`. These directories remain ignored by Git. The orchestrator never
adds its own properties to the downloaded checksum payload.

A normal PASS or orderly benchmark FAIL requires `status.properties`, `metadata.txt`,
`environment.txt`, `checksums.sha256`, and a successful local `sha256sum -c`. An interrupted
Spot run may retain incomplete evidence without a checksum, but is never reported as PASS.

| Exit | Meaning |
|---:|---|
| 0 | verified PASS; cleanup succeeded or `--keep-vm` was explicit |
| 2 | local configuration or preflight error |
| 10 | provisioning failure |
| 20 | bootstrap, checkout, or pre-benchmark remote setup failure |
| 30 | benchmark FAIL with verified evidence |
| 40 | confirmed Spot interruption |
| 50 | artifact discovery or collection failure |
| 60 | missing or invalid checksum evidence |
| 70 | cleanup failure when no earlier primary failure exists |

The remote boot disk stores atomic benchmark state, the benchmark exit code, an
orchestration log, and a best-effort Spot shutdown marker. If an active SSH operation
fails and the Spot VM is observed in `TERMINATED`, the runner classifies the run as an
interruption even when the best-effort shutdown marker is missing. It attempts at most
one restart and waits at most ten minutes, solely to recover evidence. It never resumes
or relaunches the interrupted benchmark. The orchestration record distinguishes the
instance-status evidence, shutdown-marker value, and restart outcome.

Default cleanup covers success, failure, Ctrl-C, and partial VM creation. `--keep-vm`
is a deliberate debugging escape hatch and prints the exact deletion command.

Find possible orphaned benchmark VMs without mutating them:

```bash
gcloud compute instances list \
  --project=PROJECT_ID \
  --filter='labels.purpose=gse-benchmark'
```

Delete only the confirmed instance:

```bash
gcloud compute instances delete INSTANCE \
  --project=PROJECT_ID \
  --zone=ZONE
```

## No-cost validation

Normal CI and local development validate shell syntax and run a deterministic fake-gcloud
lifecycle suite:

```bash
bash -n run-cloud-benchmark.sh \
  run-cloud-benchmark-set.sh \
  compare-cloud-benchmark.sh \
  scripts/run-v3-production-performance.sh \
  scripts/analyze-v3-soak.sh \
  scripts/analyze-v3-soak-stabilization.sh \
  scripts/compare-v3-soak-stabilized.sh \
  scripts/test-v3-soak-analysis.sh \
  scripts/cloud/*.sh
scripts/test-v3-soak-analysis.sh
scripts/test-v3-soak-stabilization-analysis.sh
scripts/test-v3-soak-stabilized-comparison.sh
scripts/test-v3-soak-stabilization-e2e.sh
scripts/cloud/test-benchmark-system-facts.sh
scripts/cloud/test-cloud-runner.sh
scripts/cloud/test-benchmark-set-runner.sh
python3 -m unittest \
  scripts.cloud.test_benchmark_v2 \
  scripts.cloud.test_benchmark_comparison_v2
```

The synthetic analyzer suite covers stable, drifting, queue-pressure, malformed, and
counter-regression evidence. The fake cloud suite covers immutable-image creation,
Spot/Standard flags, no-service-account
creation, dry run, IAP, benchmark failure, preemption, partial artifacts, checksum and SCP
failure, partial provisioning, cleanup failure, dirty source, and an unpushed commit. It
does not prove project IAM, quota, network reachability, current gcloud flag compatibility,
or real C3D performance; the user performs the first real quick run manually.

The V2 fixture suite additionally covers schema-1 and explicit schema-0 adapters, raw
immutability, checksum and orchestration contradictions, detached branches, byte-stable
serialization, fingerprint inclusion/exclusion, JMH average/sample/throughput and
string-`NaN` semantics, soak properties, duplicate metric identities, and derived-output
boundaries. Phase 2 fixtures add mutation-free set dry runs, paid-run confirmation,
exact attempt binding, three-member finalization, deterministic set identity, odd/even
median and range semantics, categorical consensus, incompatible-member stops,
crash-safe resume, and explicitly attested infrastructure replacement. They use no real
`gcloud` command and create no paid resource.
