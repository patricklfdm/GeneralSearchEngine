# V5.0 public bootstrap and lifecycle contract amendment

- **Status:** Contract accepted through [PR #151](https://github.com/patricklfdm/GeneralSearchEngine/pull/151); Step A declarations/fixtures under review
- **Base:** Phase 5 accepted at `4a8fd3dfd9e398d712e896c9af511cf55f4cb16e`
- **Scope:** Complete the public-admission gap before Phase 6
- **API delta:** [Proposed declarations and compatibility](PUBLIC_ADMISSION_API.md)
- **Delivery and evidence:** [Entry plan](PUBLIC_ADMISSION_ENTRY_PLAN.md), [Step A foundation](PUBLIC_ADMISSION_FOUNDATION.md)
- **Byte specification:** [Exact replicated/wire 1.1](PUBLIC_ADMISSION_FORMAT_1_1.md)
- **Contract master:** `72ea9a6b176a7371d708cea1d84ad8d603adef61`, [CI 34960589647](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34960589647)

## Decision and existing gaps

The public engine must open only a completely bootstrapped, identity-bound group.
Planning must expose enough input to review exactly which source, manifest and three
targets will become authority. This amendment supplies that workflow and the public
operations needed to use the Phase 3–5 runtime.

The following are findings at the base commit, not delivered public capabilities:

| Existing implementation | Missing boundary |
| --- | --- |
| `ReplicatedSearchEngineBuilder.build()` always throws | Deferred construction, startup ownership and complete delegation |
| Bootstrap plan/apply always throw; plan stores IDs, source, target paths and a digest | Full manifest, typed source verification, group publication and cleanup |
| `ReplicaStore.initialize()` makes one independently openable empty voter | No all-three bootstrap decision or public startup seal |
| `ReplicaManifest` binds codec/schema/indexes; `ReplicaSnapshot.sequence()` counts application anchors | Genesis content is not in the manifest; imported base sequence is absent |
| `SearchEngineBuilder` keeps schema, indexes, engine and planner configuration private | Supported immutable configuration handoff across artifacts |
| Core backup reader/writer are package-private | Supported canonical application import/export without a second live V4 WAL |
| Internal checkpoint pushes a second copy and advances recovery floor | Public checkpoint must also support local committed-state maintenance |
| Internal catch-up and replacement reconstruction exist | Explicit public administrative entry points |
| `ReplicationStatus` contains local counters | Manifest/incarnation, peer progress, recovery floor and failure diagnostics |

Protected acceptance of this document authorizes only the enumerated follow-up
changes. The existing Phase 0 quorum/proof, fencing, fixed membership, V4.4 semantics
and source-preservation rules still apply. Sections below explicitly amend the
replicated format/protocol version and fill in the lifecycle/API contract; they do
not describe the currently accepted `1.0` implementation as already supporting them.

## Complete bootstrap input

The typed request contains the source kind/path, exactly three local
`ReplicationGroupConfig` values, an absent operation directory and explicit byte
bounds. It is paired with one application builder. The three configurations must
agree on group/configuration IDs, ordered members/endpoints, configured leader,
codec identity/version, schema identity and application storage identity/format.
Their local NodeIds must form exactly the manifest voter set. Paths and local bounds
may differ; all are included in the plan. No sorting may change member order.

The schema format version is explicitly `1`, matching the existing application
descriptor. Codec versions must be positive, as required by the replicated manifest;
a V4 codec with version zero rejects during planning. Built-in durable equality,
range, prefix and simple-analyzer text indexes are supported. Unsupported descriptors
reject before any target exists. Local planner and snapshot settings are preserved
but do not become peer identity. Their values are nevertheless bound into the plan.

The manifest binds protocol/storage versions, initial epoch `1`, all group/member
identities, codec/schema/index identity and the genesis fields below. Paths are
operation provenance, never group identity. Schema identity includes the operator's
versioned semantics: Java lambdas cannot be fingerprinted or proven deterministic.
Canonical codecs and descriptors are validated; callers must keep their behavior
stable for the group's lifetime.

`EMPTY` uses no source path and base application sequence zero. A
`VERIFIED_V44_BACKUP` source must pass both codec-free structural verification and a
typed canonical decode/reconstruction using the checksum-pinned published V4.4
semantics. Supported backup families are exactly the `gse-backup (1,0)`, `(1,1)` and
`(1,2)` families understood by V4.4. A live store or replica directory rejects.
The source's active index configuration must match the requested genesis indexes.
The source is rechecked before the durable commit decision and remains byte-for-byte
unchanged on success, failure and cleanup.

All source, target, materialization and operation paths are checked for ancestry,
aliases, symlinks and overlapping ownership. Targets and operation directory must be
absent, their parents must already exist on supported local filesystems, and target
parents must support directory forcing. Planning performs no write, marker creation,
repair, networking or engine startup. Apply revalidates paths and source bytes under
exclusive operation/target ownership; lexical `Path.equals()` is insufficient.
This is an offline coordinator with three locally accessible node volumes. It does
not mount remote filesystems or provision hosts. Once bootstrap finishes, the volumes
can be attached to their respective nodes; original paths remain provenance and
normal startup validates node identity at the configured local path.

### Plan identity and bounds

The existing `ReplicationBootstrapPlan` remains a compact immutable projection.
Its new typed overload is meaningful only together with the complete request and
builder configuration. `planDigest` is SHA-256 of a domain-separated, versioned,
canonical descriptor containing:

- all request values, normalized paths and observed parent filesystem identities;
- the immutable application configuration and every numeric bound;
- exact source family/profile, history, sequence, member sizes and SHA-256 digests;
- ordered manifest bytes and the digest/length of the complete canonical genesis
  projection; and
- deterministic operation member names and per-target authority payload inventories.

Planning generates no random identity: the application export history is a nonzero
UUID from the first 16 SHA-256 bytes of ASCII `gse-v50-application-history-v1` plus a
zero byte and the GroupId's 16 bytes in big-endian UUID order. A zero value or collision
with the imported source history rejects planning; the operator must choose a new
GroupId. Independent fixtures freeze this derivation before apply opens.
Source history and source sequence are retained separately as provenance. Repeated
planning over unchanged inputs yields identical plan bytes/digest. Caller-created
plans confer no authority; apply recomputes the entire descriptor and rejects any
change before writing.

To avoid self-reference, the plan's payload inventory excludes the operation journal,
preparation records and completion seals that later embed `planDigest`. Preparation
records bind that digest and the already planned payload inventory; the completion
receipt then binds all three preparation records. Each descriptor/journal/receipt
record is bounded by the existing 64-KiB metadata limit. Large genesis bytes are
referenced by digest and length, not embedded in a receipt.

The request's positive `maxSourceBytes` and `maxOperationBytes` have a hard ceiling
of 1 TiB each. The latter covers all three outputs, staging, manifests, markers and
receipts together, counting simultaneous copies. Each replica also obeys its existing
retained/staging limits. Canonical genesis/snapshot size remains at most 64 MiB and
at most each node's configured snapshot limit, including framing overhead. Existing
document, key, bulk, one-million-anchor, 10,000-index and transfer-chunk bounds remain.
Planning rejects projections that cannot fit; apply checks before each allocation
and write with overflow-safe arithmetic. A large backup cannot bypass the smaller
replicated snapshot bound. Core application-transfer APIs also honor caller decode,
document, retained-byte and backup limits.

## Genesis and explicit format amendment

Public admission uses `gse-replicated (1,1)` and `gse-replication/1.1`. The existing
`1.0` golden bytes remain immutable historical fixtures. There is no implicit
conversion, mixed-version group or public startup of an unsealed `1.0` test store.
The new independent byte fixtures are a prerequisite to production enablement.

The `1.1` manifest extends the existing fields with `genesisDigest`,
`applicationHistory` and `baseApplicationSequence`. The genesis digest covers a
versioned canonical record of source provenance, export history, base sequence,
active index descriptors and ordered canonical key/document bytes. It excludes the
manifest digest to avoid a hash cycle. The manifest digest then binds the genesis.
All requests, ACKs, proofs and transferred snapshots validate that same manifest;
an identical GroupId with different genesis bytes cannot handshake successfully.

Each node durably retains the same immutable genesis record, even after compaction.
At index zero it is authoritative application state and must be loaded even when
`CommitIndex == snapshotIndex == 0`. It is not a fabricated entry quorum or commit
proof. Public voting is gated separately by the group completion receipt.

An imported backup at sequence `S` starts with:

```text
LastLogIndex = CommitIndex = AppliedIndex = 0
ApplicationSequence = baseApplicationSequence = S
next application entry: LogIndex 1, ApplicationSequence S + 1
control entry: advances LogIndex only
```

Snapshot/replay sequence is the manifest's base sequence plus the number of
application anchors through the applied index, using checked arithmetic. The `1.1`
snapshot explicitly binds that base sequence and validates it against the manifest.
`S == Long.MAX_VALUE` rejects bootstrap because no application continuation exists.
Document iteration preserves the source's canonical live-document order; any internal
ID reconstruction must preserve all published ordering, scoring and query behavior.
No synthetic ADD operations or counterfeit proofs may be used to seed V4 data.

The `1.1` storage inventory adds versioned genesis, preparation and local completion
records. The new wire version carries/validates the amended manifest identity in
every envelope. Precise field order, framing, digest domains, allowed filenames and
negative fixtures must be frozen in the first implementation PR. This amendment
selects the versions and semantics; it does not silently replace the Phase 2 binary
specification. Legacy bytes remain independently inspectable under their own rules.

## One durable group decision

Three directory writes are not an atomic transaction. Bootstrap therefore uses one
coordinator operation journal and one global completion receipt. It never treats
three separate calls to the current single-node initializer as group publication.

| Durable phase | Allowed effect and recovery |
| --- | --- |
| PREPARING | Create only exact plan-owned output and preparation records; no public node may start |
| PREPARED | All three genesis/manifests/ledgers are forced and independently re-read; still no public startup |
| COMMITTING | Force this phase before attempting receipt publication; cleanup is now forbidden |
| COMMITTED | Atomically publish and force the global completion receipt and its parent, binding all three prepared inventories |
| Local seal delivery | Copy the already committed receipt into each node using atomic publication and directory force |

Apply retains exclusive target ownership until seal delivery completes or failure
unwinds. It returns a result only after all three local receipts are forced and
independently verified. The receipt contains the plan, manifest/genesis identity and
three preparation digests; it is a non-Byzantine durable publication record, not a
cryptographic signature by remote peers. Each local seal also binds its NodeId.

Before the global decision, every partial output is unstartable. After that decision,
all three prepared authorities already exist durably. Interrupted local seal delivery
is recovery of a committed bootstrap, not permission to delete a partial group.
A sealed member may start after its owner is released; quorum rules still apply.
This is the precise meaning of the Phase 0 partial-output rule across three volumes.

`resumeBootstrap` reacquires ownership and validates the exact journal, plan and
inventories. Before COMMITTING it may finish the original preparation with the same
source; at/after COMMITTING it may only complete the decision/deliver missing seals.
It never overwrites an existing seal, altered output or running node. After the
decision, missing source bytes cannot invalidate committed authority; resume verifies
the retained genesis and preparation evidence. A missing/corrupt decision with an
ambiguous journal fails closed; absence alone does not authorize cleanup.

Normal startup requires the local completion seal, genesis and manifest to agree.
It has no dependency on the coordinator directory or source backup after successful
delivery. Loss of one disk is handled by replacement, never by replaying bootstrap.

### Cleanup and replacement

Cleanup is codec-free plan/apply over an exclusively owned operation directory and
all affected targets. It lists exact files/directories and binds the full observed
inventory. Only a proven pre-COMMITTING attempt can enter durable ABORTING state;
then a plan may remove known non-authoritative outputs in dependency order and force
each parent. Unknown files, aliases, changed inventories, missing evidence, completed
receipts or a live owner reject before deletion. A crash retains the operation marker
until target cleanup completes; a fresh plan resumes the remaining deletions.
Cleanup never removes the V4 source, published group or any replica authority.

Replacement has separate plan/apply/resume operations. A closed intact member supplies
the verified manifest, genesis and completion provenance; source bytes are preserved.
The target must be absent and retain the same manifest NodeId. Initialization creates
only a non-voter with a durable rebuilding marker, never a fresh genesis voter. Its
operation journal uses the same cleanup restrictions. After all nodes start, an
activated leader explicitly catches up a follower replacement. A configured-leader
replacement explicitly reconstructs against **both surviving follower identities**
before activating. Bootstrap receipts never substitute for their current promises
and committed-history evidence. Corrupt existing disks are not overwritten in place.

## Public construction and lifecycle

`builder(...).build()` captures an immutable core configuration and validates pure
arguments. It creates a stopped handle in `STARTING` with zero progress, no write
quorum and no applied application view. It opens no directory, lock, thread or socket.
Later mutation of the supplied builder cannot change that handle.

`start()` asynchronously acquires local ownership, verifies sealed authority and
exact configured identity, reconstructs committed application state and starts the
bounded transport. It never bootstraps absent storage or activates the leader.
Success returns `CATCHING_UP`; it does not admit public application reads/writes.
Before binding or connecting, startup validates that each resolved address is on the
configured private network or loopback; wildcard/public listeners reject. Re-resolution
cannot bypass that check. This preserves the accepted private-network boundary and
does not introduce TLS, peer authentication or Internet deployment support.
Concurrent/repeated start calls share one underlying attempt. A failed startup
cleans acquired resources and leaves `FAILED`; closing and building a new handle is
the retry path. Close racing startup prevents later publication/listener leakage.

`activateConfiguredLeader()` is an explicit administrative action. It requires a
successfully started configured leader and the complete Phase 4 fencing/recovery
barrier. Concurrent requests share an attempt; calling again on a READY incarnation
returns its status without minting another epoch. A failed attempt can be retried
only after its ordered work settles. Cancellation of a returned future does not
cancel a shared activation/start operation or establish that it had no effect.

No automatic election, promotion or catch-up scheduler is added. `catchUp(peer)` on
the activated leader explicitly drives incremental or snapshot recovery and returns
the peer's verified boundary. `reconstructConfiguredLeader()` is available only for
a started non-voter leader replacement; it includes the two-survivor recovery and
activation barrier. A fresh builder/restart cannot silently enter replacement mode.

| Call | Admission and result |
| --- | --- |
| All single/bulk mutations and index create/drop | Configured READY leader; one ordered entry per operation and Phase 0 success boundary |
| Every search overload, ranking, page, highlight and explain | Previously activated leader's immutable applied view; no follower public reads |
| `currentSequence()` | Same leader read admission; base plus applied application units, never LogIndex |
| `schema()`, field lookup | Immutable configuration metadata, available on either role and before start |
| `metrics()` | Leader application view; no follower application observation |
| Replication status/diagnostics | Either role, every lifecycle state; local snapshot with no synchronous network wait |
| `checkpoint()` | Started node with a verified applied committed cut, including a follower; local maintenance |
| `backup(request)` | Activated leader's writer-ordered committed cut; no follower export |
| `close()` | Any state; deterministic ownership shutdown and retry after incomplete cleanup |

After quorum loss, an already activated leader may read its last published committed
view. It admits no successful new mutation without a new proven quorum. A fencing,
history-conflict or integrity failure revokes the readable view. `UNAVAILABLE` is
not by itself evidence of either readable or write-ready state; diagnostics explain
the last failure. Public states remain the Phase 1 enum (`STARTING`, `ACTIVATING`,
`CATCHING_UP`, `READY`, `UNAVAILABLE`, `FAILED`, `CLOSED`); Phase 0's conceptual
OFFLINE/BOOTSTRAPPING/DEGRADED names are not additional Java enum values.

### Checkpoint, backup and metrics

A local checkpoint serializes behind already admitted work, captures only committed
applied state, forces and atomically installs a verified local snapshot. It does not
change application sequence, mint an application entry, require a current remote
ACK, or automatically advance the group recovery floor. If there is an unresolved
suffix that cannot safely coexist with installation, it rejects until reconciliation;
it never drops that suffix merely to make maintenance succeed. Prefix deletion still
requires two complete durable recovery sources. Explicit catch-up/maintenance can
establish that evidence later. If retaining the old source and new snapshot exceeds
capacity, checkpoint rejects without deleting the old source.

Backup captures a committed cut on the same writer and exports a canonical V4-format
application bundle through the core transfer API. Export uses the group's stable
application history, captured application sequence and current active indexes. It
does not export replication epochs/proofs as V4 authority. It succeeds only after
absent-target atomic publication, parent force and independent structural verification.
The target byte bound covers all authoritative bundle members; cancellation or a lost
response is indeterminate and never triggers deletion of an already published bundle.
Quorum loss alone does not prevent exporting an already readable committed cut.

The inherited `durabilityMetrics()` is a local storage view, not a quorum signal.
`currentSequence` and `checkpointSequence` use application sequences; `walRecords`
and `walBytes` describe retained replica entry-journal records/bytes, while
`walGeneration` describes that journal's installed generation. `retainedBytes` covers
all local authority. Recovery source maps empty fresh genesis to `FRESH`, a genesis
or snapshot alone to `CHECKPOINT_ONLY`, and a snapshot plus replayed committed entries
to `CHECKPOINT_AND_WAL`; no V4 WAL is opened. Recovery durations/counts are measured,
not synthesized. OPEN describes the initialized local storage writer; quorum and
application admission require replication status. Before initialization the method
fails as unavailable. FAILED/CAPACITY_BLOCKED/CLOSED describe local storage outcomes.
`lastReopenReport()` retains the empty default because a V4 reopen report would
misdescribe replicated recovery. Replication diagnostics provide the missing detail.
The legacy `lastCheckpointFailure` maps local capacity to `CAPACITY_EXCEEDED`,
snapshot integrity to `CORRUPT_CHECKPOINT`, incompatible format to
`INCOMPATIBLE_STORAGE`, IO to `IO_FAILURE` and close to `CLOSED`. A replication-only
admission/history rejection has no fabricated V4 checkpoint failure; its exact reason
appears in diagnostics and in the failed future.

### Failures, bounds and close

Null/invalid pure arguments retain Java argument exceptions. Role rejection happens
before codec execution, queue admission or network work. Async replication failures
complete their futures exceptionally with `ReplicationException`; synchronous reads
throw the same reason. Existing V4 document/index validation and bundle-operation
exceptions are preserved. For example, an occupied backup target still produces
`DurableOperationException(TARGET_EXISTS)`; an occupied bootstrap/replacement target
uses the replication storage reason below. Core failures retain their original cause
when a replication operation translates them.

| Condition | Replication reason |
| --- | --- |
| Follower application call or follower activation/catch-up command | `NOT_CONFIGURED_LEADER` |
| Not started/activated, unavailable peer or insufficient recovery quorum | `QUORUM_UNAVAILABLE` |
| Version, immutable configuration, codec/schema/index mismatch | `PROTOCOL_MISMATCH` |
| Invalid checksums, seals or canonical source bytes | `INTEGRITY_FAILURE` |
| Divergent proven history, changed plan binding or inappropriate replacement | `CONFLICTING_HISTORY` |
| Stale epoch/incarnation | `STALE_EPOCH` |
| Queue, byte, decode, staging or retained capacity exceeded | `CAPACITY_EXCEEDED` |
| Owned/existing target, unsafe filesystem path or IO failure | `STORAGE_FAILURE` |
| Admission stopped by close | `CLOSED` |

Typed bootstrap translates core invalid-backup/source evidence to `INTEGRITY_FAILURE`,
unsupported format or identity mismatch to `PROTOCOL_MISMATCH`, and core capacity/IO
to the corresponding replication capacity/storage category. An expected operation
rejection does not by itself put the whole node in FAILED; failure of trusted local
authority, fencing or a conflicting proven history stops the affected admission.

Pending mutations, maintenance, startup/control work, transfer buffers and diagnostic
probes must have finite shared admission and byte accounting. Per-peer observations
carry their observation time; stale evidence never becomes a fresh quorum claim.
At most one diagnostic probe per peer is pending; retries use existing transport
bounds, and refresh is coalesced at the configured request-timeout interval. This is
diagnostic observation, not a lease, automatic activation or automatic catch-up.

Close stops admission, settles all accepted futures, quiesces authority writes,
stops transport/probes, closes application views and releases storage ownership only
after the writer can no longer mutate. It preserves Phase 5 callback/concurrent-close
and retry behavior. A termination timeout retains ownership and reports failure;
a subsequent close can finish. Codec or user callback execution must cooperate;
arbitrary synchronous code and filesystem force do not acquire a hard wall-clock
termination guarantee. Cancelled work retains its admission until settled, and no
cancellation reverses an entry, bootstrap decision or backup that may be durable.
