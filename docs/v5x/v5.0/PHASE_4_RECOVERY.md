# V5.0 Phase 4 recovery and snapshot installation

- **Status:** Accepted through protected PR #149 and exact-master CI 34950041552
- **Entry:** [Phase 4 plan](PHASE_4_ENTRY_PLAN.md)
- **Authority:** [recovery contract](PROTOCOL_RECOVERY_AND_FAILURES.md)
- **Foundation:** [Phase 2 storage](PHASE_2_STORAGE_FORMAT.md), [Phase 3 leader path](PHASE_3_LEADER_PATH.md)

## Recovery authority and publication

`ReplicaNode` serializes recovery with application writes on its existing ordered
writer. Activation probes intact voters, selects a higher epoch, and forces the new
promise on a quorum before reading the protected boundaries returned by that quorum.
A replacement disk contributes no vote. The configured leader's explicit reconstruction
requires both surviving followers to promise the new epoch.

The selected source has the highest valid committed proof, never merely the longest
entry log. Its ancestry must agree with every observed protected voter boundary and
all locally retained proofs. Conflicting valid proofs stop leader writes. Missing
committed entries or damaged promise/proof ledgers reject opening; a healthy source
cannot silently authorize a generic corrupt-store repair.

Recovery-open alone permits an incomplete final ENTRY frame. It reports a damaged
tail and cannot append to it. Only after quorum fencing and proof reconciliation may
an atomic generation installation discard an uncommitted suffix or incomplete entry.
Public read-only inspection stays strict. A locally forced valid proof survives even
when its application future did not return success. An entry without a valid proof
may be removed after fencing; a failed or cancelled future is not evidence of rollback.

The selected application cut is rebuilt privately before disk installation. After
installation, the node atomically adopts the rebuilt committed view, brings at least
one recovered follower to READY, and commits a new NO_OP through entry and proof
quorums. Only then does leader activation expose reads and accept writes. Controls do
not advance ApplicationSequence. Followers continue to reject public reads/writes.

## Catch-up and replacement

`catchUp(peer)` is an internal leader-owned maintenance operation. It fences the peer
at the active epoch, checks its protected prefix, and sends contiguous committed
entries/proofs in batches bounded by both `maxEntriesPerAppend` and encoded frame size.
Each batch installs a complete verified generation. Exact repeated batches preserve
the same committed boundary. A torn tail, unavailable retained prefix, oversized batch
or replacement voter uses a fresh immutable snapshot instead.

Snapshots travel through the existing message IDs: SNAPSHOT_OFFER, SNAPSHOT_CHUNK,
SNAPSHOT_INSTALL and SNAPSHOT_ABORT. Offers bind transfer UUID, manifest, node, total
length and SHA-256. Chunks are contiguous and forced before ACK; identical chunk retries
are safe, and conflicting or gapped chunks reject. Installation verifies the full
image digest and proof ancestry before publishing. A lost installation ACK can be
retried with the same receipt while the process lives. After restart, a new offer
clears the exact old staging members and starts again; cross-process chunk resumption
is not implemented. Staging files never become authority by themselves.

A replacement follower remains non-voting until installation includes a committed
entry from the active epoch/incarnation. Replacement identity is recorded permanently
in the root NODE body plus its required rebuilding marker; deleting the marker cannot
turn it into a genesis voter. The configured leader's erased disk requires explicit
two-survivor reconstruction. Membership and configured leadership remain fixed.

Catch-up runs during activation and explicit maintenance. This candidate does not add
a background catch-up scheduler or a public bootstrap workflow.

## Immutable application cut

`ReplicaSnapshot` retains an ordered ancestry anchor for each logical position,
its terminal proof, and canonical application bytes. Each anchor contains epoch,
incarnation, operation, original entry digest and payload digest. Index and predecessor
are implicit in ordered ancestry. Same-epoch anchors must share an incarnation.
The terminal proof still binds configured distinct voter receipts and exact predecessor.

Application bytes contain format version 1, sorted registered built-in index
descriptors, and ordered live key/document codec bytes. Reconstruction validates keys,
codecs, duplicate keys, descriptor order and exact canonical re-encoding, then replays
the committed tail. Live document order, query tie order, updates/removals and index
lifecycle are checked against published V4.4. Private internal IDs may be renumbered;
this is not a stable internal-ID export. Rebuild uses ordinary in-memory engines and
never opens a V4 WAL as a competing replicated authority.

## Disk publication and format

The original seven root members and normal Phase 2 records remain readable and their
golden bytes are unchanged. Root promises and the exclusive owner FileLock are never
replaced with a generation. The extension uses GSER 1.0 framing (48-byte header),
big-endian integers, length-prefixed blobs/text and existing identity/digest rules.
Record IDs 1–7 retain their meanings. A replacement NODE body adds exactly one trailing
byte `1`; a normal NODE body has no extension. Mixed candidate-runtime interoperability
is not claimed.

