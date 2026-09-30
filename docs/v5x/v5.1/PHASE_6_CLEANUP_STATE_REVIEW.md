# V5.1 Phase 6C3C30 — independent cleanup state review

**Status:** implementation candidate based on master
`5ec1e13d64b3236c4aa87dec2d63496d6ea6d1ed`; protected CI pending.
[6C3C29](PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md) is accepted through PR #264/#265
and exact-master CI `36756473536`, attempt 1, all 29 jobs. Identity enablement,
workflow deployment, cleanup execution and paid experiments remain separate.

## Why another observation is needed

The cleanup entry's `PASS` alone does not distinguish an empty lease from the
reclamation of an interrupted attempt. Its own absence report is also not an
independent observation. The [new read-only collector and reviewer](../../../scripts/v51/cloud_cleanup_observation.py)
records native state before and after a run and compares it to the entry result.
It never calls the reconciler, modifies a resource or dispatches a workflow.

| Review case | Required independent state |
| --- | --- |
| `NO_LEASE` | Lease absent on both sides; unchanged ledger; no pending reservation; no resource claim |
| `ACTIVE_OR_GRACE` | Run occurred before expiry plus grace; `WAITING`; unchanged lease generation, ledger, retained context/completion and resource observations |
| `EXPIRED_ABSENCE_CONFIRMED` | Run occurred after expiry plus grace; original operations resolved; every attempted name and resolved numeric ID absent; lease released; correct terminal ledger/completion; original charges retained |

An expired reservation with no create intent can be finalized with zero resource
observations. The result records the number of attempted and previously present
resources, so it cannot be presented as a real resource-deletion test. A pending
ledger reservation without a lease blocks the empty-state review even if the
cleanup entry itself returned `PASS` for no lease.

## Fixed read-only collection

The CLI uses the repository's fixed configuration, current checkout SHA and a
hash of the collector's own bytes. Its generic HTTP API permits only GET on the
fixed Google endpoints. An additional wrapper requires GET even for offline test
inputs and caps all calls at one 180-second collection deadline. No configuration,
clock, credential endpoint, resource name or deletion override is exposed.
The existing active gcloud credential supplies read access; the collector does
not switch accounts or impersonate a cleanup identity. Raw credentials and
provider exception text are never retained.

Collection reads generation-bound native lease/ledger objects. If a lease exists,
it reads that request's retained context and completion, resolves each attempted
original insert operation, and inspects both the intended name and known numeric
ID. Provider shape/ownership validation remains in the established adapter.
Finally it rereads the retained objects and control generations; a change or
unavailable read returns `BLOCKED`. A 403 is never interpreted as a 404.

The after observation takes the original before snapshot as its reference. It
continues checking that original inventory even after the lease was deleted, and
rejects a different active request. No project-wide resource listing or arbitrary
caller-selected inventory is used. Only the observed state is collected; active
cloud resources can still change after the sample.

The same collector can be exercised with an offline HTTP model in unit tests;
those records carry `execution=offline-cleanup-observation`. A review requires
both observations to share their execution domain and collector hash. JSON hashes
bind local files to each other, not to a trusted external signer.

## Commands for a separately approved real validation

The first command is read-only and can be used before activation:

```bash
python3 -m scripts.v51.cloud_cleanup_observation capture \
  --output target/v51-cleanup-validation/before
```

After a separately approved manual/scheduled cleanup run completes, keep the same
checkout and collector bytes, download that exact run's diagnostics, then:

```bash
python3 -m scripts.v51.cloud_cleanup_observation capture \
  --before target/v51-cleanup-validation/before/observation.json \
  --output target/v51-cleanup-validation/after
python3 -m scripts.v51.cloud_cleanup_observation review \
  --before target/v51-cleanup-validation/before/observation.json \
  --after target/v51-cleanup-validation/after/observation.json \
  --entry target/v51-cleanup-validation/downloaded/reconciliation \
  --output target/v51-cleanup-validation/review
```

All output directories are create-only. The `--entry` directory is the formal
entry's directory containing `binding.json` and `receipt.json`, not its nested
reconciliation receipt. The before snapshot must finish before the GitHub job
starts; the after snapshot must begin after the job ends. Before/after timestamps
are local clock observations, so correct UTC clock synchronization matters.

The reviewer fetches the latest run, exact attempt, its jobs, then the latest run
again. It verifies the original repository/owner, master source, workflow/event,
trigger-specific service account/provider/environment, completed successful run,
sole cleanup job and successful identity/auth/reconciliation/retention steps.
A rerun, fork, skipped step, changed source or binding from another run blocks review.
No dispatch or cloud request is made by the review command.

