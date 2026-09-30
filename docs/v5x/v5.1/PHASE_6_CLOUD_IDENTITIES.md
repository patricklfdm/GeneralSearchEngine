# V5.1 Phase 6C3C23 — disabled runner and cleanup identity staging

**Status:** accepted through PR #255, master
`41b567b7cb96d36157a4434b02268b746492edfd`, with all 29 jobs passing
[CI 36648030423](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36648030423).
This accepts disabled staging code and audits, not application or activation.
The preceding [read-only preflight 36643330675](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36643330675)
passed all seven observations after the separately authorized observer setup and
Private Google Access change. These observations have a 900-second lifetime;
the historical success records integration, not current paid admission. Effective
organization/folder IAM remains unverified.

## Scope

This batch generates a concrete configuration proposal for three new identities
and supplies read-only absence/staging audits plus offline rejection evidence.
It applies no GCP/GitHub configuration, deploys no cleanup workflow, dispatches
nothing and does not enable live HTTP mutations or change fake request schemas.

| Purpose | New service account / dedicated WIF pool | Exact future workflow | Environment |
| --- | --- | --- | --- |
| Runner | `gse-v51-runner` | `v51-replication-evidence.yml`, manual dispatch | Existing `v51-cloud-benchmark`, operator approval |
| Scheduled cleanup | `gse-v51-cleanup` | `v51-expired-cleanup.yml`, schedule only | New `v51-cloud-cleanup`, no approval/timer |
| Manual cleanup | `gse-v51-manual-cleanup` | `v51-manual-cleanup.yml`, manual dispatch only | New `v51-cloud-manual-cleanup`, operator approval |

All three new service accounts, pools and providers remain **disabled**. Each
fresh account is disabled before granting roles or impersonation. The current
read-only preflight occupies the future runner workflow path and environment;
its OIDC claims would match that future runner. Therefore a role/WIF match is
insufficient to enable it. There is no enable command or activation flag in this
batch. A later implementation must review the workflow/credential transition,
real admission and provider reconciliation before activation. Existing observer
and V5.0 trust/roles/environments remain unchanged.

