# V5.2 protected operator workflow

Phase 6BJ adds the source-controlled **V5.2 Replication Runner** workflow and
prepare/run/verify-set operations. This is local implementation, not deployment
or paid acceptance. [Phase 6BK](PHASE_6_CLOUD_SETUP.md) adds the fixed provider
configuration and dedicated identity/environment setup review. Deployment and
protected cloud acceptance remain pending.

## Preconditions and operation boundaries

The workflow accepts only manual dispatch on `master`. Its one `runner` job uses
the `v52-cloud-benchmark` environment and the dedicated `gse-v52-runner` identity.
Before authentication, the bootstrap validates the clean source, actual workflow
bytes, repository/owner, job/environment and original in-progress run/attempt.
Inputs pass through environment variables and strict JSON parsing; input text is
never interpolated into a shell command. There is no force mode or rerun fallback.

The operator accepts ordinary relative output directories such as the workflow's
`target/v52-runner`. It anchors that directory to the current working directory
before any operation and passes absolute paths through admission, guest identity,
storage, Java installation, retention and sealing. The direct execution entry
does the same. Parent traversal (`..`) and symbolic links in any path component
reject before admission; conversion does not resolve links or overwrite an
existing run directory.

Before any native operation, the exact source must include reviewed
`docs/v5x/v5.2/cloud-provider.json`; its absence rejects at identity bootstrap.
The setup review must cover the dedicated WIF/IAM identities, environment and
secret, private networking/image, conditional object permissions and evidence
retention. The successful exact-master build and recent successful manual cleanup
are independently checked for preparation and again at original Runner admission.
The [temporary V5.2 CI policy](PHASE_6_CI_PROVENANCE.md) suspends the requirement
for the remaining full-CI jobs to finish/pass. The original build and artifact
remain mandatory, and summaries expose `fullCiRequired: false`.
After a merge that skipped normal CI, manually run
`gh workflow run v52-cloud-build.yml --ref master` and wait for the build job to
succeed before cleanup and preparation. This separate build executes Java tests
and uploads the original bundle; it does not start an experiment. The latest
manual build for this SHA takes precedence over regular CI, including failed or
pending attempts. Only sources without a manual build use the latest regular CI
producer. Reuse that build across the sequence; a new build/attempt after
preparation requires fresh preparation.
Scheduled cleanup is optional and cannot substitute for missing original data.

| Operation | Input JSON | Effect | Public artifact |
| --- | --- | --- | --- |
| `prepare` | `member`, `sequence`, dated `estimate` | Original CI/build, package, controls, cleanup and provider/control observations; no resource/ledger/lease mutation | `v52-prepared-<run>-<attempt>` |
| `run` | `preparedRun`, `preparedAttempt`, `confirmation` | Execute that exact approved whole member once, retain evidence, close resources, then seal | `v52-runner-<run>-<attempt>` |
| `verify-set` | All five member names mapped to `requestSha256`, `runId`, `runAttempt` | Independently restore originals, authenticate their invocations and replay complete histories | `v52-cloud-set-<run>-<attempt>` |

The five members are `experiment`, `failure-drill`, `canonical-1`, `canonical-2`
and `canonical-3`. Any can be first. All five must share the same source,
configuration, sequence, build and controls. Original failures and their charged
reservations remain in the ledger; a member already passed in that sequence is
not executed again. A source/build change requires a new sequence even when all
previous attempts in the old sequence failed: the ledger binds sequence identity
at its first reservation. A new sequence does not reset prior reserved costs.
A rerun is never used as a substitute for a selected original.

Time and accumulated cost budgets remain soft warnings. Each operation prints
progress at least every minute, including during prepared-artifact download.
The workflow routes all three operations to the dedicated D-backed Linux
self-hosted Runner (`gse-v52-cloud-d-wsl`) with a 1,380-minute job ceiling. That
administrative ceiling is not a new per-stage timeout. Request/parser/storage bounds, approval expiry,
credential freshness and lease/grace checks remain hard. Cancellation/interruption
still requires the original lease's safe cleanup path; active leases are not
force-deleted.

Before native resource admission, the Runner checks Python and local SDK startup
using IAP's isolated environment. This does not authenticate or call a cloud API.
Failures expose `V52_RUNNER_SDK_RUNTIME_REJECTED` and a closed `sdkCode` through
the operator failure artifact, before lease/ledger/resource writes. Successful
checks retain `run/native/sdk-runtime.json`. A corrected source requires fresh
build provenance and preparation; an earlier plan cannot be rebound to it.
See [native admission](PHASE_6_NATIVE_RUNNER.md) for the environment and diagnostic
contract. Experiment time and cost budgets remain soft.

