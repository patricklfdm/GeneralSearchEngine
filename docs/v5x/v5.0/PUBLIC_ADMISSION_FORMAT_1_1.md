# Public admission: replicated storage and wire 1.1

- **Status:** Step A bytes accepted in PR #153; [Step B](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md) implements offline writers; public runtime remains Step C
- **Authority:** [Accepted amendment](PUBLIC_ADMISSION_CONTRACT.md), [API](PUBLIC_ADMISSION_API.md)
- **Frozen bytes:** [fixture catalog](../../../general-search-engine-replication/src/test/resources/replication/v50-admission-fixtures-v2.json), [SHA-256](../../../general-search-engine-replication/src/test/resources/replication/v50-admission-fixtures-v2.sha256)
- **Independent readers:** [Python](../../../scripts/v50/admission_format.py), [Java test oracle](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionOracle.java)

## Version boundary

Public startup requires exact `gse-replicated (1,1)` authority and a completion seal.
Wire peers require exact `gse-replication/1.1`; there is no downgrade, implicit upgrade
or mixed-minor group. The public PROTOCOL constant changes to 1.1; recompile unpublished
V5 consumers that inlined 1.0. The Phase 1–5 internal runtime remains explicitly 1.0
until Step C. It does not obtain a 1.1 identity by reading the new public constant.
All historical 1.0 fixtures, readers and gates remain under their original rules.

This document fixes the bytes B/C must implement. It does not claim that decoding a
fixture performs typed V4 verification, acquires ownership or forces a remote disk.
The fixture source members are deliberately labelled synthetic provenance samples;
pinned published V4.4 import/export and real crash evidence are Step B/C gates.

## Scalars, bounds and digest domains

All integers are big endian: u8/u16/i32/i64 occupy 1/2/4/8 bytes. Counts and lengths
are nonnegative i32; allocation checks also require the count to fit remaining bytes.
`uuid` is 16 bytes in Java UUID most-significant/least-significant long order.
`hash` is 32 raw SHA-256 bytes. JSON digests are exactly 64 lowercase hex characters.
`blob` is i32 byte length then bytes; zero length is allowed only where specified.
`text` uses the same length prefix and strict UTF-8, with no terminator or malformed
surrogates. Empty text is forbidden. No complete record permits trailing fields.

