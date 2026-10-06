# V5.1 manual native experiment entry

**Status:** implementation candidate on accepted PR #292, master
`20f977e8b5fed5bc5f54f53218c27d7971c2b3d4`,
[CI 37424341468](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37424341468)
attempt 1 (all 36 jobs passed). That accepts the
[native owned lifecycle](PHASE_6_NATIVE_OWNED_EXPERIMENT.md) and
[preparation failure cleanup](PHASE_6_OWNER_FAILURE_CLEANUP.md), not an actual
GCP workload. This entry still requires its own protected CI and separately
confirmed, operator-triggered execution. Full Phase 6 remains open.

## Workflow selections

The existing `v51-replication-evidence.yml` is named **V5.1 Preflight and Experiment
Runner**. It preserves the observer job and exact master workflow/environment
identity. No WIF, IAM, role, cleanup workflow or cumulative budget change is made.
The runner job ID remains `run`; its name becomes **Runner precheck and approved
execution**. The default dispatch is still observer-only.

| Selection | Additional inputs | Result and cloud mutations |
| --- | --- | --- |
| `runner_experiment=off` | Optional `check_runner_permissions=true` | Existing diagnostic precheck; no allocation |
| Storage request | Existing storage request and confirmation, explicit permission precheck | Existing separate storage qualification and charge; cannot mix with experiment |
| `runner_experiment=prepare` | Explicit permission precheck, quote JSON, configured SSH secret | Original CI artifacts and a public review plan; no resource or ledger writes |
| `runner_experiment=run` | Explicit permission precheck, preparation run ID, exact plan SHA-256, matching SSH secret | Fresh native admission and complete four-cell owned experiment |