## Prepare an explicit estimate

The draft helper reads the committed provider configuration locally and renders
the required hashes. It does **not** query live prices or derive a charge estimate.
The operator supplies an estimate including three VMs, both disk types, controls,
evidence, cleanup and failed attempts, with its priced coverage duration.
`$V52_ESTIMATE_MICROUSD` and `$V52_COVERAGE_SECONDS` must be set from that review.

After the readiness review and merge, from the exact clean master checkout:

```bash
V52_SEQUENCE=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
python3 -m scripts.v52.cloud_operator prepare-request \
  --source "$(git rev-parse HEAD)" \
  --member canonical-3 --sequence "$V52_SEQUENCE" \
  --cost-microusd "$V52_ESTIMATE_MICROUSD" \
  --coverage-seconds "$V52_COVERAGE_SECONDS" \
  --output target/v52-request-1
```

Use a new output directory for each draft, keeping earlier requests intact.
The default estimate validity is four hours; `--valid-seconds` may be explicitly
set up to one day. Actual preparation creates a plan valid for at most one hour,
bounded by estimate expiry. The same sequence is used for the remaining members;
each preparation generates a fresh attempt/access identity.

The `V52_EXPERIMENT_SSH_KEY` environment secret must contain one valid, unencrypted
Ed25519 OpenSSH private key. Preparation derives its public key; run checks the
same key against the authenticated original plan. An optional OpenSSH key comment
is removed only from local `ssh-keygen -y` output in both paths; descriptors and
host pins still require the exact comment-free Ed25519 wire key.

When a secret lacks its final line feed (for example after `gh secret set` reads
it from standard input), the operator appends one LF before writing the private
temporary file. It does not trim or rewrite the key body, repair truncated keys
or convert CRLF input. Both the supplied and written key remain bounded to 4096
bytes. This applies to preparation and run; no secret replacement is necessary.

Key loading or matching failures report `prepare-key` / `run-key` before entering
preparation or paid execution. A fixed `causeCode` distinguishes invalid secret
input (`V52_SSH_SECRET_INVALID`), unsafe/missing files (`V52_SSH_FILE_INVALID`),
reader startup/timeout (`V52_SSH_KEYGEN_UNAVAILABLE` / `V52_SSH_KEYGEN_TIMEOUT`),
unreadable or encrypted keys (`V52_SSH_KEY_UNREADABLE`), invalid Ed25519 output
(`V52_SSH_PUBLIC_KEY_INVALID`) and a different key (`V52_SSH_KEY_MISMATCH`).
Neither exception text nor subprocess diagnostics/key bytes enter the report.
Rotation between preparation and run
rejects before acquiring resources. The secret is removed from the Python process
environment before child commands run, written only into a private temporary
directory and removed on scope exit. It is never an artifact input or report field.

## Dispatch preparation and approve its exact plan

The following commands are operator actions after the merge/readiness boundary;
they are not run by local development or tests:

```bash
python3 - <<'PY' | gh workflow run v52-replication-evidence.yml --ref master --json
import json
from pathlib import Path
print(json.dumps({"operation": "prepare", "request": Path("target/v52-request-1/request.json").read_text()}))
PY
```

Inspect the completed summary's source, member, sequence, request/plan hashes,
expiry, new estimated cost and previous reserved cost. Preparation is
`PREPARED_NOT_ADMITTED`, and its approval template remains `confirmed=false`.
The summary supplies the exact `run` JSON. Selecting operation `run` with that
plan hash is the operator's explicit approval of the displayed request/costs.

The run operation downloads only the selected original preparation run/attempt.
It validates the successful original job and ordered steps, exact workflow Git
blob, repository/source, artifact digest/upload interval and bounded ZIP inventory.
The ZIP must contain exactly `plan.json`, `approval.json`, `preparation.json` and
`inputs.tar.gz`. Missing, changed, expired, foreign or rerun inputs reject before
native acquisition. Original CI/build, package bytes, provider/ledger state,
cleanup and approval are independently rechecked by the native factory.

