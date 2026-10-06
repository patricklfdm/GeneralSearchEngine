# V5.1 Runner resource and workload integration

**Status:** fixed-image read accepted through PR #287 and actual Runner observation.
The [ordinary resource lifecycle](PHASE_6_EXPERIMENT_RESOURCES.md) is accepted
through PR #288 / CI `37383808101` attempt 2 (36 successful jobs).
The [read-only request inspection](PHASE_6_RUNNER_ADMISSION.md) is accepted through
PR #289, master `e442e734564cd0cd34b47a29f0ab27401ab9a535`,
[CI 37392515334](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37392515334)
attempt 1 (36 successful jobs). Native resource creation and fixed IAP identity
probes are accepted through PR #290, master `5cf4bf10efb2df7b084ffee7f297877c7a494dee`,
[CI 37400113526](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37400113526)
attempt 2 (36 successful jobs). The rerun does not diagnose the original failure.
[Native guest volume/package preparation](PHASE_6_NATIVE_GUEST_SETUP.md) is accepted
through PR #291 / CI `37411762406` attempt 2 (36 jobs).
[Immediate owner failure cleanup](PHASE_6_OWNER_FAILURE_CLEANUP.md) and the
[native owned experiment](PHASE_6_NATIVE_OWNED_EXPERIMENT.md) are accepted through
PR #292 / CI `37424341468` attempt 1 (36 jobs). The next candidate is the
[manual Runner entry](PHASE_6_NATIVE_RUNNER_ENTRY.md), requiring protected CI and
separate exact-request approval before actual cloud execution.

## Starting evidence

[Live storage review](PHASE_6_RUNNER_STORAGE_LIVE_REVIEW.md) records two 8/8
successful probe runs, verified original artifacts and independent state. The
second run retains a missing outside-write provider audit separately from probe
success. Reserved cost is USD 17 / 200, with no pending reservation or lease at
that observation. The temporary Storage audit addition has been restored.

The accepted [complete-topology cleanup](PHASE_6_CLEANUP_TOPOLOGY.md) proves
operator preparation and manual cleanup of thirteen exact resources. It does not
prove that the Runner identity can create those resources or open an IAP tunnel.
The accepted [owned experiment](PHASE_6_OWNED_EXPERIMENT.md) executes real JVMs
with an offline provider; it is not native cloud evidence. These are complementary
prerequisites, not interchangeable credentials or execution claims.

## Accepted Runner image-read evidence

PR #287 at `530fe8573ebf25b2ac489175f33b6abc3794da3f` passed
[exact-master CI 37341517723](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37341517723),
attempt 1, all 36 jobs. [Manual cleanup 37375168508](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37375168508)
passed NO_LEASE. [Runner 37375846878](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37375846878)
attempt 1 passed the actual project, bucket and image queries with its bound credential.
The image was `ubuntu-os-cloud/ubuntu-2404-noble-amd64-v20260918`, ID
`763874002631433611`, READY / X86_64. All nine observer checks replayed;
eleven observer files matched the Runner's copied inputs byte for byte.

The original Runner artifact `11372275680` (59579 bytes) has SHA-256
`17f5f334460422aa383bfbdbe6a28a136db13ce3b860a4e6cce2b50525279857`;
observer artifact `11371152023` (50524 bytes) has SHA-256
`d6262d5efbc5445cc4202d6eadb210b292c1b51ec0c61ed960be0a00511b9253`.
Run/attempt/source/job/step identity, original ZIP hashes and unchanged GitHub
metadata were checked. Retained originals and replay are at
`target/v51-runner-image-acceptance/run-37375846878/`.

The original checked time `1791235666` and expiry `1791236498` are historical;
review does not renew admission. The observer's ledger generation and bytes
match the previous independent storage observation: USD 17 / 200, nine terminal
attempts, zero pending, no lease. This is the observer's retained state, not a
new post-Runner cloud snapshot. Both storage transaction steps were skipped;
no allocation or engine workload was selected. The earlier audit gap remains.

## Read the frozen image as Runner

The existing optional Runner precheck adds one fixed `GET` using the same bound
Runner credential. The URL is derived from the pinned `imageProject` and
`imageName`; the result must match `imageId`, READY, X86_64 and no deprecation.
A returned self-link, if present, must identify that exact image. Only the four
validated identity/status fields enter the receipt and Actions summary; arbitrary
descriptions, encryption fields and provider error bodies are not retained.

