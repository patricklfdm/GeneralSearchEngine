# Reproducible GCP performance testing

## Purpose and safety boundary

`run-cloud-benchmark.sh` provisions one ephemeral Google Compute Engine VM, checks out
the exact pushed Git commit, runs the existing
`scripts/run-v3-production-performance.sh`, retrieves and verifies its evidence, and
deletes the VM. It does not duplicate JMH workloads and does not change search semantics.

The runner never enables APIs, changes billing or IAM, creates networks/firewall rules,
or creates service accounts. Pull-request CI uses a fake `gcloud` implementation and
never authenticates to GCP or creates billable resources.

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
the same exact image, machine, JVM, and workload configuration. Retain every raw run and
report medians and run-to-run variation; do not select the fastest run.

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
| `GSE_SOAK_INVESTIGATION_CELL` | Required only for `investigation`; `read-only`, `stable-update`, or `revision-update` |
| `GSE_SOAK_PROFILE` | `none`; accepts `none` or `jfr` only for `investigation` |
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
  scripts/run-v3-production-performance.sh \
  scripts/analyze-v3-soak.sh \
  scripts/test-v3-soak-analysis.sh \
  scripts/cloud/*.sh
scripts/test-v3-soak-analysis.sh
scripts/cloud/test-cloud-runner.sh
```

The synthetic analyzer suite covers stable, drifting, queue-pressure, malformed, and
counter-regression evidence. The fake cloud suite covers immutable-image creation,
Spot/Standard flags, no-service-account
creation, dry run, IAP, benchmark failure, preemption, partial artifacts, checksum and SCP
failure, partial provisioning, cleanup failure, dirty source, and an unpushed commit. It
does not prove project IAM, quota, network reachability, current gcloud flag compatibility,
or real C3D performance; the user performs the first real quick run manually.
