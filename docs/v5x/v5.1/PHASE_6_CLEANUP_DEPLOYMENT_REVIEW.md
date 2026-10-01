# V5.1 Phase 6C3C29 — cleanup deployment review and readback

**Status:** accepted through PR #264 and the outer CI timeout correction in
PR #265, master `5ec1e13d64b3236c4aa87dec2d63496d6ea6d1ed`.
[CI 36756473536](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36756473536)
passed all 29 jobs on attempt 1, including Cloud runner in 9m26s. The exact-source,
exact-attempt checker also accepted the owned-experiment gate. The original PR
and master 10-minute cancellations and master read-heavy burst-spread failure
remain retained; later success does not establish that burst delay's cause.
No cleanup workflow is installed, no identity is enabled and no cloud cleanup or
paid workload is executed by this acceptance. The
[next independent state review](PHASE_6_CLEANUP_STATE_REVIEW.md) prepares real
provider observations without replacing actual-identity permission qualification
or activation approval. The [IAM scope amendment](PHASE_6_CLEANUP_STATE_REVIEW.md#iam-admission-scope-amendment--2026-09-30)
makes ancestor-policy reads optional while retaining required configuration,
permission and cleanup checks. No extra organization privilege is requested.

## Concrete review package

The [deployment generator](../../../scripts/v51/cloud_cleanup_deployment.py)
produces a separate package outside `.github`:

```bash
python3 -m scripts.v51.cloud_cleanup_deployment generate \
  --source "$(git rev-parse HEAD)" \
  --output target/v51-cleanup-deployment-review/proposal
python3 -m scripts.v51.cloud_cleanup_deployment validate \
  --source "$(git rev-parse HEAD)" \
  --output target/v51-cleanup-deployment-review/proposal
```

Use a new output directory on regeneration. Its contents are:

| File | Review purpose |
| --- | --- |
| `v51-manual-cleanup.yml` | Exact manual workflow proposal; dedicated approved environment and identity |
| `v51-expired-cleanup.yml` | Exact scheduled proposal at minute 7/22/37/52; dedicated environment without approval |
| `commands.json` | Six enable and six disable requests for the two cleanup identities, grouped by trigger |
| `REVIEW.md` | Deployment prerequisites, ordering, qualification and rollback procedure |
| `review.json` | Source/configuration binding, four payload hashes, explicit not-applied/readiness flags |

The source is the review base, not a fabricated future deployment commit. After
protected merge, regenerate and review against the actual master source; deploy
those exact workflow bytes in a separately approved change. The validator compares
every payload to the trusted generator/configuration/source, so modifying a
workflow and recomputing its self-reported hash still fails. Extra/missing files
and payload symlinks fail. Generation is create-only and rejects `.github` even
through a symlink. There is no apply, install, enable or dispatch subcommand.
The previously authorized 33-file disabled/inactive package is not rewritten.

## Proposed workflow behavior

Both entries bind exact repository/owner IDs, master source, workflow path, event,
environment and in-progress run attempt before the pinned auth action. They use
separate identity and reconciliation output directories. Only the cleanup job has
`id-token: write`; provider/account inputs come from the validated identity step.
The action writes its external-account descriptor and removes it in post cleanup.
The [pinned auth action definition](https://raw.githubusercontent.com/google-github-actions/auth/7c6bc770dae815cd3e89ee6cdf493a5fab2cc093/action.yml)
is the credential-file contract; the artifact upload covers only
`target/v51-cleanup`, not the checkout or credential file.

The [6C3C31 candidate](PHASE_6_IDENTITY_PERMISSIONS.md) inserts a bound permission
precheck after authentication. Missing required, returned forbidden or unavailable
project/bucket queries stop the job before reconciliation. PRECHECK_PASS cannot
establish object-name conditional access; real-path qualification remains required.
The independent state reviewer also requires the successful precheck step.

The job then invokes the existing `cloud_cleanup_entry reconcile`; it accepts no
force/resource/age override. Summary and evidence upload run on success or failure.
The fallback summary does not claim no credentials were acquired when auth might
already have run. The job has the existing 15-minute limit, no automatic retries,
no paid-workload/green-CI dependency and no new runner path.

The proposals preserve the common advisory `v51-native-cleanup` concurrency group
and `cancel-in-progress: false`. A manual run waiting for environment approval can
hold up the shared queue. Approve or cancel abandoned waiting runs before relying
on scheduled cleanup. GitHub's [concurrency and environment rules](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments)
are separate mechanisms; this proposal does not establish an unattended timing
SLA. Lease generations, expiry plus grace, operation identity and exact numeric
resource IDs remain deletion authority.

## Enable, inspect, qualify, then schedule

Only after separate operator approval and the review prerequisites:

1. Verify fresh disabled identity readback, exact explicit roles/grants, WIF trust
   and environment restrictions. Missing/denied required observations still block;
   optional organization/folder reads remain an unassessed limitation. Deploy the
   reviewed workflow bytes with identities disabled.
   A triggered schedule may fail authentication; this does not count as readiness.
2. Enable **manual** provider, then pool, then service account. Inspect each result,
   stopping on errors or ambiguous responses. Do not blindly retry mutations.
3. Read back the complete configuration in `manual` state. The runner and scheduled
   account/pool/provider must still be disabled. Have the operator dispatch and
   approve the manual workflow. Preserve actual authentication/provider evidence.
   Before readiness, qualify required access and forbidden-action probes with the
   actual workflow account. Required permission denial, inconclusive checks or
   forbidden access still block. An operator account cannot substitute.
4. A no-lease `PASS` only qualifies the empty path. Before declaring readiness,
   use a separately reviewed bounded real-provider fixture for active/grace
   `WAITING`, expired cleanup, exact-ID/name-reuse handling, ambiguous operations,
   generation conflicts, denied/lost responses and preservation of failed charges.
   This package does not allocate that fixture or authorize any expenditure.
5. Enable **schedule** provider, pool, then account; read back `cleanup` state and
   retain a real scheduled result. Qualify readiness separately. The paid runner
   remains disabled, and cloud experiments remain user-triggered.

The generated commands use only account `enable`/`disable` and pool/provider
`--no-disabled`/`--disabled`; no grant, trust, role, key, resource or ledger changes
are included. See Google's [pool update](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/update)
and [provider update](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/providers/update-oidc)
references. Provider disabling alone does not revoke existing tokens. Rollback
starts with account disablement, then provider and pool, followed by fresh state
inspection; allow for propagation and inspect any in-progress cleanup separately.
Disablement does not prove resource absence or release a retained lease.

## Independent configuration readback

```bash
python3 -m scripts.v51.cloud_cleanup_deployment readback \
  --state staged --output target/v51-cleanup-deployment-review/readback
```

Use `manual` only when manual enablement is separately authorized/completed, or
`cleanup` when both cleanup identities have been enabled. These are expected-state
checks, not switches that change cloud configuration.

| Expected state | Runner | Manual | Schedule |
| --- | --- | --- | --- |
| `staged` | disabled | disabled | disabled |
| `manual` | disabled | enabled | disabled |
| `cleanup` | disabled | enabled | enabled |

Each column represents account **and** pool **and** provider. The auditor first
checks all nine enable bits, then reuses the unchanged staged audit for the 33
read observations: identity, keys, exact trust/impersonation, custom roles, explicit
project/bucket bindings and environment protection. Partial or extra enablement
fails. A default omitted `disabled=false` is accepted only for an expected-enabled
object; expected-disabled objects must explicitly report true. The original
`cloud_identity_audit staged` remains strict and rejects enabled identities.

`CONFIGURATION_MATCH` keeps `activationAllowed`, `effectiveIamQualified`,
`cleanupReady` and `paidAdmission` false. It is neither operator approval nor proof
of inherited IAM, genuine provider behavior or an operational watchdog.

## Retained live observations and revised review boundary

On 2026-09-30, the fresh staged audit passed all 16 groups / 33 reads. All nine
disable states remained true and the explicit grants/trust/environments matched.
Project `gse-benchmark` still reported direct organization parent `821373826893`;
the project deny listing was empty. Reads of the organization allow policy and
deny-policy list were again denied. These observations originally blocked
activation under the earlier review scope. The operator-authorized
[IAM scope amendment](PHASE_6_CLEANUP_STATE_REVIEW.md#iam-admission-scope-amendment--2026-09-30)
now records them as an unassessed limitation without requiring ancestor-policy
access. Required explicit-policy checks, actual-identity permission probes and
real cleanup qualification remain prerequisites; no privilege is added.

Local evidence is retained in `target/v51-cleanup-deployment-review/staged/` and
`inherited-iam/`. Observations describe their timestamps and expire for subsequent
admission; they are not permanent permission evidence. The project-wide cleanup
Compute permissions and exact control-object delete scope remain as recorded in
the [original activation review](PHASE_6_CLEANUP_ACTIVATION_REVIEW.md).

## Validation and remaining boundary

The preflight gate includes the new deployment tests: all three state transitions,
each incorrect enable bit, omitted/malformed fields, policy/grant drift, stale or
incomplete observations, altered/rehashed packages, symlinks and no-execution
behavior. Existing inactive proposals still stop before credentials. The same gate
generates and validates the review package under its retained evidence directory;
CI executes no cloud readback or enable command.

```bash
scripts/verify-v51-phase6-cloud-preflight.sh
```

Explicit role/binding review, approved deployment, actual-identity required and
forbidden permission checks, real credential/provider qualification and native
cleanup readiness are still required. Comprehensive inherited IAM is unassessed
and is not an admission prerequisite. Nothing here substitutes for remaining native workload integration,
pricing, exact-request confirmation or Phase 6 acceptance.
