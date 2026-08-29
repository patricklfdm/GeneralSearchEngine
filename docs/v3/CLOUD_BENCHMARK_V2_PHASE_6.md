# Cloud Benchmark V2 Phase 6 secure manual workflow

Status: frozen before implementation

## Purpose

This document freezes the Cloud Benchmark V2 Phase 6 contract before a paid GitHub
Actions workflow is added. It is subordinate to the Phase 0 evidence model and
preserves the completed V1 runner plus the Phase 2 set, Phase 3 comparison, Phase 4
profile, and Phase 5 durable-retention contracts.

Phase 6 adds one secure, manually approved automation path from GitHub Actions to the
existing repository scripts. It does not create a second cloud orchestrator.

Phase 6 must:

- expose exactly one `workflow_dispatch`-only cloud-performance workflow;
- validate every dispatch input before authentication or paid mutation;
- use short-lived GitHub OIDC and Google Workload Identity Federation;
- run the existing checkpointed set wrapper and immutable upload wrapper;
- require durable GCS retention for canonical evidence;
- retain only bounded, allowlisted lightweight GitHub artifacts;
- write an evidence-bounded `GITHUB_STEP_SUMMARY` on success or failure;
- preserve infrastructure, benchmark, evidence, upload, and cleanup failures; and
- keep normal pull-request and push CI free of credentials and cloud cost.

Phase 6 must not:

- add a push, pull-request, schedule, tag, repository-dispatch, or workflow-call trigger;
- store or accept a service-account JSON key;
- create a WIF pool/provider, service account, bucket, IAM binding, network, or quota;
- duplicate VM creation, SSH, benchmark, cleanup, set, upload, or receipt logic in YAML;
- accept an arbitrary shell command, JVM option, URI, zone, image, preset, or duration;
- automatically register or replace a baseline;
- download a registered baseline or add unverified comparison retrieval;
- upload raw benchmark directories to GitHub Actions artifacts;
- introduce a hard performance-regression gate; or
- trigger a real workflow, VM, or GCS write during implementation tests.

Historical index generation and verified remote-baseline retrieval remain deferred.

## Workflow identity and trigger

Phase 6 adds exactly:

```text
.github/workflows/cloud-performance.yml
```

Its only trigger is:

```yaml
on:
  workflow_dispatch:
```

It has no automatic trigger hidden behind a reusable workflow or another workflow.
Normal `.github/workflows/ci.yml` validates the workflow statically and synthetically;
it never calls it.

The paid job uses the GitHub Environment:

```text
cloud-benchmark
```

The environment requires manual approval and restricts deployment branches to
`master`. A solo maintainer may allow self-review; with a second maintainer, prevention
of self-review is preferred. Environment approval is a safety boundary, not evidence
that a benchmark result is canonical or suitable as a baseline.

Workflow concurrency is repository-wide and never cancels an in-progress run:

```text
group = cloud-performance-<repository>
cancel-in-progress = false
```

This serializes paid workflows and avoids cancellation-driven VM leakage or overlapping
quota use. The paid job runs on `ubuntu-latest`, has a maximum six-hour job timeout, and
does not use a self-hosted runner.

## Bounded dispatch inputs

The workflow accepts exactly these inputs:

| Input | Type | Choices/default | Meaning |
|---|---|---|---|
| `evidence_profile` | choice | `experiment`, `canonical`; default `experiment` | Phase 4 evidence profile |
| `mode` | choice | `quick`, `full`, `concurrency`, `soak`, `all`; default `quick` | Existing V1 mode subset |
| `repeats` | choice | `1`, `3`, `5`; default `1` | Independent set slots |
| `provisioning` | choice | `spot`, `standard`; default `spot` | Existing GCE provisioning model |
| `machine_type` | choice | `c3d-standard-30`, `c3d-standard-60`; default `c3d-standard-30` | Bounded benchmark machine |
| `soak_duration` | choice | `30m`, `2h`; default `30m` | Maps to 1800 or 7200 seconds |
| `retention` | choice | `actions`, `gcs`; default `actions` | Experiment retention path |
| `source_commit` | string | optional; default dispatch SHA | Exact repository commit to benchmark |

GitHub cannot populate a choice list dynamically from the tracked baseline registry.
Phase 6 deliberately provides no free-form baseline input: a registry name would resolve
to no local set on an ephemeral runner, and Phase 3/5 do not implement verified remote
retrieval. Accepting the input while silently skipping comparison would be misleading;
downloading ad hoc objects in YAML would violate evidence integrity. A later frozen
retrieval phase may add this capability.

This is an explicit Phase 0 contract refinement: the optional reviewed-baseline input
is conditional on a frozen, checksum-verified retrieval path. Phase 6 omits it instead
of weakening the comparison evidence model.

