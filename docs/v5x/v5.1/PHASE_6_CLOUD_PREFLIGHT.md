# V5.1 Phase 6C3C22 — source and provider preflight

**Status:** implementation candidate after PR #252. The accepted complete owned
experiment ran on master `471a36eea31f6e7cd5cbbdf4cd963f352fb29059`,
[CI 36566870122](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36566870122)
attempt 1, all 29 jobs successful. This batch requires its own protected CI.

## Manual entry points

| Workflow | Execution | Credentials / cloud effects |
| --- | --- | --- |
| `V5.1 Replication Foundation (No GCP)` | `plan` or the existing 19-case fake controller qualification | No OIDC/GCP credentials; local artifacts only |
| `V5.1 Read-only Preflight` | Exact-master GitHub observations and bounded provider GETs | Dedicated observer identity; no cloud writes or cleanup |

Both dispatch only from protected master, check out the exact dispatch SHA, pin
actions, retain failures, and use distinct V5.1 artifacts. Foundation reports the
frozen topology and all preset sizes. Preflight reports source, machine, image
name/ID, quota, bucket policy, previous reserved charge, lease state, freshness,
per-check blockers and remaining admission requirements. Neither runs Maven or
repeats a measured workload. The existing CI Cloud runner lane executes the new
short offline preflight gate; all 29 required jobs and docs-only routing remain.

The preflight workflow occupies the reserved V5.1 runner path but has **no paid
run/prepare option**. It does not deploy either reserved cleanup workflow. A fake
or read-only job must not become a successful cleanup watchdog receipt.
V5.0 workflows, identity, control objects, receipts and budgets remain separate.

## Exact source and attempt

`cloud_ci` reads master before and after collection, checks the newest exact-source
CI run, and queries jobs through the specific run-attempt endpoint. It verifies
the run again and rejects a newer run appearing during collection. A failed or
pending newest run cannot be hidden by an older green run. Bounded pagination
must match its reported total; duplicate, missing, skipped, wrong-source or
wrong-attempt jobs are rejected. Documentation-only CI cannot qualify.

Expected display names come from the checked-out CI's explicit job inventory and
its one reviewed rich-workload matrix. New/unknown matrix syntax fails closed.
The GitHub copy of that workflow and the preflight configuration at the exact
source must match the local bytes/semantic configuration digest. Repository name,
numeric repository/owner IDs, master ref and CI event/path are checked. The owned
complete-experiment step must actually have executed successfully. These are
GitHub job observations of the accepted no-GCP experiment, not native-cloud evidence.

