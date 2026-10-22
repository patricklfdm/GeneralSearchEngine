# V5.3 API, bytes and compatibility contract

Phase 0 declaration/encoding contract, with the locally reviewed
[Phase 1 declaration amendments](PHASE_1_CONTRACT_AMENDMENTS.md). The additive
declarations exist on the isolated V5.3 branch; runtime execution remains disabled. All new public
types live in `io.github.patricklfdm.generalsearch.replication`; no existing method,
record component, enum constant or configured/automatic factory is removed.

## Public declarations

Imports below use existing `SearchEngineBuilder`, `DurableStorageConfig`, replication
identity/bounds/read types, `DurableSearchEngine`, `Function`, `Instant`, `Path`,
`UUID`, `List`, `Optional`, `CompletableFuture`.
Each record has its standard canonical constructor/accessors, immutable copies of
collections, exact validation below, and no I/O. Signatures, not method bodies:

```java
public record MembershipIdentity(ReplicationNodeId nodeId, UUID storageId,
        ReplicationEndpoint endpoint) {}
public record MembershipRoot(ReplicationGroupId groupId, UUID historyId,
        String manifestDigest) {}
public record MembershipOperationId(MembershipRoot root, long number) {}
public enum MembershipChangeKind { ADD, REMOVE, REPLACE }
public enum MembershipPhase {
    NOT_FOUND, RESERVED, PREPARING, READY, SEALED, JOINT,
    COMPLETED, CANCELLED, RETIRED
}
public enum MembershipLocalState { VOTER, LEARNER, REMOVED, DRAINING }
public record MembershipChangeRequest(MembershipOperationId id,
        String expectedConfigurationDigest, MembershipChangeKind kind,
        List<MembershipIdentity> target) {}
public record MembershipView(MembershipRoot root, long generation,
        String configurationDigest, List<MembershipIdentity> oldVoters,
        List<MembershipIdentity> newVoters, Optional<MembershipOperationId> active,
        long nextOperationNumber, long retiredThrough, ReplicaReadToken applied,
        MembershipLocalState localState) {}
public record MembershipOperationStatus(MembershipOperationId id,
        MembershipPhase phase, Optional<String> requestDigest, long revision,
        Optional<ReplicaReadToken> preparedCut, Optional<ReplicaReadToken> terminalCut,
        Optional<MembershipOperationException.Reason> blockedReason) {}
public record MembershipMaintenancePlan(MembershipRoot root,
        String configurationDigest, ReplicationNodeId target, UUID nonce,
        ReplicaReadToken observedCut, List<ReplicationNodeId> readySurvivors) {}
public record MembershipReplicaConfig<K,T>(MembershipRoot root,
        MembershipIdentity localIdentity, List<MembershipIdentity> seedPeers,
        Path replicaDirectory, DurableStorageConfig<K,T> materialization,
        ReplicationBounds bounds, AutomaticLeadershipPolicy leadershipPolicy) {}
public record MembershipReplicationStatus(ReplicationNodeId localNodeId,
        AutomaticReplicationState state, Optional<MembershipView> membership,
        Optional<ReplicationNodeId> observedLeader, long promisedCounter,
        Optional<MembershipIdentity> promisedBy, long activeCounter, long provenIndex,
        long appliedIndex, long applicationSequence, int pendingOperations,
        Optional<Instant> lastQuorumSuccess, List<ReplicationPeerStatus> peers) {}
public interface MembershipSearchEngine<K,T>
        extends DurableSearchEngine<K,T> {
    CompletableFuture<MembershipReplicationStatus> start();
    MembershipReplicationStatus leadershipStatus();
    default <R> CompletableFuture<ReplicaReadResult<R>> read(ReplicaReadOptions options,
            Function<ReplicaReadView<K,T>,R> reader);
    MembershipView membershipStatus();
    CompletableFuture<MembershipView> membership();
    CompletableFuture<MembershipOperationStatus> submitMembershipChange(
            MembershipChangeRequest request);
    CompletableFuture<MembershipOperationStatus> membershipOperation(
            MembershipOperationId id);
    CompletableFuture<MembershipOperationStatus> cancelMembershipChange(
            MembershipOperationId id);
    CompletableFuture<Void> retireMembershipResults(long through);
    CompletableFuture<MembershipMaintenancePlan> planMaintenance(ReplicationNodeId target);
    CompletableFuture<Void> drainForMaintenance(MembershipMaintenancePlan plan);
}
public final class MembershipSearchEngines {
    public static final String PROTOCOL = "gse-replication/1.3";
    public static <K,T> MembershipSearchEngineBuilder<K,T> builder(
            SearchEngineBuilder<K,T> applicationBuilder,
            MembershipReplicaConfig<K,T> configuration);
}
public final class MembershipSearchEngineBuilder<K,T> {
    public SearchEngineBuilder<K,T> applicationBuilder();
    public MembershipReplicaConfig<K,T> configuration();
    public MembershipSearchEngine<K,T> build();
}
public final class MembershipOperationException extends RuntimeException {
    public enum Reason {
        NOT_LEADER, NOT_READY, BUSY, STALE_CONFIGURATION, CONFLICTING_OPERATION,
        INVALID_MEMBERSHIP, IDENTITY_REUSED, OPERATION_RETIRED, IRREVERSIBLE,
        STALE_OPERATION_NUMBER, INCOMPATIBLE_HISTORY,
        STALE_PREPARATION, LEARNER_UNAVAILABLE, CAPACITY_EXCEEDED,
        QUORUM_UNAVAILABLE, STALE_EPOCH, PROTOCOL_MISMATCH, INTEGRITY_FAILURE,
        STORAGE_FAILURE, DEADLINE_EXCEEDED, REENTRANT_CALL, REMOVED, DRAINING, CLOSED
    }
    public MembershipOperationException(Reason reason,
            AutomaticReplicationException.Outcome outcome,
            Optional<MembershipOperationId> operation, String message, Throwable cause);
    public Reason reason();
    public AutomaticReplicationException.Outcome outcome();
    public Optional<MembershipOperationId> operation();
}
```

