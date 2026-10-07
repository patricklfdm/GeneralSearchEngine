# V5.1 native owned experiment integration

**Status:** accepted through PR #292, master
`20f977e8b5fed5bc5f54f53218c27d7971c2b3d4`,
[CI 37424341468](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37424341468)
attempt 1 (36 successful jobs), together with
[immediate preparation failure cleanup](PHASE_6_OWNER_FAILURE_CLEANUP.md).
The subsequent [manual Runner entry](PHASE_6_NATIVE_RUNNER_ENTRY.md), guest
deadline correction and source preparation passed protected CI through PR #298.
The [producer correction](PHASE_6_SOURCE_PRODUCER.md#native-source-preparation-correction)
worked in admitted run `37569971625`: source generation and download succeeded.
That run then exposed the [controller path defect](#controller-path-correction-and-chain-review)
before any workload. PR #299 accepted that correction at master
`45b49095643aef6a5bb171e0f61158f3f7f22a27`, CI `37575940225` attempt 1
(all 36 jobs). The next native run reached a [preparation deadline](#preparation-round-trip-reduction)
after both published-mode bootstraps. The round-trip reduction below is a local
candidate; protected CI and a fresh approved experiment remain required. Full Phase 6 remains open.

## Fixed entry and reused workload

`cloud_runner_owned.run_native` continues fresh request/credential admission,
once-only resource creation, pinned IAP identity, native volume setup and original
package transfer into the existing complete experiment. It accepts the original
reviewed inputs, with no backend, credential, clock, SSH command or target override.
The legacy fake Runner and public offline adapters remain closed to native inputs.

The workload is the existing [complete experiment](PHASE_6_OWNED_EXPERIMENT.md):
three healthy modes (published V4.4, published V5.0 configured, candidate V5.1
automatic), followed by automatic leader-loss, maintenance and no-quorum. The
same authenticated V4.4 backup feeds all three healthy modes. Three installed
packages are reused across six distinct service groups; the fault groups retain
their existing public empty bootstrap. No measurement or mutation is resubmitted
after a lost response. Existing bounded immutable source downloads can retry reads.

Physical/history replay, shared source validation, backup/restore checks, combined
evidence budgets, 270 healthy calls and frozen per-cell ceilings are unchanged.
Native request validation is passed explicitly to the aggregate evidence readers;
replay does not infer authority from a claimed result. Independent replay receipts
remain evidence-only; the outer native owner records actual execution scope.
A complete experiment is not the full canonical qualification set:
`fullRemoteQualification` remains false.

## Guest session and deadlines

A new trusted session receiver runs from the controller's closed source bundle,
before importing any installed Python. It rechecks the original native package,
account, metadata and mounted filesystem. The admitted session binds package
hash, original preparation clock/boot identity, three exact private peer IPs,
port and the original owner lease deadline. Roots, node identities, group IDs,
mode and fault-cell names are derived from that session and cannot be supplied
as arbitrary service destinations. Bootstrap accepts transferred source objects,
not a controller-provided guest filesystem path.

An exclusive durable session claim precedes service use. A torn claim stays
UNCERTAIN; a lost begin response permits queries only. Preparation, source creation,
source transfer and bootstrap retain their original deadline. Completed service
sessions remain usable after preparation expires, only until that same original
lease deadline. Both the parent launcher and new daemon check it; reconnecting,
changing the boot ID, or starting another daemon cannot renew it.

Source creation has a separate consumed, seed-only directory derived from the
installed package. It authenticates the original exact session configuration and
uses the original preparation clock; it does not construct a persistent service
with a relocated configuration. Its one-shot published-control generator shares
the existing bounded setup process helper. Ordinary daemon roots remain exact.

Every native connection uses pinned SSH with a short-lived bound token file and
isolated gcloud configuration. Ambient credentials and API redirects are not
inherited. Provider IDs, attached disks, exact retained lease/ledger and host pins
are rechecked. Binary partial source bytes may be retained for diagnostics; raw
credential-bearing transport diagnostics are not retained.

## Completion and cleanup

The original creation API is consumed once when the completed preparation hands
off to the owner. The new owner independently reads the retained lease, charge and
cleanup context. Creation authority cannot be reused after handoff. Runtime calls
cannot create resources or mutate control state; cleanup alone permits exact-ID
resource deletion and lease-ID adoption through the existing reconciliation code.
Manual/scheduled reconciliation still enforces expiry plus grace independently.

The controller stops and collects after any cell failure. It retains the closed
startup/preparation inventory, native sessions, original history archive, evidence
result and a hash inventory under the exact attempt prefix. Each immutable upload
must be read back exactly. Collection failures keep partial history where it can
be packaged. Cleanup is attempted even if validation, service shutdown or upload
fails. An uncertain authority read stops mutations; the retained lease remains
available to independent expiry cleanup.

A terminal PASS requires all four cells, independent physical/history and backup
validation, the original time budgets, verified evidence and confirmed cleanup.
Failures remain FAIL and their charge is never refunded. Completion retention
precedes the append-only ledger event. Lease release requires verified evidence,
completion, a terminal ledger state and resource absence; unresolved uploads or
cleanup keep the lease. Partial preparation uses its separate immediate failure
continuation and cannot produce a successful workload completion.

The [native experiment timing amendment](PHASE_6_PREPARATION_BUDGET.md) sets
preparation to 1800 seconds and binds the same allocation in the approved plan
and owner controller. The USD 200 cumulative ceiling, lease 5400 seconds, operation
grace 1080 seconds, validation/retention 600 seconds and cleanup 600 seconds
are unchanged. Final completion calls use the remaining existing control
allowance. The retained completion labels its timing as `budgetBeforeCompletion`;
the local final receipt also accounts for the completion calls in `budget`.

## Qualification and next step

Native session tests exercise actual claim/package/configuration validation with
synthetic provider and operating-system boundaries. Owner-policy tests use the
real CAS, immutable retention, terminal ledger and exact-ID cleanup algorithms
against synthetic HTTP. Deterministic lifecycle tests inject workload, collection,
shutdown and upload failures; they do not count as real JVM/cloud evidence.
Shared guest regressions and the existing complete loopback-SSH experiment cover
the reused workload implementation. New unit tests join the existing storage
lanes; no CI job or paid entry is added.

Local validation and the combined PR description are retained under
`target/v51-native-owned-workload/`. The [manual entry candidate](PHASE_6_NATIVE_RUNNER_ENTRY.md) supplies explicit
workflow selection, original artifact/approval handoff, summary and operational
prechecks; its own protected CI and exact-request approval precede cloud execution. Actual Compute/IAP,
guest privilege and end-to-end timing still need that separately approved run.
Manual cleanup remains sufficient admission evidence; delayed schedule does not
block this development step. Never resume a failed preparation or reset charges.

## Controller path correction and chain review

PR #298 passed [exact-master CI 37565010319](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37565010319)
attempt 1 (36 jobs) at `58a2376c0687810ee8e294737ccf6f7c98cc6fc3`.
[Native run 37569971625](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37569971625)
completed three volume/package/session preparations and generated/downloaded the
published-V4.4 backup. The controller then failed with `guest root` while
repacking that backup for the first healthy service. Preparation used 529.357 of
1800 seconds. No workload cell ran; this was neither a preparation timeout nor a
failed source download.

The workflow supplies a relative output such as `target/v51-experiment`.
The native owner previously propagated it into `SharedSource.prepare`, which
constructed a relative `producer_config.root`. Export validates an absolute
guest root and therefore rejected it. The loopback qualification had normalized
its output on entry, and existing unit fixtures used absolute temporary paths.
Retained source bytes reproduced the defect without new cloud allocation.

The owner now makes its controller root absolute before admission and passes
absolute paths into preparation, services, evidence and retention. Shared-source
export also normalizes its own output before deriving the local producer config,
so direct callers are covered. Both use the existing directory symlink rejection;
normalization does not resolve a linked parent into an accepted path. Guest
configuration roots, package/session bindings and persistent-service admission
remain exact. A used output directory cannot start another invocation.

The review followed the native entry through completion:

| Boundary | Verification and preserved constraint |
| --- | --- |
| Prepared request → native owner | Fresh request/artifact/source checks remain before paid admission. Relative output is bound before resource preparation; linked parents and reused outputs reject before admission. |
| Resource creation → package/session | Original provider IDs, host pins, installed inventory and consumed boot-bound preparation ticket remain required. Long native preparation uses 1800 seconds; a session cannot renew it. |
| Producer → shared source | One original seed download; independent backup decode before each mode; one V4.4 and three V5.0/V5.1 exports with unchanged guest configs. |
| Export → receiver/bootstrap | Binary chunks, assembled archives, exact descriptors and six-file inventories are rechecked. All transfers precede imports and receiver-local public seals; fault groups use their separate empty bootstrap. |
| Session → experiment | Three healthy groups and three fault groups retain distinct configs. The controller consumes healthy, leader-loss, maintenance and no-quorum once, with the original per-cell deadlines and query-only recovery after ambiguous submissions. |
| Shutdown → evidence | Stop/collection order, history and physical replay, source/backup checks, aggregate budgets and terminal service evidence remain required. Failure cannot turn an incomplete workload into PASS. |
| Retention → cleanup/completion | Original immutable object read-back, exact-ID cleanup, terminal ledger charge and lease release conditions remain enforced. Both successful and failed relative-path controller cases exercise these algorithms with modeled HTTP/workload boundaries. |

Six new regressions reject the original implementation. The corrected tests cover
relative export across seven receivers, linked export/controller parents, the
native entry's path and one-use boundary, full controller completion and failed
cell retention/cleanup. Replaying the failed run's unchanged real seed passes all
three exports for both path styles; seven local binary receivers also assemble
and independently decode the same backup. The original failures, replay scripts,
unit/gate logs and hash index are under `target/v51-native-controller-paths/`;
original run evidence remains under `target/v51-native-experiment-pr298/`.
Local Python 3.11 validation passed the 18 focused path/lifecycle tests, 330 guest
chain tests, the storage gate (191 tests and 28 qualification cases) and the
admission gate (219 tests plus its qualifications). The additional controller
symlink test is covered by the focused run. All 27 packaged guest inputs also
match the authenticated PR #298 artifact byte-for-byte.

These checks cover controller logic, real retained source bytes and offline
provider/guest boundaries. They do not establish corrected-source real VM/IAP
timing or rerun the JVM experiment. Protected CI must still execute its complete
owned loopback-SSH/JVM qualification before a fresh, separately approved request.
No workload retry, guest validation relaxation, timing/budget increase, Java,
workflow or IAM change is included.

The failed run's immediate recovery passed in 263.530 seconds. Independent reads
confirmed all thirteen resource names/numeric IDs absent, lease release and
USD 77 / 200 retained. Keep that FAIL and charge. After corrected-source acceptance,
prepare/review a fresh request and obtain its exact confirmation; do not rerun the
expired preparation or reset its ledger entry as part of normal failure recovery.
The subsequent explicit operator budget restart is recorded separately below.


## Preparation round-trip reduction

Admitted run [37580265449](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37580265449)
used PR #299's exact master and the original 1800-second preparation allocation.
The V4.4 bootstrap/idle service passed; V5.0 completed all three receiver imports
and public seals, then started its first idle service. Preparation expired before
starting the second service. No formal workload cell executed (0/4). The original
controller path defect did not recur. Immediate owner recovery passed in 342.374
seconds, explaining the roughly 36-minute paid step. Exact name/ID reads confirmed
all thirteen resources absent and the active lease released.

The retained preparation journal contains 6298 GETs and 44 POSTs. All three IAP
connections stayed usable: one connection per instance, 174 commands, zero recorded
connection failures. Repeated serial provider checks amplify network cost. The
old journal has no individual HTTP durations, so their exact share of the 1800
seconds cannot be reconstructed. Local correctness qualification did not measure
this native round-trip cost.

The correction preserves the original checks and clocks while removing redundant
work:

- Direct GCP HTTP reuses at most one TLS connection per origin. Every request still
  obtains its own response and current credential header; there is no authority or
  response cache. OIDC, STS and impersonation retain their original unpooled
  exchange and exact endpoint admission. Idle connections are retired after ten seconds. Mutations use
  fresh connections, and transport failures never replay a request. Redirects,
  oversized/truncated replies and late responses reject. Configured HTTPS proxies
  retain the previous transport behavior. Preparation and owner exit close sockets.
- A combined guest identity observation reads both disks and the instance, reads
  the host key, then reads all three resources again. This uses seven GETs instead
  of nine, retaining exact numeric IDs, attachment checks and the two samples
  surrounding the host-key observation. Lease and ledger reads remain fresh and
  generation-bound, with their original metadata/media checks.
- Native mounted readiness uses its original volume endpoint's before/after
  identity checks once. The service wrapper no longer adds another identical pair.
  The remote mount/UUID/startup checks and all existing phase boundaries remain.
  Each readiness boundary therefore uses 22 provider GETs instead of 52
  (two checks of 4 control + 7 resource reads, versus four of 4 + 9).
- `preparation/provider-timings.json` records bounded operation groups, request and
  failure counts, total/max seconds and connection-open/reuse counts. It is in the
  existing retained diagnostic allowlist and contains no credentials or response
  bodies. It cannot authorize cleanup or establish workload success.

A read-only local comparison alternated the old and new transports over the same
GCS metadata and Compute zone reads. Twenty GETs took 10.504 seconds with the old
transport and 6.071 seconds with reuse (42.2% less elapsed time); median request
latency was 0.562 versus 0.233 seconds. This is a local network observation, not a
GitHub Runner timing guarantee or a completed native preparation measurement.
The raw measurements and original failed artifact remain under
`target/v51-preparation-roundtrips/` and
`target/v51-native-experiment-pr299/run-37580265449/` respectively.

Preparation remains 1800 seconds and the original lease remains 5400 seconds.
Workload parameters, per-cell ceilings, no-resubmit rules, resource/IAM scope and
measurement acceptance are unchanged. After protected acceptance, review a new
prepare/request and have the operator trigger the paid run; do not reuse the
failed request. Corrected native completion is still open.

## Bounded native session recovery

PR #300 merged the round-trip correction at
`a91101f7a88a0a592ecaf98da8e889d9b3a1ef48`; exact-master CI
[37590718799](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37590718799)
passed all 36 jobs. Native run
[37595059219](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37595059219)
installed all three packages and initialized node 1's session. Node 2's first
session exchange failed; its SSH connection was reopened, followed by 387 query
exchanges without an established session. Those queries caused 8523 provider
GETs, consuming 1091.075 seconds in provider calls alone. Preparation expired at
1800.065 seconds; all four formal cells remained unexecuted. TLS reuse was active
(10958 reused connections). This run does not establish whether the first
failure was IAP, SSH or a remote command rejection: the old wrapper discarded the
distinction, and query states were not retained.

Immediate owner recovery passed in 296.403 seconds. Independent current reads
checked all thirteen names and numeric IDs absent, no active lease, and USD 10 / 200
retained after the separately authorized accounting restart. Original evidence
and diagnosis are retained under
`target/v51-native-experiment-pr300/run-37595059219/`.

The next implementation candidate bounds recovery of the exact session claim:

| Boundary | Limit |
| --- | --- |
| Total recovery per node | 120 seconds, capped by original preparation deadline |
| One exchange, including provider identity/control guards | 30 seconds, capped by recovery deadline |
| Identical `begin` submissions | 3 total |
| Transient transport failures | 3 cumulative, including failures separated by successful queries |
| `UNCERTAIN` responses | 3 cumulative |
| All exchanges | 8 total |
| Backoff | 1, 2, then at most 4 seconds; counted within the same deadline |

A dropped connection or bounded exchange timeout first queries the original
claim. `SUCCEEDED` must match the exact session hash. Only a well-formed
`NOT_FOUND` query permits another identical `begin`; receiver `mkdir` still admits
one writer, and concurrent/torn claims remain `UNCERTAIN`. Recovery never removes
claims, changes the session, renews preparation/lease clocks or replays workload
mutations. Repeated uncertainty fails without submitting another begin.

SSH host-key/authentication failures, IAP permission denial, remote nonzero exits,
unclassified errors, changed authority and malformed replies fail immediately.
Native terminal process errors bypass existing generic connection-retry loops.
The bounded private SSH diagnostic stream is classified into fixed public codes;
raw stderr, credentials and command text are not retained. A failed master is
closed before another explicit exchange can reconnect. There is no SSH fallback
or automatic command replay below the session protocol.

Root/helper validation retains six closed terminal codes for metadata identity,
ancestor permissions, private parent, missing invoking account, changed admission
and changed installed bytes. Classification requires exit status 1 and an exact
final allowlisted `ValueError` line in a Python traceback; unrelated diagnostics
keep the generic terminal code. Root and loopback SSH qualification compare these
codes, including host-key/authentication codes, instead of raw stderr fragments.
The code is diagnostic only and does not establish authority or permit retries.

`preparation/session-recovery.json` records per-node limits, actions, times, safe
codes, query states and counters on both success and failure. It is included in
the existing failure-retention allowlist. The Actions summary shows the recovery
counts and outcome, and threshold failure enters the original owner cleanup and
FAIL accounting path immediately. It does not wait for the preparation ceiling.

Validation includes deterministic retry/deadline/terminal-error cases, actual
receiver claims, provider-guard deadline propagation, retained cleanup diagnostics,
and eight loopback OpenSSH cases. The SSH cases cover an unsent begin, a lost reply,
remote command rejection, wrong pinned host and expired channels. These are local
qualifications, not a completed native experiment. Corrected-source protected CI
and a fresh reviewed, operator-triggered run remain required. No paid run, ledger
reset, Java change, timing expansion or measurement retry is part of this change.

## Explicit operator budget restart — 2026-10-07

The repository owner separately authorized restarting the budget counter at zero.
After confirming no active experiment/lease and all prior reservations terminal,
the original USD 87 ledger was read at generation `1791355813533567`, preserved
byte-for-byte locally, and replaced with an empty native ledger using that exact
generation as the write precondition. Read-back confirmed generation
`1791356875141336`, USD 0 and no active lease. The ceiling remains USD 200.

The original ledger SHA-256 is
`c1bc490a9e9dc696fb483aca02d25b6144e496f3f5c8a17eae3c0458ce448b93`.
Its local backup and reset receipt are in
`.local/v51-ledger-backups/1791355813533567/`, outside Maven build output and
explicitly ignored by Git. A working copy also remains in
`target/v51-preparation-roundtrips/ledger-reset/`. No cloud backup was uploaded;
automatic approval review rejected that additional upload, so the operation used
a verified local backup. Retained attempt completions and evidence were not
modified or deleted. Preserve this local backup with other operator records.

This is an explicit operator accounting restart, not a refund, a successful
experiment or evidence that prior cost was zero. Ordinary failure cleanup still
retains charges; no reset CLI, workflow input or automatic refund path is added.