The common frame is the [Phase 2 envelope](PHASE_2_STORAGE_FORMAT.md#scalars-and-common-record-envelope),
with minor **1**: magic `GSER`, u16 major 1, u16 minor 1, u16 kind, u16 flags 0,
i32 positive body length, hash(prefix bytes 0–15 + body), body at offset 48.
The embedded checksum is the **record digest**; it differs from SHA-256 of the
complete file. Inventories hash complete file bytes, including headers/checksums.
Nested records use complete frames, not bodies or unframed checksums.

| Binding | Exact SHA-256 input |
| --- | --- |
| Frame / manifest / genesis / plan / preparation / receipt / seal / journal row | Its 16-byte prefix followed by its body; version and kind provide separation |
| Complete file in an inventory | All file bytes (empty lock hashes SHA-256 of empty input) |
| Payload inventory | ASCII `gse-v50-payload-inventory-v1`, one NUL byte, canonical inventory encoding below |
| Application history | First 16 bytes of SHA-256(ASCII `gse-v50-application-history-v1`, one NUL byte, group uuid) |
| Index configuration | SHA-256 of canonical JSON array of **descriptor strings**, sorted by Java String order, as in Phase 3 |
| Durable entry receipt | `text("gse-replication/1.1/DURABLE_ACK")`, manifest hash, voter text, i64 epoch, incarnation uuid, i64 index, entry hash |
| Payload / transfer image | SHA-256 of the exact payload / complete image frame bytes |

A derived application history of zero, or equal to the imported source history,
rejects. No UUID version/variant bits are rewritten. Source history stays separate.
The genesis has no manifest hash; the manifest binds the genesis, avoiding a cycle.
The plan excludes journal/preparation/receipt/seals from its payload inventory.
Preparations bind the plan; a receipt contains the complete plan and preparations;
a local seal contains that receipt. None of these records hashes itself recursively.

Every metadata **frame**, including nested plan/receipt/seal overhead, must fit 64 KiB.
Geneses, snapshots and complete recovery images each fit 64 MiB and each local
`maxSnapshotStagingBytes`, including the 48-byte frame. Source/operation byte bounds
are positive and at most 1 TiB. All arithmetic uses checked addition/multiplication.
There are at most 10,000 indexes, 1,000,000 ancestry anchors, 10,000 promises and the
existing core document/key/bulk limits. A document count must also fit its enclosing
snapshot bytes. Descriptor strings use the existing 1024-byte field-name and
8192-byte individual descriptor bounds. The receipt bound can reject a plan whose
standalone frame would fit: planning must project all nested completion records.

### Inventory encoding

`i32 count`, then each member: `text relativeName`, `u8 kind`, `i64 size`, `hash`.
Kind 0 is a directory (size zero, all-zero hash); kind 1 is a regular file. Names are
nonempty UTF-8, at most 4096 bytes, strictly sorted by unsigned UTF-8 bytes, unique,
relative, slash-separated, with no empty, dot, dot-dot, NUL or backslash components.
Count is at most 10,000 and must fit its metadata record. Size is 0–1 TiB.
Runtime checks reject symlinks, hard links, aliases and unexpected files before using
an inventory. A hash of a path string is never evidence of exclusive ownership.

## Manifest, genesis and application bytes

**MANIFEST, kind 1, `manifest.gsr`:** the ordered Phase 2 manifest fields, with both
embedded storage/protocol versions set to `(1,1)`, followed by:

```text
hash genesisDigest
uuid applicationHistory
i64 baseApplicationSequence
```

Group UUID is nonzero; epoch is exactly 1; schema version is exactly 1; codec version
is positive. Node/config/codec/schema IDs, the three ordered unique voters, private
endpoint admission and configured leader retain their existing bounds. Member order
is identity. Paths and builder tuning do not become manifest identity.
`indexConfigurationDigest` describes the active genesis indexes.

**GENESIS, kind 16, `genesis.gsr`:**

```text
u16 projectionVersion = 1
uuid groupId
blob sourceDescriptor
uuid applicationHistory
i64 baseApplicationSequence
blob applicationState
```

`sourceDescriptor` is the following ordered, unframed metadata-bounded encoding:

```text
u8 sourceKind                 # 0 EMPTY, 1 VERIFIED_V44_BACKUP
text family
u16 major
u16 minor
text profile
uuid sourceHistory
i64 sourceSequence
inventory sourceMembers
```

EMPTY is exactly `none, 0, 0, none, zero UUID, 0, empty inventory`; it has no source
path and no documents. Its configured indexes remain in applicationState. Backup is
`gse-backup, 1, minor 0/1/2`; profile is `full` for 0/1 and `canonical-only` for 2.
Its source history is nonzero, sequence is 0–Long.MAX_VALUE-1, and inventory contains
exactly `gse-backup-checkpoint`, `gse-backup-manifest`, `gse-backup-metadata`, all
nonempty regular files. Family/profile is a canonical provenance projection of the
verified V4 format; it does not change any V4 bytes. Base sequence equals source
sequence. EMPTY base is zero. A base of Long.MAX_VALUE cannot continue and rejects.

`applicationState` retains the Phase 4 application encoding: u16 version 1, i32 index
count, canonical JSON descriptor texts sorted uniquely by **field name in Java String
order**, i32 document count, then ordered `(blob canonicalKey, blob canonicalDocument)`
pairs. Descriptor keys are exactly `analyzer`, `field`, `kind`; kinds are equality,
range, prefix, text. Analyzer is empty for the first three, `gse-simple-v1` for text.
Keys are unique. Codec canonical re-encoding and document/key agreement are typed
Step B checks. Live-document order is source order; never sort it by key.
The genesis remains immutable and retained after every compaction.

At index zero, applicationState must be loaded even with commit/applied/snapshot index
zero. It contributes base sequence S without an ENTRY or fabricated quorum proof.
The first application entry at LogIndex 1 contributes S+1; controls contribute zero.

## Existing record families under 1.1

Kinds 2–15 keep the [Phase 2](PHASE_2_STORAGE_FORMAT.md) and
[Phase 4](PHASE_4_RECOVERY.md#disk-publication-and-format) ordered fields and validation
rules, with the following explicit changes. All nested GSER frames also use 1.1.

| Kind | Exact change |
| --- | --- |
| 2 NODE | Always append u8 origin: 0 bootstrap, 1 replacement. Unknown values reject; missing byte rejects. Replacement requires kind 13 rebuilding marker regardless of any completion seal. |
| 3 JOURNAL_HEADER | No body change: manifest hash, local node text, u16 record kind. |
| 4 PROMISE | No body change; initial epoch 1/zero incarnation, real epochs at least 2/nonzero incarnation. |
| 5 ENTRY | No body change or operation renumbering; predecessor at zero is the amended manifest hash. |
| 6 PROOF | No body change; receipt hash domain is now `gse-replication/1.1/DURABLE_ACK`. |
| 7 STORAGE_READY | No body change; still binds five root/header hashes and **does not authorize public startup**. |
| 8 SNAPSHOT | Ordered body: manifest hash, **i64 base sequence, i64 application sequence**, i32 anchor count, 89-byte anchors, terminal PROOF blob, application blob. |
| 9 RECOVERY_IMAGE | Snapshot blob, i32 entry count + ENTRY blobs, i32 proof count + PROOF blobs; all exact 1.1, same amended manifest. |
| 10–15 | No body changes; selectors, seals, recovery floor, rebuilding, transfer offer and generation-started all bind the amended manifest. |

SNAPSHOT's base must equal the manifest. Its application sequence must equal base
plus count of operation IDs 1–8 in the complete ancestry, using checked arithmetic.
IDs 9 NO_OP and 10 SNAPSHOT_MARKER advance only LogIndex. A nonzero snapshot requires
its exact terminal proof and sorted distinct two/three voter receipts. At zero, the
proof blob is empty and application bytes equal genesis application bytes exactly.
A snapshot with another base, invented control sequence, wrong predecessor or old
receipt domain rejects even if its outer checksum has been recomputed.

## Plan and three-member publication records

### PLAN, kind 17, `plan.gsr`

```text
u16 descriptorVersion = 1
blob canonicalJsonDescriptor
blob completeManifestFrame
blob sourceDescriptor
i64 completeGenesisFrameLength
inventory node1Payloads
inventory node2Payloads
inventory node3Payloads
```

The JSON descriptor uses the canonical ASCII JSON rules in
[the wire specification](TRANSPORT_AND_FRAMING.md#exact-frame-envelope): exact keys,
sorted objects, preserved arrays, signed 64-bit integers, no floats, depth at most
16, canonical escaping, duplicate-key rejection and byte-identical re-encoding.
The following keys are exhaustive. Strings in this descriptor are nonempty unless
explicitly allowed; paths are absolute normalized local paths, not URIs.

| Object | Exact keys and interpretation |
| --- | --- |
| root | `operation`, `source`, `maxSourceBytes`, `maxOperationBytes`, `application`, `replicas` |
| path binding (`operation`, non-null `source`, each target/materialization directory) | `path`, `parentRealPath`, `fileStoreName`, `fileStoreType`, `parentFileKey`; strings bounded to 4096 UTF-8 bytes. Capture the real existing parent and stable local file-store/file-key observations; absent/unavailable identity rejects. Root parent may be `/`. Source uses its existing directory's parent. Apply rechecks actual resolved identity under ownership. |
| source | null for EMPTY, otherwise path binding |
| application | `documentType` (binary class name), `idField` (canonical field name), `fields`, `textFields`, `indexes`, `snapshot`, `planner` |
| fields | array sorted uniquely by Java String field name; each `{name,type}`, type is `Class.getName()`; includes ID and every registered field |
| textFields | array sorted uniquely by field name; each `{field,analyzer}`; analyzer `gse-simple-v1`; field must be registered |
| indexes | exact captured builder index descriptor strings in startup order; same active descriptor set as genesis, with no duplicates; order stays bound into the plan |
| snapshot | `queueCapacity`, `maxBatchSize` (positive i32), `maxBatchWaitSeconds` (nonnegative i64), `maxBatchWaitNanos` (0–999999999), exact Duration components |
| planner | `COST_AWARE`, `FORCE_INDEX` or `FORCE_SCAN` |
| replicas | exactly three local descriptors in manifest member order |
| local descriptor | `node`, `target` path binding, `materialization`, `replicationBounds` |
| materialization | `directory` path binding, `format`, `storageIdentity`, `schemaIdentity`, `codecId`, `codecVersion`, `bounds` |
| format | `{family,major,minor}`; exact `gse-durable` 1.0/1.1/1.2 |
| materialization bounds | `maxEncodedKeyBytes`, `maxEncodedDocumentBytes`, `maxBulkElements`, `maxDocuments`, `checkpointWalBytes`, `maxRetainedBytes`, `maxDerivedStateBytes`; exact captured core values, including inactive V4 tuning |
| replicationBounds | `maxFrameBytes`, `maxEntriesPerAppend`, `maxInFlightPerPeer`, `maxPendingClientOperations`, `maxRetryAttempts`, `requestTimeoutMillis`, `retryBackoffMillis`, `snapshotChunkBytes`, `maxRetainedLogBytes`, `maxSnapshotStagingBytes` |

All numeric fields obey their existing core/replication maxima and cross-field
constraints, plus the amendment's aggregate source/operation/snapshot limits. All
local application identity/format values agree and match manifest/genesis. Schema
lambdas, comparator implementations and codecs are represented by the operator's
stable schema/codec identity, not an invented hash of JVM object identity. Captured
schema/index descriptors preserve canonical fields; runtime typed validation still
rejects unsupported implementations. Path aliases/ancestry across source, targets,
materialization anchors and operation directory reject. Directory relocation after
successful bootstrap does not change group identity.

Each payload inventory has exactly the sorted eight root names: `entries.gsr`,
`genesis.gsr`, `manifest.gsr`, `node.gsr`, `promises.gsr`, `proofs.gsr`, `replica.lock`,
`storage-ready.gsr`. Every item is a file. Lock is empty; promise journal includes the
initial promise; entry/proof journals contain only their headers. Root NODE origin
is 0. These are **initial bytes**, never a requirement that a live journal remain
unchanged after valid startup. Preparation and seal are deliberately excluded.

`planDigest` is the kind-17 record digest, rendered lowercase hex in Java. Planning
constructs this same deterministic frame in memory without creating a target. Apply
rebuilds and compares its complete bytes under ownership before the first write.
Projection includes simultaneous metadata/staging copies, all three node outputs,
journal rows and pending receipt/seal copies in `maxOperationBytes`; each node also
checks retained/staging budgets. No capacity estimate may omit nested receipt copies.

### PREPARATION, kind 18, `bootstrap-prepared.gsr`

Ordered fields: plan hash, manifest hash, node text, payload inventory hash. Each node
receives its own record after all eight planned payloads and directory entries were
forced and independently reread. It is not a voting seal.

### GLOBAL_RECEIPT, kind 19, `receipt.gsr`

Ordered fields: complete PLAN blob, i32 preparation count = 3, then three complete
PREPARATION blobs in manifest member order. Each preparation binds the same plan,
manifest and its matching payload inventory. Duplicate/reordered/missing nodes,
foreign plans or mismatched inventories reject. Manifest/genesis/history/base are
available through the embedded plan; genesis bytes are referenced by hash and length.
The receipt has no timestamp, random operation ID or mutable current status.

### LOCAL_SEAL, kind 20, `bootstrap-seal.gsr`

Ordered fields: local node text, complete GLOBAL_RECEIPT blob. Verify that the node
is the corresponding manifest voter, all three preparations are valid, and local
manifest/genesis/history/base agree. Startup reads the local seal and retained local
preparation; it needs no source backup or coordinator directory after delivery.
An exact already-published seal can be verified/re-forced on resume, never overwritten
with different bytes. A replacement can receive a seal for its existing NodeId using
the original committed receipt, but NODE origin 1/rebuilding still prohibits voting.

### OPERATION_ROW, kind 21, append-only `operation.gsr`

Ordered fields: plan hash, i64 row sequence, previous row hash, u8 phase, three
preparation hashes in manifest order, decision receipt hash. Row sequence starts at
1, previous hash starts all-zero, every row is complete/checksummed, maximum 64 KiB.
No torn or unknown tail authorizes cleanup or successful resume.

| Phase ID | Meaning | Preparation hashes | Decision hash |
| --- | --- | --- | --- |
| 1 | PREPARING, first row | all zero | zero |
| 2 | PREPARED, after 1 | all three verified preparation digests | zero |
| 3 | COMMITTING, after 2 and forced before receipt publication attempt | same three | zero |
| 4 | COMMITTED, after forced receipt rename and parent force | same three | receipt digest |
| 5 | ABORTING, only after 1 or 2 | unchanged from previous row | zero |

Repeated operations do not append duplicate phase rows. Cleanup cannot transition
out of 3/4/5 into preparation. ABORTING is permanent, and cleanup resumes only the
same ownership-bound deletion plan. A present receipt with a COMMITTING journal is
an interrupted committed publication: reverify and force receipt/parent, append and
force COMMITTED, then deliver seals. A missing receipt after COMMITTING is ambiguous;
resume must prove the exact pending receipt/owned prepared set or fail closed.
Local delivery starts only after phase 4 is forced. The fixture oracle's successful
full-publication path requires all four rows; negative traces cover earlier seals.
It does not infer a force from byte presence; real force/crash barriers belong to B.

## Filenames, staging, cleanup and replacement

Fresh node authority consists of the eight initial payload files plus
`bootstrap-prepared.gsr` and `bootstrap-seal.gsr`. Preparation alone cannot start.
After startup the two generation slots, transfer directory and known Phase 4 marker
names remain legal. Genesis, manifest, root identity, preparation and completion seal
are retained across compaction. Unknown filenames, unexpected links or missing
required records fail closed. Kind 7 alone never substitutes for kind 20.

The coordinator owns `operation.lock` (empty), `plan.gsr`, `operation.gsr`,
`receipt.pending.gsr`, `receipt.gsr`, and, only during cleanup, `cleanup.gsr`.
Node bootstrap publication may temporarily contain `bootstrap-seal.pending.gsr`.
These pending files carry complete final-format bytes and confer no authority until
atomic publication and parent force. Other staging names are forbidden. Partial
initial payloads are recognized only under exact PREPARING ownership and cannot open.
The operation lock is kept until all target owners and accepted file writes quiesce.

**CLEANUP_PLAN, kind 22, `cleanup.gsr`:** operation plan hash, observed journal-tail
hash, blob canonical cleanup descriptor. Exact JSON keys: `operation`, `inventory`,
`deletePaths`. `operation` is the same path binding as PLAN. `inventory` is sorted
by absolute normalized UTF-8 path and contains `{path,kind,size,digest,owner}` for
**every observed member**, including protected survivors. Kind is `file`/`directory`;
directory size/hash is 0/all-zero; `owner` is the original plan digest for proven
owned output or `source` for protected input. `deletePaths` is a unique array of exact
inventory path strings, files before their containing directories, operation marker
and directory last. No `source` member may appear. Inventory digest is SHA-256 of
ASCII `gse-v50-cleanup-inventory-v1`, NUL, canonical JSON inventory bytes; Java cleanup
`planDigest` is the kind-22 frame digest. The observed tail is a proven
PREPARING/PREPARED row. Planning is read-only. Apply
rechecks the exact inventory, exclusively publishes/forces the cleanup plan, then
appends/forces the deterministic ABORTING row linked to that observed tail before
removing anything. Resume requires that same retained plan and exact ABORTING
transition; it admits only the already deleted prefix of its ordered deletion set.
The journal's deliberate ABORTING append is validated against the planned predecessor
and row encoding, rather than mistaken for an arbitrary inventory change. Unknown
members, changed surviving payloads or a global receipt reject. Each deletion forces
its parent. The cleanup plan file is excluded from the inventory that would bind its
own bytes; the plan and journal are retained as deletion authority and removed last.
Their deletion is an explicit final step after every ordinary listed member is gone.

**REPLACEMENT_PLAN, kind 23, `replacement-plan.gsr`:** u16 descriptor version 1,
complete original GLOBAL_RECEIPT blob, blob canonical replacement descriptor,
inventory complete closed source members. Exact descriptor keys: `operation`,
`source`, `configuration`, `manifestDigest`, `genesisDigest`, `sourceInventoryDigest`.
Operation/source are path bindings; configuration is the complete PLAN local
configuration schema (same manifest membership is supplied by embedded receipt).
The inventory includes the closed source's genesis, seal, headers, journals, selected
and retained generations and known markers; it uses the inventory encoding above,
with `sourceInventoryDigest` using the payload-inventory domain. Source selection
must independently verify a complete recovery representation. The plan is at most
64 KiB including its receipt; reject if it cannot fit.

Replacement coordinator inventory is `operation.lock`, `replacement-plan.gsr`,
`replacement.gsr` (kind 21 with the replacement plan digest), and
`replacement.pending.gsr` (the exact row pending atomic publication). It uses phase 1
PREPARING then phase 2 PREPARED; its row preparation slots and decision hash are all
zero. PREPARED means all target copies, identity with origin 1, required kind-13
rebuilding marker and node-specific original bootstrap seal were forced and reread.
It never creates a new group decision. Resume rechecks the same plan/inventory and
repeats only exact uncompleted copies; it cannot turn a replacement into a voter.
The next admitted leader catch-up or explicit two-survivor leader reconstruction is
required by [the lifecycle contract](PUBLIC_ADMISSION_CONTRACT.md#cleanup-and-replacement).
Cleanup of bootstrap output and replacement recovery are separate operations.

## Wire 1.1

Wire header is the [frozen GSRP envelope](TRANSPORT_AND_FRAMING.md#exact-frame-envelope)
with major/minor `(1,1)`; kinds 1–16 keep their IDs. Full frame limit remains configured
(default 8 MiB, hard 64 MiB), including base64 expansion. JSON is canonical ASCII.
Every envelope has exactly:

```text
protocol manifestDigest groupId configurationId sender recipient epoch
incarnationId traceId eventSequence type payload
```

`manifestDigest` is now a mandatory **top-level** field on every request and response,
including rejection, ACK, status and chunk. It must equal the complete amended
manifest's record digest. It is removed from payload; duplicate/nested identity rejects.
Group/config and sender/recipient must agree with that manifest; sender differs from
recipient. UUID/counter/trace and retry-correlation rules are unchanged. Header minor,
protocol string and any embedded storage frame must all be 1.1. Validate identity
before dispatch or payload allocation. Same IDs with different genesis cannot handshake.

The table gives exact payload keys (empty means `{}`). JSON integer counters are
nonnegative i64 unless the existing operation requires a positive value. Binary fields
are padded standard base64; digests lowercase SHA-256 hex, transfer IDs canonical UUIDs.
Request/reply variants are distinguished by their exact key set and pending request
context; an unsolicited reply never executes a request. Reserved CONFLICT remains a
classified rejection and cannot append/apply. Unknown actions/extra keys reject.

| Type | Request payload | Reply payload |
| --- | --- | --- |
| HANDSHAKE | empty | empty |
| ACTIVATE_EPOCH | `recovery:true` | ACTIVATION_PROMISE status |
| ACTIVATION_PROMISE | reply only | status |
| APPEND | `entry` (complete ENTRY) | DURABLE_ACK |
| DURABLE_ACK | reply only | `index,entryDigest,receiptDigest` |
| COMMIT_PROOF | `proof` (complete PROOF) | COMMIT_PROOF_ACK |
| COMMIT_PROOF_ACK | reply only | `index,proofDigest` |
| AUTHORITY_STATUS_PROBE | empty; or `{action:"export"}`; or `{action:"chunk",transferId,offset,length}` | AUTHORITY_STATUS |
| AUTHORITY_STATUS | reply only | status; or `{transferId,length,digest}` export offer; or `{transferId,offset,data}` exported chunk |
| COMMIT_ADVANCE | `{action:"ready",index,digest}`; `{action:"floor",index,digest,voters}`; `{action:"batch",entries,proofs}` | status |
| SNAPSHOT_OFFER | `transferId,length,digest` | `transferId` |
| SNAPSHOT_CHUNK | `transferId,offset,data` | `transferId,offset` (next accepted offset) |
| SNAPSHOT_INSTALL | `transferId,admit` boolean | `transferId,imageDigest,index,digest,snapshotIndex` |
| SNAPSHOT_ABORT | empty | empty |
| REJECT / CONFLICT | reply only | `reason` (existing ReplicationException reason name) |

Status keys: `promisedEpoch,lastLogIndex,commitIndex,lastDigest,commitDigest,appliedIndex,
snapshotIndex,recoveryFloor,voter,damagedTail`. Last/commit digest refer to the exact
ancestry boundary (manifest digest at zero). Application sequence is reconstructed
from the manifest and verified ancestry; it is never inferred from LogIndex.
Embedded entry/proof epoch/incarnation must match the envelope. Proofs and transferred
snapshots must validate the same manifest, base and receipt domains before admission.
Batch/chunk counts, offsets, image hashes, proof quorum and floor source rules retain
Phase 4 bounds. Snapshots do not manufacture a bootstrap receipt for an unsealed node.

## Evidence and remaining runtime gates

The catalog also includes kind-22 cleanup and kind-23 replacement plan bytes, an
ABORTING row linked to a pre-commit fork, replacement PREPARING/PREPARED rows and
origin-1 NODE/rebuilding examples. Their `admin-*` catalog names label separate
projections; they are not physical storage filenames or permission to clean up the
committed sample. Negative projections cover protected-source deletion, post-commit
abort, replacement inventory corruption and premature voting/group commitment.

Both independent readers consume the same checked-in bytes and compare exact expected
history/base/sequence/digest results; tests never rewrite expectations. Invalid cases
include recomputed outer checksums so nested bindings are exercised. The readers are
standard-library test tools, outside the replication implementation package and absent
from production/source/Javadoc JARs. Frozen legacy fixtures are not regenerated.

Step A proves declaration/format agreement. B must add actual filesystem ownership,
full typed source semantics, resource reservation, all publication/abort/replacement
crash cuts and independent pre-reopen inspection. C must add standalone sealed-node
startup, full 1.1 transport/payload execution and the outside-package three-JVM public
consumer gate. This specification and synthetic catalog are not substitutes for
those acceptance receipts.