There is no automatic execution after `prepare`, and no automatic business retry
after a failed `run`. Preserve the original diagnostic and cost record, inspect
the failure and reconcile the expired lease before preparing a new attempt.

## Verify the five original members

Retain each successful run summary's member name, request digest and original
run/attempt. The selected map contains all five names, for example these keys
(replace each value with its original recorded values):

```text
experiment       -> {requestSha256, runId, runAttempt}
failure-drill    -> {requestSha256, runId, runAttempt}
canonical-1      -> {requestSha256, runId, runAttempt}
canonical-2      -> {requestSha256, runId, runAttempt}
canonical-3      -> {requestSha256, runId, runAttempt}
```

Choose `verify-set` with that JSON map. It uses the
[original Runner/set join](PHASE_6_PROTECTED_RUNNER.md), not uploaded success
summaries as proof. Only complete original object/provenance/physical/history
replay can produce a qualified set PASS. The selected reservations and the full
ledger's cumulative reservations are shown separately; they are not a billing
invoice. Each whole history, including M01 offered windows, remains indivisible.

## Artifact and diagnostic boundaries

Successful operation artifacts are retained for 90 days. The workflow uploads
only `target/v52-runner/result`, whose closed contents depend on the operation.
Original workload archives remain in the immutable provider retention path.
Prepared inputs, member seals and final set receipts have different names and
inventories; they are not interchangeable.

An always-run diagnostic upload retains only `target/v52-runner/diagnostics`:
safe status, phase/code, source, declared counts/costs and public identifiers.
It cannot match a successful member artifact. The workflow does not upload the
private work tree, raw SSH/provider diagnostics, credentials or keys. The job
summary prefers a failure record over any earlier report and escapes table text.
Failures after resource acquisition remain subject to the original Session's
cleanup; an upload or summary success cannot make the entire job successful.

