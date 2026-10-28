# V5.2 Phase 6AR provider HTTP contract

This stage connects the [V5.2 lease owner](PHASE_6_CLOUD_AUTHORITY.md) to a dedicated
Compute/Storage wire adapter and a concrete in-process HTTP fixture. It qualifies
request construction, response validation and reconciliation. It does **not**
contact GCP, discover credentials, install guests, execute engine histories or
admit paid execution. V5.1 configuration, namespaces and workflows are unchanged.

## Configuration and recoverable ownership

`cloud_provider.py` accepts a closed V5.2 configuration: project, evidence bucket,
network/subnetwork, region/zone, pinned image project/name/numeric ID, machine and
disk types, and replication port. The exact digest must match the original request.
These are expected values, not fresh provider observations or a reviewed live
configuration. The offline test project, image and machine values are fixtures.

The owner retains a public provider context before the first resource intent is
submitted. An independent reconciler reconstructs the original configuration and
request from that immutable context. It cannot substitute current defaults or a
replacement source. No credentials, SSH private key or provider error body is
included. A missing or altered context rejects reconstruction.

Only `OfflineApi` with the exact `cloud_provider_offline.Server` implementation is
accepted. Native request records, generic APIs, subclasses and objects merely
advertising `offline=True` do not enable this entry. This is an accidental-use
boundary in trusted Python code, not protection from arbitrary code execution.
There is no network-enabled factory, CLI or workflow at this stage.

## Conditional storage and original submissions

Storage reads validate bucket, object name, numeric generation, content type and
bounded size, then read that exact generation with a matching precondition. Strict
JSON rejects duplicate fields, non-finite constants and non-object control data.
A changed/deleted generation between metadata and media requests is a failure.
Only the V5.2 control namespace is accepted; escaped or traversing keys reject.