`source_commit` is the only non-choice input because commits cannot be enumerated in a
static workflow. The preflight resolves an empty value to the dispatch commit, otherwise
requires exactly 40 lowercase hexadecimal characters, fetches it from the same
`patricklfdm/GeneralSearchEngine` repository, verifies the object is a commit, and
requires it to be an ancestor of protected `origin/master`. A commit that exists only
on another repository branch cannot run repository scripts with the paid job's cloud
identity. The value is passed as one quoted action/script value and never evaluated as
shell.

## Input compatibility matrix

Preflight enforces all combinations before the paid job requests an OIDC token:

| Profile | Modes | Repeats | Provisioning | Retention |
|---|---|---:|---|---|
| `experiment` | `quick`, `full`, `concurrency`, `soak`, `all` | `1`, `3`, `5` | Spot or Standard | Actions or GCS |
| `canonical` | `full`, `concurrency`, `soak`, `all` | `3`, `5` | Standard only | GCS only |

Additional bounds are:

- `2h` is accepted only for a one-repeat experiment in `soak` or `all` mode;
- canonical and multi-repeat soak/all workflows use the frozen `30m` duration;
- non-soak modes require the default `30m` value, which is ignored by the workload;
- canonical mode deterministically uses the existing mode-owned
  `v3-production-<mode>-v1` preset through `run-cloud-benchmark-set.sh`;
- experiment mode does not become canonical because its shape resembles a canonical
  run; and
- the exact image, project, zone, network policy, boot disk, JVM, and repository values
  come from reviewed environment variables, not dispatch inputs.

Invalid combinations fail preflight with exit `2`. They do not enter the protected
environment, request an OIDC token, invoke `gcloud`, create a set workspace, or upload
an artifact.

## Repository and environment configuration

Phase 6 stores no cloud credential secret. The `cloud-benchmark` Environment provides
these non-secret variables:

```text
GSE_CLOUD_WIF_PROVIDER
GSE_CLOUD_SERVICE_ACCOUNT
GSE_GCP_PROJECT
GSE_GCP_ZONE
GSE_CLOUD_IMAGE
GSE_BENCHMARK_GCS_BUCKET
```

`GSE_CLOUD_WIF_PROVIDER` is the full provider resource name. The service-account value
is its email. Project, zone, and exact image use the same validated formats as the V1
runner. The bucket is one exact `gs://bucket` value and is required whenever retention
is `gcs`.

The workflow freezes these repository-controlled values rather than accepting inputs:

```text
repository = https://github.com/patricklfdm/GeneralSearchEngine.git
image project = ubuntu-os-cloud
image family = ubuntu-2404-lts-amd64
boot disk = pd-balanced 100GB
JVM = -Xms8g -Xmx16g
network = default unless the reviewed Environment supplies an approved fixed replacement
IAP/external-IP policy = one reviewed fixed configuration
```

An exact image is mandatory for both profiles. Phase 6 does not resolve a moving image
family inside a paid workflow.

The workflow validates that every required variable is nonempty, single-line, and
format-safe before authentication. It never prints a credential file, access token,
authorization header, signed URL, or complete environment dump.

## OIDC and WIF authentication

Top-level permissions remain read-only. Only the paid job has:

```yaml
permissions:
  contents: read
  id-token: write
```

No job receives `contents: write`, `actions: write`, `packages: write`, or a release
secret. The workflow checks out source before authentication, then uses:

```text
google-github-actions/auth v3
google-github-actions/setup-gcloud v3
```

Both actions, checkout, setup-python, and upload-artifact are pinned to full reviewed
commit SHAs with a human-readable release comment. `setup-gcloud` installs the exact
Cloud SDK version `582.0.0`; it does not use `latest` or a lower-bound constraint.

Authentication uses WIF through the configured service account. The auth action creates
an ephemeral credentials file, exports it only for subsequent steps, and cleans it up.
The repository adds `gha-creds-*.json` to `.gitignore` so a locally reproduced auth step
cannot accidentally stage generated credentials. `credentials_json` is forbidden.

The user configures the provider outside this repository. Its attribute condition must
at minimum restrict:

```text
repository = patricklfdm/GeneralSearchEngine
ref = refs/heads/master
workflow_ref = patricklfdm/GeneralSearchEngine/.github/workflows/cloud-performance.yml@refs/heads/master
environment = cloud-benchmark
```

WIF service-account impersonation grants `roles/iam.workloadIdentityUser` only to that
bounded principal set. The service account receives only permissions required by the
existing VM lifecycle and selected retention:

- instance create/get/set-metadata/delete and required machine/image reads;
- approved network use;
- bucket object create and object read/metadata verification under the dedicated
  benchmark prefix.