This uses the official [images.get API](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/get).
The [images.testIamPermissions API](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/testIamPermissions)
also requires `compute.images.list`; adding that diagnostic requirement on the
external image project would exceed what this fixed read needs. No new permission
or grant is requested. Actual boot-disk creation must later establish image use;
a successful metadata read cannot substitute for it.

The query shares the existing 180-second overall deadline, thirty-second request
cap, 64 KiB response limit and one read-only 401 refresh retry. Missing/drifted
image data, HTTP denial, late response, changed endpoint and incomplete saved
observations block the precheck. It does not use an image family or choose a newer
image automatically. Observer and both cleanup identities retain their two
existing project/bucket queries. No workflow input or identity activation changes.

The same-run raw precheck replay now requires all three Runner observations and
their plan digest. Old two-query receipts cannot satisfy this source's precheck.
Use the original source when reproducing historical receipts; never rewrite an
old receipt or refresh its timestamps. All existing admission/qualification flags
remain false. The existing admission CI lane covers this change without a new job.

## Integration status: resource lifecycle, then native owned experiment

The shared creation state machine now serves the accepted cleanup-only fixture
and the ordinary experiment resource stage. The latter retains its bound input
plan before any create intent, uses ordinary DELETE termination, and leaves a
charged active lease for the next stage or the unchanged expired reconciler.
[Resource qualification](PHASE_6_EXPERIMENT_RESOURCES.md) describes exact scope
and failure evidence. Its supplied build/price digests bind inputs; they are not
an authenticated build, a current price quote or paid user approval.

The [accepted request inspection](PHASE_6_RUNNER_ADMISSION.md) now verifies
original build/package, quote, exact approval, precheck and credentials without
mutating state. The internal `cloud_runner_resources.prepare_native` constructor
now connects that inspection to the shared creation policy and fixed IAP probes.
The manual entry routes through the complete owned lifecycle. The ordinary `prepare` entry remains
offline-only; native construction requires the full original inputs and a fresh
admission, not a copied `REQUEST_BOUND` receipt.

Implement the actual Runner path using the existing topology and owned workload,
so resource and IAP qualification can be observed during the first approved
experiment. A separate paid topology-only allocation is not a default prerequisite.
Keep a distinct failure phase and evidence for creation, IAP, guest setup, workload,
retention and cleanup so a failure does not get mislabelled as an engine result.

| Surface | Reuse | Remaining native work |
| --- | --- | --- |
| Request and control | `cloud_native_authority`, storage CAS and accepted Runner request inspection | Accepted native constructor rechecks original inputs before lease CAS; explicit manual dispatch candidate awaits protected acceptance |
| Compute | Shared thirteen-resource creation policy, input/context/intent/ID records | Local native constructor and interruption qualification; actual image use/creation remains to be observed in the approved experiment |
| SSH/IAP | Accepted fixed identity probe, retained VM IDs, pinned host key and Runner credential | Accepted native volume/package/session integration; actual IAP remains to be observed |
| Workload | Accepted complete owned experiment and independent physical/history validators | Accepted native complete-experiment bridge; actual private guests and pinned controls still need an approved run |
| Cleanup | Existing native retained-context reconciler and manual entry | Accepted immediate owner-failure cleanup/retention; unresolved cases retain the lease and unchanged expiry replay |
| Review | Original GitHub artifacts, independent state and provider observations | Retain stage outcomes and audit coverage without claiming missing events were observed; price retention/failure overhang and preserve all failed reservations |

The native path must remain a distinct authority domain. Changing an offline
`execution` string or marking the existing fake adapter qualified is insufficient.
Mutations remain once-only; an uncertain response triggers reconciliation against
the retained original operation, not a fresh allocation or budget refund. Native
cleanup must also work when the Runner exits before a guest/workload starts.

Use the frozen workload's ordinary VM termination behavior for actual experiments;
the earlier cleanup-only STOP profile is not an engine profile. Keep no external
IP or attached VM service account. IAP's actual scoped connection and the existing
forbidden-action checks must be validated without exposing an arbitrary remote
command, URL or target. Workload success requires its independent evidence gate.

