# V5.0 Phase 3 configured-leader path

- **Status:** Accepted through protected PR #148 and exact-master CI 34940262703
- **Entry:** [Phase 3 plan](PHASE_3_ENTRY_PLAN.md)
- **Authority:** unchanged [Phase 2 storage format](PHASE_2_STORAGE_FORMAT.md)
- **Wire envelope:** unchanged [Phase 1 transport decision](TRANSPORT_AND_FRAMING.md)

## Runtime and phase boundary

`ReplicaNode` owns one existing replica store, one ordered writer, a bounded NIO
transport and a `ReplicaApplication`. These implementation classes are package-private.
The public builder/bootstrap declarations remain reserved until group-bootstrap and
recovery admission can prove valid startable authority. Test workers initialize fresh
storage explicitly; they do not create or impersonate an accepted bootstrap receipt.
Public API signatures and existing core/processor code are unchanged.

A node reconstructs its local committed prefix into private application state on open.
Leader reads remain unavailable until quorum activation succeeds. This phase accepts
only a complete matching committed prefix on the local node and at least one other
voter. It refuses uncommitted suffixes, divergent histories and missing committed
bytes. It never repairs/truncates a log, invents an empty replacement voter, installs
a snapshot or promotes a follower. Phase 4 owns these recovery paths.

## Activation and ordered commitment

The configured leader probes the other voters in parallel. A remote response must
bind the exact manifest, configuration, sender/recipient and request correlation.
A responding voter can join activation only if its LastLogIndex, CommitIndex and
last-entry digest match the local complete committed prefix. The leader chooses one
greater than the maximum promise observed in its quorum. Overflow rejects permanently.
It forces its own fresh incarnation promise, obtains a distinct remote promise, and
commits a NO_OP through both entry and proof quorums before admitting application work.
NO_OP advances LogIndex/AppliedIndex but leaves ApplicationSequence unchanged.

For each admitted application operation, one writer executes:

```text
canonical payload + private validation/preparation
  -> local entry force
  -> valid entry ACK from at least one other voter
  -> create one proof binding those distinct entry receipts
  -> local proof force
  -> valid proof ACK from at least one other voter
  -> advance confirmed leader CommitIndex
  -> atomically publish prepared application state with AppliedIndex/sequence
  -> complete the application future
```

Only validated entry/proof receipts count; socket completion does not. One fast READY
follower is sufficient and the leader does not wait for a slow third voter once it
has quorum. Work to each peer remains FIFO, including retries, so later proof/append
requests cannot overtake earlier requests on that peer's outgoing path.

The underlying store protects any valid locally persisted proof immediately. The
active leader's reported CommitIndex advances after confirmed proof quorum. Therefore
an indeterminate failed operation can leave a higher local proof in storage than the
last confirmed leader publication; that evidence must not be discarded during recovery.

A timeout after admission stops subsequent leader writes and reports UNAVAILABLE;
it leaves the last published view readable. Other fatal storage/application-path
failures report FAILED. These are the Phase 1 frozen enum names for the lifecycle
states. Quorum availability describes the last confirmed/request-observed state;
this phase does not add heartbeat-based failure detection or automatic election.

## Application state and reads

`ReplicaApplication` uses two ordinary in-memory snapshot engines. It never opens a
V4 WAL or writes a second authoritative decision. One engine is the published view;
the other privately validates and prepares the next operation using the existing V4
mutation/index behavior. This makes duplicate/missing-key, atomic bulk and built-in
index validation happen before the first replicated authority write.

Private preparation is not replicated application visibility. After proof quorum,
one atomic reference publishes the prepared engine together with AppliedIndex and
ApplicationSequence. Each application entry increments that sequence once, including
a bulk call; control entries do not. A failed or cancelled application future does
not retract a record or revoke a later committed publication.

Readers acquire an atomic lease on the current published engine without taking a
mutex. Publication retires the old engine. Before using that retired engine as the
next private preparation target, the writer waits for its existing reader leases
to drain, then catches it up with the already committed operation. Readers arriving
after retirement retry against the current published reference. Consequently an old
reader can never access a reused engine while it contains a new uncommitted change.
Reader-drain waiting is bounded by the configured request timeout.

This design uses two materializations and adds private preparation/catch-up work;
Phase 3 makes no performance claim. Phase 6 must measure it. Retained documents follow
the existing core contract: callers treat accepted/returned documents as immutable.

Followers reject application submissions, reads and leader activation before execution.
They prepare a contiguous new entry privately, force it before ACK, and publish only
after storing its valid commit proof. Exact append/proof retries re-force existing
records without duplicate apply. Test-only worker status includes local document
observations; it is not a public follower-read capability.

## Deterministic application payloads

Every application payload starts with big-endian u16 version 1. Fields use the Phase 2
strict UTF-8 text and i32-length-prefixed byte encodings. The outer entry's payload
checksum covers the complete payload.

| Operation | Remaining payload |
|---|---|
| ADD, UPDATE | i32 count = 1; encoded key blob; encoded document blob |
| ADD_ALL, UPDATE_ALL | i32 count; ordered key/document blob pairs |
| REMOVE | i32 count = 1; encoded key blob |
| REMOVE_ALL | i32 count; ordered key blobs |
| INDEX_CREATE | text containing the canonical index descriptor JSON |
| INDEX_DROP | canonical schema field text |
| NO_OP | Entire payload is empty, without a version field |

