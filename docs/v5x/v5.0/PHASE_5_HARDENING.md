# V5.0 Phase 5 runtime hardening

- **Status:** Accepted through [PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150)
- **Exact-master CI:** [34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066) at `4a8fd3dfd9e398d712e896c9af511cf55f4cb16e`
- **Entry:** [Phase 5 plan](PHASE_5_ENTRY_PLAN.md)
- **Authority:** [protocol and failure contract](PROTOCOL_RECOVERY_AND_FAILURES.md)
- **Foundation:** [leader path](PHASE_3_LEADER_PATH.md), [recovery](PHASE_4_RECOVERY.md)

## Problems and resulting behavior

Phase 4's internal close path marked the node closed before cleanup completed. An
interrupted close or a writer-termination timeout left storage owned, and a later
close returned immediately without finishing cleanup. A transport completion callback
could also wait for its own sender thread to terminate. Immediate writer interruption could also interrupt a
partially written proof record.

Close now separates admission shutdown from completed resource cleanup. Under the
store's existing serialization lock it finishes the current record/installation,
rejects later authority writes, and only then interrupts the writer. Closing cannot
use interruption to truncate a record halfway through its write. Interruption
preserves the caller's interrupt flag; a termination timeout retains the store owner
while a writer can still mutate. A later close retries cleanup. Concurrent callers
share shutdown ownership, and a reentrant writer/completion callback avoids waiting
on a closer that is joining it. Status reports unavailable while cleanup is incomplete,
with writes disabled, and reports CLOSED only after application/store cleanup.

Queued tasks own one idempotent admission cleanup action. Queue rejection and shutdown
both run it; cancellation alone does not. Completed actions release admission before
calling application-future callbacks. A full writer queue returns the classified
CAPACITY_EXCEEDED outcome; shutdown rejection returns CLOSED. Queued, cancelled and
running operations cannot strand client slots or payload accounting after termination.

Transport shutdown closes sockets, interrupts other sender threads, drains their
bounded queues and shuts down inbound workers. Callback close skips joining its own
sender. Acceptor failure initiates the same transport shutdown instead of leaving
sender workers alive. An impossible snapshot chunk/envelope bound rejects before
staging creation or arithmetic on an invalid chunk size.

Configured bounds cover transport/writer waits and admitted work. Arbitrary synchronous
application callbacks/codecs must cooperate; their execution is not a hard real-time
shutdown guarantee. Completing an in-progress filesystem force also follows the
filesystem's I/O completion semantics rather than a wall-clock cutoff. If a writer
does not terminate, ownership stays held. This
candidate does not forcibly stop arbitrary application threads or weaken storage locks.

## Deterministic faults on production networking

The internal transport exposes package-private event hooks at BEFORE_REQUEST_WRITE,
BEFORE_RESPONSE_WRITE and AFTER_RESPONSE_READ. Normal construction uses a no-op hook.
Hooks do not replace wire decoding, durable processing, response identity checks,
quorum counting, retry deadlines or publication. The test-only fault controller drops
a connection by throwing IOException at the selected real socket boundary, or holds
a response until an explicit release. BEFORE_RESPONSE_WRITE occurs after the actual
follower force/apply path, so disconnecting there tests a lost durable ACK.

Each recorded attempt contains exact request/response envelopes, request-frame SHA-256,
node, owned JVM PID, per-process event sequence, attempt number, boundary and action.
Fault plans, raw controls, store events, crash markers and process lifetimes are
retained separately. The independent Python validator re-encodes canonical wire bytes,
checks identical retries, configured retry limits, correlation, process ownership and
that requested faults actually occurred. It does not interpret a socket send as a
quorum acknowledgement.

The deterministic replay case serializes a Phase 1 schedule containing dropped,
duplicated, reordered, stale-incarnation and conflicting-entry requests. A fresh
reader executes that same schedule twice against a real follower socket; both
transcripts and unchanged follower state must agree. Another ACK-loss plan repeats
in a fresh three-JVM group. Raw UUIDs, ports and thread timing vary across groups;
the named plan, fault outcomes and application oracle are the repeatable evidence.
This is not a claim that all OS thread interleavings are deterministic.

## Local Java matrix

