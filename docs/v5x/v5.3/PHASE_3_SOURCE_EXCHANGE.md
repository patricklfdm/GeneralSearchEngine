# Phase 3B — complete original-source exchange

Status: locally qualified. This connects [TCP transport](PHASE_3_TRANSPORT.md),
[original export ownership](PHASE_3_SOURCE_EXPORT.md) and
[complete receiving scratch](PHASE_3_SOURCE_RECEIVE.md) using the existing 1.3 wire
frames. The complete [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open.

## One serial source session

`MembershipSourceSession` takes ownership of one actual exclusive writer's export
for one exact reader, root, view, ballot and trace. It exposes only that original
PROMISE, BASIS, packet and declared images. It does not resample the latest source.
The reader must be a permanently reserved identity; the existing contextual wire
checks enforce voter/learner traffic eligibility. Historical/newer-view discovery
and learner export registration are separate protocol work.

The protocol uses unchanged fields and bytes:

1. A CHUNK REQUEST with a new transfer ID, offset zero, empty bytes and a known
   reference asks for a SOURCE_OFFER. The offer gives the actual complete content
   hash, length and kind. The BASIS's capsule hash refers to its complete packet;
   that offer's digest is the packet-file hash. The receiver later verifies the
   original capsule/inventory binding, rather than assuming the two hashes match.
2. Subsequent CHUNK REQUESTs for that transfer use the offered file hash and exact
   next offset. DATA binds the same ID/start offset and hashes its actual bytes.
   Base64 expansion plus the complete envelope must fit the caller's frame bound;
   decoded bytes also fit the source session's chunk bound. The receiver checks
   its own frame/chunk bounds. Runtime registration must supply compatible peer
   chunk bounds; this wire format does not negotiate a new limit.
3. Only after complete hash, typed validation and (for scratch files) force does
   the receiver send TRANSFER_COMMIT. The sender checks that it supplied the
   complete extent and echoes the exact transfer/hash. This is read-only transfer
   completion, **not** a remote installation/voting ACK.

The source retains only the last exact request digest and response for replay.
Every new request has the next sequence; each transfer ID and content can be used
only once in that session. At most ten members (two original records, one packet
and seven images) can be offered. A completed transfer ID cannot identify another
member. The immutable last response supports a lost offer, data or commit reply
without duplicating bytes or renewing the original deadline. Older, changed,
reordered or foreign exchanges cannot advance the source.

Session metadata and cached replies reserve shared CONTROL capacity. A DATA
response's exact encoded extent is reserved before reading/encoding its chunk.
The transport owns its separately counted send/receive frames. Expiry, invalid
session traffic and close release the session's cache and export borrow. The
runtime must explicitly close abandoned sessions; no background reaper is claimed.
Server exceptions close that attempt without manufacturing a durable REJECT.

## Complete pull and failure handling

`MembershipSourcePull` starts with a known exact BASIS digest and verified current
root/identity context. It fetches and validates the actual BASIS, derives only the
reference for its matching PROMISE, then fetches that actual original record too.
Untrusted record lengths are checked against their typed maxima before allocation;
their buffers retain CONTROL reservations until the source scratch owns its copy.
No placeholder basis identity is introduced to fetch the initial referenced record.

The packet and all declared images go through `MembershipSourceReceive`; transfer
IDs in its bindings are the same IDs carried on the wire. Every operation shares
one original start/deadline and a required runtime fencing guard. A pull is single
use. Its returned scratch remains borrowed and resource-accounted until close.
Data/packet hashes and the complete received inventory are rechecked before return.

Only classified transport I/O/per-attempt deadline failures are retryable. Each
exchange uses identical bytes and at most three attempts (or a smaller caller
retry limit). Capacity, protocol, closed transport, malformed replies, explicit
REJECT, semantic/storage failure, cancellation and the original deadline abort.
The original REJECT is preserved for the runtime to process its higher promise;
this byte-delivery component does not itself allocate or fence a journal ballot.
There is no workload/client mutation retry and no nested transport retry loop.

Cancellation cancels pending I/O. Failure after writing a packet or preallocating
images closes the owned scratch and releases its reservations after deletion;
cleanup errors remain attached and cannot justify deleting uncertain paths.
Source authority files remain unchanged. Received bytes do not create `Owned`
observations: full capsule/ancestry authority validation and selected installation
still belong to the live protocol owner.

## Evidence boundary

The real TCP test uses public offline bootstrap at sizes 3/4/5, actual forced
grants and source files. It records every request/reply and the complete received
files. The independent reader reconstructs original storage first, then checks
the exact ordered record/packet/image offers, chunks, commits, permanent identities,
session/transfer IDs, root/view/ballot, hashes and unchanged final authority files.
It checks the original before 13 exact negative variants. That is complete source
delivery evidence, not a distributed election or ready learner qualification.

Remaining: generic referenced voting-record service, live activation integration,
newer-prefix discovery/adoption, failed-source rotation, abandoned-scratch restart
recovery, learner/joint completion and full distributed S/N evidence. Public APIs,
protected CI, cloud execution and Phase 3 closure are not enabled by this batch.

The [local receipt](phase3-evidence/source-exchange.json) binds 43 focused Java
tests across seven suites, including 14 exchange tests, and all 545 V5.3 Python
tests in normal and optimized modes. The final three-size trace contains 45 TCP
exchanges; its 13 exact negatives pass in normal, optimized and relocated replay.
The receiving component's original physical evidence also replays unchanged.

A new regression first demonstrated reuse of a previously completed transfer ID
for a different member. The session now retains a bounded set of used IDs as well
as content identities; that regression and the complete focused suite pass after
the correction. Its failed log, reports, source index and earlier artifact remain
retained. These small-source functional runs do not establish maximum-envelope
network throughput or a failover latency guarantee.
