# V5.0 Phase 6C cloud setup and readiness

- **Status:** First experiment rejected before VM allocation; permission corrections and audited lease repair applied and read back on 2026-09-17 UTC. Fresh-source CI, scheduled cleanup, preparation and successful paid evidence remain pending.
- **Predecessor:** Setup/preflight accepted through [PR #164](https://github.com/patricklfdm/GeneralSearchEngine/pull/164), master `36b7e44828864b11b696c6f2a1d81e9af28f1c44`, [full CI 35089239868](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35089239868).
- **Frozen boundaries:** [Runner](PHASE_6_CLOUD_RUNNER.md), [full workload](PHASE_6_CLOUD_WORKLOAD_PLAN.md), USD 40 complete sequence.

## 1. Capture configuration and generate an offline proposal

After this change is merged, use the clean, synchronized master with its full CI
green. These commands only read existing configuration and write local files:

```bash
mkdir -p target/v50-setup-inputs
gcloud iam workload-identity-pools providers describe general-search-engine \
  --project=gse-benchmark --location=global --workload-identity-pool=gse-github \
  --format=json > target/v50-setup-inputs/provider.json
gcloud iam roles describe gseCloudBenchmarkRunner --project=gse-benchmark \
  --format=json > target/v50-setup-inputs/runner-role.json
gcloud projects get-iam-policy gse-benchmark --format=json \
  > target/v50-setup-inputs/project-policy.json
python3 -m scripts.v50.cloud_setup \
  --provider target/v50-setup-inputs/provider.json \
  --runner-role target/v50-setup-inputs/runner-role.json \
  --project-policy target/v50-setup-inputs/project-policy.json \
  --output target/v50-setup-review
```

The output directory must be new; previous reviews are not overwritten. The tool
does not invoke `gcloud`, obtain credentials or call any cloud API. It records input
hashes, the frozen plan hash, WIF before/after expressions and diff, role definitions,
the exact delete condition and `APPLY.md` commands. Inspect these before executing
any configuration changes. Snapshots and proposals belong under ignored `target/`,
not in source control.

Local setup and generated review commands use `python3` from the environment;
they do not require an executable named for a particular Python minor version.

## 2. Review and apply configuration separately

The proposed changes are:

| Scope | Change |
| --- | --- |
| Existing WIF provider | Add the exact V5 master/environment workflow as a guarded alternative; preserve every existing workflow and reject conditions that bypass repository/ref/environment guards |
| Project role `gseV50RunnerSupplement` | Add only required permissions missing from the directly bound `gseCloudBenchmarkRunner` role |
| Bucket role `gseV50EvidenceMetadataReader` | Grant only `storage.buckets.get` on the frozen evidence bucket |
| Bucket role `gseV50ControlDeleter` | Grant only `storage.objects.delete`, conditioned on the exact bucket's `v5.0-replicated-single-shard/control/` object prefix |

The shared service account already has object creator/viewer grants and WIF
impersonation access. The generator verifies the base project role's direct,
unconditional service-account binding; it does not infer effective access from
other inherited or conditional grants. The project supplement is project-scoped
and affects that account's existing workflows too. It does not grant IAM editing,
bucket-wide object deletion or a VM service account.

Configuration changes require their own review. `APPLY.md` first compares fresh
provider, base role and project-policy snapshots with the reviewed inputs. Drift
stops the commands and requires regeneration. This is a freshness check, not an
atomic lock against concurrent administrators. New roles are created separately;
an existing role must be inspected rather than silently overwritten. No command
replaces the bucket's full IAM policy or changes existing roles.

After approved execution, read back the WIF condition and bucket policy. IAM
conditions require a version-3 policy response; a version-1 response containing
`_withcond_` role suffixes is not enough to review prefix restrictions. Confirm the
new binding's exact member, role and condition, preserving earlier V4 grants.
The later workflow preflight is the effective permission check.

Command references: [WIF update](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/providers/update-oidc),
[custom role creation](https://docs.cloud.google.com/sdk/gcloud/reference/iam/roles/create),
[conditional bucket binding](https://docs.cloud.google.com/sdk/gcloud/reference/storage/buckets/add-iam-policy-binding).

## 3. Enable cleanup, then refresh workflow preflight

### Separate cleanup from experiment approval

The original shared `cloud-benchmark` environment requires a reviewer. A schedule
using it also waits for that reviewer. The dedicated
[cleanup workflow](../../../.github/workflows/v50-expired-cleanup.yml) therefore uses
`cloud-benchmark-cleanup`: only the `master` branch is allowed, with no reviewers,
wait timer or custom deployment protection rules. The manual experiment workflow
keeps its existing approval requirements. Cleanup has a separate concurrency group
so an experiment waiting for approval cannot prevent it from checking expired
leases. The retained lease, 180-second operation grace, exact ownership and resource
IDs still guard deletion; an active lease produces `WAITING` without mutation.

Generate the separate configuration proposal offline:

```bash
python3 -m scripts.v50.cloud_cleanup_setup --output target/v50-cleanup-setup-review
```

The output contains exact commands, role definitions, environment/branch policy
JSON and WIF condition. Before applying, verify the new account, provider, roles
and environment are absent; an existing object requires inspection instead of
overwriting. Also verify the reused `gseV50ControlDeleter` role contains only
`storage.objects.delete`. The initial runner setup above must already be applied.

| Scope | Cleanup configuration |
| --- | --- |
| WIF provider `v50-expired-cleanup` | Exact repository/ID/owner, master, cleanup workflow, cleanup environment and `event_name == schedule` |
| Principal mapping | `attribute.gse_v50_cleanup` and prefixed `google.subject`; no `attribute.repository_id` mapping, so the existing experiment account's impersonation grant cannot match |
| Service account `gse-v50-cleanup@gse-benchmark.iam.gserviceaccount.com` | Only the cleanup principal can impersonate it |
| Project role `gseV50CleanupRunner` | Compute instance/disk/firewall get/delete, operation get/list and `compute.networks.updatePolicy` required for firewall deletion; no resource creation, SSH metadata or disk attachment privileges |
| Bucket role `gseV50CleanupEvidence` | Object get/create for reading the lease and appending reconciliation evidence; no object deletion |
| Conditional `gseV50ControlDeleter` binding | Delete only `v5.0-replicated-single-shard/control/active-run.json`, using exact resource equality |
| Environment `cloud-benchmark-cleanup` | Exact master branch, no approval or delay; does not alter the paid environment |

The cleanup workflow verifies its service-account identity and effective required
permissions before reading the lease. It rejects resource creation/modification
privileges and delete access on the budget, sequence ledger or evidence probe name.
These negative probes complement the exact IAM binding review; they are not an
exhaustive audit of every possible object name. The workflow exposes no manual
dispatch or paid execution input and has a 15-minute job timeout.

The configuration commands also enable `iap.googleapis.com` and add the two
preflight read permissions `compute.networks.getRegionEffectiveFirewalls` and
`serviceusage.services.get` to the experiment supplement. The regional query has a
[separate permission](https://docs.cloud.google.com/compute/docs/reference/rest/v1/regionNetworkFirewallPolicies/getEffectiveFirewalls)
from the global firewall query. Preflight checks IAP's state through
[Service Usage](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1/services/get);
IAM tunnel permission alone cannot establish that the API is enabled.

Firewall creation and deletion also require `compute.networks.updatePolicy` on
the network ([insert](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/insert),
[delete](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/delete)).
Both runner and cleanup permission probes include it. Instance creation uses tags
and labels, so the runner additionally probes `compute.instances.setTags` and
`compute.instances.setLabels`
([instance insert](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/insert)).
For an existing installation, inspect the roles and add only missing permissions;
the cleanup role must retain its prohibition on instance creation, tags and labels.

### Scheduled receipt and fresh preflight

Only after configuration review and checking that any retained lease is understood,
enable the existing scheduled cleanup:

```bash
gh variable set GSE_V50_EXPIRED_CLEANUP_ENABLED --body true \
  --repo patricklfdm/GeneralSearchEngine
```

This enables the dedicated workflow's cleanup behavior: a verified expired owned
lease can lead to deletion of its owned resources. It does not allocate a topology.
The cron is `7,22,37,52 * * * *`; scheduling can be delayed. Wait for an actually
executed successful `Verify cleanup identity and permissions` and
`Reconcile only an expired retained ownership lease` steps in
`v50-expired-cleanup.yml` for the current master SHA. A skipped job, manual
reconcile, receipt from the old combined workflow or older source does not satisfy
the gate. If the job is skipped, inspect the repository/environment variable values
and environment protection settings. With an older `gh` lacking `variable`, use
the repository Variables REST API and read back the result.

Then request the read-only workflow:

```bash
gh workflow run v50-replication-evidence.yml --ref master \
  --repo patricklfdm/GeneralSearchEngine -f execution=preflight
```

Inspect its retained `preflight.json`. It must identify the workflow service
account, the exact current source/full CI, successful recent scheduled cleanup,
current quotas/image/firewalls, bucket metadata and permissions for all three
control objects. It also validates the isolated cleanup WIF mapping and queries
the cleanup environment, exact branch policy and the separate
[custom protection rules endpoint](https://docs.github.com/en/rest/deployments/protection-rules#get-all-deployment-protection-rules-for-an-environment).
Missing configuration, API errors and any approval gate block admission, even if
an earlier cleanup was manually approved. These queries use Actions read access.
Project/bucket permission failures list the specific missing permissions; firewall
and cleanup-query errors retain their cause. A local owner's successful
query cannot replace this receipt. Receipts expire after 900 seconds and cleanup
must have executed within two hours; refresh during final paid preparation.

### Observed configuration and migration boundary

On 2026-09-16, the original WIF/IAM configuration and cleanup variable were applied.
[Preflight 35126231016, attempt 2](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35126231016/attempts/2)
passed the previous checks after adding the missing regional firewall read
permission. Its cleanup receipt came from a manually approved rerun of the old
schedule. That historical receipt does not satisfy the new unattended cleanup gate.

The isolated cleanup account/provider/roles/environment and IAP enablement were
then applied and read back. Existing experiment WIF, service-account impersonation,
environment reviewers and branch policy were preserved. No V5 VM, disk, firewall
or retained lease existed, and no cloud experiment was triggered. The new workflow
must first be merged; then record full exact-source CI, a successful new schedule
and a fresh service-account preflight. Configuration read-back is not proof that
the unmerged scheduled workflow has run.

### First experiment rejection and configuration correction

[Run 35167079625](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35167079625)
failed on 2026-09-17 UTC at its first firewall insert. The provider audit bound to
request ID `d80946e5-b9d0-4d77-972c-ca3fda50aa7a` recorded denial of
`compute.networks.updatePolicy`; no VM or disk was attempted. The runner supplement
was updated with that permission and `compute.instances.setTags`, and the cleanup
role with `compute.networks.updatePolicy`. Both roles were read back; existing base
permissions already include `compute.instances.setLabels`.

After confirming the Actions owner had stopped, its exact request/audit binding,
and absence of all 13 intended resources, an immutable recovery receipt was stored
under that request's GCS `recovery/denied-insert-audit-<sha256>.json` prefix. A
generation-conditional lease update marked only the denied insert as finished.
The original expiry remains 02:06:35 UTC, with the existing 180-second grace;
scheduled cleanup is eligible after 02:09:35 UTC. The lease was not deleted early.
The failed sequence and USD 6 reservation remain unchanged; USD 34 reservation
capacity remains under the USD 40 ceiling. Reservations are not actual billing.
Fresh source CI, scheduled cleanup and paid preparation are still required before
the user starts a new sequence.

## 4. Prepare the paid review only after readiness

Keep the sequence experiment, failure-drill, canonical 1/2/3 serial. Prepare the
exact artifact/request bundle, then present its request/preflight digests and a
fresh complete-sequence cost calculation before paid execution. Configuration
approval, offline proposal generation and a green preflight are not paid approval.
Any source change requires new exact-source CI, cleanup and admission receipts.

The 2026-09-16 price worksheet below is a historical planning estimate, not a live
quote or admission document. Reprice it and agree evidence retention before use.

| Complete five-topology sequence | Calculation | USD |
| --- | --- | ---: |
| VM watchdog ceilings | 22.5 VM-hours × 0.437496 | 9.8437 |
| Boot/data disks and cleanup overhang | 4050 GiB-hours × 0.000150685 | 0.6103 |
| Evidence retention assumption | 20 GiB × (30 + 7) days × 24 × 0.000031507 | 0.5596 |
| Evidence transfer allowance | 60 GiB × 0.23 | 13.8000 |
| Operations/control/metadata allowance | Reserved | 3.0000 |
| Failed-attempt allowance | Reserved | 8.0000 |
| **Planning estimate / frozen ceiling** | | **35.81 / 40.00** |

Rates use the official `us-west4` [N2](https://cloud.google.com/products/compute/pricing/general-purpose),
[balanced disk](https://cloud.google.com/compute/disks-image-pricing), and
[Standard storage](https://cloud.google.com/storage/pricing) tables. The
[network](https://cloud.google.com/vpc/network-pricing) allowance uses a conservative
destination rate for three 20-GiB copies: guest extraction, GCS read-back and one
independent reviewer download. No discount or free credit is assumed. All five
topologies are priced at 5400 seconds, plus 1080 seconds of disk overhang each.

The observed bucket has seven-day soft delete and no automatic lifecycle expiry.
Thirty days is only a proposed review horizon; keeping 20 GiB longer adds about
USD 0.46/month. Public-repository standard [GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
usage is free; the workflow retains Actions artifacts for 14 days. Failed attempts
consume the same append-only budget. Outages beyond the cleanup allowance and
taxes/currency conversion are not a provider-enforced USD 40 cap.

## Local validation

```bash
python3 -m unittest discover -s scripts/v50 -t . -p 'test_*.py'
```

This covers prefix permission regressions, malformed/missing observations, WIF
guard preservation, role/binding identity, permission deltas and offline generation.
It neither applies configuration nor starts paid workloads.
