# V5.1 Runner resource and workload integration

**Status:** fixed-image read accepted through PR #287 and actual Runner observation.
The [ordinary resource lifecycle](PHASE_6_EXPERIMENT_RESOURCES.md) is implemented
locally with offline HTTP/fresh-process cleanup qualification, pending protected CI.
A paid native Compute/IAP/engine entry is not yet exposed.

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

Next connect the actual Runner admission/credential boundary, IAP and owned
services. The resource stage deliberately has no network constructor or workflow
selection until that integration and its failure qualification are complete.

Implement the actual Runner path using the existing topology and owned workload,
so resource and IAP qualification can be observed during the first approved
experiment. A separate paid topology-only allocation is not a default prerequisite.
Keep a distinct failure phase and evidence for creation, IAP, guest setup, workload,
retention and cleanup so a failure does not get mislabelled as an engine result.

| Surface | Reuse | Remaining native work |
| --- | --- | --- |
| Request and control | `cloud_native_authority`, storage CAS and exact-request entry checks | Bind complete source/build/package/workload/prices, current ledger and approval to a native experiment request; reserve once before allocation |
| Compute | `cloud_gcp.Compute`, existing thirteen-resource inventory and durable create intents | Add a closed Runner policy for exact inserts/readback/operation polling; verify image-derived boot disks, ownership, numeric IDs, private interfaces and dependencies |
| SSH/IAP | Accepted guest bootstrap, source delivery and persistent owned services | Bind tunnels to the retained VM identities and original public key; verify host/guest identity and mount evidence before delivering the source-exact package |
| Workload | Accepted complete owned experiment and independent physical/history validators | Connect the three actual private guests and published controls; preserve frozen cells, parameters, time budgets and evidence limits |
| Cleanup | Existing native retained-context reconciler and manual entry | Persist reconstruction inputs before resource intents; test interruption/unknown insert results, cleanup ordering and lease release using the same implementation |
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
observation recorded above. The new resource implementation still requires its
own protected CI; offline fixtures do not establish Compute/IAP permissions.
