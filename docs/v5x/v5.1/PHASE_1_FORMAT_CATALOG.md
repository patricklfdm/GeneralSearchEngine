# V5.1 Phase 1 automatic 1.2 byte catalog

**Status:** foundation fixture specification; production decoding/writing is disabled.
**Authority:** [accepted API/format decisions](API_FORMAT_AND_COMPATIBILITY.md), PR #184.

## Exact catalog and encodings

The complete machine-readable schema is
[format-catalog.json](../../../general-search-engine-replication/src/test/resources/replication/v51/format-catalog.json).
It supplies every supported record/message ID, ordered binary field list, JSON key
set, nested-frame type, optional discriminator, enum and finite field/count bound.
[format-fixtures.json](../../../general-search-engine-replication/src/test/resources/replication/v51/format-fixtures.json)
and [fixtures.sha256](../../../general-search-engine-replication/src/test/resources/replication/v51/fixtures.sha256)
freeze 25 storage and 19 wire projections. Kinds reserved below have only rejection
coverage. Normal verification reads these files; explicit regeneration requires review.

Every frame has the existing 48-byte envelope: four magic bytes (`GSER` storage,
`GSRP` wire), unsigned big-endian u16 major=1, minor=2, kind, zero flags, signed
big-endian i32 body length, then SHA-256(prefix16 || body), then the body. Length must
be positive and exactly consume the frame within the record/message limit. Unknown
mode/version/flags/kind, trailing bytes or wrong checksum rejects; no negotiation.

PROMISE, ENTRY, PROOF and ACCEPT bodies use their ordered `fields` arrays. Hashes
are 32 raw bytes; UUIDs are 16 bytes; positive/counter integers are signed i64;
operation is u8. Text is i32 UTF-8 byte length plus strict bytes. Blobs/nested frames
are i32 byte length plus raw bytes. Optional values are exactly u8 0 (absent) or
u8 1 followed by the value. Arrays are i32 element count followed by elements;
binary object fields follow lexicographic key order in the frozen catalog. No
unordered map iteration is allowed to define byte order. ENTRY's payload blob
includes its length and is followed by its payload SHA-256. This is explicit 1.2
encoding, not a reinterpretation of 1.1 entry bytes.

Other metadata, images and wire envelopes use canonical ASCII JSON bodies: sorted
keys, no whitespace, ASCII escapes for non-ASCII characters, no duplicate or unknown
keys, no floats/NaN, integer bounds and maximum nested depth 16. Hashes are lowercase
hex, UUIDs canonical lowercase strings, blobs/nested frames canonical RFC 4648 base64.
Schema `optional` means JSON null or the declared value; missing keys still reject.

The entry digest is the entry frame's checksum field. Re-proposal preserves the
entire immutable ENTRY frame. ACCEPT wraps the newer acceptance ballot and exact
entry; PROOF receipts bind that acceptance ballot. Receipt preimages are length-
prefixed domain string, manifest hash, voter text, i64 acceptance epoch, proposer
text, UUID incarnation, i64 slot, and entry digest, in that order. Domains are
`gse-replication/1.2/ACCEPT_ACK` and `gse-replication/1.2/PROOF_ACK`; the latter's final
hash is the full proof-record digest. These are trusted-peer integrity receipts,
not signatures or proof that an fsync happened; process evidence supplies force order.

## Files and durable ordering

Required root inventory is `replica.lock`, `manifest.gsr`, `node.gsr`, `genesis.gsr`,
`promises.gsr`, `accepted.gsr`, `proofs.gsr`, `storage-ready.gsr`,
`bootstrap-prepared.gsr`, `bootstrap-seal.gsr`. The lock is an exclusive ownership
file, not a framed record. Ledger files begin with a JOURNAL frame binding manifest,
node and payload kind, followed by same-kind frames: PROMISE=4, ACCEPT=24, PROOF=6.
ENTRY=5 exists inside ACCEPT; no bare-entry ledger can establish acceptance.

| IDs | Purpose and path |
| --- | --- |
| 1-7 | Manifest, node, journal, promise, entry, proof, storage-ready |
| 8-9 | Complete snapshot and transferable recovery image |
| 10-15 | Current-generation selector, generation inventory seal, two-source recovery floor, rebuilding marker, transfer progress, generation-started marker |
| 16-22 | Genesis, full bootstrap plan, per-voter preparation, all-three receipt, local seal, decision ledger, inventory-bound cleanup plan |
| 23 | Reserved; configured-mode replacement authority is rejected in automatic mode |
| 24-26 | Accepted ballot/value, frozen recovery basis, selected prefix/next value |

