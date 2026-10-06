# Ordinary experiment resource lifecycle

**Status:** accepted through PR #288, master `d1f7b798897b83c51be6d3de53912860005b9f6d`,
[exact-master CI 37383808101](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37383808101)
attempt 2, all 36 jobs successful. The rerun does not establish a cause for the
original failure.
Native Runner allocation, IAP and engine execution remain closed. This stage
continues the [accepted image-read and resource plan](PHASE_6_RUNNER_RESOURCE_ENTRY.md).

## Shared creation, distinct experiment profile

`cloud_resource_creation.CreationPolicy` extracts the closed HTTP state machine
from the accepted cleanup-only topology preparer. Both callers now share lease
acquisition, one ledger reservation, conditional writes, create intents, exact
original operation polling, numeric identity readback and VM dependency checks.
The existing topology entry, confirmation and STOP profile stay intact.

`cloud_experiment_resources` adds the ordinary thirteen-resource stage: four
firewalls, six disks (three 50 GiB boot and three 100 GiB data), and three
`n2-standard-8` voters. The native request binds source, package archive, frozen
workload, configuration and guest public-key identity. An immutable input plan
also binds selected build/package-manifest/price digests and the observed ledger
generation/bytes. **These supplied digests are bindings, not authenticated build
evidence, current price observations or a paid approval.** The future actual
Runner entry must independently validate those inputs before using this stage.

The ordinary VM uses DELETE after its frozen 5400-second lifetime, has no external
IP or attached service account, and preserves its separately owned disks for
reconciliation. It does not inherit the cleanup-only fixture's STOP override.
The ordinary native cleanup-context format is sufficient; no new cleanup schema
or deletion algorithm is introduced.

## Durable order and interruption behavior

1. Read back the absent lease, exact observed ledger and absent attempt objects;
   reject existing resource names or original operations before any write.
2. Acquire the lease with generation zero and reserve the attempt once against
   the observed ledger generation. The cumulative USD 200 ceiling and prior
   failed reservations remain enforced.
3. Retain immutable cleanup context and resource input plan before a create intent.
4. For each resource, persist its intent, re-read lease/ledger/context/plan, submit
   its exact insert once, and persist the returned numeric identity. Before each
   VM, inspect the exact owned firewall and disk dependencies again.
5. Retain `resources-prepared.json`. Return `RESOURCES_PREPARED` with an active
   lease and pending reservation for the following workload stage.

Every POST consumes its one authorization before sending, including HTTP 401,
lost replies and readback failures. Base HTTP calls still invoke the closed
endpoint/body/generation policy. Read-only 401 refresh stays bounded by the
original deadline. One 600-second preparation clock covers all resources; retries
cannot renew it. A late insert result fails the stage but leaves its original
intent for reconciliation.

An interrupted stage uses the existing retained-context cleanup after lease
expiry plus 1080-second operation grace. A new process receives only retained
provider bytes, never the old Runner object or private SSH key. It resolves the
original insert operations, deletes exact numeric IDs in dependency order, and
retains a failed completion without refunding the reservation. Active/grace
checks return WAITING without mutations. A lease interrupted before the ledger
write has no allocation and no charge to refund; later charges remain recorded.

If an intent has no observable original operation, an operation is still pending,
an identity is replaced, context is missing or deletion is denied, cleanup stays
FAIL with the lease retained. A missing operation does not prove absence. The
implementation does not erase such cases or turn their interruption into a
successful experiment.

## Offline evidence and CI

The qualification covers **41 cases**, including lost insert responses at all
13 positions, lost durable identity responses at all 13 positions, lost
lease/ledger/context/plan uploads, active/grace boundaries, timed VM absence,
asynchronous deletes, unresolved intents/operations, image drift, replaced VM
identity, missing context, denied deletion, preparation deadline and lost final
completion reply. Every case checks exact insertion counts/unique original
request IDs, retained cost/history, numeric delete targets and the expected
remaining lease. Expected refusal is a passing negative case, not successful
resource cleanup. Forty-four cleanup replays use fresh interpreters, including
active/grace checks and the optional schedule equivalence check; completion-loss
also runs the interrupted first cleanup in-process.

Focused tests cover request/domain/input drift, cumulative budget and stale
control, no network exposure, duplicate preparation, immutable plan drift,
once-only authorization, 401 behavior, CAS conflicts, image denial and replaced
disk dependencies. The existing topology and native cleanup regressions continue
to cover their original behavior.

The existing `cloud-cleanup-fixture-tests` lane runs the additional focused suite
and qualification, retains every original state/replay/HTTP receipt (including
expected failures), and keeps its original artifact and Required semantics.
The Python unit module belongs to storage. No new CI job or reactor build is
introduced. The offline matrix has a 600-second process cap; this does not extend
any simulated resource, workload or lease budget.

Local receipts are retained under `target/v51-native-resource-lifecycle/` and
the final cleanup gate's `target/v51-cloud-preflight/run.*/experiment-resources`.
An outer qualification PASS always keeps `paidCloud`, `paidAdmission`,
`nativeResourcesQualified`, `engineWorkloadExecuted` and
`fullRemoteQualification` false. Native request bytes inside these explicit
fixtures express the authority domain, not a real cloud execution.

## Local validation result

The complete cleanup gate passed 59 unit tests and all four qualification
receipts: 8 single-disk, 5 operator-driver, 24 topology trigger/case records and
41 new resource cases. The new matrix completed 44 fresh-interpreter replays in
approximately 127 seconds. Python 3.11 passed the 13 new regressions plus
six partition tests; 29 CI classifier tests also passed. A baseline/current
comparison produced identical 255 topology HTTP requests, provider state and
preparation receipt. The documentation/link/syntax/whitespace checks passed.

Final gate evidence is at `target/v51-cloud-preflight/run.Rf0eb6/`; source hashes
and receipt index are at `target/v51-native-resource-lifecycle/validation-summary.json`.
These are working-tree validations, not corrected-source protected CI or native
cloud acceptance. No Maven reactor or cloud experiment was run for this batch.

## Remaining work

The [accepted Runner request inspection](PHASE_6_RUNNER_ADMISSION.md) now binds
original build/package/prices, fresh preflight, exact approval and renewable
credentials in a read-only entry (PR #289 / CI `37392515334`, attempt 1, 36 jobs).
The [native resource/IAP candidate](PHASE_6_RUNNER_RESOURCE_ENTRY.md#native-resource-and-iap-candidate)
connects fresh admission to this shared driver and fixed guest identity probes;
PR #290 / CI `37400113526` attempt 2 accepted it (36 jobs). The local
[native guest setup](PHASE_6_NATIVE_GUEST_SETUP.md) now connects volumes and exact
package delivery, pending its own protected CI. Next connect the complete owned
experiment, independent evidence gates and immediate cleanup/retention.
This ordinary preparer remains offline-only;
the internal native entry has no installed CLI/workflow caller. A successful
resource stage keeps its active lease rather than marking a whole experiment PASS.

Resource and IAP observations should come from the first separately approved
experiment; an extra paid topology-only run is not a prerequisite by default.
The accepted image-read run needs no rerun for this implementation. The actual
ledger remains historically observed at USD 17 / 200; the qualification's USD 5
reservation and USD 1 prior failure are synthetic fixtures. Manual cleanup
remains primary, schedule optional, and all paid dispatch/approval stays with
the user. Phase 6 remains open through native failure qualification, experiment,
failure-drill and three valid canonical repetitions on one admitted source set.