Claims bind repository name, numeric repository/owner IDs, master ref, exact
workflow path, event and environment. A separate pool per identity prevents one
provider from satisfying another pool's service-account impersonation grant.
Only `roles/iam.workloadIdentityUser` is proposed on each account; no keys or
Token Creator grant is generated. See Google's
[disabled pool behavior](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/create)
and [provider semantics](https://docs.cloud.google.com/iam/docs/reference/rest/v1/projects.locations.workloadIdentityPools.providers).
A provider disable alone does not revoke existing tokens; this staging also
requires the pool and service account to be disabled.

## Permissions and residual boundaries

[cloud_identity_setup.py](../../../scripts/v51/cloud_identity_setup.py) retains
seven exact custom role definitions and every proposed binding. Permissions map
to the current [provider adapter](../../../scripts/v51/cloud_gcp.py), with a
separate runner IAP permission constrained to destination TCP port 22, using the
[documented IAP condition](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding).

- Runner: current topology create/read/delete, original operation resolution,
  private subnet and disk attachment, guest attributes, metadata and labels/tags.
  It does not gain project SSH metadata, attached-service-account impersonation,
  public-IP allocation or future replacement/fault permissions by default.
- Cleanup: resource and operation reads, resource deletion and
  `compute.networks.updatePolicy`, needed by
  [firewall deletion](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/delete).
  It has no instance/disk/firewall create, SSH/IAP or guest metadata/label grants.
- Bucket metadata: `storage.buckets.get` on the exact bucket.
- Object reads: only the V5.1 control prefix, which includes retained attempts.
- Object creation: exact lease/ledger names and the separate attempts prefix.
- Object deletion/replacement: **only** the exact V5.1 lease and ledger. GCS
  overwrites need create and delete; attempt evidence has no delete grant.

Cleanup needs ledger replacement because the shared
[reconciler](../../../scripts/v51/cloud_runner.py) appends a terminal event before
releasing the lease. This is deliberately different from V5.0's cleanup model.
Failed charges remain recorded; IAM cannot enforce append-only JSON contents.
Generation conditions, ledger validation, expiry/grace, original operation,
exact ownership/IDs, immutable attempt completion and absence checks remain
application responsibilities. No parallel deletion implementation is introduced.

The explicit Compute permissions are project grants. They do **not** enforce
V5.1 resource-name or ownership boundaries by themselves, and network policy
permission affects the shared network. This residual authority must be reviewed
before applying or enabling credentials. Public-image access, IAP connectivity,
provider acceptance of conditional/numeric operations, inherited allow/deny
policies and resource-level grants remain separately unqualified. Role contents
are a reviewable candidate, not proof of effective least privilege or successful
native execution. Insertion field permissions include
[`compute.disks.setLabels`](https://docs.cloud.google.com/compute/docs/reference/rest/v1/disks/insert)
to avoid the historical V5.0 missing-label permission failure.

## Operator commands

From the repository root:

```bash
python3 -m scripts.v51.cloud_identity_setup --output target/v51-identity-proposal
python3 -m scripts.v51.cloud_identity_audit absent --output target/v51-identity-absence
```

The generator never calls a subprocess or provider. Its `APPLY.md`, role/condition
JSON, environment payloads and structured command list are for review and separate
operator authorization. The absence audit performs only GCP reads and GitHub GETs;
pre-existing names, including returned soft-deleted pools/roles, stop the review.
Service-account tombstones are not enumerated; create-only commands still stop
on conflicts. GitHub environment enumeration must match its total and rejects
more than one page instead of assuming absence. Existing observer/runner approval
settings are checked and never rewritten.

After a separately authorized application, run:

```bash
python3 -m scripts.v51.cloud_identity_audit staged --output target/v51-identity-readback
```

`STAGED_MATCH` requires exact disabled account/pool/provider states, a single exact
provider per pool, exact issuer/mapping/condition, no user-managed keys, exact
impersonation policy, seven exact role permission sets, scoped project/bucket
bindings and exact master/approval rules. API member ordering/merged bindings are
normalized; extra grants to the new accounts or extra principals for these roles
block. The audit rejects missing/failed reads, truncation, stale/future snapshots,
permission drift and enabled credentials. It retains only an error type for failed
commands, never their stderr or token material.

This is a sample of explicit policies, not atomic effective-IAM proof. Receipts
retain `activationAllowed=false`, `effectiveIamQualified=false`,
`cleanupReady=false`, `paidAdmission=false` and `fullRemoteQualification=false`.
The live read-only absence audit for this batch succeeded; no proposal command was
applied. Enabling or deploying the future workflows requires a later review.

## Validation and next integration

The existing short preflight gate now also qualifies identity staging:

```bash
scripts/verify-v51-phase6-cloud-preflight.sh
```

Its existing always-uploaded CI artifact contains the full proposal, sampled
fixture, 33 exact read commands and 16 rejected drift cases. Tests cover account,
pool and provider enablement; trust/impersonation changes; cleanup allocation;
bucket-wide/evidence deletion; extra roles; SSH port scope; user keys; approval
and branch drift; absence collisions; malformed/incomplete reads; and API binding
normalization. The independent existing control/provider gates continue to verify
shared reconciliation and live-adapter/mutation rejection. No extra CI job,
Maven build or measured workload is added.

Next: review/apply disabled identities, qualify native source/SSH/mount/provider
operations and the existing shared expired reconciler; implement separate manual
and scheduled cleanup entry points; then separately review activation and collect
fresh exact-source cleanup evidence. Remaining failure-drill/canonical cells,
retention, pricing and exact-request confirmation still precede user-triggered
paid experiments. Neither staged configuration nor observer success closes 6C.

The next [retained cleanup reconstruction candidate](PHASE_6_CLOUD_CLEANUP.md)
provides independent process recovery through the same HTTP adapters and shared
reconciler. It retains the native activation boundary described above.
