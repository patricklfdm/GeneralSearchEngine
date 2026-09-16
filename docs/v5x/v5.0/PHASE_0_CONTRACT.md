# GeneralSearchEngine V5.0 Phase 0 replication contract

- **Status:** Accepted contract (protected PR #145)
- **Reference:** published GeneralSearchEngine `4.4.0`
- **Target:** GeneralSearchEngine `5.0`
- **Production implementation:** prohibited until Phase 0 acceptance

## Objective and scope

The [public-admission amendment](PUBLIC_ADMISSION_CONTRACT.md) was accepted in PR #151
after Phase 5. It specifies bootstrap publication, public lifecycle, additive APIs
and genesis-bound replicated storage/protocol `1.1`. [Step A](PUBLIC_ADMISSION_FOUNDATION.md)
accepted the declarations and independent bytes in PR #153. [Step B](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md)
implements offline authority; [Step C](PUBLIC_ADMISSION_RUNTIME.md) supplies the public runtime accepted in PR #155. The `1.0`
contract below remains the historical Phase 1–5 baseline.

V5.0 establishes correct replicated single-shard durability under one configured
leader. It supports exactly one group containing exactly three fixed voters: the
configured leader identity and two follower identities. Quorum is always two voters.

The V5.0 fault model is crash/restart, omission, delay, duplication, reordering,
bounded corruption detection and permanent loss of one node-local disk. It does not
cover Byzantine behavior, a hostile network, cross-region operation, automatic
leader selection, online promotion, public follower reads or membership change.

V5.0 is not itself a complete high-availability release: configured-leader loss may
stop public reads and writes. It must nevertheless preserve committed history and
permit explicit offline recovery of the configured leader when the remaining valid
evidence is sufficient.

## Frozen V4.4 inheritance

V5.0 preserves immutable snapshots, lock-free reads, one ordered writer, atomic bulk,
all published query/ranking/pagination/highlighting/explanation behavior,
force-before-success durability, indeterminate incomplete operations, deterministic
codecs, fail-closed corruption, backup inspection and bounded resources.

V4 `gse-durable` and `gse-backup` formats retain their exact published meaning. They
are never opened as V5 cluster authority and are never modified in place.

## Cluster identities and manifest

Every group has a durably identical immutable genesis manifest containing:

```text
ReplicationGroupId
ConfigurationId
protocol family and major/minor
replicated storage family and major/minor
three ordered (NodeId, endpoint, voter role) members
configured leader NodeId
initial Epoch
application codec identity/version
schema identity/version
index configuration identity
manifest digest
```

`ReplicationGroupId`, `ConfigurationId` and each `NodeId` are explicit stable opaque
identifiers. They are not inferred from a hostname, address, process, path or disk.
The fixed V5.0 manifest cannot be edited. Any mismatch fails startup and handshake.

V5.0 starts at `Epoch = 1`. Every configured-leader process incarnation must activate
under a strictly greater epoch before admitting writes. Only the configured leader
NodeId may request activation. Each voter durably promises at most one leader
incarnation in an epoch and rejects every request, append or commit from a lower epoch
or a different incarnation in its promised epoch. Activation uses quorum-persisted
promises and no wall-clock lease. This is the restricted precursor to V5.1 election;
it is not automatic leader promotion.

## Authority and index model

The unique cluster authority is the valid logically committed prefix of the
`gse-replicated` history for the immutable manifest.

Each replica tracks:

- `LastLogIndex`: greatest valid locally appended replicated entry;
- `CommitIndex`: greatest index covered by valid durable commit proof;
- `AppliedIndex`: greatest committed index materialized into application state; and
- `ApplicationSequence`: the V4-style logical application sequence at AppliedIndex.

The invariant is:

```text
AppliedIndex <= CommitIndex <= LastLogIndex
```

`LogIndex` begins at one and advances for every replicated entry. It is distinct from
`ApplicationSequence`: control entries do not advance the application sequence.
Application entries advance it exactly once in committed log order.

Searchable state contains only entries through `AppliedIndex`. Locally appended but
uncommitted entries never affect public search, backup or application results.

## Replicated operations

The logical log supports versioned entry families:

- single `ADD`, `UPDATE` and `REMOVE`;
- atomic `ADD_ALL`, `UPDATE_ALL` and `REMOVE_ALL`;
- `INDEX_CREATE` and `INDEX_DROP`;
- `NO_OP` for leadership/commit establishment;
- `SNAPSHOT_MARKER`; and
- reserved `CONFIGURATION`, rejected by V5.0 because membership is immutable.

Document, key and index descriptors reuse or extend V4 deterministic codecs. No
entry contains Java identity, lambdas, process-local callbacks, runtime-only Field
instances or nondeterministic collection/serializer order.

One public bulk call is one entry, one commit decision and one all-or-nothing apply.
Ordinary writer batching may transport several entries together but does not merge
their operation identity or Future outcomes.

Every entry binds:

```text
GroupId, ConfigurationId, Epoch, LogIndex, EntryType,
previous entry epoch/index/digest, payload length, payload digest, entry digest
```

The digest chain and exact predecessor must match. Same identity and same bytes is an
idempotent retry. Same identity with different bytes is a hard conflict.

## Durable append, commit proof and Future success

A voter counts toward append quorum only after validating and forcing the complete
entry to its durable boundary. Receipt or buffered write is insufficient. The leader
counts as one voter only after its own force completes.

For entry `N`, successful completion requires this exact order:

```text
validate deterministic operation
  -> allocate (Epoch, LogIndex N)
  -> force leader entry
  -> obtain durable-entry acknowledgements from any 2 of 3 voters
  -> create commit proof binding epoch, N and entry digest
  -> force that commit proof on any 2 of 3 voters
  -> advance leader CommitIndex
  -> apply committed entries in order
  -> publish leader immutable snapshot
  -> complete the application Future successfully
```

A commit proof is trusted only when its referenced entry and manifest identities
validate. It binds the group/configuration, epoch/incarnation, committed index, entry
digest, preceding digest chain and the distinct voter identities/durable-ACK receipt
digests that formed entry quorum. A receiver also requires the referenced entry bytes
before acknowledging the proof. Under the non-Byzantine fault model, a valid proof
could only have been issued by the configured leader after entry quorum. Persisting it
on two voters before success guarantees that at least one recoverable proof survives
permanent loss of one node-local disk. Proof for index N transitively commits the
contiguous valid prefix through N; conflicting valid-looking proofs fail closed.

Followers receive commit advancement and apply in order. Follower application lag
does not revoke a committed entry and does not delay leader success after the required
leader publication. Followers must persist their commit proof before exposing the
corresponding state internally.

No quorum means no new successful Future. A timeout, cancellation, disconnect or
failed response is indeterminate: it does not prove that the operation failed to
commit. V5.0 adds no public client request ID; application retry deduplication remains
the application's responsibility. Replica retries remain entry-idempotent.

## Storage layering

V5.0 introduces outer family `gse-replicated (1,0)`. A replica directory has one
exclusive process owner and separates:

```text
immutable genesis manifest
epoch/incarnation promise ledger
replicated entry log
durable commit-proof ledger
installed replicated snapshots
current applied materialization and reconstructible derived images
staging and bounded cleanup metadata
```

The replicated log plus valid commit proofs is cluster authority. V4 canonical
document/checkpoint encodings may be reused inside a replicated snapshot, but a
normal V4 WAL is not run as a second competing authority. Application materialization
is rebuildable from an installed replicated snapshot and the committed tail.

A crash between commit proof and apply replays committed entries. A crash after apply
but before publication reopens and republishes the same committed state. A crash
before commit proof leaves only an uncommitted suffix and can never manufacture
successful application state.

## Logical history and physical compaction

Committed logical history never changes, reorders or regresses. Conflicting
uncommitted suffixes may be removed only after activation and reconciliation establish
the preceding committed authority.

Physical log-prefix deletion is not logical truncation. A node may compact a prefix
only behind a locally verified, atomically installed replicated snapshot. The group
may advance its recovery floor only after at least two voters durably report a valid
snapshot or equivalent complete recovery source covering that floor. The leader
retains the committed tail after the floor. Cleanup is plan-bound, crash-safe and may
never delete the only recoverable representation of committed state.

## Bootstrap and migration

Group creation is an offline plan/apply operation. It accepts either:

1. an empty application state; or
2. one independently verified V4.4 `gse-backup` bundle.

Apply requires three absent replica targets and one immutable manifest. It creates the
same genesis snapshot and authority identity for all three voters, forces every
target, independently verifies them and only then publishes the bootstrap receipt.
Partial output is never startable authority and is removable only by its exact cleanup
plan. The V4 source/bundle is preserved byte-for-byte.

A live V4 store cannot be converted in place, copied as a replica or joined directly.
V4/V5 mixed-version replication, downgrade and rolling upgrade are unsupported in
V5.0. Restoring a V4 application backup creates a new group; it does not recover or
join an existing group.

## Public capability and lifecycle

V5.0 is opt-in and additive through the replication artifact. It does not change
existing `SearchEngine`, `DurableSearchEngine`, core or processor behavior.

The exact Phase 1 declaration fixture must provide:

- a replicated engine capability preserving the `SearchEngine` mutation/search
  surface on the configured leader;
- immutable group, node, endpoint, storage, bound and transport configuration;
- explicit node role/state, replication status and failure classifications;
- asynchronous startup/activation and deterministic close ownership; and
- separate offline bootstrap/inspection operations.

Every mutating SearchEngine operation, including index create/drop, enters the same
replicated order. Followers reject public searches and application mutations before
execution. Leader reads may continue at the last AppliedIndex without quorum, but the
status must expose loss of write quorum.

`currentSequence()` remains application sequence, not LogIndex. `checkpoint()` is a
node-local maintenance request over committed applied state and does not create an
application sequence. Leader `backup()` captures a writer-ordered applied committed
cut as a V4 application backup; it is not a replica-transfer artifact or existing-
group authority. Replica snapshot transfer uses the separate replicated format.

Close first stops admission, resolves or exceptionally completes accepted work,
stops transport, forces required local metadata and releases exclusive ownership.
Cancellation never retracts an entry that may already be committed.

## Protocol and security boundary

Logical protocol family `gse-replication/1.0` includes handshake, activation promise,
append, durable-entry ACK, commit proof/ACK, commit advancement, conflict response,
authority/status probe and chunked snapshot install. Every request and response binds
protocol version, group/configuration, sender/recipient, epoch/incarnation and a
stable trace/event identity. Unknown major versions, manifest mismatch, unknown nodes,
stale epochs, invalid bounds and invalid integrity fail closed.

Safety never depends on wall-clock time. Timeouts and heartbeats affect liveness and
diagnostics only. Phase 1 freezes exact frame, batch, in-flight, queue, retry, timeout,
snapshot chunk and disk-retention bounds before Phase 2 production storage.

V5.0 assumes authenticated operators, a controlled private network and non-Byzantine
members. It makes no confidentiality, peer-authentication, Internet exposure or
multi-tenant hostile-network claim. Production configuration must not bind an
unprotected endpoint to a public interface. TLS/authentication is a separately
reviewed capability; cloud evidence uses private addresses and firewall-scoped peers.

## Restart and recovery

A restarting leader cannot admit writes from local state alone. It must:

1. validate local manifest, storage, promise and commit ledgers;
2. contact at least one other voter and obtain responses from a quorum;
3. persist a new configured-leader epoch promise on a quorum, fencing older epochs;
4. select the greatest valid commit proof available from the contacted voters;
5. verify or fetch the referenced committed prefix/snapshot and committed tail;
6. discard only a proven uncommitted conflicting suffix;
7. rebuild/apply through CommitIndex and publish; and
8. admit writes only after the new-epoch activation barrier completes.

If committed data referenced by valid proof cannot be reconstructed, the group fails
closed and requires operator recovery. It must not lower CommitIndex.

A follower recovers local state, validates the leader activation and then becomes
`CATCHING_UP`. It uses contiguous log catch-up when the leader retains the range,
otherwise verified replicated snapshot installation plus a committed tail. It becomes
`READY` only at the leader-required committed boundary. A rebuilding follower with
the same manifest NodeId is allowed; changing NodeId or membership is not.

An absent/replaced voter disk has no vote until its promise, commit and history state
is reconstructed and verified. Permanent configured-leader disk replacement is an
offline operation that must contact both surviving follower identities, reconcile
their maximum promises/proofs and install valid authority before the replacement may
request activation. This prevents erased local state from participating in a quorum
that excludes the sole survivor of an earlier quorum.

Replica states are `OFFLINE`, `BOOTSTRAPPING`, `ACTIVATING`, `CATCHING_UP`, `READY`,
`DEGRADED` and `FAILED`. Only a READY voter can acknowledge new application entries;
the leader plus one READY follower can commit while the other follower catches up.

Snapshot install uses absent staging, bounded chunks, complete identity/digest
verification, atomic publication and parent force. A snapshot behind the receiver's
proven CommitIndex is rejected. Arbitrary live-directory copy is never supported.

## Observability

Every replica exposes structured group/node/configuration identity, role, epoch and
incarnation, LastLogIndex, CommitIndex, AppliedIndex, ApplicationSequence, state,
quorum availability, per-peer durable/match/applied index, lag, last quorum success,
recovery floor, snapshot-install state, retained bytes and last classified failure.

Critical events have stable schema/version, node, epoch, index and trace identity.
Failure artifacts preserve the exact deterministic event schedule and trace needed to
replay the failure.

## Exit rule

Phase 0 exits only after all linked documents and the checklist are reviewed, no
critical decision remains only in a root prompt, the documentation checks pass and a
protected-master PR accepts the candidate. Only then may Phase 1 open
`5.0.0-SNAPSHOT`. Production replication remains prohibited until Phase 2 gates.
