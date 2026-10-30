# Migrating to V5.2 explicit replica reads

Status: final candidate preparation at `5.2.0`. Published stable is
5.1.0; final 5.2.0 artifacts and publication are pending the
[release checklist](RELEASE_CHECKLIST.md).

## Dependencies and deployment

Use aligned core and optional replication artifacts. The annotation processor
remains optional and separate. V5.2 adds six public types and one default method
to `AutomaticReplicatedSearchEngine`; configured-leader handles and ordinary
core handles gain no explicit replica-read API. Existing reads retain their
strong leader behavior. Existing third-party automatic implementations inherit
a failed future with `UnsupportedOperationException`, without invoking callbacks.

Packaged compatibility is checked against pinned published 5.1.0, including an
implementation compiled against 5.1.0 and executed with the candidate JARs.
This establishes API/binary compatibility, not mixed-version replication support.
Deploy a homogeneous fixed three-voter group. The supported cross-minor migration
is verified offline backup/import into a **new group**, using the existing
bootstrap/storage operations and explicit ownership plans. Do not assume equal
GSER/GSRP formats permit an in-place cross-minor restart or downgrade. Membership
changes, rolling upgrades and automatic client rerouting remain outside V5.2.

## Choose consistency explicitly

| Policy | What success establishes | Requirement |
| --- | --- | --- |
| `LEADER_STRONG` | One published application cut following a fresh leader/quorum barrier | Ready leader and quorum; empty minimum, wait 0 |
| `STALE_ALLOWED` | One verified locally published committed cut, possibly behind the leader | Readable local state; empty minimum, wait 0 |
| `AT_LEAST_INDEX` | One locally published cut at or beyond a same-history token's log index | Compatible token; progress wait 0–60000 ms |

Local policies require no new quorum and do not silently strengthen or downgrade
the requested consistency. Persisted proof progress alone is insufficient until
the application publication is readable. Recovery and installation may temporarily
reject reads. A token is not a commit certificate: its checksum detects malformed
bytes, not an untrusted client's forgery.

```java
var strong = new ReplicaReadOptions(ReplicaReadPolicy.LEADER_STRONG,
        Optional.empty(), 0);
// Await a successful write before this strong read if the token must cover it.
var captured = leader.read(strong, view -> view.get(id)).join();
var minimum = new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,
        Optional.of(captured.progress()), 5_000);
var later = follower.read(minimum, view -> view.get(id)).join();
```

The example assumes started handles, a known document ID and normal exceptional
completion handling. Positive progress waits are also bounded by the configured
operation timeout. A zero wait requests one scheduled capture attempt; it does
not promise an immediate inline callback. A timeout never returns a weaker result.
`ReplicaReadResult.applicationSequence()` is the application sequence of that cut;
it is not interchangeable with `progress().index()`.

## Callback and token lifetime

Use the view only on the callback's thread and only before the callback returns.
Retaining or returning its wrapper, or invoking it on another thread, fails with
`VIEW_NOT_ACTIVE`. Return values needed by the application, not the view itself.
Accepted document objects remain immutable by the existing application contract.
The view exposes queries and the captured sequence, without mutation, paging,
maintenance or underlying-engine access. Existing leader paging remains unchanged.

Keep callbacks short and cooperative; they hold the captured application view.
Do not block on same-handle operations inside the callback. Cancellation or a
deadline does not interrupt arbitrary user code or establish that accepted writes
were rolled back. GSE never automatically retries the callback.

Tokens are immutable, exactly 112 bytes, versioned and bound to group, history,
manifest digest and log index. They have no wall-clock expiry and pin no retained
snapshot. Same-history restart/leader change/compaction preserves their lower-bound
meaning; a new group/restore identity rejects them. They do not retrieve an exact
old snapshot. Malformed tokens, unsupported versions, incompatible histories and
unreached progress have distinct failure reasons. See the
[API and wire contract](API_FORMAT_AND_COMPATIBILITY.md).

## Failure handling

Unwrap exceptional futures and inspect the documented read/replication reason.
Bound retries at the application boundary only when the operation and reason
allow them; do not retry mutations merely because their response was lost.
`NOT_SUBMITTED` and `INDETERMINATE` retain their V5.1 distinction. Reconcile an
indeterminate write through application identity/state before deciding to submit
again. A later read token does not retrospectively classify a failed write.

The [accepted cloud record](PHASE_6_CLOUD_ACCEPTANCE.md) preserves real histories,
original source identities and two narrowly authorized evidence exceptions.
Neither exception changes client consistency or deployment guarantees.