Before enabling that native entry, qualify it offline through its real request,
credential and HTTP boundaries, including lost insert responses, changed resource
IDs, denied image/IAP access, retained cleanup and budget/time exhaustion. Then
obtain corrected-source protected CI and review a concrete priced request. User
confirmation, dispatch and environment approval remain separate execution steps.
The USD 200 ceiling does not authorize spending the remaining USD 183 automatically.

## Native resource and IAP candidate

The native entry owns its actual GitHub, source checkout, clock, credential-file,
OIDC/STS/Runner impersonation and HTTP boundaries. Before acquiring any lease it
checks the request's private key against the approved public key, replays the
accepted inspection, and scans the thirteen resource names and original operation
IDs for collisions. Immediately before the first CAS it repeats original archive
verification, checkout binding, current master/CI/run identity, raw precheck,
approval/price expiry and generation-pinned control reads. A changed input or
active lease stops the entry before mutations; CAS still protects the final race.

The shared driver reserves once, persists cleanup context and the bound resource
plan before create intents, then retains each original numeric result before the
next insert. The native policy allows only that state machine's exact bodies,
generation conditions and deterministic request IDs. A failed or lost mutation
reply is never replayed, including HTTP 401. The read policy adds only the three
planned VMs' `hostkeys/` guest-attribute queries after resource creation completes.
VM shape remains private `n2-standard-8`, no attached service account, ordinary
5400-second DELETE termination and separately owned boot/data disks.

Resource creation and IAP share the [native experiment preparation allocation](PHASE_6_PREPARATION_BUDGET.md)
of 1800 seconds from original entry with guest/service setup. Original plan/preflight
expiry gates the first lease mutation. Reinspection retains its original
180-second budget. Credential refresh, guest readiness and reconnects
cannot create a new budget. The existing 5400-second lease and 1080-second grace
are unchanged. The retained resource plan is the shared unqualified input recipe;
the native stage receipt/marker identifies the actual execution domain separately.