Collection follows GitHub's [run](https://docs.github.com/en/rest/actions/workflow-runs)
and [specific-attempt job](https://docs.github.com/en/rest/actions/workflow-jobs)
APIs. It does not dispatch, rerun or cancel workflows.

## Provider observations

The reviewed [configuration](phase6-preflight-config.json) selects the frozen
V5.1 image/machine/disk/zone and a separately named observer. `cloud_http` still
permits live GET only; no mutation permission switch is added. Collection reads:

- Exact image name, numeric ID, READY state, x86-64 architecture and deprecation.
- Project/zone/machine/subnet identity, private Google access and available quota
  for three 8-vCPU voters, 450 GiB of balanced disks and four firewalls.
- Bucket identity and uniform access. A bucket-wide retention policy or default
  event hold blocks the shared mutable control objects. Every Delete lifecycle
  rule must explicitly retain objects for at least the frozen 30 days.
- Only the V5.1 lease and ledger, through generation-bound metadata/media reads.
  A retained lease blocks admission even after expiry. Pending reservations,
  denied/malformed reads, foreign formats and exhausted budget block it too.
  Failed reservations remain charged; absence of a lease never resets the ledger.

The [bucket metadata API](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets)
defines lifecycle, holds and retention policies. These observations cannot prove
immutable evidence retention, effective IAM, firewall policy, allocation, image
availability at future creation time or token identity beyond the observed account.
Those remain explicit requirements. The historical frozen image is not refreshed
silently when unavailable.

Receipts expire no later than 900 seconds after the earliest input observation.
`OBSERVATIONS_READY` means only these checks passed. Every receipt retains
`paidAdmission=false`, `paidCloud=false`, `fullRemoteQualification=false` and a
list of unqualified admission requirements. Its schema differs from the existing
synthetic authority preflight, and `cloud_authority.admit` rejects it. Missing
authentication still yields a retained BLOCKED report and summary when checkout
and dispatch identity verification completed.

## First live observation and identity correction

[Preflight 36631676728](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36631676728)
ran on PR #253 master `739e1e7fb75f007af37aa78cb7d62105977ef682` after the
operator-authorized observer setup. Authentication, all provider GETs, exact-source
CI (29 jobs), image, quota, storage policy and control state checks succeeded.
The report blocked on `topology: project identity`.

The checker incorrectly compared Compute Project `id` (`5021569533786003310`)
with the Cloud project number (`266952534277`). The [Compute Project API](https://docs.cloud.google.com/compute/docs/reference/rest/v1/projects)
defines this as a Compute resource identifier; `name` identifies the project.
The correction validates a numeric resource ID and exact project name/self-link,
accepting Google's two Compute URL hosts through the existing link normalization.
The bucket's independent `projectNumber` check remains required. Fixtures now use
distinct identifiers; foreign names/links and bucket project numbers still block.

The same retained response also reports `privateIpGoogleAccess=false` on
`us-west4/default`. Corrected replay must still block on that real configuration
requirement, with an explicit Private Google Access diagnostic. Enabling this
shared subnet setting needs separate operator authorization from observer setup;
it is not an observer permission change. See [Private Google Access configuration](https://docs.cloud.google.com/vpc/docs/configure-private-google-access).
Historical replay does not refresh observations or authorize a cloud experiment.
Corrected-source protected CI and a fresh user-triggered preflight remain required.

## Observer configuration proposal

```bash
python3 -m scripts.v51.cloud_observer_setup \
  --output target/v51-observer-setup
```

This writes a reviewable proposal, three custom read-role definitions, an exact
control-object condition and `APPLY.md`; it executes no commands. The new
`gse-v51-observer` pool avoids sharing principal mappings with existing providers.
The provider accepts only the numeric repository/owner IDs, exact workflow,
master, manual event and `v51-cloud-benchmark` environment. The service account
can be granted project metadata reads, bucket metadata and GET of only the two
V5.1 control objects. No instance/disk/firewall mutation or storage create/delete
permission is proposed. See Google's [deployment pipeline federation guide](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

These identities are proposed, not asserted to exist. Configuration and application
need separate review: IAM bindings are additive and the generator cannot attest
inherited grants. Create-only commands stop when a named resource exists. Read
back WIF/IAM and configure the GitHub environment for master plus approval before
using the observer. No cloud configuration was applied by this implementation.

## Validation and next integration

```bash
scripts/verify-v51-phase6-cloud-preflight.sh
```

The offline gate retains real adapter GET requests, source/job observations and
thirteen rejected mutations. Unit regressions additionally cover every job/attempt,
missing/duplicate jobs, rerun/readback races, source/config drift, missing auth,
expired receipts, nonfinite quotas, stale/foreign lease/ledger, retained failed
charges, premature deletion and isolated observer proposals. Both manual entry
points remain subject to corrected-source protected CI.

Next: review/apply and independently inspect observer WIF/IAM/environment; qualify
V5.1 native cloud setup, runner/cleanup identities and shared real reconciliation;
wire remaining frozen failure-drill/canonical cells and provider faults. Only then
can fresh cleanup, pricing, exact-request confirmation and user-triggered paid
execution open. Neither this batch nor C21 closes all of Phase 6.