Factories/build are pure stopped-handle construction. Only `start()` acquires files
and transport. The independent `MembershipReplicationStatus` supports variable membership without
weakening the fixed-three `AutomaticReplicationStatus` constructor. Before opening,
its membership is absent rather than fabricated. Once running, a learner/known-removed
node reports UNAVAILABLE, with its exact role in `membershipStatus()`. Local diagnostics do not authorize a write or fresh read.
All remote operations are asynchronous; no hidden leader forwarding/replay.

`membership()`, operation query and maintenance planning require a leader strong
barrier. Submission succeeds after the requested reservation is proven/applied;
it returns queryable progress, not an assertion that FINAL already happened.
Background progress may complete later. Query returns NOT_FOUND for an unallocated
number, RETIRED at/below the retained watermark, or the exact retained state.
RETIRED omits request/revision/cuts because details have been retired; it never
means the number is reusable. Same ID plus different retained request is CONFLICT;
the caller obtains `nextOperationNumber` from a strong view, and concurrent distinct
requests racing that number must not both reserve it. A gapped/future submission
is STALE_OPERATION_NUMBER; wrong root/history is INCOMPATIBLE_HISTORY. Querying
a future number still returns NOT_FOUND. These refusals precede dispatch.

Explicit cancellation and retirement are certified controls. Future cancellation
only detaches the waiter; it cannot cancel a committed/background membership
operation. Cancellation after SEAL fails IRREVERSIBLE. A public deadline before
any admission/dispatch is NOT_SUBMITTED; after possible dispatch it is INDETERMINATE.
Read-only failures are NOT_APPLICABLE. Never infer NOT_SUBMITTED from a later status.
No successful terminal outcome is synthesized on timeout. Synchronous invalid
arguments throw `IllegalArgumentException` (nulls: `NullPointerException`) before I/O.

