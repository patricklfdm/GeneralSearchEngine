# V5.0 Phase 6C cloud setup and readiness

- **Status:** Local setup tooling and preflight candidate; cloud configuration and paid admission pending.
- **Predecessor:** Remote workload integration accepted through [PR #163](https://github.com/patricklfdm/GeneralSearchEngine/pull/163), master `ddff5dd0e0af5b5aa7726ec7107f9815de6d5eef`, [full CI 35079404376](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35079404376).
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

Only after configuration review and checking that any retained lease is understood,
enable the existing scheduled cleanup:

```bash
gh variable set GSE_V50_EXPIRED_CLEANUP_ENABLED --body true \
  --repo patricklfdm/GeneralSearchEngine
```

This enables the workflow's existing cleanup behavior: a verified expired owned
lease can lead to deletion of its owned resources. It does not allocate a topology.
The cron is `7,22,37,52 * * * *`; scheduling can be delayed. Wait for an actually
executed successful `Reconcile only an expired retained ownership lease` step for
the current master SHA. A skipped job, manual reconcile or older source does not
satisfy the gate. If the job is skipped, inspect the repository/environment variable
values and environment protection settings.

Then request the read-only workflow:

```bash
gh workflow run v50-replication-evidence.yml --ref master \
  --repo patricklfdm/GeneralSearchEngine -f execution=preflight
```

Inspect its retained `preflight.json`. It must identify the workflow service
account, the exact current source/full CI, successful recent scheduled cleanup,
current quotas/image/firewalls, bucket metadata and permissions for all three
control objects. Project/bucket permission failures now list the specific missing
permissions; cleanup-query errors retain their cause. A local owner's successful
query cannot replace this receipt. Receipts expire after 900 seconds and cleanup
must have executed within two hours; refresh during final paid preparation.

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