Preparation failures under `original-build` additionally project
`buildProvenance`: the precise collection subphase, last owned check's module and
line, and (for read failures) closed reason, HTTP status, request kind/ordinal,
attempt count and stopping reason. This includes the second independent build
replay. Unknown fields and raw error text are excluded. The existing diagnostic
artifact carries these fields without uploading the private work tree. See the
[bounded original GitHub reads](PHASE_6_CI_PROVENANCE.md#bounded-reads-and-retained-diagnostics)
for the three-attempt transient GET policy; authentication, source, attempt and
artifact validation failures remain terminal. Time and cost budgets remain soft.

Member failures additionally report a fixed `V52_MEMBER_<PHASE>_REJECTED` code
and `memberPhase`: guest identity, storage, Java installation, placement, history,
correlation, completion or guest closure. A subsequent guest-close failure does
not replace the original failing phase. These fields contain no exception text.
When available, the failure summary also projects the original resource cleanup's
status, lease-release flag and delete count. Missing or malformed cleanup evidence
cannot become a PASS; a recorded cleanup exception takes precedence over an
earlier cleanup receipt. This summary remains diagnostic, not cloud acceptance.

Run `39830398260/1` on source `81f47688c69c212534a8e73d09e8fba90ad4c098`
failed before executing the first `failure-drill` history, during node 3's
`m02-below-0` placement-volume check. The final IAP admission ended after 30.001
seconds during `identity-after`, reported `ValueError` from the native HTTP exchange and
stopped with `IAP_IDENTITY_OR_AUTHORITY_REJECTED`. Node 2 had already recovered
from a typed read deadline using the second admission attempt. Cleanup confirmed
all 13 resources absent, no leftovers and the lease released.

A local transport reproduction shows that a successful HTTP response arriving
just past its deadline raised plain `ValueError`, which bypassed both read and
IAP timeout handling. The retained incident did not include the innermost error
message, so that exact HTTP subcase remains an inference. The shared transport
now distinguishes actual expiry from validation/HTTP rejection across its lock,
socket, pooled/unpooled response and API paths. Local regression coverage includes
the actual HTTP-to-read-retry-to-IAP route with one process and unchanged original
bytes; it does not establish corrected-source cloud qualification.

IAP capacity applies to **four active connections per node**, including channels
still cleaning up their process and private credentials. Completed channels free
their slots; there is no lifetime connection-count limit. Every newly accepted
connection still checks the original authority and opens at most one SDK tunnel.
Before that tunnel starts, a typed timeout or plain connection interruption may
receive one admission retry: at most two 90-second attempts, one one-second
backoff and a shared 240-second connection ceiling. This reserves 59 seconds after
two full attempts and backoff for SDK startup and the SSH banner. A provider `V52_READ_DEADLINE`
may use that second attempt only when the current admission attempt's own deadline
has elapsed, before SDK spawn. Exhausted read counts, earlier nested deadlines and
other read scopes remain terminal. Every retry repeats the original checks using a
fresh private credential directory. Explicit denials, identity/ownership drift and malformed or
unknown errors remain terminal. These are connection bounds, not experiment time
or cost budgets.
Cold native SSH control calls reserve the explicit 240-second connection allowance
plus their existing 30-second command allowance (270 seconds total). Warm channels
and ordinary local qualification retain their original allowance. Delivery probes,
lifecycle/collection calls, voter stream opening and partition controls share this
calculation. Native guest probes, history-parent creation/query and standalone
Python/Java verification allow 240 seconds for connection plus 60 seconds of work.
All retries of an installation verification share its first absolute deadline.
Native Python/Java installation reserves 240 seconds for connection plus the
existing 300 seconds for upload, durable writes and original-result recovery
(540 seconds total); it is submitted once. Direct identity observations allow
90 seconds, still clamped by an existing startup or operation grant where present.
Explicit caller deadlines, lease/identity checks and consumed-command semantics
are never extended. Mount initialization and each mount check retain their
original 300-second, lease-bounded grant across their clock and result exchanges;
no individual reconnect can restart that grant.

The forwarder never retries a business request or replays bytes. Terminal errors
stop all routes; the outer guest scope joins their threads before deleting the
private credential directory.

Run [39769150976/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39769150976)
on source `20c104abd29268895fd042007bb38ad5eb4de193` completed two of thirteen
failure-drill histories. The third, `m02-below-5000`, failed in preparation with
`SSH master original deadline`. Node 2's last connection recorded zero sent and
received bytes and no SDK PID: its provider identity-after check exhausted the
30-second admission attempt (`V52_READ_DEADLINE`), while the caller also allowed
only 30 seconds for the entire cold SSH exchange. That typed read error was not
recognized by the admission retry predicate. Cleanup passed, deleted thirteen
resources and released the lease. The retained evidence identifies these control
path failures; it does not identify the underlying cause of provider read latency.

Regressions reproduce the old 30-second caller failure with a 35-second simulated
connection and the typed-read retry omission. Real loopback SSH qualification
models only provider admission and the SDK byte pipe: the first admission uses
its actual 30-second deadline, the second authorizes one pipe, and cold/warm
probes reuse one authenticated SSH master. It is not a cloud PASS or a replay of
failed workload measurements. Local review artifacts are retained under
`target/v52-iap-startup-budgets/`; corrected-source cloud qualification is pending.

Run [39857308589/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39857308589)
on source `29b2b575a8289a8200a24ba928838e3e255ac556` failed before node 1's Java
installation, with zero of thirteen failure-drill histories started. Both
pre-SDK attempts reached `identity-after` and returned `V52_READ_DEADLINE` after
30.001 and 28.997 seconds. The second attempt ran: the prior error-classification
fix worked, but the old 60-second shared connection budget left the second attempt
less than 30 seconds and no reliable startup headroom. Successful channels in
this run already averaged roughly 23 seconds for admission. Cleanup reports PASS,
thirteen delete submissions and a released lease.

The operator's Windows disk monitor also recorded intermittent WSL management
call timeouts, followed by recovery. The shown 22:04 UTC warnings occurred after
the 22:03:07 UTC execution failure; monitor staleness warns during an active run
and did not abort it. A subsequent host snapshot showed nearly full swap, but
neither observation establishes the historical latency's cause. This correction
does not restart WSL, alter shared resource settings or stop other development.

Fake-clock regressions cover two admissions plus delayed SDK startup, a slow guest
probe, cold/warm control limits, and delayed Python/Java uploads with one
original-result grant. Real local transport and storage endpoint tests exercise
cleanup and terminal rejections with modeled external I/O. Review material is
under `target/v52-iap-cold-start-headroom/`. Corrected-source cloud execution is
still pending; these tests do not establish a cloud PASS or eliminate host stalls.

The private `gse-v52-iap-connections-v2` diagnostic retains only the latest 64
completed records per node, plus at most four active records. Cumulative counters
and the last safe failure code survive record eviction. The public failure
summary projects only fixed node names, accepted/completed/failed/active counts,
peak concurrency, capacity rejections, completed-channel byte totals, dropped
record counts and allowlisted failure codes. It excludes command text, stderr,
credentials, paths, PIDs and individual records; missing or malformed diagnostics
are omitted and cannot mask the original failure. These observations do not
qualify a workload or change cleanup, lease, source or history boundaries.

The same summary also retains cumulative admission milliseconds/retry counts and
the latest failed/retried admission (at most two records per node). Each record
contains an allowlisted phase, elapsed/phase milliseconds, reason/type and source
module/line. Phases distinguish owner/API lock waiting, identity checks before and
after credentials, credential refresh and local credential-file preparation.
Historical receipts without these optional fields remain readable. This allows
a deadline to be distinguished from a permission failure without publishing
private provider or SDK text.

Run `39503311609` on source `30b17fe46c5791a5e04c0d32b445fe928a491b04`
finished seven histories and failed preparing `m02-above-1000`, before its
original workload, after about 3h30m total job time. Its retained diagnostic
reported node-1 `IAP_IDENTITY_OR_AUTHORITY_REJECTED`, cleanup PASS, 13 delete
submissions and a released lease. That old code also covered untyped deadline
errors, so it does not establish an IAM denial or the precise original cause.
This was not the hosted six-hour ceiling. The seven completed histories averaged
1368.5 seconds, including 764.1 seconds of placement and about 303 seconds of
preparation; these measured costs motivate admission timing diagnostics, not
removal of authority checks. Corrected-source cloud qualification remains pending.

Storage preparation now emits fixed node/operation milestones alongside the
minute heartbeat. Its failure summary projects a bounded
`gse-v52-storage-diagnostic-v1` record: node, operation, exchange action/stage,
closed reason code, known source module/line and initialized/Python-installed/
Java-installed nodes. It never exports exception messages, stack locals, raw
receipts, commands, stderr or credentials. Malformed diagnostics are omitted;
diagnostic write failure cannot replace the original exception or skip cleanup.
The existing always-uploaded diagnostics artifact carries this projection,
including failures during Java installation or subsequent history placement.

Control-read failures distinguish `V52_CONTROL_READ_GENERATION` (the pinned
generation is no longer the policy's observation), `V52_CONTROL_READ_TRUNCATED`,
`V52_CONTROL_LEASE_ABSENT` and `V52_CONTROL_LEASE_INACTIVE` (changed owner, inactive
phase or expired lease). Their exception type is `ControlReadError`, a validation
error. Known provider, wire-policy and controller modules are included in source
locations; the shared assertion helper is skipped to retain the meaningful
caller. Unknown codes and private exception text still cannot enter the public
projection. Provider HTTP errors remain errors, not evidence of an absent lease.

Run `39406318322` (attempt 1, source `567d0d6`) completed four of thirteen
failure-drill histories and failed in `m02-equal-1000` placement before that
history's workload. Its diagnostic identifies node-2's volume-clock postcheck,
with cleanup PASS, a released lease and no IAP failures or capacity rejections.
The reported `cloud_identity` line combined the control read and absence check;
deeper provider/policy locations and the actual exception text were omitted.
It therefore does not establish that the lease was absent.

A deterministic local two-thread regression reproduces renewal between metadata
and body as a generation rejection with the same original diagnostic location,
while preserving the ACTIVE lease and allocation. The corrected
[control read](PHASE_6_NATIVE_STORAGE.md#control-reads-during-lease-renewal)
excludes that local interleaving and retains distinct diagnostic causes for any
later failure. This proves the implementation race, not the unique cause of the
hosted failure. Original evidence and charged reservations remain retained.
Corrected-source protected CI and new approved cloud execution are still needed;
the prior successful experiment belongs to its original source and is not
automatically joined to a changed-source cohort.

Run `39375349697` failed in storage preparation before any history. Its retained
cleanup reports PASS and a released lease; IAP counters report no failed
connections or capacity rejection. Detailed storage exchanges were not uploaded,
so the exact failed assertion is unavailable. Connection/byte counts suggest
node-2 installation or subsequent checks, but do not establish that location or
a timeout root cause. Local regressions separately expose the shared 30-second
Python connect/upload allowance, renewed query deadlines, misclassified upload
timeouts and acceptance of buffered late Python replies. The corrected installer
uses the original operation grant described in
[native storage](PHASE_6_NATIVE_STORAGE.md). This does not retrospectively prove
the hosted cause; corrected-source CI and a new approved experiment are required.

Run `39351687369` completed four experiment histories and failed during the
fifth history's placement. Source analysis gives a no-retry lower bound of 57
connections per node after four histories; the next placement needs eight more.
The old forwarder retained completed channels and silently refused connection 65.
That defect was reproduced with real local sockets and child processes. The
hosted artifact did not retain its connection counters, so attribution of that
specific hosted failure remains an inference. Regression coverage now exercises
70 sequential connections, active-capacity rejection and reuse, delayed credential
cleanup, bounded diagnostic eviction and simultaneous terminal shutdown. Original
failed cloud evidence and reservations remain unchanged; this correction still
requires protected CI on the new source and a new approved experiment.

Run `39334536942` exposed a relative/absolute path mismatch at guest identity,
before its first history. The unchanged path boundary was reproduced locally;
its original retained cleanup reports 13 absent resources and no leftovers.
Regression coverage now uses the workflow's relative directory through the
operator and execution into the original IAP constructor, and checks relative
prepare/verify-set entry points and direct execution through retention/sealing.
External admission and guest effects in these tests are modeled. Corrected-source
protected CI and a new explicitly approved cloud run remain required.

## Validation scope

The control-plane disconnect in run `39640228986/1` is addressed by
[bounded read retries](PHASE_6_READ_RETRIES.md). Retry progress identifies the
scope, attempt, closed failure reason and terminal stop without exposing tokens
or response bodies. This does not replay a failed measurement or change soft
stage/cost budgets.

Local evidence is recorded under `target/v52-operator-entry`. Tests use actual
workflow bytes, strict ZIP/JSON decoding and original native preparation code
with external GitHub/GCP/control downloads modeled. Real local `ssh-keygen`
checks cover secret permissions, public-key equality, environment removal and
temporary-file cleanup. No workflow was dispatched, no actual cloud credential
was obtained, no resource was created and no measurement was rerun.

The final 17 preparation/operator/workflow cases pass, including rotated-key
rejection before native acquisition. The original-artifact/provenance group
passes 19 cases and the CI/provenance contract group passes 78 cases. These
groups overlap with earlier local runs. Exhaustive CI discovery contains 1,139
cases across the unchanged eight partitions; this batch did not rerun every
case or the long physical/runtime matrix.

The [setup review and pre-cloud checklist](PHASE_6_CLOUD_SETUP.md) now supply
the remaining local configuration and deployment materials. Real deployment,
full protected CI on final master and paid dispatch remain operator actions.


## D-backed self-hosted operator Runner

The manual `prepare`, `run` and `verify-set` operations use
`[self-hosted, Linux, X64, gse-v52-cloud-d-wsl]`. The original workflow path,
job name, protected environment, exact-master/exact-attempt binding, OIDC
identity, required step ordering, public artifact inventories and 90-day
retention are unchanged. Ordinary CI and manual cleanup remain GitHub-hosted;
cleanup remains available when the operator machine is offline. No experiment
is dispatched by installation or registration.

The dedicated Ubuntu 24.04 WSL2 distro is `GSE-Runner`, backed by
`D:\GSE-Runner\Ubuntu\ext4.vhdx`. Run the Linux Runner as the unprivileged
`gse-runner` account. Keep its work, tool cache, temporary data and retained
results on the native ext4 filesystem. Direct `/mnt/d` workspaces do not satisfy
the existing private-directory and immutable-file contracts. Windows drive
automount and Windows executable interoperability are disabled in this distro.
Manage this dedicated distro from Windows PowerShell. WSL distributions share
kernel components, so this setup is not a VM security boundary.
The existing development distro is separate and is not moved.

Bootstrap dependencies with
[`v52-bootstrap.sh`](../../../scripts/self-hosted/v52-bootstrap.sh), **only as root
inside the dedicated distro**. Install the reviewed
[`cloud_self_hosted.py`](../../../scripts/v52/cloud_self_hosted.py) as
`/opt/gse-runner/cloud_self_hosted.py`, owned by root and readable by the Runner.
Register the official hash-verified Runner package using a short-lived GitHub
registration token; never put that token in a command transcript, repository,
archive or report. The installed root-owned hooks check the exact manual master
workflow before checkout. Runner labels are routing, not a sandbox for untrusted
pull requests; this persistent host is reserved for trusted operator work.

The Windows launcher
[`v52-start.ps1`](../../../scripts/self-hosted/v52-start.ps1) starts the service,
keeps a WSL process alive and requests system wakefulness while its window is
open. It reports actual D-drive free space every minute and warns below 20 GiB.
The operation reports Linux free space every minute and warns below 30 GiB.
The launcher also publishes a root-owned D-drive observation into the distro,
so Actions logs show physical host free space separately from virtual Linux
capacity. A fresh observation (at most 180 seconds old) is required before a new
job starts; a later stale monitor or low-space observation only warns.
These warnings do not interrupt the current experiment. WSL's virtual filesystem
capacity does not establish available Windows host storage. Do not sleep,
restart Windows or terminate the distro during an active job. The 23-hour job
ceiling leaves room below the normal job token's 24-hour lifetime; stage/time/cost
budgets remain soft and cannot override a platform/job-token limit.

Install `v52-start.ps1` as `D:\GSE-Runner\Start-GSE-Runner.ps1`. From Windows
PowerShell, start it with a process-scoped execution policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\GSE-Runner\Start-GSE-Runner.ps1
```

Append `-CheckOnly` for one publication check without starting the service or
requesting wakefulness. Do not use that option as a long-running monitor.
Each publication call has a 20-second timeout and at most three attempts with
two-second retry delays. An exhausted periodic cycle warns and the next cycle
tries again; it does not exit the monitor, release wakefulness, stop the Runner
or replay the experiment. Initial publication is still required before this
launcher starts the service. Management stdout/stderr are drained concurrently;
errors include exit/timeout codes and bounded stderr. Small per-launch logs are
retained under `D:\GSE-Runner\monitor-logs`. A log-write failure only warns.

Only child WSL management calls clear `WSLENV` and use a local Windows working
directory, preventing inherited VS Code paths from being translated into the
isolated distro. The parent environment and distro interop/automount settings
are unchanged. Linux stamps disk observations when received, so its freshness
check does not compare Windows and Linux wall clocks. This does not change the
clock used for measurement or relax the 180-second freshness requirement.
Native Windows regression checks (no WSL/service/cloud mutations) are available:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\self-hosted\test-v52-start.ps1
```

Original prepare/member artifact provenance allows **five seconds** on either
side of its exact original upload step because Runner and artifact-service
timestamps come from separate clocks at whole-second API precision. Creation
must still precede update; neither may be in the future. Source, repository,
run, attempt, required steps, expiry, inventory and SHA-256 remain exact. The
tolerance does not apply to workload execution windows, approvals or leases.
Prepare `39544678816/1` exposed this boundary: upload ended at `04:37:26Z` but
the original artifact was recorded at `04:37:27Z` on 2026-10-21. Offline replay
of its unchanged ZIP passes this correlation and the original package checks;
it is not a new admission or paid execution. New source still requires fresh
preparation after protected master CI and recent cleanup.

After all steps and action credential cleanup, the installed completion hook
atomically moves `target/v52-runner` to
`/home/gse-runner/evidence-archives/<run>-<attempt>/evidence` on the same D-backed
filesystem. This preserves failed and successful private working evidence
without a second full copy. It does not upload the private tree or grant PASS.
The next start refuses to let checkout erase any unpreserved prior result.
These local archives are retained without automatic deletion or compression;
monitor cumulative occupancy and archive reviewed old runs separately. The
existing development-repository archive cron does not cover this new distro.

Deployment checks (Linux permissions, private staging, local hook lifecycle,
GitHub connectivity and Runner registration) are separate from a hosted job or
paid-cloud qualification. First protected execution after merge still needs
the successful exact-source build, recent cleanup, fresh preparation and operator approval.


### Native storage read rejection diagnostics

A failed mount check now includes its exact closed receiver code when available,
and `storage.readCheck` shows up to three attempts with phase, elapsed and remaining
milliseconds. `V52_VOLUME_CLOCK_EXPIRED` and `V52_VOLUME_EXCHANGE_DEADLINE` can retry
only read operations within one 300-second check window. Identity/mount drift and
unknown `REMOTE_EXIT` remain terminal. Initialization and measured histories are
never resubmitted by this mechanism. See the
[native storage timing and diagnostic contract](PHASE_6_NATIVE_STORAGE.md#slow-read-checks-and-closed-receiver-diagnostics).