| Area | Coverage |
| --- | --- |
| Lost response | Activation promise, entry ACK, proof ACK, snapshot offer/chunk/install ACK; retries preserve exact bytes and apply once |
| Retry exhaustion | Both follower entry ACKs lost; no publication; fenced recovery removes only unproven suffix |
| Slow follower | Healthy quorum makes progress while one response is held; bounded FIFO pressure and explicit catch-up restore the follower |
| Wire admission | Duplicate/reordered commit/append, old incarnation, same-index conflict, proof before entry, truncated/oversized/checksum/wrong-identity frames |
| Lifecycle | Interrupted and timed-out close retry, storage lock retention, sender callback close, concurrent/reentrant close, close during a partial proof write, leased reader across checkpoint replacement |
| Pressure | Client admission, full writer queue, aggregate outbound bytes, cancelled-slot retention, retained disk capacity and corrupt/impossible transfer staging |

The slow-follower process case records the follower within the initial-to-acknowledged
prefix. Holding an APPEND response does not freeze application: an expired outgoing
exchange can release its FIFO slot, allowing a later valid COMMIT_PROOF to arrive.
The case requires all ten leader writes to complete with a healthy quorum, verifies
the real hold in the wire transcript, then independently checks the recovered state.

The slow-follower process case releases the fault before requesting catch-up. Release
does not synchronously drain the leader's eight admitted peer exchanges. A
`CAPACITY_EXCEEDED` catch-up result is therefore retried only while the leader remains
READY with write quorum, at 50-ms intervals, for at most 100 attempts and with no new
attempt after a ten-second admission window. Each command retains the existing worker
response timeout. Every response is retained in `catchup-after-pressure-node-3.json`;
other failures and persistent capacity exhaustion still fail the case. This changes
test-driver admission handling, not production queue, retry or timeout bounds. The
subsequent restart, history/proof oracle and published V4.4 comparison remain required.

Storage format, normal wire bytes, public signatures, core/processor source and POMs
remain unchanged. Hooks, workers, fixture codecs and controls are not public runtime
entry points; test classes are excluded from production artifacts.

## Three-JVM process matrix

The gate runs 16 cases, each starting three concurrent production nodes:

1. entry-ACK loss;
2. proof-ACK loss;
3. snapshot-chunk ACK loss;
4. snapshot-install ACK loss;
5. the entry-ACK plan repeated in a fresh group;
6. exhausted entry-ACK retries;
7. exhausted proof-ACK retries, preserving the indeterminate committed result;
8. slow follower with continued writes and catch-up;
9. exact deterministic wire schedule replay;
10. three repeated leader SIGKILL/recovery/checkpoint cycles;
11. cancellation at entry quorum, a full client queue, close and restart; and
12. five SIGKILL cuts during recovery: after promise quorum, selection, installation,
    application publication and recovered READY quorum.

Recovery-cut cases first create an unproven suffix through real lost entry ACKs. Thus
reconciliation must repair history; an interrupted install is not represented solely
by a healthy matching-history reopen. Crash records identify the exact killed process,
and retained pre-reopen stores feed the independent recovery oracle.

After faults, the group recovers, catches up and checkpoints. Independent inspection
checks all observed valid proof prefixes and prior successful boundaries. Application
replay, actual document/equality-query order, index lifecycle and ApplicationSequence
must agree with checksum-pinned published V4.4 in a separate control JVM; its loaded
SearchEngine code source is checked. Five recovery cuts plus three repeated-cycle
kills add eight real process kills, alongside the existing Phase 2–4 crash matrices.

The trace validator has negative tests for changed retry bytes, absent requested
faults, response correlation drift, excessive retry, wrong process owner and missing
events. Evidence production is bounded to 100,000 records and 64 MiB per worker run;
the collector additionally bounds each retained per-node transcript and checks PIDs
against exact process receipts. Invalid or missing evidence rejects the gate.

## Admission and limits

[The baseline](PHASE_5_BASELINE.md) records actual results. Required CI runs the new
gate after Phases 1–4 and uploads `target/v50-hardening` even on failure. The reactor
job timeout increases from 15 to 20 minutes to cover the additional process matrix. Local dirty-tree
evidence remains candidate evidence until protected PR and exact-master CI acceptance.

Public builder/bootstrap plan/apply and end-user checkpoint/backup integration remain
reserved as detailed in the [entry plan](PHASE_5_ENTRY_PLAN.md). Their full authority
and lifecycle admission is a separate required step before public runtime/cloud
admission. This candidate hardens the existing internal runtime and does not claim
those missing public flows were tested. Automatic background catch-up, membership
changes, election, hostile-network security, performance, kernel/device power loss,
paid cloud and signed publication remain outside this result.