Writes use `ifGenerationMatch`, including zero for create-only objects. The shared
controller validates exact read-back. A lost write response can only observe the
original value; it cannot resubmit. Deletes carry the original generation and
observe the result without deleting a newer owner. These precondition semantics
follow the [Storage request-preconditions contract](https://docs.cloud.google.com/storage/docs/request-preconditions)
and [objects.insert endpoint](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/insert).

Before each Compute insertion, the original active lease, unexpired ownership,
durable intent and pending ledger reservation are checked. After image observation,
the adapter checks again, writes a create-only submission marker, then checks
ownership immediately before the POST. The marker prevents reissuing that original
insert, including from a reconstructed process after response loss. There is no
automatic workload or mutation retry. An unobserved outcome remains unresolved;
a crash between marker persistence and POST can therefore retain the lease for
further reconciliation rather than claim absence. A retained CLEANING lease,
absent original operation and absent submission marker can instead prove that an
intent never reached POST. This proof is retained before accepting non-creation;
image rejection or failed marker persistence can therefore clean safely. A marker
with an unknown provider outcome remains unresolved.

## Operation identity and cleanup

Each original mutation has a deterministic nonzero UUID. Responses bind the request
ID, operation type/name, exact project/scope/resource target and numeric resource
incarnation. Original-operation polling keeps its finite exchange deadline and
rejects a changed operation name. Lookup follows bounded pagination, including
empty pages; duplicate matches, cyclic tokens and excessive pages reject. The
[zone operation list contract](https://docs.cloud.google.com/compute/docs/reference/rest/v1/zoneOperations/list)
defines pagination and the operation fields used here.

Completed insertion operations are retained immutably before the owner accepts the
resource. The record contains only checked identity/status fields and a sanitized
error flag. This preserves the original result after provider operation retention
expires; it does not turn a pending or unknown operation into DONE. Failed receipt
retention keeps ownership unresolved and prevents successful finalization.

A terminal insertion error may include a numeric `targetId`, even when no VM
survives (for example, `ZONE_RESOURCE_POOL_EXHAUSTED`). DONE resolves the original
operation; it does not prove successful creation. The decoder retains that ID
and the existing sanitized error flag. Creation rejects the failed result before
admitting any resource or workload. Cleanup observes the original target: absence
can complete reconciliation; a remaining resource requires matching ownership and
the exact ID before deletion. A replacement ID, unknown/pending operation or failed
deletion still retains the lease. Errors without an ID require actual absence.
No insertion is replayed and no zone or machine type is substituted.

Live insertion failures expose only closed `providerCode` diagnostics:
`V52_PROVIDER_CAPACITY_UNAVAILABLE` for the recognized zone-capacity errors, or
`V52_PROVIDER_INSERT_REJECTED` otherwise. Stored boolean error flags replay as
generic failures, preserving the existing immutable operation format without raw
provider messages. Classification cannot authorize retries or successful admission.

Owner-finally, manual and scheduled reconciliation use the existing shared cleanup
algorithm. The HTTP adapter also requires a retained CLEANING lease with the exact
request and resource ID before deletion; an in-memory cleanup flag is insufficient.
Deletion addresses the numeric resource incarnation and never falls back to a name.
A reused name or changed numeric ID is not deleted or accepted as final absence.
A lost delete response retains failure for later observation of the original result.

The REST deletion references describe request UUIDs and target incarnation IDs
([disks](https://docs.cloud.google.com/compute/docs/reference/rest/v1/disks/delete),
[instances](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/delete),
[firewalls](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/delete)).
Their prose path descriptions use resource names. This stage tests the repository's
existing numeric-address convention offline; it does **not** newly establish live
provider compatibility. A numeric-address rejection must remain a failure, never
cause a name-based fallback. Fresh V5.2 provider qualification remains required.

## Resource checks and time policy

The closed inventory remains four firewall rules, six disks and three instances.
Responses check ownership descriptions/labels, firewall scope/priority/ports,
pinned boot-image numeric ID, disk sizes/types/attachments, instance type,
metadata, tags, no service account and no external network configuration. Image
creation requires the same pinned READY image; a DEPRECATED marker alone does not
invalidate that exact image, while OBSOLETE/DELETED states and ID drift reject.
This is a V5.2 implementation rule; it supplies no V5.1 cross-source exception.

Instance bodies impose no maximum lifetime and do not auto-delete attached disks.
Stage duration and cost thresholds remain soft. Renewable lease ownership,
individual HTTP/operation deadlines, response sizes and pagination bounds remain
firm. An expired owner cannot gain more work by increasing its stage budget.

## Validation and remaining integration

`test_cloud_provider` exercises the actual mapping through an independent HTTP
fixture, including complete 13-resource preparation and reconstructed cleanup,
conditional generations, metadata/media races, lost responses, credential-refresh
bounds, operation pagination, retained context/operation drift, reused resources,
image states, no-hard-lifetime bodies and fenced mutations. It runs in the existing
measurement unit gate alongside the original in-memory owner tests.

Three added regressions first fail on the initial implementation: reissuing an
original insert after response loss, expiry during image observation, and deleting
an active lease's resource after changing only the in-memory cleanup flag. The
corrected submission/ownership checks pass all three. A fourth regression first
fails without the fenced non-submission proof and passes with it. A fifth regression verifies that owner/provider request mismatch rejects before
reservation. The initial fixture parser failure, failing source snapshots and
red/green logs remain in
`target/v52-cloud-provider/`; no failed evidence is overwritten.

Final corrected-source validation: all **613 V5.2 Python tests pass in 215.678
seconds**, including **35 new HTTP regressions**, and all **30 CI classification
tests pass in 44.720 seconds**. Documentation contract, changed local links/fences,
Python AST, shell syntax and whitespace checks pass. No Maven build or complete
engine-history/paid qualification was rerun for these control-only changes.

The earlier sandbox full-suite attempt retains 16 installer failures caused by
ancestor UID mapping (`Python capsule linked/writable ancestor`), not HTTP test
failures. The final complete suite runs with the actual local UID and passes;
installer ownership/permission checks are unchanged. Printed synthetic unit fixture
PASS records are not real engine or cloud experiment evidence.

Still required: independently admitted native API/credentials, reviewed live
configuration, fresh permission/image/network checks, actual guest access and
boot/mount/host-key observations, owned IAP route lifetime, complete owned members
and independent five-member aggregation, then dedicated exact-master/full-CI and
operator-controlled cloud entry. Existing local SSH/history receipts keep their
original source bindings and are not promoted by these HTTP tests.