Fresh maintenance reports are observations, not a distributed lease or remote
shutdown permission. `drainForMaintenance` is called on the named local target,
rechecks exact current root/configuration and a fresh nonce-correlated surviving
majority excluding itself, refuses an active membership operation, then stops local
admission, drains existing bounded work and checkpoints/closes. The operator must
serialize maintenance and membership and wait for rejoin before the next target.
Concurrent operators and a new failure after the check can lose availability;
the API does not claim a distributed maintenance lock. Each drain generates a new
challenge; the saved survivor list/nonce is not reused as authority. Data progress
may refresh the observation to a newer exact common cut at least as high as the
plan's token; configuration change invalidates the plan. No API kills a process or
deletes a removed replica. A stale saved plan alone is insufficient to drain.

Known-removed/draining replicas refuse all new inherited data/read operations with
existing `AutomaticReplicationException` NOT_READY; read outcome NOT_APPLICABLE,
mutation NOT_SUBMITTED before dispatch. New membership methods report REMOVED or
DRAINING. Already captured read callbacks may finish their exact old cut; uncaptured
minimum-progress waiters fail. An isolated node unaware of its removal may still
serve explicitly requested local-stale/minimum reads under the inherited contract;
neither a local role nor a local token is fresh authority.

## Offline bootstrap and learner opening

New independent types avoid the existing bootstrap plan/result constructors that
enforce exactly three targets:

```java
public enum MembershipBootstrapSource { EMPTY, VERIFIED_DURABLE_BACKUP }
public record MembershipBootstrapTarget<K,T>(MembershipIdentity identity,
        Path replicaDirectory, DurableStorageConfig<K,T> materialization) {}
public record MembershipBootstrapRequest<K,T>(ReplicationGroupId groupId,
        String configurationId, MembershipBootstrapSource source,
        Optional<Path> sourcePath, List<MembershipBootstrapTarget<K,T>> targets,
        Path operationDirectory, long maxSourceBytes, long maxOperationBytes) {}
public record MembershipBootstrapPlan(String planDigest, ReplicationGroupId groupId,
        List<Path> absentTargets, Path operationDirectory) {}
public record MembershipBootstrapResult(MembershipRoot root, String planDigest,
        String receiptDigest, long applicationSequence, Path operationDirectory) {}
public record MembershipLearnerRequest(MembershipRoot root, MembershipIdentity identity,
        MembershipChangeRequest change, Path replicaDirectory, Path operationDirectory) {}
public record MembershipLearnerPlan(String planDigest, MembershipLearnerRequest request) {}
public final class MembershipStorageOperations {
    public static <K,T> MembershipBootstrapPlan planBootstrap(SearchEngineBuilder<K,T> builder,
            MembershipBootstrapRequest<K,T> request);
    public static <K,T> MembershipBootstrapResult applyBootstrap(SearchEngineBuilder<K,T> builder,
            MembershipBootstrapRequest<K,T> request, MembershipBootstrapPlan plan);
    public static <K,T> MembershipBootstrapResult resumeBootstrap(SearchEngineBuilder<K,T> builder,
            MembershipBootstrapRequest<K,T> request, MembershipBootstrapPlan plan);
    public static MembershipBootstrapResult readBootstrapResult(Path operationDirectory);
    public static MembershipLearnerPlan planLearner(MembershipLearnerRequest request);
    public static void applyLearner(MembershipLearnerPlan plan);
    public static void resumeLearner(MembershipLearnerPlan plan);
}
```

