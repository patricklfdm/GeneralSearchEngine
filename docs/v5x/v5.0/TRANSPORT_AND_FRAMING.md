# V5.0 Phase 1 transport and frame decision

- **Status:** Candidate decision for protected Phase 1 review
- **Protocol:** `gse-replication/1.0`
- **Production networking:** disabled in Phase 1

## Transport dependency

The production transport will use the Java 21 `java.base` NIO TCP channels and
selector API. There is no additional Maven networking dependency. The replication
artifact owns the transport; core and processor remain independent. Phase 1 contains
only independent fixture codecs and tests, not a listening endpoint.

Each peer connection has one ordered outbound frame queue and one incremental inbound
decoder. Reads/writes may be partial; completion of a socket write is never a durable
ACK. The configured frame, queue, in-flight, retry and timeout limits apply before
allocation/admission. A disconnected or slow peer cannot grow an unbounded queue.
Production bind admission must resolve addresses and reject wildcard/public binds;
tests may use loopback, deployment uses private addresses. DNS labels alone do not
prove a private bind. TLS and peer authentication remain outside the accepted scope.

JDK references: [SocketChannel](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/nio/channels/SocketChannel.html),
[ByteBuffer](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/nio/ByteBuffer.html).

## Exact frame envelope

Integers in the header are unsigned, big endian. No padding or native Java object
serialization is permitted.

| Offset | Size | Meaning |
| --- | ---: | --- |
| 0 | 4 | ASCII `GSRP` |
| 4 | 2 | Protocol major: 1 |
| 6 | 2 | Protocol minor: 0 |
| 8 | 2 | Message ID from the frozen registry |
| 10 | 2 | Flags: 0; unknown bits rejected |
| 12 | 4 | Body byte length, excluding the 48-byte envelope |
| 16 | 32 | SHA-256 of bytes 0–15 followed by the complete body |
| 48 | variable | Canonical JSON body encoded as ASCII |

The 8-MiB default and 64-MiB absolute maximum apply to **the entire frame**.
Check the declared length before body allocation. An incomplete stream frame waits
within the request timeout; an offline complete-frame inspector rejects truncation
or trailing bytes. Unknown major/minor, flags or message ID fails closed. A future
minor requires negotiated capabilities and reviewed fixtures before use.

The body has exactly these keys: `protocol`, `groupId`, `configurationId`, `sender`,
`recipient`, `epoch`, `incarnationId`, `traceId`, `eventSequence`, `type`, `payload`.
The three UUIDs use lowercase canonical hyphenated text. Member/configuration IDs
match `[a-z0-9][a-z0-9._-]{0,127}`. Epoch and event sequence are nonnegative signed
64-bit integers; epoch zero is allowed only in HANDSHAKE/REJECT before activation.
The header message ID and body type must agree. Every message binds the same common
identities, including replies and snapshot chunks.

Canonical JSON rules are: ASCII object keys matching `[A-Za-z][A-Za-z0-9_]*`, sorted
lexicographically at every level; no insignificant whitespace; arrays retain order;
only objects, arrays, strings, booleans, null and signed 64-bit integers; no floats.
String escaping matches JSON `ensure_ascii`: escape quote/backslash, use the short
escapes for backspace/form-feed/newline/carriage-return/tab, use lowercase `\uXXXX`
for other controls and code units outside printable ASCII (including DEL), and
represent supplementary characters as surrogate pairs. Maximum nesting is 16.
Re-encoding must reproduce the body bytes, so duplicate keys/noncanonical numbers or
escapes are rejected. Binary payload fields use padded standard base64; their encoded
size counts against the total frame bound. For example a default 4-MiB snapshot chunk
must also fit its base64 and envelope overhead inside the 8-MiB frame.

This decision freezes framing and the common envelope. Entry/proof/snapshot payload
examples are logical fixtures; complete production payload codecs and storage bytes
remain subject to the Phase 0 identities and later phase-specific format review.
Placeholder payload digests in the examples are not production-valid commit proofs.

## Registry and compatibility examples

IDs 1–12 preserve the existing logical fixture names in order: HANDSHAKE,
ACTIVATION_PROMISE, APPEND, DURABLE_ACK, COMMIT_PROOF, COMMIT_PROOF_ACK,
COMMIT_ADVANCE, CONFLICT, AUTHORITY_STATUS_PROBE, SNAPSHOT_OFFER, SNAPSHOT_CHUNK,
SNAPSHOT_INSTALL. IDs 13–16 are ACTIVATE_EPOCH, AUTHORITY_STATUS, SNAPSHOT_ABORT,
REJECT. IDs are never reused.

COMMIT_ADVANCE corresponds to the contract's ADVANCE_COMMIT; SNAPSHOT_OFFER and
SNAPSHOT_INSTALL correspond to SNAPSHOT_BEGIN and SNAPSHOT_COMPLETE. These are
spelling aliases for the existing transitions, not different operations.

The exact registry and golden frames for every message family live in
[`v50-wire-fixtures.json`](../../../general-search-engine-replication/src/test/resources/replication/v50-wire-fixtures.json).
Python independently checks canonical envelopes and malformed-frame rejection; a
Java test independently checks header layout, lengths and SHA-256 using JDK APIs.

## Executable model traces

`DeterministicTransport` serializes payloads by digest along with the schedule.
Replay executes drop, duplicate, absolute-tick delay/reordering, bidirectional
disconnect and explicit reconnect. `ModelNetwork` drives the independent model;
entry force and delivery of its ACK are separate events, as are proof force and ACK.
Rejection remains in the replay transcript and does not prevent a later retry.

This is logical safety evidence. The model tracks no real filesystem crash or
application document corpus; full recovery and equality with the V4.4 search-state
oracle remain later production-matrix work. The process harness currently validates
fixture lifecycle and classified exits, not the frame/force barriers of a production
replica.
