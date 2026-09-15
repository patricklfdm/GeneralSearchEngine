# V5.0 Phase 2 replicated storage format

- **Family/version:** `gse-replicated (1,0)`
- **Status:** Accepted through protected Phase 2 PR #147
- **Implementation:** package-private `ReplicaStore`, `ReplicaFormat`, `ReplicaManifest`,
  `ReplicaEntry` and `ReplicaProof` in the optional replication artifact
- **Golden bytes:** [independent fixture](../../../general-search-engine-replication/src/test/resources/replication/v50-storage-v1/README.md)

## Authority and scope

The manifest, promise ledger, entry chain and received commit-proof ledger are local
replica authority. The existing public `ReplicationStorageOperations.inspect(Path)`
now verifies that authority without an application codec. All public declarations,
including status fields, remain identical to the Phase 1 API inventory.

This phase has no coordinator, socket listener, activation quorum, application apply,
publication or successful application Future. A stored proof advances **local**
CommitIndex only. Its receipts establish entry quorum under the configured-leader,
non-Byzantine trust model; SHA-256 receipts are integrity bindings, not signatures or
independent evidence that remote disks were forced. Phase 3 must obtain proof quorum
before publishing or completing an application operation.

Internal initialization requires an absent directory. It does not implement public
empty/V4.4-backup group bootstrap, create an installed snapshot, or issue a three-node
bootstrap receipt. The ready marker below means only that the local storage files
were initialized. Snapshot installation, suffix reconciliation and physical cleanup
remain Phase 4. Phase 1 JSON examples remain separate logical fixtures.

## Scalars and common record envelope

Integers are big endian. `u8`, `u16`, `i32` and `i64` use 1, 2, 4 and 8 bytes.
`uuid` is the RFC UUID byte order (16 bytes). `hash` is SHA-256 (32 raw bytes).
`text` is `i32 byteLength` followed by strictly valid UTF-8, without a terminator.
No record permits trailing fields. IDs use `[a-z0-9][a-z0-9._-]*`, at most 64 ASCII
bytes for nodes and 128 for configuration/codec/schema IDs. Versions are positive
i32 values. Hosts are nonblank and bounded to 253 Java UTF-16 code units (UTF-8
reader bound 1012 bytes); ports are 1–65535. Member ordering is part of the immutable
manifest identity and is preserved exactly.

| Offset | Bytes | Field |
|---|---:|---|
| 0 | 4 | ASCII `GSER` (`47 53 45 52`) |
| 4 | 2 | major = 1 |
| 6 | 2 | minor = 0 |
| 8 | 2 | record kind |
| 10 | 2 | flags = 0 |
| 12 | 4 | positive body byte length |
| 16 | 32 | SHA-256 of bytes 0–15 followed by body |
| 48 | body length | body |

The checksum in bytes 16–47 is the record digest. An entry's digest is therefore
also its full frame checksum. Unknown versions, flags/kinds, truncated records,
oversized lengths, invalid strings and checksum failures reject before admission.
Declared body size is checked before allocation. This framing is distinct from V4
WAL and from the Phase 1 `gse-replication` wire envelope.

## Directory and metadata records

Exactly seven regular, non-symlink, singly linked files exist. Unknown/missing members
and nonempty lock files fail closed. Root and ancestor symlinks are rejected.

| File | Kind | Ordered body fields |
|---|---:|---|
| `replica.lock` | — | Empty file; held for the entire open lifetime |
| `manifest.gsr` | 1 | See immutable manifest below |
| `node.gsr` | 2 | manifest hash, local node text |
| `promises.gsr` | 3 then 4 | Journal header then promise records |
| `entries.gsr` | 3 then 5 | Journal header then entry records |
| `proofs.gsr` | 3 then 6 | Journal header then commit-proof records |
| `storage-ready.gsr` | 7 | Five hashes: manifest, node, promise header, entry header, proof header |

Every journal header (kind 3) contains manifest hash, local node text and u16 expected
record kind (4/5/6). Single-record files must contain exactly one complete frame.
The ready marker binds only journal headers, so normal appends do not rewrite it.

The manifest body, in order:

1. text `gse-replicated`, u16 1, u16 0;
2. text `gse-replication`, u16 1, u16 0;
3. group uuid, configuration text, i64 genesis epoch = 1;
4. configured-leader text, i32 member count = 3;
5. three ordered members: node text, host text, i32 port, u8 voter = 1;
6. codec text, i32 codec version, schema text, i32 schema version;
7. index-configuration hash.

All voter identities and endpoints are distinct; the leader is a voter. The manifest
hash binds the complete group/configuration/protocol/application identity into every
other authoritative record. Writer open compares both expected manifest and local
node. Codec-free inspection reports recorded identity without loading its codec.

## Promise, entry and proof records

**Promise (kind 4):** manifest hash, configured-leader text, i64 epoch, incarnation
uuid. Genesis has epoch 1 and zero incarnation; real promises start at 2 with a
nonzero incarnation and strictly increase. A same-epoch/same-incarnation retry forces
the existing ledger; it never adds a duplicate record. Old epochs and conflicting
incarnations reject. Reopen retains the full bounded promise history to validate
entries from earlier epochs.