Bootstrap verifies all 3–5 absent, distinct non-aliasing target directories, matching
schema/codec/indexes, bounded source inventory and the exact full plan before writes.
PREPARING/PREPARED/COMMITTING/COMMITTED decisions and original receipt inventory
survive interruption; never reconstruct missing committed authority from arguments.
The new history UUID is allocated and forced into the plan once, not on every resume.
Storage UUIDs are nonzero and never reused. An absent local learner directory starts
only from its exact forced admission plan; discovery peers cannot grant voter rights.
Learner plan validates identity against a verified reservation and authentic root
obtained from live peers before materialization; loss of peers returns unavailable.
Plan/resume is exact and idempotent, never a general-purpose recursive delete.
Post-failure source cleanup remains an explicit operator task after inspecting the
retained inventory; no new automatic offline cleanup API is introduced in V5.3.

Node IDs retain the existing `[a-z0-9][a-z0-9._-]{0,63}` limit. Hosts are canonical
lowercase ASCII DNS/IPv4/IPv6 text (1–253 bytes), no URLs or DNS alias identity claims;
port 1–65535. Exact host/port, node and storage identities are separately unique and
never recycled within one root. Operators must additionally ensure a single live
owner of each disk identity: cloning a disk is unsupported, not magically fenced
by its copied UUID. Paths are normalized and checked for filesystem aliasing at
admission; wire paths are bounded relative inventory names, never arbitrary paths.

## Authoritative machine catalog and byte fixtures

[format-catalog.json](format-catalog.json) fixes IDs, field names/types/order rules,
array bounds, nullability, enum spellings, maxima and command payloads for **24
storage kinds and 21 wire kinds**. [byte-fixtures.json](byte-fixtures.json) retains
45 independent syntax fixtures. These fixtures do not certify identity/quorum
semantics: the model oracles and later physical decoder must check those too.

Both families use the existing 48-byte framing shape with **new minor version 3**:
bytes 0–3 ASCII GSER (storage) / GSRP (wire); 4–5 major=1; 6–7 minor=3; 8–9 kind;
10–11 zero flags; 12–15 unsigned body length, all big-endian. Bytes 16–47 are
SHA-256(first16 || body), followed by the exact canonical ASCII JSON body. Sort
object keys lexicographically, no whitespace, decimal integers without redundant
zeros, lowercase standard JSON booleans/null, no floats, duplicate/unknown fields,
non-ASCII text or alternative base64 spellings. Arrays keep semantic order.
Member/target/identity/source/witness arrays sort by node-ID bytes and reject
duplicates; operation results sort by operation number, capsule items by contiguous
log position, inventories by relative path. Valid alternate witness sets may prove
the same immutable entry, but ACKs for different PROOF bytes cannot be combined as
if they acknowledged one exact proof record.
Validate header/length/cap before allocation, checksum, canonical bytes, shape,
then contextual authority. Reject unknown 1.x minor/kind rather than negotiate
down to a fixed-manifest interpretation. Limit nesting to 16 and decoded JSON
tokens (including object keys) to 65,536; the catalog's largest bounded form fits within these ceilings.

The immutable root identifier is the ROOT record's **embedded 32-byte checksum**,
matching the existing read-token manifest field convention. References to other
files/frames are SHA-256 of their entire exact bytes; operation/statement/config
bindings are SHA-256 of their canonical JSON values with the schema-defined root.
These are different quantities. ROOT references a GENESIS record that does not
recursively contain ROOT; GENESIS binds new group/history, verified application
bytes and source identity. Full application bytes use the existing durable backup
and operation encodings; do not re-encode search semantics in this format.

Digest inputs are exact: view/configuration digest is canonical
`{root,generation,old,new,operation}` with ordered node-ID arrays and null operation
in a stable view. This digest is used by `MembershipView.configurationDigest`,
request `expected`, and storage/wire authority/view fields. Group/history in a
public `MembershipRoot` must also match the referenced ROOT before encoding its
digest into a wire request. Request digest covers the exact catalog `request`
object; sealed binding covers exactly `{request,prepared,receipt}`. A checkpoint
statement digest covers its complete CHECKPOINT frame, and witness receipts cover
their exact phased record plus voter/storage identity. An ENTRY identity is the
digest of its full immutable framed bytes, independent of later certificate
ballot/witness representations. Catalog/application hashes cover complete retained
bytes, including application sequence. Research models use abstract identities and
hash expressions; they are not interchangeable with these production byte fixtures.

