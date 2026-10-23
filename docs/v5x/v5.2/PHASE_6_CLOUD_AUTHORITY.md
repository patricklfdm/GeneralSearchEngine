# V5.2 Phase 6AQ resource and lease authority

The [bound receiver backend](PHASE_6_BOUND_RECEIVERS.md) now has a V5.2 control
record model and a qualified **in-memory** owner/reconciler. This stage performs
no HTTP call, creates no cloud resource and executes no engine history. A record
with native intent is data; it cannot enable the offline entry or grant admission.

## Independent identity and complete attempts

`cloud_authority.py` binds an exact [suite selection](PHASE_6_CLOUD_SUITE.md),
configuration digest, resource layout, ownership policy and original creation time.
Offline/native records have disjoint execution identities. No V5.1 record is
converted, and its workflows, provider configuration, lease and ledger are unchanged.
The new namespace is `v5.2-bounded-follower-reads/control/`.

The resource inventory is closed: four network rules, three boot disks, three data
disks and three instances. Names include the original attempt; operation identities
bind the exact request and name. Layout sizes are explicit request inputs, not a
claim that current cloud configuration or pricing has been reviewed. The offline
fixtures' 50/100 GiB disks do not authorize that live allocation.

The append-only ledger permits the fifteen whole execution units in any order.
They represent five logical members; failure-drill uses the
[five fixed shards](PHASE_6_HOSTED_DRILL.md). One unresolved
attempt blocks another reservation. A failed whole attempt retains its original
charge and completion; a new explicitly selected attempt may retry that member,
with fresh resource names. A passed member cannot be repeated in the same sequence.
All members share source/checkout/sequence/build/package/control, configuration,
layout and policy. Successful history fragments cannot fill another attempt.

Reservations are cumulative cost **estimates**, not measured billing. The configured
cost threshold only produces a warning; failure does not refund a reservation.
Stale cost observations, integer overflow and ledger size limits still reject.
V5.1's old budget history is neither read nor reset.

## Renewable ownership, soft execution budgets

Ownership progresses from `ACQUIRING` to `ACTIVE` to `CLEANING` through conditional
object writes. Lease acquisition precedes the ledger reservation; the reservation
must be present before active resource intents or creation. Each original intent
is persisted before the insert, and exact numeric IDs are retained afterward.
A lost write response may query the original value at most three times. It never
reissues the CAS or original resource insertion.

An active owner can renew before its current expiry. Renewal preserves the original
request and resource IDs; it is not a new workload or a new measured window. A
slow original insert does not hold the owner lock and prevent a heartbeat. Actual
heartbeat scheduling and native transport remain future integration work.

No total preparation/workload stage limit is imposed here. Individual exchanges
remain finite, and an expired or fenced owner cannot continue or revive itself.
The request's lease window and operation grace are authority bounds, separate from
soft experiment duration. Reconciliation waits until expiry plus grace, except
when the original owner has already explicitly entered irreversible cleanup.

`resource_claim()` captures the complete original allocation and per-node resource
identity hashes. It stays stable across renewals. It is not fresh provider evidence:
exact live instance/disk IDs, attachments, boot/user, host keys and mounted storage
must still be independently observed before constructing receiver placements.

## One cleanup implementation, exact generations

`cloud_control.py` reuses the existing namespace-independent V5.1 exact-ID deletion
algorithm. Owner-finally, manual and scheduled reconciliation enter the same
V5.2 fencing and finalization path. Both manual and schedule return `WAITING`
without writes for an unexpired active lease. Schedule timeliness is not a separate
admission prerequisite; fresh manual cleanup remains sufficient.

Cleanup resolves each original operation before treating absence as final. A pending
or unknown insert retains the lease; a reused numeric ID or changed owner is never
deleted. Other independently owned resources can still be cleaned. Deletion orders
instances before disks and network rules, and verifies final absence.

Immutable cleanup receipts and original completion precede terminal ledger append
and conditional lease release. Retention or deletion failure keeps the lease for
reconciliation. A later successful cleanup does not rewrite the original failed
completion. A lost release reply is observed; a replacement lease is never deleted.
An updated generation of the same original lease is not proof of release and
cannot produce a successful release receipt.
An interrupted acquisition before any charge/intent can release its empty lease,
while attempted resources without their original reservation block cleanup.

Repeated preparation on the same owner rejects before cleanup and cannot destroy
its existing resources. Preparation failure retains the original error separately
from cleanup failure. No successful engine/member completion can be emitted by the
current offline owner: even successful resource qualification finishes an explicitly
failed/non-workload attempt, while its cleanup can independently pass.

## Verification and remaining work

Regression coverage includes closed domains and inventories, all 120 member orders,
soft cost warnings, source/configuration drift, renewal/expiry, two concurrent lease
claimants, slow insert plus renewal, duplicate preparation, lost CAS and insert
responses, unresolved operations, foreign/reused IDs, missing charges, failed
retention, lost release replies and preservation of old V5.1 objects.

The new modules are included in the existing V5.2 measurement unit-test gate.
Implementation `ecbe215` passes all 578 V5.2 Python tests (126.540 seconds), including
40 new control regressions. All 30 CI classification tests, the V5.0 documentation
contract, changed Markdown links/fences, Python/shell syntax and whitespace checks
also pass. No Maven or engine history rerun was needed for these control-only
changes.

Results and executed source hashes are retained in `target/v52-cloud-authority/`.
The first complete suite retained one stale diagnostic expectation: a new
post-insert checkpoint correctly fences the owner before the later CAS conflict.
The updated assertion preserves rejection and no-second-insert checks. A separate
new release regression failed before the correction and passed afterward: a new
generation of the same lease must not be mistaken for a released lease. Both
original failure logs and the pre-correction control implementation are retained.
The later documentation commit does not replace the tested implementation.
Unit/control receipts are not engine or independent-host qualification. The earlier
four-history SSH receipt still belongs to implementation `2649555`, not this source.

Remaining integration: independently admitted native provider/lease capability,
owned IAP routes and credential lifetime, fresh guest/mount identity, complete
owned members and five-member independent aggregate, then dedicated exact-master
full-CI and fresh permission/image/cleanup admission. Push, merge and any paid
trigger remain operator-owned; there is no live CLI or workflow in this stage.

The subsequent [Phase 6AR HTTP mapping](PHASE_6_PROVIDER_HTTP.md) adds a second
concrete offline adapter and retained provider context before resource submission.
Its wire qualification does not alter the source-bound results above or enable
native execution.