**Entry (kind 5):** manifest hash, i64 epoch, incarnation uuid, i64 log index,
u8 operation, i64 previous epoch, i64 previous index, previous hash,
i32 payload length, payload hash, opaque payload bytes.

Entries start at index 1, whose predecessor is `(epoch=1, index=0, manifest hash)`.
Every next record extends the exact previous epoch/index/digest; epochs never decrease
and each entry must match a durable historical promise. Incoming writes must also
match the current promise. The payload may be empty. The total fixed frame and field
overhead is 197 bytes. One bulk operation remains one entry; this layer does not
interpret payloads or aggregate application operations.

| ID | Operation | ID | Operation |
|---:|---|---:|---|
| 1 | ADD | 6 | REMOVE_ALL |
| 2 | UPDATE | 7 | INDEX_CREATE |
| 3 | REMOVE | 8 | INDEX_DROP |
| 4 | ADD_ALL | 9 | NO_OP |
| 5 | UPDATE_ALL | 10 | SNAPSHOT_MARKER |

All other IDs, including reserved CONFIGURATION, reject.

A durable-entry receipt digest hashes the following ordered encoding:
`text("gse-replication/1.0/DURABLE_ACK"), manifest hash, voter text, i64 epoch,
incarnation uuid, i64 index, entry hash`.

**Proof (kind 6):** manifest hash, i64 epoch, incarnation uuid, i64 committed index,
entry hash, predecessor hash, i32 receipt count, then 2 or 3 receipts, each containing
voter text and receipt hash. Receipt voters must be distinct and lexicographically
sorted. Each must be a manifest voter and match the exact entry identity/digest.
The local entry must already exist before proof force/ACK. A proof for N commits the
contiguous local prefix through N. Persisted proofs strictly increase their index;
exact already-persisted retries force again without growing the ledger. A different
proof at an already committed index rejects, even if it adds a third voter.

## Durability, ownership and failure

Initialization forces the new parent entry, creates and locks `replica.lock`, writes
and forces each member in inventory order, and forces the containing directory after
each member. `storage-ready.gsr` is written last. Failures retain the partial target;
no retry silently overwrites it.

Append/promise/proof paths validate before writing, complete bounded short-write
loops, call `FileChannel.force(true)`, update in-memory state, and only then return
an ACK/receipt. An exact retry forces before re-ACK. Any write/force/ACK-boundary I/O
exception poisons the writer until close/reopen. Disk-integrity failures while reading
an already indexed record also poison the writer. Validation rejection alone does
not poison it. Close releases data channels before the owner lock and is idempotent.

One writer holds an exclusive OS record lock; Java and independent Python inspectors
hold shared record locks and reject a live writer. Inspect never creates storage,
truncates tails, repairs files, applies payloads or emits a bootstrap receipt. The
Java absent-directory result has `present=false`, `structurallyValid=false`, and no
group/node. Existing invalid storage raises a classified `ReplicationException`.
The Python CLI reports failure for absent or invalid storage.

A torn authoritative tail currently rejects the entire open, including an
uncommitted tail. Future recovery must explicitly validate any safe truncation before
implementing it. An unacknowledged complete record is indeterminate and may survive.
The local SIGKILL matrix checks process-crash behavior on the current filesystem;
it does not simulate loss of kernel page cache or certify device power-loss behavior.
NFS/CIFS/SMB/FUSE/tmpfs/ramfs/9p filesystems are rejected by the Java store. Durable
storage still relies on the host honoring file and directory force semantics.

## Finite limits

- Metadata frame: 64 KiB including the 48-byte envelope.
- Entry frame: configured `maxFrameBytes` (default 8 MiB; hard maximum 64 MiB).
- Aggregate retained bytes of all seven files: configured `maxRetainedLogBytes`
  (default 8 GiB; hard maximum 1 TiB), checked at open and before every append.
- Entry offset index: at most 1,000,000 records; promise history: at most 10,000
  distinct epochs; proof records: at most one per entry. These are Phase 2 internal
  safety caps, not new public settings. No automatic compaction is enabled.
- No-progress I/O: at most 16 consecutive zero-byte attempts.

Inspection uses hard frame/disk bounds because it has no runtime configuration.
Other frozen Phase 1 transport/queue/batch limits remain for the later coordinator;
this phase accepts one entry per local append call.

## Independent verification

`scripts/v50/storage_format.py` implements framing, generation, parsing and receipt
validation using Python's standard library, with no Java or model imports. It checks
Java output independently; Java opens Python-produced golden bytes. Both writers
produce byte-identical directories. The gate retains exact child PIDs, crash barriers,
exit signals, logs, pre-reopen raw bytes and SHA-256 inventories, independent reports,
and Java reopen results under `target/v50-storage` even on failure.

```bash
scripts/verify-v50-phase2-storage.sh
python3 -m scripts.v50.storage_format inspect /absolute/path/to/closed/replica
```