An ACCEPT witness digest is SHA-256 of canonical
`{root,voter,incarnation,phase:"ACCEPT",record:<full ACCEPT frame hash>}`; PROOF uses
phase `"PROOF"` and its full PROOF frame hash. An exact duplicate has the same receipt.
The receiver validates the referenced phased record/context and authentic sender
before counting it. No bare witness hash proves that an uncontacted voter forced it.

`cut.index` is the last proven index; `cut.view` governs the **next** index. This is
one less than the research `Authority.index`. Views carry ordered node IDs; complete
endpoint/storage descriptors are recovered from the sealed catalog/operation and
must match. A certificate preserves exact ENTRY bytes, ACCEPT witnesses and PROOF
witnesses. The entry's origin is immutable through recovery; a new current ballot
may re-prove that same entry, never silently rewrite its payload/origin/parent.

The content-addressed payload of a control ENTRY is the exact object in `commands`
of the catalog. BARRIER has empty payload bytes; DATA retains existing application
operation bytes. INTENT retains the full sealed descriptor; FINAL payload names
that binding. All referenced records must be in a validated bounded inventory or
already verified owned storage. A digest by itself is not a received body or an ACK.

Wire messages transfer missing records through SOURCE_OFFER/CHUNK/TRANSFER_COMMIT.
Offsets, transfer/session IDs, counts and hashes must match. REQUEST/ACK chunks
have empty bytes; DATA has 1..4 MiB decoded bytes and exact chunk digest. Commit
requires every byte, digest and semantic validation before selector/ACK. A voter
cannot ACK a referenced ACCEPT/PROOF/SELECTED it has not fetched and forced.
Only ROOT discovery, reservation-scoped source transfer and readiness traffic are
allowed from a learner; no PREPARE/ACCEPT/PROOF, checkpoint votes or service reads.
Voting messages bind exact sender storage identity, recipient, root, view, ballot,
correlation and sequence. Late ACKs from earlier views/sessions cannot count.

Checkpoint capsule metadata and referenced bounded records are packed into one
inventory-checked file; ranges/edges resolve references inside that complete file.
The inventory includes its exact bytes and catalog/application objects, not an
unbounded graph fetched on trust. Missing objects, loops, duplicate names, symlinks,
path traversal, orphaned required proof and size mismatch fail before installation.
The complete capsule bound includes all referenced descriptors and receipts.

## Compatibility and migration

- Existing configured 1.1 and fixed automatic 1.2 factories, disk/wire bytes,
  the six published-consumer suites plus the current V5.2 consumer, and search
  semantics remain unchanged. Preserve all seven current consumer modules.
- Existing read token v1 stays 112 bytes, G S R T magic, three zero flag bytes,
  UUIDs, immutable root digest, signed nonnegative index and its existing domain
  checksum. Membership changes within that root preserve token compatibility;
  restore/new-group transfer changes history/root, so old tokens fail.
- No in-place 1.2 manifest edit or fixed-three to membership conversion. Bootstrap
  a distinct homogeneous V5.3 group from a verified durable backup, explicitly
  transfer client routing, and retain the old group until operator acceptance.
- No mixed-version rolling upgrade, downgrade, fallback decoder or automatic
  conversion. Same-version rolling restart is separately tested. A 1.3 directory
  opened by 1.2 must reject without writing; wrong-history tokens remain errors.
- Preserve published ABI consumers and add new V5.3 declaration/runtime consumers.
  Pin actual published V5.2 source/JAR hashes after its release; the current running
  cloud source is not a published control. Nothing here authorizes a release.
