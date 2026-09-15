# V5.0 protocol, recovery and failure contract

- **Status:** Accepted Phase 0 contract
- **Protocol family:** `gse-replication/1.0`
- **Storage family:** `gse-replicated (1,0)`

## Logical messages

The minimum protocol contains:

1. `HANDSHAKE` / rejection with exact protocol, group, configuration and peer identity;
2. `ACTIVATE_EPOCH` / durable promise acknowledgement;
3. `APPEND` / durable-entry acknowledgement or predecessor/conflict rejection;
4. `COMMIT_PROOF` / durable-proof acknowledgement;
5. `ADVANCE_COMMIT` / applied-status response;
6. `STATUS` with authority, role, bounds and recovery floor;
7. `SNAPSHOT_BEGIN`, bounded `SNAPSHOT_CHUNK`, `SNAPSHOT_COMPLETE` and abort; and
8. classified unavailable, stale-epoch, mismatch, capacity and corruption responses.

Every retry is idempotent by exact identity and bytes. Unknown major protocol,
manifest mismatch, stale epoch, wrong peer, noncontiguous index, invalid digest or
oversized message fails before durable mutation. A minor-version capability can be
used only after both peers advertise it; otherwise the shared 1.0 subset applies.

A durable-entry ACK binds voter, epoch/incarnation, index and entry digest. A commit
proof binds a distinct manifest quorum of those receipt digests and the contiguous
entry digest chain. Receipt identities are integrity evidence under the trusted,
non-Byzantine member model; they are not a public-key signature or hostile-peer claim.

Exact binary framing and transport library are Phase 1 decisions. The logical fields,
state transitions and rejection behavior are already frozen here and may not be
redefined by that selection.

## Time, cancellation and pressure

Clocks, timeout and heartbeat do not prove authority, failure or commitment. They may
close a request, update health and cause a retry only. A cancelled client Future does
not cancel an entry already admitted to replication.

All queues, batches, frames, in-flight entries, retry counts, retained log bytes,
snapshot chunks and staging bytes have finite configured limits. A bound violation
rejects new work or moves the peer to catch-up; it cannot silently drop a committed
entry. Phase 1 freezes exact defaults and absolute maxima before Phase 2.

## Restart reconciliation

The configured leader first reads promised epochs from a quorum, chooses exactly one
greater than the maximum valid observed epoch and obtains durable promises for its
fresh incarnation from a quorum. This fences old incarnations. It then examines valid
commit proofs from the quorum and reconstructs the greatest proof whose digest chain
is consistent with every other valid proof. It may fetch missing committed bytes from
any valid replica/snapshot. It discards only suffix entries not covered by commit
proof. Epoch arithmetic overflow fails permanently rather than wrapping.

That ordinary quorum procedure assumes the configured leader retained its own durable
voter state. If its disk was replaced, the new disk is not yet a voter and offline
reconstruction must contact both surviving followers. Only after their promises,
proofs and highest valid history are reconciled and installed may the configured
leader identity vote or activate again. The same non-voting rule applies to every
replaced follower until catch-up completes.

The leader cannot reopen writes if quorum is absent, the manifest differs, two valid
proofs conflict, committed bytes are unavailable or applied reconstruction fails.

A follower reopens locally, validates current leader activation and catches up in
contiguous batches. If required history precedes the recovery floor, it installs a
verified replicated snapshot into absent staging, atomically publishes it, forces the
parent and replays the tail. Transfer interruption leaves the prior authority intact.

## Failure matrix

| Failure | Commitment/visibility | Admission/recovery |
| --- | --- | --- |
| Message drop/delay/reorder | No semantic change | Retry idempotently; timeout is indeterminate |
| Duplicate append/proof | No duplicate apply | Same bytes ACK; conflicting bytes fail closed |
| Crash before entry force | Not acknowledged | Discard invalid/incomplete tail |
| Crash after entry force, before entry quorum | Uncommitted | Legal suffix reconciliation |
| Crash after entry quorum, before proof quorum | Uncommitted to clients | No valid quorum-persisted proof; reconcile suffix |
| Crash after proof quorum, before Future | Committed, possibly not visible before crash | Replay/apply; client result indeterminate |
| Crash after publication, before response | Committed and visible | Replay same state; client result indeterminate |
| One follower down/slow | Existing commit unchanged | Writes use leader + other READY follower; lag is bounded |
| Both followers unavailable | Last AppliedIndex readable on leader | Reject new writes until quorum returns |
| Leader process crash | Committed history preserved | Restart same configured identity through new epoch |
| Leader disk loss | Proof/history must not regress | Offline reconstruct same NodeId; no online promotion |
| Follower disk loss | Group remains authoritative | Recreate absent storage for same NodeId and snapshot/catch up |
| Local corruption | Corrupt source never counts | Use another valid recovery source or fail closed |
| Snapshot interruption | Old installed authority remains | Remove only exact staging and retry |
| Restart during reconciliation | No write admission | Repeat idempotently from durable promises/proofs |
| No reconstructible committed bytes | Proven history must not be lowered | Group remains failed; operator recovery required |

## Security and deployment assumptions

V5.0 models trusted non-Byzantine peers on a controlled private network. It does not
claim TLS, peer authentication, confidentiality or safe Internet exposure. Production
configuration rejects unprotected public-interface binding. Cloud evidence restricts
private peer addresses with workflow-scoped identity, least-privilege firewall/IAM
and an exact GCS prefix.

Adding authenticated/encrypted transport requires a later reviewed contract and must
not change consensus semantics.