Paths for each record are in the catalog; optional root paths are listed there.
`generation-a`/`generation-b` contain snapshot, accepted/proof ledgers and generation
seal. Root promise authority survives every generation switch. A selected record
and the still-required original acceptance survive until the new ACCEPT is forced;
a selection is not an acceptance receipt. Frozen bases use at most one subdirectory
per requesting peer under `basis`; all basis/image files count against staging.
Transfer image/chunks remain bounded under `transfer`. Unknown files prevent cleanup.

Bootstrap forces all three genesis authorities and preparations before the global
PREPARING -> PREPARED -> COMMITTING -> COMMITTED decision chain. Each decision binds
plan, monotonically increasing sequence and previous frame digest; the first previous
digest is all zero. Local seals contain the full all-three receipt. Cleanup can act
only on verified inventory before COMMITTING; ambiguous/torn decisions reject.

Runtime promise, acceptance and proof ACKs require completed force first. Retries
re-force exact records without appending duplicate rows. Ambiguous authority writes
quarantine the voter. A torn required promise/proof/accepted record is never an empty
state or permission to reset a vote. Snapshot install requires a complete verified
proven prefix, retention of the accepted next value and monotonic root promise.
Physical prefix deletion still requires two complete durable recovery sources.

Generation publication writes/forces all staged files, forces their parent, forces
the pending selector, atomically replaces the selected pointer and forces its parent
before old-generation deletion. A crash must leave a complete verifiable old or new
selection; missing/ambiguous required authority fails closed. The product implementation
and pre-reopen directory inspector for these cuts belong to Phase 2.

## Wire and independent rejection

Historical wire numbers remain stable. IDs 2/3/4/13 (old activation promise, APPEND,
DURABLE_ACK and explicit activation) reject in automatic mode. IDs 17-23 are PREPARE,
PROMISE, BASIS_CHUNK, ACCEPT, ACCEPT_ACK, HEARTBEAT and HEARTBEAT_ACK. Other admitted
families have explicit 1.2 payload schemas. The envelope additionally binds exact
manifest and proposer; proposer rank is `(epoch-2) mod 3` in manifest order.
Genesis epoch 1 with absent proposer/zero incarnation is limited to handshake/status/
rejection; it never grants mutation authority. Incoming nested ACCEPT/PROOF/basis
frames are checked against the envelope's admitted manifest and voter set.

Snapshot offer/install/abort payloads use an explicit `response` boolean; requests
come from the proposer and successful replies go to it after the corresponding
durable transition. Failures use REJECT. Chunk messages distinguish REQUEST, DATA
and ACK, binding identity/offset, maxChunkBytes, chunkBytes and chunkDigest. REQUEST
has zero bytes and the empty digest; DATA has exactly chunkBytes bytes and their
digest; ACK has no data but echoes the received byte count/digest. A receiver may
request a missing bounded range; the frozen basis/image identity cannot change.
The owning transfer state must verify request/ACK correspondence before progress.

Heartbeat sequence freshness is required for an activated idle leader. During
recovery, only advancing verified stages/bytes count as progress. A heartbeat is
not a read barrier. Snapshot/basis chunks bind transfer identity, offset and digest;
a changed basis cannot be substituted under an existing basis identity.

Metadata remains bounded at 64 KiB; complete snapshots/images at 64 MiB; ancestry at
1,000,000; promises at 10,000. Automatic transport requires at least 128-KiB frames,
projects actual encoded size (including base64), and fragments large images. The
catalog's per-scalar maxima are additionally restricted by the whole-frame and
[configured bounds](API_FORMAT_AND_COMPATIBILITY.md#resource-and-timing-bounds).

The [encoder](../../../scripts/v51/format_encoder.py) and
[read-only inspector](../../../scripts/v51/format_inspector.py) share only declarative
schema data. Neither imports production readers/writers. Tests recompute checksums
for invalid fields, duplicate voters, wrong receipt domains, nested foreign manifests,
wrong proposer rank, illegal optionals, mode/version changes and sequence violations.
The fixture projections are not a bootable directory, a valid V4 application backup,
or proof of end-to-end automatic bootstrap/recovery. Product/independent directory
agreement must be earned in Phase 2; public V4 semantics in the later consumer gate.