The benchmark VM continues to use `--no-service-account --no-scopes`. The workflow
identity is not attached to the VM. Storage permission should be composed from object
creator plus viewer; delete, overwrite, bucket admin, IAM admin, service-account-key
admin, and project owner are not required.

Phase 6 documents setup commands only after the workflow implementation is frozen and
reviewed. Neither YAML nor repository scripts execute IAM setup commands.

## Job sequence

The workflow has two jobs.

### 1. No-cloud preflight

The preflight job has `contents: read` only, no Environment, and no OIDC permission. It:

1. checks out the workflow revision from protected `master`;
2. installs Python 3.11;
3. validates the complete input matrix with one repository helper;
4. resolves and validates the exact source commit from the same repository;
5. emits only bounded validated outputs; and
6. records a mutation-free plan summary.

The helper owns input semantics and is directly unit tested. YAML does not duplicate
the matrix in nested shell expressions.

### 2. Approved paid benchmark

The paid job depends on preflight, uses `environment: cloud-benchmark`, and:

1. checks out the exact validated source commit with full history;
2. installs Python 3.11;
3. authenticates through WIF and installs exact gcloud;
4. runs a V1/set dry-run using the same bounded environment;
5. runs exactly one checkpointed V2 set with `--confirm-paid-run`;
6. requires exactly one completed set directory in the fresh workspace;
7. uploads the set through `upload-cloud-benchmark.sh --confirm-upload` when retention
   is `gcs` (mandatory for canonical);
8. stages allowlisted lightweight evidence;
9. uploads that staging directory as a GitHub Actions artifact;
10. writes the final step summary; and
11. exits with the original benchmark/upload failure category after evidence handling.

The workflow never calls `register-cloud-baseline.sh`. Baseline promotion remains a
separate human review and tracked PR after durable evidence has been inspected.

The workflow invokes repository scripts through quoted argument arrays or fixed shell
words. It contains no inline `gcloud compute instances create/delete`, SSH, benchmark,
set aggregation, upload, receipt, or registry implementation.

## Failure preservation and exit behavior

The benchmark step records its exit code without converting failure into success. Later
summary/artifact steps use `if: always()` and read only allowlisted files. A final gate
returns the saved code or a stable workflow-infrastructure failure.

The existing meanings remain authoritative:

- V1 lifecycle exits `10..70` remain visible;
- analysis/set exits `80..86` remain visible in logs and summary;
- an invalid dispatch/configuration fails with `2` before authentication;
- an infrastructure, benchmark, checksum, schema, upload, receipt, or cleanup failure
  fails the workflow; and
- a reported suspected performance regression does not itself fail a V2 workflow.

Phase 6 performs no comparison because it has no verified baseline retrieval. It does
not invent a regression conclusion from one candidate set.

The existing V1 traps and per-VM maximum runtime remain the lifecycle authority.
Repository-wide non-cancelling concurrency reduces forced interruption. If the GitHub
runner disappears, operators follow the existing cloud-runner recovery documentation
and inspect instances/disks by the `purpose=gse-benchmark` label; Phase 6 adds no broad
best-effort deletion command that could target another run.

## GitHub artifact boundary

GitHub Actions artifacts are review convenience, not the canonical raw archive. A
repository helper creates a fresh staging directory containing only available:

```text
workflow-plan.json
workflow-result.json
workflow-summary.md
completed set v1 files
derived run manifests and normalized metrics
matching orchestration properties/logs
upload receipt v1 files when GCS retention completed
```

It excludes:

```text
raw JMH/soak directories
partial or quarantine payloads
Maven target directories
.git
gha-creds-*.json
environment dumps
access tokens or signed URLs
arbitrary workspace files
```

The helper rejects symlinks, path escapes, special files, unexpected names, and a total
staging size over 100 MiB. It writes a checksum manifest for staged files. Failure to
prepare a safe artifact is visible and fails the workflow after the primary result is
recorded.

The official upload-artifact action is pinned to a full SHA and uses:

```text
retention-days = 14
if-no-files-found = error
include-hidden-files = false
overwrite = false
```

Artifact names contain only the immutable GitHub run ID/attempt and validated profile,
not a free-form input. Canonical raw evidence lives in GCS through its Phase 5 receipt;
experiment `actions` retention is intentionally bounded and temporary.

## Step summary

One repository helper renders deterministic Markdown from the validated workflow plan,
saved exit/result state, completed set manifest when present, and upload receipt when
present. YAML does not concatenate untrusted benchmark text into
`GITHUB_STEP_SUMMARY`.

The summary states:

