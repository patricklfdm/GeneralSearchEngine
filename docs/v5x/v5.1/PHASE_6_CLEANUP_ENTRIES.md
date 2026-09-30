# V5.1 Phase 6C3C26 — bound cleanup entries and inactive workflow proposals

**Status:** implementation candidate on PR #257 master
`133b05e5cc02560877a74902911b21efacf2ba4c`. Its
[CI 36664035569](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36664035569)
passed on attempt 2. This accepts the preceding
[native authority and HTTP policy](PHASE_6_NATIVE_CLEANUP.md), not this candidate
or live cleanup. Attempt 1's automatic-healthy warmup retained nine successful
calls; GET 9 took 1.134 seconds, so arrival 10 encountered `LANE_BUSY`. A successful
rerun does not establish the latency's cause. Corrected-source protected CI is
required for this batch.

## Entry binding

[cloud_cleanup_entry.py](../../../scripts/v51/cloud_cleanup_entry.py) binds each
entry to the existing [disabled identity proposal](PHASE_6_CLOUD_IDENTITIES.md):

| Entry | Event / exact workflow | Environment / dedicated identity |
| --- | --- | --- |
| Scheduled | `schedule` / `v51-expired-cleanup.yml` | `v51-cloud-cleanup` / `gse-v51-cleanup` |
| Manual | `workflow_dispatch` / `v51-manual-cleanup.yml` | `v51-cloud-manual-cleanup` / `gse-v51-manual-cleanup` |

The checks require the fixed repository name and numeric repository/owner IDs,
`refs/heads/master`, exact workflow reference, `cleanup` job, selected environment,
positive bounded run ID/attempt, and identical checkout, source and workflow SHA.
The service account and WIF provider come from the selected configuration and
identity proposal. Caller environment variables cannot override those identities,
the bucket or the retained request. There is no force, age or resource override.

The identity CLI reads the current run, its explicit attempt and then the current
run again. All three must describe the same in-progress attempt, source, workflow,
event and repository, including the head repository. This detects mismatched or
intervening reruns. Only comparison fields are retained; neither the complete
GitHub environment nor tokens are dumped. The checks follow GitHub's
[workflow variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)
and [run-attempt API](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt).

These are context checks, **not OIDC authentication or effective-IAM evidence**.
`identityAuthenticated`, `activationAllowed`, `cleanupReady`, `paidCloud` and
`fullRemoteQualification` remain false. The live adapter is rejected before
credentials, provider traffic or output creation. No new credential is acquired.

## One reconciliation implementation

Both entries call the accepted native policy and shared retained reconstruction.
Expiry plus operation grace, ownership, original insert operations, numeric IDs,
generation conditions, immutable completion, append-only terminal accounting and
absence checks remain there. Active or grace-period leases return `WAITING`.

The cleanup program's source is distinct from the abandoned request's source.
A newer cleanup entry may recover an older-source request through its own retained
lease/context/ledger and original operations. Cleanup does not require current
green CI, current master tip equality, paid admission or the original runner's
workspace. Changed provider configuration still blocks reconstruction. No failed
charge is reset, and cleanup cannot produce successful workload evidence.

## Inactive workflow proposals

Generate reviewable files locally:

```bash
python3 -m scripts.v51.cloud_cleanup_workflows --output target/v51-cleanup-workflow-proposal
```

The generator writes two YAML files, their hashes/identity mapping and `REVIEW.md`.
It refuses a destination under `.github`, including symlink resolution. Nothing
is installed in `.github/workflows`, so merging this batch does not start a schedule.
There are no cloud mutations, configuration grants or workflow dispatches.

The proposed entries use separate events/environments, pinned checkout/Python and
artifact actions, exact-source checkout, one shared concurrency group without
canceling an active job, a 15-minute job bound, and always-retained diagnostics.
The summary displays source, run/attempt, entry, environment, selected identities,
configuration hash and result. Manual environment approval remains an identity
configuration responsibility. Workflow concurrency is advisory; the durable
generation/ownership checks remain authority.

Both proposals stop at `activation-check` with exit 2 and a retained `BLOCKED`
receipt. They contain no auth action, `id-token` permission or live reconciliation
command. Removing the stop alone cannot enable cleanup. These files must not be
advertised as an operational watchdog or recent cleanup readiness.

## Qualification

The existing provider gate includes the entry tests and fresh-process matrix:

```bash
scripts/verify-v51-phase6-cloud-provider.sh
```

Each of the fourteen retained cleanup cases runs through **both** entries (28
fresh processes). The validator compares their Compute operations and independently
checks unchanged active/blocked state, exact numeric deletion, preserved failed
charges, absence and lease release. Outputs bind the source and implementation
hashes and remain explicitly offline. The matrix covers no lease, active/grace,
expired lease, empty reservation, absent/changed context or reservation, lost
insert acknowledgement, pending/missing operation, reused name and deletion denial.

Unit negatives additionally cover missing/drifted context, branch/source/run/attempt
mismatch, forks, cross-entry/runner/observer/V5.0 identities, live transport,
configuration drift, fake records, closed activation and unsafe proposal paths.
The existing HTTP policy tests retain lost-delete and lease-generation race coverage.
No Java build, timing threshold, workload retry, CI job or paid-cloud parameter changes.

## Next integration

Review/apply the already generated disabled identities under separate operator
authorization, and qualify effective IAM and the workflow/credential transition.
Wire and qualify native transport plus actual provider reconciliation before
deploying/enabling these entries. Then retain a fresh exact-source manual **or**
scheduled cleanup observation for paid admission. Source/workload/retention/price
qualification and exact-request user confirmation still precede user-triggered
paid experiments. Full Phase 6C remains open.