The terminal ledger must equal the prior history plus exactly the appropriate
finish event (or remain unchanged if already terminal), with the retained
completion hash. Cleanup-created completions must be `FAIL`; a previously retained
successful owner's completion is preserved. Original operation IDs cannot change,
missing operation history cannot prove absence, and a reused name cannot stand
in for an original numeric resource. Receipt absence checks must match the new
independent observations for every attempted resource.

## What STATE_MATCH does and does not establish

`STATE_MATCH` means the supplied snapshots, entry receipt and observed GitHub run
are consistent under these rules. Every result retains
`artifactProvenanceVerified=false`, `effectiveIamQualified=false`,
`activationAllowed=false`, `cleanupReady=false`, `paidAdmission=false`,
`paidCloud=false` and `fullRemoteQualification=false`.

The reviewer does **not** authenticate the provenance of locally supplied JSON,
verify that the downloaded bytes match GitHub's artifact digest, inspect deployed
workflow bytes, prove the acting cloud principal from an audit log, or establish
an IAM permission boundary. An offline fixture or edited local snapshot cannot
be promoted to admission by this tool. Historical state comparisons also do not
establish current cleanup freshness. The remaining admission gate must perform
those checks independently.

In particular, absence after a run does not identify who deleted a resource.
Retain provider audit evidence for the exact operation/resource ID and principal;
Compute documents its methods and audit categories in the
[audit logging reference](https://docs.cloud.google.com/compute/docs/logging/audit-logging).
If that evidence is unavailable, retain the uncertainty instead of declaring a
real deletion or permission-denial case qualified. No destructive negative is
injected into a running experiment by this collector.

## IAM blocker and administrator review inputs

The project's last observed direct parent is organization `821373826893`. The
existing project/bucket/identity audit cannot establish inherited permissions:
[effective allow policies include ancestors](https://docs.cloud.google.com/iam/docs/resource-hierarchy-access-control).
The current account could not read organization allow/deny policies in the
retained 2026-09-30 observations. Those denials remain unresolved.

An authorized administrator can retain the following read-only exports, with the
collection time and current project-parent identity:

```bash
gcloud projects describe gse-benchmark --format=json > project.json
gcloud organizations get-iam-policy 821373826893 --format=json > organization-allow.json
gcloud iam policies list \
  --attachment-point=cloudresourcemanager.googleapis.com/organizations/821373826893 \
  --kind=denypolicies --format=json > organization-deny-index.json
```

If the deny listing contains policies, fetch each exact returned policy ID with
[`gcloud iam policies get`](https://docs.cloud.google.com/sdk/gcloud/reference/iam/policies/get)
on that same attachment point. Check pagination, every listed policy body, parent
changes and any intermediate folders. An unreadable/partial export is not an
empty policy. Review the exports together with fresh explicit grants, relevant
broad-principal/group membership and account/bucket policies. Do not grant Owner,
Editor or organization write access merely to unblock this review.

These exports are inputs for authorized review, not automatic approval. They may
remain local and need not be committed. If administrator access is unavailable,
resolve the deployment approach with the operator; this batch neither migrates
the project nor waives the inherited IAM requirement.

## Current read-only evidence and remaining validation

The exact-source CI checker accepted `36756473536` attempt 1. Fresh deployment
readback returned `CONFIGURATION_MATCH` in staged state: all three accounts,
pools and providers remain disabled. A genuine GET-only baseline sample found
both V5.1 control objects absent (`active.json` and `ledger.json`). This says
nothing about resources outside that namespace and is not a cleanup execution.

Retained local evidence: `target/v51-cleanup-qualification-review/accepted-ci.json`,
`staged/` and `live-before/`. The capture used the candidate collector hash and the
master checkout as its source base; it is not corrected-source protected acceptance.
The preflight gate exercises the new collector/reviewer against offline native
states, including failures, stale/replaced identities, lost insert acknowledgements,
ledger changes, generation movement, denied reads and missing resources/operations.

Next: protected CI, resolve the IAM review, then separately authorize the already
prepared workflow/identity deployment and bounded real-provider fixture. Capture
both successful and rejected cases, verify artifact/audit provenance, and establish
fresh manual or scheduled cleanup readiness before paid admission. The fixture's
allocation, pricing and exact-request approval remain separate from these reads.
