# V5.2 Phase 6AY native cleanup reconciliation

This stage connects the existing exact-ID deletion and generation-conditional
control algorithm to a concrete native cleanup entry. It follows the
[provider preflight](PHASE_6_PROVIDER_PREFLIGHT.md) and
[request-scoped wire policy](PHASE_6_REQUEST_WIRE_POLICY.md). Local tests replace only
external GitHub, source/credential-file and provider I/O. They do not demonstrate
GCP compatibility, deployed identities, effective IAM or hosted acceptance.

## Entry and authority

`python3 -m scripts.v52.cloud_native_cleanup --source <exact-master-sha>
--output <new-directory> --role manual` is the operator recovery entry once its
fixed tracked configuration and protected identity/workflow are deployed.
`--role schedule` uses the same reconciliation with its separate identity;
schedule remains optional. The entry has no force, request-file, transport,
token, clock or stored-PASS argument. It creates its own Native NetworkReader,
NetworkCredentials and fixed provider transport. Private constructor tickets
separate trusted code paths; they are not a security sandbox against Python code
execution. Offline adapters, subclasses/lookalikes and native records passed to
an OfflineOwner remain rejected.

Cleanup requires exact current master source, its dedicated workflow/run/attempt,
fresh diagnostic permission/bucket observations and named control reads. It does
not require Java, a build artifact, full CI, current image availability or a new
spending approval: those dependencies must not prevent recovery of expired
resources. Native Runner creation, reservation, renewal and workload PASS remain
closed. The existing context helper still defaults to the offline domain; only
the native data path explicitly selects native, and concrete adapters separately
validate their execution domain. No source configuration, identity, workflow, IAM deployment or provider
operation was applied by this development stage.

## Original resources, current cleanup invocation

The first read brackets the original lease/ledger generations around preflight.
Before mutation, the same generations are checked again. Original provider context
is read only from the request-SHA-bound key, with metadata, generation-pinned media
and repeated metadata/lease observations. Its complete request and configuration
must match their retained hashes. Project and control bucket must match the
current dedicated identity's configuration; the old source, image, zone and disk
layout stay original. A current image or zone change cannot redirect cleanup.
Missing or inconsistent original context fails before mutations; no ambient
configuration or resource-name reconstruction is substituted.

| Observed state | Result |
| --- | --- |
| No lease and no pending reservation | PASS observation, zero writes/deletes; no delete-path qualification |
| No lease but a pending reservation | FAIL with retained diagnostic; do not erase or reset the ledger |
| Original ACQUIRING/ACTIVE lease before expiry plus grace | WAITING; no context lookup, control write or resource delete |
| Expired lease after original grace, or already CLEANING | Same fenced reconciliation used by offline control |
| Unresolved original operation, changed resource ID, failed deletion or retention | FAIL; retain the lease and original evidence for later reconciliation |

The native path calls the existing shared cleanup algorithm. It resolves original
insert operations, checks the exact observed numeric resource ID and ownership,
deletes instances before disks and firewalls, then checks final name absence.
It never creates resources or deletes by name. The scoped wire gate rechecks
ownership after any credential refresh, including the lease generation and phase
before a cleanup CAS. A concurrent renewal/replacement blocks that original write.

A DONE insertion error with a target ID also resolves the original operation.
It never proves that creation succeeded: reconciliation still checks ownership,
the exact target ID and final absence. This permits current cleanup code to finish
an older CLEANING lease stranded by such a response, using the retained original
source/configuration and operation. The original FAIL completion and finished
ledger charge remain unchanged; only successful cleanup releases the lease. A
cleanup PASS cannot promote that failed experiment to qualified evidence.

Every provider/control mutation is sent once. Lost CAS replies may only observe
the original value; an uncertain DELETE is not automatically repeated. A later
manual reconciliation checks the original operation and current exact-ID absence.
Unknown submission history remains unresolved. One bounded 401 refresh is allowed
for GET; 401 on a mutation is not retried. Existing finite exchange/decoder limits
remain; no overall cleanup stage deadline or new cost cap is introduced.

## Retention and result meaning

The entry writes fresh local observations, original context, a redacted exchange
journal, reconciliation and final receipt. Exchange records contain generated
method/route and status, never authorization headers or provider error bodies.
The final receipt binds current source, exact credential run/attempt, original
request SHA, before/after control generations, submitted writes/deletes and final
status. Source/invocation drift after cleanup preserves reconciliation evidence
but prevents a final successful receipt.

`deletionPathExercised` requires successful reconciliation with at least one
actual resource DELETE submission. An empty-bucket PASS or WAITING is not a
real-delete qualification. `paidCloud: true` identifies native provider execution;
it does not admit a workload or assert a billed amount. `paidAdmission`,
`effectiveIamQualified` and `fullRemoteQualification` remain false.

Cleanup records and terminal ledger events precede release. A missing workload
completion is recorded FAIL with no workload evidence. Existing completion bytes
and original costs are retained, including failed attempts; cleanup does not
promote an interrupted workload to PASS or reset the budget. Immutable old failure
records remain available after a subsequent successful cleanup.

## Local validation and remaining work

Final local validation: all 857 V5.2 Python tests passed in 404.260 seconds,
including 30 native-entry tests; 100 existing CI/V5.1 control/HTTP tests passed in
61.064 seconds under Python 3.11. The unchanged old HTTP pool tests require that
interpreter. Documentation contract, 199 local links, syntax and whitespace checks
passed. Raw logs, original failures and tested-source index are retained locally
at `target/v52-native-cleanup/validation-summary.json`.

The new native-entry suite covers the real factory and credential exchange path
with mocked external I/O: all thirteen resource intents, exact numeric deletes,
manual/schedule, activity/grace/CLEANING, old-source/zone/image cleanup, orphan
reservations, changed generations, source/invocation/permission failures,
credential-refresh fencing, uncertain writes/deletes, unresolved submission,
same-name replacement, input/capability rejection and redaction. Existing offline
control/provider/wire/preflight regressions remain in the gate. No real token,
provider call, Java measurement, paid experiment or workflow dispatch was run.

Next independently verify recent native cleanup workflow evidence before Runner
admission. Join actual CI/build provenance, package inspection, fresh provider
observations, original ledger generation and exact prepared approval in one owned
Runner factory. Its context-retention/acquisition ordering must cover crashes
before original context exists: the cleanup entry deliberately will not fabricate
missing context, even for an unattempted lease. Then complete immutable member
retention, strict IAP/guest identity, all whole members and five-member aggregation,
and protected operator workflows before asking the user to push/merge/dispatch.