For each guest the IAP probe rechecks the retained lease/reservation, both disk
attachments and exact numeric identities before and after connection. The guest
agent's Ed25519 key is read through Compute with numeric-ID checks on both sides,
then pinned to `gse-v51-<instanceId>` in a private known-hosts file. A valid response
with no published Ed25519 key may be polled under the original deadline. The
[first-run correction](PHASE_6_NATIVE_RUNNER_ENTRY.md#first-native-run-and-bounded-readiness-correction--2026-10-06)
also permits a host-key GET 404 to remain pending only after the same owned numeric
instance ID is read back; malformed/duplicate keys, permission denial and changed
IDs still fail immediately. Native SSH uses
the existing strict host-key/no-agent/no-forwarding options. Its only remote
command is a bounded read of the metadata instance ID, which must equal the
retained ID. It does not initialize volumes or execute packaged code.

The official CLI routes `start-iap-tunnel` by **instance name**, not a documented
numeric-ID selector. Generation binding comes from the pinned host key and
provider/guest numeric-ID checks; the receipt does not claim the CLI itself used
an ID. The accepted Runner exchange supplies a short-lived token in a temporary
0600 file, outside evidence, with an empty isolated gcloud configuration. The
child receives an allowlisted environment and an explicit `--access-token-file`;
ambient credentials, impersonation and endpoint overrides are excluded. This
matters because `CLOUDSDK_AUTH_ACCESS_TOKEN` otherwise takes precedence even over
that flag. See [gcloud authentication priority](https://docs.cloud.google.com/sdk/docs/authenticate)
and [IAP SSH connection](https://docs.cloud.google.com/compute/docs/connect/ssh-using-iap).
Tokens are never put in arguments/receipts; files are removed on return/failure,
and raw gcloud diagnostics are not retained by this entry. An interrupted identity
probe is not resubmitted by the driver. IAP access remains unobserved in real GCP.

`RESOURCES_AND_IAP_READY` is **PARTIAL**, leaves the active lease and PENDING
reservation, and keeps engine/full-qualification flags false. Failure retains
phase/type (and HTTP status where available), safe request traces and the local
lease observation, with separate confirmed-ID and unresolved-intent counts.
A lost first insert reports unknown creation (`resourcesCreated: null`), not an
assertion that nothing was created. Probe submission records identify the node
and original deadline even when no success reply arrives. Only retained CAS bytes
authorize cleanup. No
successful ledger completion or refund is synthesized. Active/grace manual
cleanup still returns WAITING; eligible expiry cleanup removes only original IDs
and retains the failed reservation. The separate
[owner-failure candidate](PHASE_6_OWNER_FAILURE_CLEANUP.md) now adds immediate
in-process cleanup and durable failure evidence. The same PR adds the separate
[native complete experiment bridge](PHASE_6_NATIVE_OWNED_EXPERIMENT.md), with shared
physical/history validation and retention, accepted through PR #292. The manual
workflow entry has its own protected review and exact-request execution approval.

The explicit offline twin drives the same entry with synthetic CI archives,
credential issuer, provider and IAP boundary. Its ten-case qualification covers
the complete stage, lost first/VM/final insert replies, lost final ID/ledger/context
replies, IAP denial, wrong guest ID and late probe. Every failure must match its
expected phase/class before it counts as a negative. Each retained state goes to
a fresh manual-cleanup process, preserving the synthetic USD 5 charge; the complete
case also proves active WAITING. The shared forty-one-case resource matrix retains
its additional unresolved-operation, replacement and cleanup-denial coverage.

Two new unit modules enter Python storage and the existing focused storage lane;
the new matrix has a 600-second process cap. There is no new CI job, Maven build,
workflow permission, IAM change or live allocation. Evidence is retained under
`target/v51-native-resource-entry/` and the focused gate's `runner-resource-entry/`.

## Operator sequence

1. Merge the reviewed implementation and sync master. Same-source successful full
   CI and recent manual cleanup remain required; no wait for schedule.
2. The image read is accepted above. No additional read-only or storage run is
   required just to review the resource implementation.
3. Continue native integration above; do not repeat the storage write experiment
   merely because this source adds a read diagnostic. The earlier storage results
   remain historical evidence and cannot refresh a later request's control state.
4. After the native path is implemented and accepted, review fresh source/control,
   prices, retention, exact resource/guest identities and request digest. Only an
   explicitly approved request may proceed to a user-triggered paid experiment.

Phase 6 stays open through native failure qualification, experiment/failure-drill
and three valid canonical repetitions on one admitted source/artifact/workload
set. This plan does not advance any of those acceptance markers.

## Local validation

The complete admission lane passed 151 unit tests, 13 source/provider negatives,
16 identity negatives and 32 permission negatives. Offline HTTP qualification
observed two queries for observer/manual/schedule and three for Runner, with the
bound credential exchange for each. Both generated review packages validated.
All 21 storage-entry regressions and 35 CI classifier/Python partition tests passed;
the complete 24-test permission suite also passed under Python 3.11.

Six new regressions cover frozen-image scope/identity, sanitized responses,
malformed/deprecated/drifted images, unavailable HTTP results, endpoint drift,
401 refresh, original deadlines and saved-observation replay. Original
project/bucket query plans match the accepted source for all four roles. The
eleven changed/new documents passed local-link/fence checks and the documentation
contract passed. Evidence and source hashes are retained at
`target/v51-runner-image-precheck/`; admission evidence is
`target/v51-cloud-preflight/run.uHXYjh/`. No new cloud run or IAM operation was
performed. Those image-read checks subsequently passed protected CI and the actual Runner
observation recorded above. The ordinary resource implementation subsequently
passed PR #288 protected CI; its offline fixtures do not establish Compute/IAP
permissions. Request inspection subsequently passed PR #289 protected CI. The
native resource/IAP candidate described above subsequently passed PR #290 protected CI.

For that candidate, Python 3.11 passed the complete focused storage gate, including
both existing storage matrices and the ten new resource/IAP cases, at
`target/v51-cloud-preflight/run.svu1OK/`. The final native unit suites passed
25 tests, including unknown-create diagnostics and probe submission records;
106 shared resource/admission/guest/CI-partition regressions also passed. The
95-document contract, 721 changed-document local links, Python/shell syntax and
whitespace checks passed. The retained index is
`target/v51-native-resource-entry/validation-summary.json`. These remain local
offline tests. Protected CI is recorded above; actual Compute/IAP observations
are still required at their cloud acceptance stage.
