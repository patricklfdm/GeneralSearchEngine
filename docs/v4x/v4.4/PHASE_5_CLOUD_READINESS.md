# GeneralSearchEngine V4.4 Phase 5 cloud readiness

- **Status:** Implemented and validated without GCP
- **Workflow:** `.github/workflows/v44-final-durable-evidence.yml`
- **Paid execution owner:** Phase 6 only
- **GCS prefix:** `v4.4-final-durable/`

## Exact execution plan

The manual workflow accepts only the three frozen tuples:

| Profile | Serial members | Duration each | Retention |
|---|---:|---:|---|
| `experiment` | 1 | 3,600 seconds | Actions |
| `canonical` | 3 | 3,600 seconds | GCS |
| `failure-drill` | 1 | 3,600 seconds | Actions |

Every member is Standard `c3d-standard-30` in `us-west4-a`, using image
`ubuntu-2404-noble-amd64-v20260906`, one 100-GiB auto-delete boot disk, one
200-GiB data disk and one 200-GiB target disk. `max-parallel: 1` keeps the project at
30 vCPU and 500 GiB total provisioned disk. Each VM has a 10,800-second maximum
runtime; the full canonical request retains the frozen USD 40 ceiling.

Preflight resolves the requested source to the exact protected `origin/master` tip
before any job may request OIDC. The source VM builds exact source, runs inherited
authority/backup/restore/migration/derived-state coverage and a paired published-4.3
control, then is deleted. A new replacement VM performs the 3,600-second durable
measurement, continuation and reopen proof. Evidence requires independent backup
inspection and exact deletion receipts for both VMs, both data disks and staging
objects. Member artifacts upload under `always()` even after failure.

## IAM boundary before Phase 6

Phase 5 does not mutate IAM. Before a paid run, the existing Workload Identity
Provider condition must additionally allow exactly:

```text
patricklfdm/GeneralSearchEngine/.github/workflows/v44-final-durable-evidence.yml@refs/heads/master
```

The benchmark service account needs object create/view access already used by the
evidence bucket and delete permission restricted to:

```text
projects/_/buckets/gse-benchmark-evidence-266952534277/objects/v4.4-final-durable/
```

No repository secret, long-lived key, VM service account or broad object-delete grant
is introduced. The exact bucket name remains a repository/environment configuration
value and must be inspected before applying the conditional binding.

## No-GCP validation

```bash
python3.11 -m unittest scripts.v44.test_phase5_cloud_readiness
scripts/v44/test_final_durable_cloud_runner.sh
```

These commands validate plan rejection, summary rendering, serial topology, remote
bootstrap ordering, frozen image/duration/resources, published-4.3 checksum binding,
strict member/set schemas, thresholds, cleanup receipts and all dry-run profiles.
They do not invoke `gcloud`, request OIDC, create a resource or upload an object.