| Kind | File or payload | Body after the GSER header |
| --- | --- | --- |
| 8 | `snapshot.gsr` | Manifest digest, anchor count, 89-byte anchors, complete terminal proof blob (empty only at zero), application blob |
| 9 | Recovery transfer image | Snapshot blob, count and complete ENTRY blobs, count and complete PROOF blobs |
| 10 | `current.gsr` | Manifest, node, generation slot name, generation UUID, seal digest, admission flag (0/1) |
| 11 | `generation.gsr` | Manifest, node, generation UUID, snapshot digest, entry/proof journal-header digests |
| 12 | `recovery-floor.gsr` | Manifest, node, floor index, ancestor digest, two/three sorted distinct configured source voter IDs |
| 13 | `rebuilding.gsr` | Manifest and replacement node identity |
| 14 | `transfer/offer.gsr` | Manifest, node, transfer UUID, image length, image SHA-256 |
| 15 | `generation-started.gsr` | Manifest and node identity |

Only `generation-a` and `generation-b` are legal generation directories. The selected
one must contain exactly snapshot, entry journal, proof journal and seal. Journal
headers retain the Phase 2 node/group/kind identity. Tail entries/proofs are validated
individually, including their chain to the snapshot. No unselected staging file can
provide a committed cut. Inventory validation rejects unknown names, links and
incomplete selected generations; partial inactive staging is restartable.

Installation writes and forces each staged member and its directory, then atomically
renames the forced `current.pending.gsr` over `current.gsr` and forces the parent.
A completed installation also forces `generation-started.gsr`; writable reopen ensures
that marker when a valid selector exists. Missing selectors after completed publication
reject instead of falling back to the legacy root. During first-publication interruption,
the previously selected complete generation or legacy history remains available.
These guarantees assume the recorded force/atomic-rename filesystem contract, not
arbitrary simultaneous deletion of independent authority files.

## Recovery floor and physical compaction

Before removing an older recovery source, the coordinator verifies two distinct
configured voters hold equivalent complete recovery representations at the cut. A
source can be an installed snapshot or a complete proven log. The local floor record
binds their identities, cut and ancestor digest and is atomically published and forced.
The local installed snapshot must cover that floor. Merely advertising a higher log
index never grants compaction authority.

Cleanup deletes only exact known inactive generation members and truncates legacy
entry/proof journals to their immutable headers. Root promises and initialization
metadata survive. Interrupted cleanup can repeat after reopen. A lost floor ACK leaves
a complete retained source. A new generation cannot overwrite an older slot while its
required source is still protected by a lower floor. This may reject with capacity
exhaustion until quorum recovery is available.

## Bounds and evidence limits

Snapshot and complete recovery image bytes are bounded by the smaller of
`maxSnapshotStagingBytes` and 64 MiB. Transfer metadata also consumes staging capacity;
there are at most 100,000 chunks, one incoming stage and one immutable exported image.
Encoded base64 and envelope sizes reduce effective chunks below the configured chunk
limit when necessary. Generation publication reserves metadata space and checks
retained, staging and aggregate disk bounds before writing. Registered indexes have
a 10,000-descriptor cap, in addition to the existing payload/JSON/document bounds.

Snapshots retain at most 1,000,000 ancestry anchors, so compaction removes historical
application payloads without promising unlimited lifetime history. Image encoding,
validation and private reconstruction can hold multiple bounded byte copies and
application engines. This is a correctness candidate; Phase 6 must measure memory,
latency and throughput before any performance claim.

The Phase 4 process gate runs 17 cases with three concurrent JVMs: maintenance and disk
replacement, 12 checkpoint publication/floor/cleanup SIGKILL cuts, two uncertain-mutation
cuts, and two interrupted follower transfers. Six corruption cases must reject in both
Java and an independent Python parser without changing retained bytes. The Python
producer's new golden fixture is format evidence only, not bootstrap authority.

The recovery oracle independently replays application state, preserves observed proof
prefixes and successful boundaries, validates voter/floor evidence, and compares actual
query/document/index state with checksum-pinned published V4.4 loaded in a separate
control JVM. The existing Phase 1 model and Phase 2/3 gates remain separate checks;
the recovery oracle does not invent historical proof copies removed by compaction.
SIGKILL evidence covers process failure, not kernel or device power-loss certification.

Public engine/bootstrap entry points remain reserved until complete offline group
bootstrap and lifecycle admission are reviewed. No paid cloud, election, membership
change, signed release or completed-V5 claim follows from this local candidate.
