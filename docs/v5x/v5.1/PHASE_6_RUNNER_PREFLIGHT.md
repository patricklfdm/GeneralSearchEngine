# V5.1 runner permission entry and activation review

**Status:** implementation candidate after PR #282. Runner enablement and native
permission qualification remain pending; this change applies no cloud settings.

## Accepted starting point

PR #282 merged at `aefaa51753c4294759981fc5feb3b2f132eae04e`.
[Exact-master CI 37095187875](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37095187875)
attempt 1 passed all 29 jobs. On that source, manual cleanup
[37105503864](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37105503864)
attempt 1 returned PASS / NO_LEASE; read-only preflight
[37105539166](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37105539166)
attempt 1 returned OBSERVATIONS_READY with all nine checks PASS.

The retained preflight artifact `11267138674` has SHA-256
`2ceba6d0ee77f28be442e3221a2e0097616150a428a6907f9ac189ad0eaf0af3`.
Its original raw observations and nested manual artifact independently replayed.
The extracted report helper also reproduces that original receipt exactly.
Evidence is under `target/v51-manual-preflight-acceptance/run-37105539166/`;
this historical replay does not renew its observation or expiry timestamps.

Manual and scheduled cleanup identities are enabled; runner is disabled. The
ledger retains USD 12 of the approved USD 200 ceiling, four terminal failed
cleanup-only attempts, no pending reservation and no retained lease. Those attempts
did not run an engine workload. Schedule timing remains optional, per the
[manual-first amendment](PHASE_6_CLOUD_PREFLIGHT.md#manual-first-native-preflight-amendment--2026-10-02).

## Optional workflow entry

`V5.1 Read-only Preflight` gains the boolean input `check_runner_permissions`,
default **false**. Its original observer job and steps remain unchanged. With
the input true, job `run` waits for `observations`, uses the existing protected
`v51-cloud-benchmark` environment, and performs runner permission diagnostics.
There is no paid prepare/run mode or resource allocation command in this workflow.

Before authentication, the job downloads the artifact named for the same run and
attempt. The entry verifies the exact current run and successful observer job,
including all five required collection/report/upload steps. It recomputes the
complete report from raw GitHub/provider, observer permissions and manual cleanup
evidence at the original timestamp, requires exact receipt equality, and checks
freshness again at the current time. A summary without its raw evidence, an older
attempt, a skipped step, a blocked/offline observation or a stale receipt cannot
emit runner identity outputs. The shared [identity and credential
binding](PHASE_6_IDENTITY_PERMISSIONS.md) still checks the source, repository IDs,
workflow, environment, account, job and attempt.

After authentication, the existing fixed permission client performs project and
bucket `testIamPermissions` queries. The final report rechecks the same run,
original prerequisites and permission receipt before producing PRECHECK_PASS.
Failures retain a BLOCKED receipt and summary; summaries show the source,
account/provider, run/attempt, original preflight digest/expiry and manual run.
Artifacts use `v51-runner-precheck-<run>-<attempt>` and 14-day retention.

Environment approval can consume the remaining 900-second evidence freshness.
If this expires, start a new complete dispatch. Rerunning only the failed runner
job cannot reuse an older attempt's observer artifact. The gate neither extends
timestamps nor retries a workload to obtain a passing result.

## Review, readback and rollback

After protected merge, generate the package against the exact merged checkout:

```bash
python3 -m scripts.v51.cloud_runner_review generate \
  --source "$(git rev-parse HEAD)" --output target/v51-runner-review
python3 -m scripts.v51.cloud_runner_review validate \
  --source "$(git rev-parse HEAD)" --output target/v51-runner-review
python3 -m scripts.v51.cloud_runner_review readback --state disabled \
  --source "$(git rev-parse HEAD)" --output target/v51-runner-disabled-readback
```

Use new output directories for each review. The generator writes the exact
workflow, runner-only enable/disable command arrays, operator guidance and a
source/configuration/file-bound manifest. It cannot execute those commands or
dispatch a workflow. Validation rejects changed payloads even if their manifest
hashes are recalculated, and generation refuses a `.github` destination.

The explicit identity readback reuses all 33 observations / 17 check groups.
Manual must remain enabled; schedule may be wholly enabled or wholly disabled.
Runner account, pool and provider must all match the selected state. Mixed
states, unavailable required reads and explicit policy/trust drift block. Missing
ancestor IAM reads remain unassessed and do not require new organization access.
The earlier cleanup deployment auditor still requires runner disabled in all its
states; this separate reviewer covers the new runner transition.

Only after separate operator approval may the three runner bits be enabled:
provider, pool, then service account, with readback after each request. Compare
fresh enabled observations with the original review; only those bits may change.
Keep all roles, grants, trust, environments, cleanup state and budget intact.
The rollback plan disables account, provider and pool, followed by disabled-state
readback. It does not delete resources or reset charges; token/revocation timing
still requires observation. The user dispatches and approves the optional job.

## Authority and remaining integration

Runner and observer share the reserved workflow path and environment claims.
**Job/input selection is a workflow guard, not IAM isolation.** Enabling runner
makes its already staged Compute and conditional storage/IAP authority available
to that protected workflow/environment. Review the whole workflow before the
separate enablement decision. No trust expansion is proposed in this batch.

PRECHECK_PASS proves only the bound diagnostic queries. Object-name conditional
access, actual resource/image/IAP access, native owned-workload integration,
provider failure paths, evidence retention, current prices and exact paid-request
approval remain separate requirements. All authority flags, including
`effectiveIamQualified`, `activationAllowed`, `paidAdmission`, `paidCloud` and
`fullRemoteQualification`, stay false. Existing manual cleanup qualification
cannot stand in for runner permissions. Full Phase 6 remains open.

## Validation

The existing `scripts/verify-v51-phase6-cloud-preflight.sh` gate includes 18 new
synthetic regressions: default/optional entry, exact job/attempt, raw report
replay, stale approval, missing/changed permissions, concurrent rerun, late final
readback, explicit enabled/disabled policy states and review-package drift.
The gate also generates and validates the review package. Shared offline
credential/HTTP qualification continues to exercise all four permission roles.
No additional CI lane, Maven build, Java runtime change or cloud execution is
introduced. Corrected-source protected CI and live runner qualification are still
required; synthetic fixtures do not establish real provider access.

Local complete gate passed: 191 unit tests, 61 source/identity/permission negatives,
eight single-disk cases, five fixture-driver cases and 24 complete-topology cases.
All 18 new tests also passed under Python 3.11. Retained logs, historical replays
and the concrete review package are indexed at
`target/v51-runner-permission-precheck/validation-summary.json`.