- workflow run/attempt and exact source commit;
- profile, mode, repeats, provisioning, machine, soak duration, and retention;
- whether preflight, benchmark, set finalization, upload, and cleanup succeeded;
- set ID/status/member count when available;
- receipt ID, object count, and immutable manifest URI when GCS upload succeeded;
- GitHub artifact name and retention period;
- the exact failure category/exit when unsuccessful; and
- that no baseline comparison or production SLA conclusion was performed.

The summary contains no absolute local path, credential path, token, project secret,
raw command output, or unsupported performance claim.

## Implementation components

Phase 6 is expected to add:

```text
.github/workflows/cloud-performance.yml
scripts/cloud/cloud_workflow_v2.py
scripts/cloud/test_cloud_workflow_v2.py
scripts/cloud/test-cloud-performance-workflow.sh
docs/v3/CLOUD_BENCHMARK_V2_PHASE_6.md
```

It may update:

```text
.gitignore
.github/workflows/ci.yml
docs/CI_CD.md
docs/v3/CLOUD_PERFORMANCE_TESTING.md
docs/v3/README.md
docs/README.md
```

The Python helper owns input validation, plan/result schemas, artifact staging, and
summary rendering. Shell/YAML remains a thin orchestrator and does not create a second
evidence parser.

No Phase 6 production change to V1, set, comparison, upload, receipt, or registration
semantics is permitted unless a focused failing compatibility test proves it necessary.

## No-cost test matrix

Input tests cover every accepted matrix edge and reject:

- canonical quick, one repeat, Spot, or Actions-only retention;
- unknown profile/mode/repeat/provisioning/machine/duration/retention;
- two-hour non-soak, canonical, or multi-repeat requests;
- malformed/nonexistent/non-commit source objects; and
- missing, multiline, or malformed required Environment variables.

Workflow static tests require:

- exactly `workflow_dispatch` and no automatic trigger token;
- protected `cloud-benchmark` environment and non-cancelling concurrency;
- preflight without `id-token: write` and paid job with only `contents: read` plus
  `id-token: write`;
- checkout before auth;
- auth/setup-gcloud/upload-artifact pinned to full SHAs;
- exact gcloud `582.0.0`;
- no `credentials_json`, release secret, arbitrary command input, or inline compute/IAM
  mutation;
- existing set/upload wrappers invoked with explicit confirmation;
- canonical GCS retention validation;
- summary/artifact/final-failure steps using the frozen result handoff; and
- no call to baseline registration.

Helper tests cover:

- canonical plan JSON stability and safe GitHub outputs;
- exact completed-set discovery in a fresh workspace;
- allowlisted artifact staging, checksums, symlink/path/special-file rejection, and
  100 MiB size failure;
- success, V1 failure, set failure, upload failure, and missing-result summaries;
- Markdown escaping and absence of secrets/local paths; and
- final exit preservation after summary generation.

The normal CI job runs only Python/shell/static tests and all existing fake-cloud,
upload, analysis, soak, compatibility, release, reproducibility, and reactor gates. It
has no `id-token: write`, cloud Environment, GCP variable requirement, or paid mutation.

## Deferred user setup and manual smoke

After implementation is merged, the user performs one-time external setup with guided
commands:

1. create or select the `cloud-benchmark` GitHub Environment and required reviewer;
2. create/select the GCP service account, WIF pool/provider, and bounded attribute
   condition;
3. grant workload-identity impersonation and least-privilege Compute/network/storage
   access;
4. set the six reviewed Environment variables;
5. verify repository/environment branch protections; and
6. manually dispatch one cheap `experiment / quick / 1 / spot / actions` smoke run.

Only after that smoke is reviewed should the user dispatch canonical Standard/GCS
evidence. Codex does not perform these external mutations or dispatch a paid workflow.

## Phase 6 completion checklist

- [x] The workflow has exactly one manual trigger and no automatic paid path.
- [x] The protected Environment, non-cancelling concurrency, and six-hour bound are enforced.
- [x] Every input and compatibility combination is validated before authentication.
- [x] Only an exact commit reachable from protected `master` is benchmarked.
- [x] Authentication uses short-lived WIF with no service-account JSON key.
- [x] Job permissions and third-party action pins are minimal and explicit.
- [x] Existing set/upload wrappers remain the only execution and retention paths.
- [x] Canonical workflows require Standard provisioning, three/five repeats, and GCS.
- [x] No workflow path automatically registers a baseline.
- [x] Lightweight artifacts are allowlisted, checksummed, size-bounded, and temporary.
- [x] Success/failure summaries are evidence-bounded and secret-free.
- [x] Original benchmark/upload failure remains visible after summary/artifact handling.
- [x] Registry download, comparison retrieval, IAM setup, and real dispatch are excluded.
- [x] Normal CI remains credential-free and cloud-cost-free.
- [x] Phase-specific tests and all existing no-cost gates pass.
