# Cloud Benchmark V2 operations record

This document records the deployed, keyless Google Cloud configuration and the first
successful protected manual smoke for Cloud Benchmark V2. It is an operations record,
not a performance baseline, SLA, or baseline-registry entry.

The state below was revalidated on 2026-08-28 PDT (2026-08-29 UTC). Secrets, SSH keys,
OIDC tokens, raw benchmark directories, and downloaded Actions artifacts are not stored
in the repository.

## Deployed resources

| Resource | Reviewed value |
|---|---|
| GCP project | `gse-benchmark` (`266952534277`) |
| Region / zone | `us-west4` / `us-west4-a` |
| GitHub Environment | `cloud-benchmark`, required reviewer `patricklfdm`, `master` only |
| Service account | `gse-cloud-benchmark@gse-benchmark.iam.gserviceaccount.com` |
| WIF pool | `projects/266952534277/locations/global/workloadIdentityPools/gse-github` |
| WIF provider | `projects/266952534277/locations/global/workloadIdentityPools/gse-github/providers/general-search-engine` |
| Evidence bucket | `gs://gse-benchmark-evidence-266952534277` |
| Reviewed image | `ubuntu-2404-noble-amd64-v20260826` |

The service account has no user-managed key. The benchmark VM is created with no
service account and no OAuth scopes; short-lived WIF credentials remain on the
GitHub-hosted runner and are not attached to the VM.

The Environment currently allows the sole maintainer to approve their own deployment.
Enable prevention of self-review when a second release/benchmark maintainer is
available.

## Federated identity boundary

The provider is active and maps:

```text
google.subject                  = assertion.sub
attribute.repository           = assertion.repository
attribute.repository_id        = assertion.repository_id
attribute.repository_owner_id  = assertion.repository_owner_id
attribute.ref                  = assertion.ref
attribute.workflow_ref         = assertion.workflow_ref
attribute.environment          = assertion.environment
```

Its deployed condition is:

```text
assertion.repository == 'patricklfdm/GeneralSearchEngine' &&
assertion.repository_id == '1341513206' &&
assertion.repository_owner_id == '147357093' &&
assertion.ref == 'refs/heads/master' &&
assertion.workflow_ref == 'patricklfdm/GeneralSearchEngine/.github/workflows/cloud-performance.yml@refs/heads/master' &&
assertion.environment == 'cloud-benchmark'
```

The condition intentionally relies on immutable repository and owner IDs in addition
to the reviewed names. It does not hard-code a complete `sub` string: repository,
workflow, ref, and Environment are already independently constrained, while GitHub may
change the representation of the subject prefix. `google.subject = assertion.sub`
remains required.

The dedicated service account grants `roles/iam.workloadIdentityUser` only to:

```text
principalSet://iam.googleapis.com/projects/266952534277/locations/global/workloadIdentityPools/gse-github/attribute.repository_id/1341513206
```

## Compute and storage permissions

The project-level custom role is
`projects/gse-benchmark/roles/gseCloudBenchmarkRunner`. Its deployed permissions are:

```text
compute.disks.create
compute.disks.get
compute.images.get
compute.images.useReadOnly
compute.instances.create
compute.instances.delete
compute.instances.get
compute.instances.list
compute.instances.setLabels
compute.instances.setMetadata
compute.instances.start
compute.machineTypes.get
compute.networks.get
compute.networks.use
compute.networks.useExternalIp
compute.projects.get
compute.projects.setCommonInstanceMetadata
compute.regionOperations.get
compute.regions.get
compute.subnetworks.get
compute.subnetworks.use
compute.subnetworks.useExternalIp
compute.zoneOperations.get
compute.zones.get
resourcemanager.projects.get
serviceusage.services.use
```

`compute.instances.setLabels` is required even during instance creation because the V1
runner attaches bounded purpose, mode, commit, and creation-date labels. Project common
instance metadata access is required by the reviewed external-IP SSH path. Do not
replace the custom role with Editor, Owner, Compute Admin, Instance Admin, or Service
Account User.

The evidence bucket is `STANDARD` in `US-WEST4`, uses uniform bucket-level access,
enforces public-access prevention, and has seven-day soft delete. The benchmark service
account has exactly:

```text
roles/storage.objectCreator
roles/storage.objectViewer
```

It has no object delete, overwrite, bucket administration, project administration, IAM
administration, or service-account-key administration grant.

## First successful protected smoke

| Field | Observed value |
|---|---|
| Workflow run | [33232355971](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33232355971) |
| Source commit | `c5eecdc7ce4c828c3d7ca5bdc89af7ca567ed511` |
| Request | `experiment / quick / 1 / spot / c3d-standard-30 / actions` |
| Soak selector | `30m` (not exercised by `quick`) |
| Primary result | `success`, exit `0` |
| Set | `gse-set-v1-0e2e0cca33a9f75af0ae69d620cc01a48fe0d967d97d5fca6032e499fb508ddb` |
| Set status | `VALID_EXPERIMENT_SET`, one member |
| Durable upload | `not-requested` |
| Actions artifact | `cloud-performance-33232355971-1-experiment`, 14 days |

The downloaded artifact contained one checksum inventory plus twelve allowlisted
payload files. `sha256sum -c artifact-checksums.sha256` passed for every payload. It
contained workflow plan/result/summary, the completed set, derived manifest and
normalized metrics, and bounded orchestration evidence. It did not contain the raw
benchmark directory or credentials.

The VM was deleted and a post-run label-filtered instance listing returned no residual
benchmark VM. The run performed no comparison and registered no baseline, so its score
must not be cited as a production regression threshold.

## Setup findings closed by the smoke

The staged rollout failed closed while uncovering four setup/integration gaps:

1. The WIF provider originally included a redundant complete `sub` comparison. The
   deployed condition now uses the independently bounded immutable and workflow claims.
2. The custom role initially omitted `compute.instances.setLabels`; provisioning was
   rejected before a VM existed, then passed after adding only that permission.
3. The workflow verifier expected a different checksum-line order from the canonical
   V1 set generator. [PR #29](https://github.com/patricklfdm/GeneralSearchEngine/pull/29)
   aligned the verifier and added an independent regression fixture.
4. The successful smoke exposed the GitHub runner's Node.js 20 deprecation warning for
   `upload-artifact` v4.6.2. [PR #30](https://github.com/patricklfdm/GeneralSearchEngine/pull/30)
   pinned v7.0.1 on Node.js 24 without changing the archived artifact behavior.

The successful smoke closes the one-time configuration gate. Future exploratory runs
may use the protected manual workflow. Canonical evidence still requires Standard
provisioning, a frozen production preset, three or five independent members, GCS
retention, durable evidence review, and a separate baseline-registration PR.
