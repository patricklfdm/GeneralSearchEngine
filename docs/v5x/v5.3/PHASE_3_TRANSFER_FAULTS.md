# Phase 3B — original TCP transfer faults

Status: locally qualified for the bounded matrix below. The complete
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open.

## Native execution

`V53TransferFaultsTest` creates three independent public-bootstrap stores with
stable sizes 3, 4 and 5. Each opens one native node-1 owner, captures its original
PROMISE/BASIS and complete source, and keeps that owner through nine consecutive
transfer-service lifetimes. Node 2 requests the original PROMISE over real TCP.
There are two transport endpoints per profile; the other bootstrapped members
remain passive. These are three stable sizes, not the seven membership-change
profiles required for Phase 3 closure.

| Case, repeated at each stable size | Observed attempts | Boundary checked |
| --- | ---: | --- |
| lost-offer | 4 | One server offer is dropped; the identical request retries successfully |
| lost-data | 4 | One data reply is dropped; original bytes and sequence are retained |
| lost-commit | 4 | One commit reply is dropped; only the identical terminal request replays |
| exhausted-offer | 3 | All three original offer replies are dropped; no received record |
| expired-active | 3 | Open export expires; resetting the injected clock cannot revive it |
| expired-completed | 5 | Completed reply marker expires; resetting the clock cannot revive it |
| closed-active | 2 | Explicit service close refuses the outstanding transfer's next request |
| changed-completed | 5 | A changed terminal digest poisons the trace; the old request then refuses |
| owner-closed-completed | 4 | Actual journal-owner close invalidates cached completion replay |

The successful original matrix has 27 cases, 102 attempts, 18 dropped replies,
18 received records and 24 terminal refusal probes. Loss is injected at the
server's `BEFORE_RESPONSE_WRITE`: the socket closes, and the real client observes
`IO`. No synthetic success is supplied to the client. The immutable original
request and original deadline are retained across retries. The pull protocol's
existing attempt limit is `min(3, bounds.maxRetryAttempts())`; neither production
retry configuration nor protocol bounds changed.

Expiry uses an explicitly recorded offset of 60 seconds on the service clock.
It is fault injection, **not** a measured 60-second wait or latency result. Client
deadlines remain tied to their original start. Before collecting resource
observations, both TCP endpoints drain incoming/outgoing work and sockets.

Client resources return to zero after every case. The server returns to the same
open-owner baseline after every service lifetime, then to zero after actual owner
close. An exhausted offer intentionally retains one bounded live export until
service close; exhaustion does not fabricate a server-side cancellation. A
completed transfer releases its export and retains only its accounted terminal
marker. These counters and local force callbacks are source-bound observations;
they are not a standalone physical proof of crash durability.

## Independent replay

`scripts.v53.transfer_fault_evidence` first reconstructs public bootstrap,
original allocator/PROMISE/BASIS, source packet and exported content. It compares
complete captured and final replica inventories. It then validates each local
capture's force order and derives the expected offer, data and commit bytes from
the original physical PROMISE, including permanent identities, root, view,
ballot, trace, transfer ID and sequence.

Every attempt must have the exact client/server request and response boundaries.
A dropped response cannot also be delivered. Refusals have no response bytes.
The reader checks the original deadline, exact retry count, control-event
positions, post-close observations, received bytes, complete case inventory and
continuous owner resource baseline. Input inventory rejects symlinks and bounds
total bytes and members; duplicate JSON keys are rejected.

Qualification validates the unmodified original before creating mutation copies.
Its 25 negative variants cover physical authority, received bytes, request and
reply correlation, loss/delivery, extended deadlines and retries, expiry and
clock reset, force order, resource observations and incomplete matrices. Each
must fail with its exact declared reason. An unrelated rejection, accepted
mutation or changed original is a qualification failure.

```bash
python3 -B -m unittest scripts.v53.test_transfer_fault_evidence
python3 -B -m scripts.v53.transfer_fault_evidence /path/to/original/raw --qualify
```

The native producer is the one JUnit method in `V53TransferFaultsTest`; its
isolated Maven execution and source/build manifests are retained with the raw
evidence. See [the receipt](phase3-evidence/transfer-faults.json). The archive
retains the tested source, compiled classes, reports, all original evidence,
reader source and development failures. A relocated archive is replayed using
its own frozen reader, without rerunning the native matrix.

## Validation and remaining scope

The final native execution passed all 27 cases. The first compile attempt used
an unavailable resource accessor; a subsequent execution incorrectly expected
12 offer attempts instead of the protocol's existing limit of 3. Both failures,
the failed source/report and partial raw execution remain retained. Correcting
those test expectations required no production change. The initial negative
driver omitted `: node-2` from one exact diagnostic; that failure is also retained.
The successful matrix comes from one complete new execution; it does not splice
the failed execution's earlier successes into the final receipt.

The scoped reader tests and existing source/export/record/service reader tests
pass, as do the related native source/record/service tests. Exact counts and
hashes are recorded in the receipt rather than inferred from case labels.

This matrix transfers one original PROMISE (one data chunk in these runs), not a
multi-content application snapshot. It does not qualify interrupted large
images, asynchronous in-flight cancellation, cross-node publication during
faults, process halt/SIGKILL/restart, all membership transitions or the complete
frozen acceptance mapping. Those remain required, together with full
force/network composition for the native joining histories. Phase 3 remains
**OPEN**; no workflow, paid cloud experiment or frozen parameter changed.
