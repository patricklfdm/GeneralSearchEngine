# V5.1 cleanup configuration and activation review

**Status:** configuration proposal reviewed on master
`27d6f7fa23377dbf305a1ac719ac5f8a6e97df9c` (PR #261).
[CI 36695145198](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36695145198)
passed all 29 jobs on attempt 1 and accepts the
[6C3C27 offline credential integration](PHASE_6_CLEANUP_CREDENTIALS.md).
The operator subsequently authorized the exact disabled identity package. All 45
configuration commands completed on 2026-09-30, and the independent 33-query audit
returned `STAGED_MATCH`. Accounts, pools and providers remain disabled; live
cleanup and paid admission remain unavailable.

## Concrete configuration package

The existing [identity generator](../../../scripts/v51/cloud_identity_setup.py)
produces `target/v51-cleanup-activation-review/disabled-identities/`. Its
`proposal.json`, exact role/condition/environment payloads and `commands.json`
are accompanied by the complete `APPLY.md`. No new mutation implementation or
activation switch is needed to stage these existing disabled identities.

| Change | Exact scope |
| --- | --- |
| Service accounts | `gse-v51-runner`, `gse-v51-cleanup`, `gse-v51-manual-cleanup` in `gse-benchmark`; disable each immediately after creation, before grants |
| Federation | Three separate pools with those names, each with one `github` provider; pools and providers created disabled |
| Impersonation | One `roles/iam.workloadIdentityUser` binding per account, scoped to its own pool and numeric repository ID |
| Project roles | Seven exact custom roles; four project bindings (runner Compute, runner IAP port 22, two cleanup Compute bindings) |
| Bucket bindings | Fifteen exact bindings on `gse-benchmark-evidence-266952534277`; mutable/delete authority limited to the V5.1 lease and ledger; attempts only read/create |
| GitHub environments | New `v51-cloud-cleanup` with no approval/timer and `v51-cloud-manual-cleanup` with operator approval; both master only |
| Reused environment | Inspect existing `v51-cloud-benchmark`; no change to it |

There are 45 structured application commands. No key creation, credential
activation, workload allocation, cleanup invocation or workflow deployment is in
that command list. Existing observer and V5.0 identities remain separate.
Disabling a service account prevents its use to access resources; this proposal
also disables its pool and provider. See Google's
[service-account lifecycle](https://docs.cloud.google.com/iam/docs/service-accounts-disable-enable).

Compute grants apply at project scope. They do not restrict deletions to resource
names or ownership on their own. The shared cleanup policy must still enforce
expiry/grace, original operations, exact IDs and generation conditions. The
[firewall deletion API](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/delete)
includes network-policy authority. The exact lease/ledger grants include both
create and delete because [GCS object replacement requires both](https://docs.cloud.google.com/storage/docs/access-control/iam-permissions).
These residual privileges must be explicit in the application approval.

## Read-only observations on 2026-09-30

- The live absence audit returned `ABSENCE_REVIEWED`: all proposed account, pool,
  role and new-environment names were absent; existing runner environment approval
  and master-only policy matched. The generator's absence/tombstone limits remain
  as documented in [identity staging](PHASE_6_CLOUD_IDENTITIES.md).
- Project ID/number matched `gse-benchmark` / `266952534277`. Its direct parent is
  organization `821373826893`; no intermediate folder was reported.
- Sampled project/bucket policies contained no grants to the three proposed
  accounts and no `allUsers`/`allAuthenticatedUsers` binding. The project deny
  policy listing was empty. These observations cover only the queried resources.
- Organization allow-policy and deny-policy reads both failed for lack of
  permission. Effective inherited IAM remains **unqualified**. A successful
  project read or disabled-staging audit cannot substitute for that review.

The retained read-only receipt and provider observations are under
`target/v51-cleanup-activation-review/identity-absence/` and `provider-review/`.
The approval package has a hash inventory in `review.json`; raw policy output is
local evidence, not a new checked-in credential or cloud admission receipt.
Absence observations expire after 900 seconds. Before an authorized application,
rerun the absence audit and inspect any collision instead of overwriting it.

## Application procedure and readback

1. Verify the reviewed proposal/payload hashes, then collect a fresh absence
   audit. Retain the current project/bucket policies and reused environment.
2. Execute the exact commands in the generated directory, stopping on failure.
   Confirm each account is disabled before any grant; inspect role propagation
   or partial state before deciding how to resume. Do not blindly replay creates
   or delete a collision. No enable command belongs to this stage.
3. Run `python3 -m scripts.v51.cloud_identity_audit staged --output <new-directory>`.
   `STAGED_MATCH` must establish disabled accounts/pools/providers, no user keys,
   exact trust, role/grant contents and environment policies. Compare unrelated
   observer/V5.0 grants and the reused environment to their pre-application state.
4. Retain the results with this batch. A failed readback leaves staging incomplete;
   even `STAGED_MATCH` keeps `activationAllowed=false`, `cleanupReady=false` and
   `paidAdmission=false`.

### Authorized application result

Application is complete. Do not rerun the create commands; subsequent verification
uses the staged audit against the existing configuration.

The operator approved the complete package represented by proposal SHA-256
`6f9ea33e6490cff162ff7175062548fdd2e02d7901624f904b25bf1090481400`
and command-list SHA-256
`be1154954777a3b37149295a6d6489654bcd43c319b93f8e10dc9c91c201bf31`.
The 33 review-package file hashes matched before execution. A new absence audit
passed immediately before application. All 45 commands returned success; no
mutation was repeated. Account state was independently checked before grants.

The manual-cleanup disable request returned success, but its immediate describe
response omitted `disabled`. Execution stopped before any grant to that account.
A later independent describe confirmed `disabled=true`, and a policy read showed
no bindings; only then did execution continue. Both observations and the stopped
command's original failure receipt are preserved, with a separate resolution
record. A later successful read does not erase the first observation.

The independent staged audit passed all 16 check groups from 33 read commands:
exact identity state, no user keys, WIF trust/impersonation, seven role permission
sets, project/bucket grants and the three environments. Additional comparisons
proved that the final project/bucket bindings equal the prior bindings plus the
approved additions, other policy fields are preserved, existing account/pool/role
inventories are unchanged, and reused/other environments are unchanged. The
reviewed proposal and inactive workflow files remain byte-identical.

Retained evidence: `target/v51-cleanup-activation-review/application/receipt.json`,
`staged-receipt.json`, `staged-observations.json`, command results and
`command-11-resolution.json`. The aggregate receipt remains
`activationAllowed=false`, `effectiveIamQualified=false`, `cleanupReady=false`,
`paidAdmission=false`, `paidCloud=false`, `fullRemoteQualification=false` and
`workflowDeployed=false`. These are disabled configuration results, not real
credential exchange, resource cleanup or workload evidence.

## Workflow and credential transition

The current `v51-replication-evidence.yml` runs the dedicated read-only observer
in `v51-cloud-benchmark`. Its path/event/environment also match the proposed
runner's future trust. **Keep the runner disabled** until its admission and
workflow transition are separately qualified. Green CI and environment approval
alone cannot make that change safe.

Generated manual/scheduled cleanup workflows remain outside `.github/workflows`.
They stop at `activation-check`, expose no force/resource/age override and have
no auth step. The two entries have separate exact workflow/event/environment
identities and one advisory concurrency group. Numeric repository/owner claims
remain part of trust, consistent with Google's
[deployment federation guidance](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

After staged readback, the [6C3C28 implementation candidate](PHASE_6_CLEANUP_NETWORK.md)
adds a cleanup-only network credential/transport path through the existing policy
and reconciler, with loopback TLS qualification. Corrected-source protected CI
remains pending. The original offline guards stay in place: changing a label or
removing one stop does not open the general provider's POST/DELETE path. Real signature authentication,
provider operation/ID semantics, effective IAM and failure evidence remain to be
established before separately approved cleanup activation. Cleanup must not depend
on green paid-workload CI, and must preserve failed charges and older-source
retained ownership records.

Fresh manual **or** scheduled cleanup evidence then contributes to paid readiness.
It cannot replace native workload integration, pricing, exact-request confirmation
or the user's manual dispatch. Full Phase 6 remains open.
