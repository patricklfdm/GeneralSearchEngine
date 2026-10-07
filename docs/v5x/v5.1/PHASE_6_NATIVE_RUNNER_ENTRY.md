# V5.1 manual native experiment entry

**Status:** entry accepted through PR #293, master
`dc71dc003bc1d541a065f7d65bd6840da8ec5f06`,
[CI 37434593823](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37434593823)
attempt 1 (all 36 jobs passed). The first approved native run failed during
preparation, before any workload cell. The [readiness and cleanup correction](#first-native-run-and-bounded-readiness-correction--2026-10-06)
passed PR #294, master `f526fddb4711dfbc5df0b1a21bbe432ea9721e41`,
[CI 37446172848](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37446172848)
attempt 1 (36 jobs). Its next paid run reached package preparation but failed;
the [connection-reuse correction](#second-native-run-and-preparation-connections--2026-10-06)
passed PR #295 / CI `37524630590`. Its next admitted run reached the 600-second
preparation ceiling; the [scoped timing correction](PHASE_6_PREPARATION_BUDGET.md)
passed PR #296 / CI `37540790465` attempt 2 (36 jobs). Run `37546477964`
then stopped before workload with about 1550 seconds still available; retained
request reproduction exposes the guest validators' unchanged 600-second limit.
The [guest deadline propagation correction](PHASE_6_PREPARATION_BUDGET.md#guest-deadline-propagation-correction)
passed PR #297 / CI `37552754929` attempt 1 (36 jobs). Its approved
[run 37555787624](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37555787624)
completed all three volume/package/session stages, then failed at source creation:
`native session exact configuration`. Preparation used 1027.482 of 1800 seconds;
this was not a timeout. The
[source-producer correction](PHASE_6_SOURCE_PRODUCER.md#native-source-preparation-correction)
passed PR #298 / CI `37565010319` attempt 1 (36 jobs). Run `37569971625`
successfully generated/downloaded the source, then failed before workload at the
[relative controller path boundary](PHASE_6_NATIVE_OWNED_EXPERIMENT.md#controller-path-correction-and-chain-review).
Preparation used 529.357 seconds; recovery passed in 263.530 seconds. Independent
exact-ID reads confirmed all thirteen resources absent, lease release and
USD 77 / 200 retained. The path correction needs protected CI and a fresh request.
Full Phase 6 remains open.

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

The plan retains the original 900-second admission expiry, bounded by quote expiry. Human
review, environment approval, tool installation and downloads consume this time;
none renew it. Run a new preparation if the review/dispatch cannot finish in time.
After admission, the [reviewed experiment preparation clock](PHASE_6_PREPARATION_BUDGET.md)
runs independently; approval expiry does not truncate already-admitted work.

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
python3 - <<'PY'
import json
import subprocess
from pathlib import Path
key = Path('/private/path/v51-experiment-key')
secret = key.read_text().rstrip('\r\n') + '\n'
subprocess.run(['gh', 'secret', 'set', '--env-file', '-',
                '--repo', 'patricklfdm/GeneralSearchEngine',
                '--env', 'v51-cloud-benchmark'],
               input='V51_EXPERIMENT_SSH_KEY=' + json.dumps(secret) + '\n',
               text=True, check=True)
PY
```

The quoted dotenv input preserves the private key's final newline. The installed
`gh 2.101.0` ordinary stdin secret path removed it during the first operator setup,
causing OpenSSH to reject the stored key. Do not print the key or put it in a
command-line argument. Updating the secret does not dispatch a workflow.

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
[1800-second experiment preparation](PHASE_6_PREPARATION_BUDGET.md),
5400-second lease and 1080-second operation grace.
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

## First native run and bounded readiness correction — 2026-10-06

After repairing the secret's final newline, unpaid preparation
[37438942134](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37438942134)
passed. The separately confirmed
[run 37439476170](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37439476170)
created all thirteen resources, then failed on node 3's `getGuestAttributes`
host-key GET with HTTP 404. No IAP identity command or workload cell started:
`engineWorkloadExecuted=false`, zero of four experiment cells completed. The
original HTTP error body was not retained; delayed guest-agent publication is a
plausible cause, not an established diagnosis of the provider's 404 semantics.

The correction treats only this host-key endpoint's 404 as pending after a second
owned numeric-instance-ID read confirms the same instance. The initial readiness
loop then polls reads under the original preparation deadline. An absent or
replaced VM, ownership drift, permission denial, malformed/duplicate key or late
reply still fails. Later pinned-key rechecks remain strict; this does not retry
guest commands, creation, workload cells or failed paid attempts.

Immediate owner recovery exposed a second issue: each asynchronous delete was
limited to thirty seconds, although the three actual VM deletes completed in
85.334, 56.434 and 49.613 seconds. All three VM operations eventually finished
without provider errors. Independent readback observed only node 3's 50-GiB boot
and 100-GiB data disks remaining, with no VM users. Disk deletion racing unfinished
VM detachment is consistent with the trace; the disk API error bodies were not
retained. See the [shared cleanup correction](PHASE_6_OWNER_FAILURE_CLEANUP.md#asynchronous-delete-wait-correction--2026-10-06).

The failed preparation diagnostics were retained and read back. Its USD 10
reservation remains charged in the append-only ledger, bringing the cumulative
reserved total to USD 27 of USD 200 at this observation. The lease was retained;
manual expiry reconciliation becomes eligible at **2026-10-06 03:46:31 PDT**.
These are the recorded failure/readback results, not a claim of later cleanup.
Original evidence and independent observation are retained locally under
`target/v51-first-native-experiment/run-37439476170/`.

After resource absence and lease release are verified and corrected-source CI
passes, obtain fresh same-source manual cleanup/preflight, current quote and
original build/package artifacts, then prepare and review a new exact request.
The old plan/attempt cannot be resumed. Only the operator triggers the separately
approved paid run; local tests do not establish native experiment acceptance.

Public preparation artifacts retain 14 days; experiment evidence retains 30 days
in Actions in addition to the native immutable GCS retention path. Run uploads
and summaries execute even after failure. No raw credential exception text is
included in the entry receipt. A complete experiment still reports
`fullRemoteQualification=false`; failure-drill, canonical repetitions and the
full admitted source/artifact set remain subsequent work.

## Second native run and preparation connections — 2026-10-06

PR #294 passed protected CI. Manual cleanup
[37497953377](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37497953377)
then reported PASS; independent original-operation and exact-ID reads confirmed
all thirteen prior resources absent and no active lease. The previous failed
charge remained recorded.

The next approved [run 37501739556](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37501739556),
source `f526fddb4711dfbc5df0b1a21bbe432ea9721e41`, created all thirteen resources,
passed all three pinned IAP identity probes and prepared all three data volumes.
Nodes 1 and 2 installed the exact 21-part, 21,299,202-byte package. Node 3's last
recorded package call was part index 5; this proves submission, not completion.
No workload cell started.

The failure timestamp matches the plan's 2026-10-06 17:23:31 UTC expiry. Preparation
consumed 552.011 seconds; the code uses the earlier of its original 600-second
budget and plan expiry. Serial per-part SSH/IAP handshakes and unchanged provider
rechecks consumed this budget. Deadline exhaustion is strongly supported; the
original redacted ValueError does not identify the final assertion. ZIP timestamps
have two-second precision. Immediate owner recovery took another 266.924 seconds;
the outer 819.027-second preparation interval includes that recovery, rather than
819 seconds of package preparation.

Owner recovery reported cleanup PASS, verified diagnostic retention and lease
release. Independent GET-only reads confirmed all thirteen resources absent by
name and original numeric ID, and no lease. The append-only ledger retained this
FAIL reservation, bringing the cumulative reserved amount to USD 37 of USD 200;
this is not actual billed cost. Original archive SHA-256:
`b776454bbe54f2f4ed4b8958e0dbde0c887596bb7fdff9308ee6f1874802bc87`.
Evidence is retained locally under
`target/v51-native-experiment-pr294/run-37501739556/`.

The correction reuses one private foreground OpenSSH master per exact VM during
volume/package/session/source preparation. Each existing bounded command still
gets a separate channel, its original deadline and all existing before/after
provider, lease, host-key, guest mount and content checks. A lost channel closes
the master; only the protocol's next explicit query can resolve the original
submitted operation. OpenSSH's implicit network fallback is disabled. Connection
creation and reconnection never extend the original preparation/plan deadline.

All masters, proxy processes, sockets and private token files close before owner
recovery or the first workload cell. Measurement transport and frozen workload
parameters are unchanged. Retained diagnostics include connection/command counts,
static failure codes, the current node/action/part and observed/deadline clocks;
raw provider or SSH exception output remains excluded. The summary separates
preparation time from owner recovery and reports its actual cleanup result.

Local unit and real loopback SSH qualification cover connection reuse, binary
parts, lost replies, missing sockets, altered pins, expiry and teardown. These
checks establish transport behavior, not GCP throughput or completion within the
cloud budget. PR #295 passed protected CI, but the next admitted attempt still
exhausted preparation. See the [timing amendment](PHASE_6_PREPARATION_BUDGET.md);
a fresh approved prepare/run remains required;
the consumed request cannot be rerun.

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