The index descriptor has exactly `analyzer`, `field` and `kind` keys. Supported kinds
are `equality`, `range`, `prefix` and `text`; text requires `gse-simple-v1`, other
kinds have the empty analyzer string. Only built-in index definitions and the simple
analyzer are supported, matching the durable V4 boundary. The initial index identity
is SHA-256 of the canonical JSON array of sorted descriptor strings. Codec identity/
version, schema identity (schema version 1) and this initial index digest must match
the immutable manifest before a runtime opens.

Keys/documents must be canonical across repeated encoding and decode/re-encode. A
decoded document must preserve the encoded key. Encoding owns its bytes; submission
owns one bounded copy. Bulk/key/document/document-count limits come from the supplied
DurableStorageConfig. Its directory is reserved and remains absent; it is not opened
as materialization authority. SNAPSHOT_MARKER application and CONFIGURATION remain
unsupported in this phase.

## Production message payloads

Every payload below also contains the exact `manifestDigest`. Unknown/missing keys
reject. The common envelope remains byte-identical to all 16 Phase 1 golden examples;
those earlier logical payload examples remain envelope fixtures, not runtime requests.

| Request/reply | Additional payload fields |
|---|---|
| HANDSHAKE request/reply / AUTHORITY_STATUS_PROBE | none |
| AUTHORITY_STATUS | promisedEpoch, lastLogIndex, commitIndex, lastDigest, appliedIndex |
| ACTIVATE_EPOCH | commitIndex, lastDigest |
| ACTIVATION_PROMISE | promisedEpoch |
| APPEND | entry: canonical padded base64 of one complete Phase 2 entry frame |
| DURABLE_ACK | index, entryDigest, receiptDigest |
| COMMIT_PROOF | proof: canonical padded base64 of one complete Phase 2 proof frame |
| COMMIT_PROOF_ACK | index, proofDigest |
| REJECT | reason: frozen ReplicationException reason name |

HANDSHAKE replies use HANDSHAKE too, including at epoch zero; they do not promise or
activate a voter. A response echoes the request's epoch, incarnation, trace ID and event sequence;
its sender must be the requested peer and its recipient must be the local voter.
Mutation envelope and embedded entry/proof epoch/incarnation must agree. Read-only
status probes can discover durable promises before activation; they cannot write.
Other message families keep their frozen IDs but reject until their later-phase
handler exists.

## Transport, bounds and close

NIO connections carry one framed request and correlated response. Each peer has one
ordered outbound queue/worker. Nonblocking connect/read/write use selectors, handle
partial progress, and share one monotonic deadline across queue wait and all retries.
The server closes malformed/incomplete connections without returning a success ACK.
This is the frozen Java 21 dependency choice, with no external transport/JSON library.

All configured endpoint addresses must resolve to loopback, RFC1918/site-local or
IPv6 unique-local addresses. Wildcard, public and multicast endpoints reject before
bind, as do overlapping resolved voter endpoints. DNS names alone do not establish
private admission. The accepted non-Byzantine/private-network model still applies;
this is not authentication or TLS.

Additional Phase 3 internal safety caps:

- runtime frame bound must be at least 4096 bytes;
- application payload maximum is `floor((maxFrameBytes - 2048) / 4) * 3 - 197`,
  reserving base64 and envelope overhead; complete messages are checked before append;
- inbound active connections: min(three times maxInFlightPerPeer, 8);
- outbound accepted count per peer: maxInFlightPerPeer, including queued requests;
- aggregate outbound encoded bytes: four times maxFrameBytes;
- pending application count: maxPendingClientOperations, held through cancellation;
- aggregate pending application payload bytes: four times maxFrameBytes;
- writer queue: min(maxPendingClientOperations + three times maxInFlightPerPeer, 100000);
- canonical JSON: depth 16 and at most 100000 value nodes, with frame bounds checked
  before allocating a body and before recursive descent/container growth.

Close stops admission, exceptionally settles unresolved application work, closes
network channels, stops peer/server workers, drains/stops the ordered writer, closes
both in-memory engines and releases the store owner. Completion-callback close is
tested to avoid waiting for the writer on itself. No cancelled operation is silently
removed from committed history.

## Evidence and limits

The Java suite exercises publication gates, exact golden wire bytes, invalid framing,
private bind admission, correlation, pending/peer limits, bulk/index operations,
retired-reader isolation, follower role rejection, quorum loss and matching-history
restart. The separate-JVM gate starts three concurrent loopback voters for each case.
It records exact PIDs, raw controls/events, 7 held leader barriers and SIGKILL exits,
then copies and independently inspects each closed replica before model comparison.

The Python oracle maps independently parsed production operations, payload hashes,
incarnations and receipt voter sets into the Phase 1 model. Production record digests
are verified by the independent storage parser; the model deliberately uses its own
logical digest formula. It checks proof quorum, publication-before-success, monotonic
application progress and control-entry counters. Valid proof quorum may exist despite
a lost client response; the oracle never equates missing success with no commitment.

The process gate covers SIGKILL and actual TCP on the current host, not kernel/device
power loss. Broad deterministic network-fault schedules and repeated recovery remain
Phase 5; snapshot transfer, repair and physical compaction remain Phase 4. Paid cloud,
performance and release acceptance remain their later gates.