The quote JSON has exactly `prices`, `maximumCostMicrousd` and `sequence` fields.
`prices` follows the existing [quote contract](PHASE_6_RUNNER_ADMISSION.md#quote-approval-and-control-binding).
The reservation is explicitly supplied in integer micro-USD; no default charge
or stale built-in price is supplied. `sequence` is 32 lowercase hexadecimal
characters. Preparation generates a new attempt identity and public SSH access
descriptor. The USD 200 cumulative ceiling does not authorize the remaining
balance; each exact plan still requires confirmation.

Every experiment selection requires run attempt 1. A failed-job rerun cannot
resume allocation or reuse a partly executed plan. Diagnose the original result,
reconcile resources if necessary, then make a new preparation and dispatch.

## Public preparation and original artifact handoff

Preparation replays the current dispatch's original observer and Runner precheck,
including recent manual cleanup, then checks current exact-source protected CI.
It downloads and authenticates the original verification build and owned-experiment
package with the existing source/toolchain, producing-job, ZIP and payload checks.
The checkout computes its own binding using pinned Temurin `21.0.12+8-LTS`.

The successful public artifact is `v51-experiment-prepared-<run-id>-1`. Its closed
inventory contains only the plan, unconfirmed approval template, preparation
receipt, original build/package ZIPs, their metadata and original build-job record.
Each file is hashed. SSH private keys, credentials and arbitrary local paths are
not inventory members. A failed preparation cannot publish a successful prepared
artifact. Preparation does not reserve money or hold a lease.

The plan retains the original 900-second expiry, bounded by quote expiry. Human
review, environment approval, tool installation and downloads consume this time;
none renew it. Run a new preparation if the review/dispatch cannot finish in time.

Execution accepts one explicitly selected successful preparation run on the same
master source and first attempt. It checks repository/workflow identity, both
producing jobs, preparation/upload steps and timestamps, unique artifact ID,
size, SHA-256, expiry and complete bounded ZIP inventory. Source metadata and the
producing job are rechecked after download. It rejects links, traversal, extra
files, changed approval templates and rehashed or replaced plans. The entered
plan digest confirms that exact previously unconfirmed template.

This is a handoff, not reusable cloud authority. The native constructor still
replays the new dispatch's precheck, original artifacts, current source/CI and
exact approval, exchanges its own bound credentials, and rereads live lease and
ledger immediately before the original once-only creation path. Failed costs are
never removed. Concurrent dispatches cannot bypass the retained lease CAS.

## SSH secret and operator sequence

After this source passes protected CI, configure an unencrypted Ed25519 key with
an empty comment in environment `v51-cloud-benchmark`, secret
`V51_EXPERIMENT_SSH_KEY`. Secret configuration is an operator step, not an action
performed by this code change. For example, from a private local directory:

```bash
ssh-keygen -q -t ed25519 -N '' -C '' -f /private/path/v51-experiment-key
gh secret set V51_EXPERIMENT_SSH_KEY \
  --env v51-cloud-benchmark < /private/path/v51-experiment-key
```

Use the same key for preparation and its corresponding run. Do not upload it as
an artifact, include it in quote JSON, or rotate it during execution. The CLI
removes the raw secret from its subprocess environment, creates a mode-0600
temporary file under `RUNNER_TEMP` outside all evidence roots, checks its public
key against the plan, and removes the temporary copy on exit. The public key is
installed only in this attempt's guest metadata. Remove or rotate the environment
secret after the attempt is closed and resource absence has been verified.

1. Synchronize the protected master; confirm that exact-source full CI passed.
2. Confirm the required enabled identity/permission state and prepare current
   reviewed prices. Complete fresh manual cleanup on this source. Schedule is
   optional and does not block this sequence.
3. Manually dispatch the workflow with `check_runner_permissions=true`,
   `runner_experiment=prepare`, and the quote JSON. Leave storage/run inputs empty.
4. Review the public plan/artifact and summary: source, CI and package identity,
   sequence/attempt, topology, estimate, maximum reservation, prior charges and
   expiry. Preparation remains unpaid.
5. With exact-request approval, manually dispatch a **new run** with
   `check_runner_permissions=true`, `runner_experiment=run`, `runner_prepared_run`
   and `runner_experiment_confirmation`. Leave quote and storage inputs empty.
   Approve the existing environment gates before the original plan expires.
6. Inspect the result, independently review retained evidence, ledger and resource
   absence, and retain failures. Do not infer success from a green preparation,
   cleanup alone, a missing execution receipt or a successful job rerun.

No workflow dispatch, secret update, IAM mutation or paid run is performed as part
of local implementation/validation. Merge enables the explicit workflow route;
it does not trigger it. A secret alone cannot approve spending.

## Results and time limits

The native run uses the accepted healthy three-mode/shared-source comparison,
leader-loss, maintenance and no-quorum cells, with independent physical/history
and backup/restore validation. It retains the 270 healthy calls, fixed parameters,
600-second preparation, 5400-second lease and 1080-second operation grace.
Validation/retention, cleanup and control allowances remain unchanged.

The outer command has a 6000-second cap plus 60-second forced-termination grace;
the selected run job allows 120 minutes for tools, prechecks and uploads. These
are process/job limits, not extensions of any admitted request, workload or lease.
SIGTERM requests normal interruption/cleanup when Python can handle it; SIGKILL
or runner loss still requires retained-lease reconciliation. Preparation and
diagnostic jobs have a 15-minute job limit.

The summary reports plan/request identities, topology, cost and time limits,
per-cell execution, independent validation, time accounting, retention, cleanup
and lease release. Missing results are explicitly not established. A failure
before/after entering native execution is distinguished; an unexpected native
exception cannot be reported as proven unpaid. Preparation-failure cleanup is
reported from its own retained owner-recovery receipt.

Public preparation artifacts retain 14 days; experiment evidence retains 30 days
in Actions in addition to the native immutable GCS retention path. Run uploads
and summaries execute even after failure. No raw credential exception text is
included in the entry receipt. A complete experiment still reports
`fullRemoteQualification=false`; failure-drill, canonical repetitions and the
full admitted source/artifact set remain subsequent work.

## Validation boundary

New Python tests exercise real bounded ZIP handoff, original artifact verification,
actual temporary Ed25519 key handling, first-attempt and selection guards,
expiry/identity/digest rejection, workflow ordering and public summaries. Entry
wiring tests fix GitHub/provider boundaries and mock the native lifecycle; they
do not spend money or claim actual GCP/IAP execution. Existing native-owner and
storage/cleanup suites retain their separate scope.

Both new modules join the existing admission Python partition and focused
cloud-preflight admission gate. There is no new CI job or additional Maven build.
Local results and the PR review are retained at `target/v51-native-runner-workflow/`.
After this PR's protected acceptance, secret setup and the first exact-request
cloud experiment require separate operator action and authorization.
