# Migrating to V5.1 automatic leadership

**Status:** migration guidance for published stable `5.1.0`. Final coordinates,
signed tag, canonical bytes and remote verification are recorded in the
[release checklist](RELEASE_CHECKLIST.md).

## Choose the operating mode explicitly

| Application | V5.1 behavior |
| --- | --- |
| In-memory or single-node durable core | Existing APIs; no replication dependency is required |
| Existing configured-leader replication | Continue using `ReplicatedSearchEngines` and sealed protocol 1.1 authority; activation stays explicit |
| Automatic leadership | Use `AutomaticReplicatedSearchEngines`, `AutomaticReplicationGroupConfig` and a newly sealed three-voter protocol 1.2 group |

Core, processor and optional replication must use aligned artifact versions.
Deploy a homogeneous qualified build to the three fixed voters. Keeping the
configured protocol string unchanged does not qualify mixed-binary deployment.
Automatic election does not enable membership changes, public follower reads,
rolling upgrades, multi-writer operation or hostile-network security guarantees.

## Bootstrap and startup

Prepare exactly three distinct ordered members, identities, endpoints, absent
replica targets, separate application materialization paths and an operation
directory. Preserve the immutable group configuration and bounds on restart.
`AutomaticLeadershipPolicy.forBounds(bounds)` derives the default policy; its
timeouts are configuration bounds, not a measured failover SLA.

Planning and building a stopped handle are read-only. Apply bootstrap once; if
its result is uncertain, use the original exact request/plan with `resumeBootstrap`
and inspect the durable result. Cleanup requires the public inventory-bound plan
and is limited to an eligible uncommitted operation. A committed bootstrap cannot
be undone by calling cleanup.

After bootstrap, each node builds its own local handle and calls `start()`.
Start the three nodes without waiting for each to become leader in sequence.
Status contains local observations: a previously observed leader or successful
status poll is not a lease for a subsequent mutation. Applications direct calls
to the current ready leader and handle a leadership change at every call.

The [independent consumer](../../../compatibility/v51-style-consumer/src/main/java/fixture/V51StyleConsumer.java)
and its [tests](../../../compatibility/v51-style-consumer/src/test/java/fixture/V51StyleConsumerTest.java)
show the actual typed request, configuration, stopped-handle and backup-import
APIs. These fixtures deliberately do not start a cluster; runtime behavior is
qualified by [public lifecycle](PHASE_4_PUBLIC_RUNTIME.md) and the
[accepted cloud set](PHASE_6_NATIVE_SET_ACCEPTANCE.md).

## Reads and outcomes

Automatic document/query reads use a fresh quorum barrier and a captured published
cut on the ready leader. Followers do not expose a stale-read API. A previously
successful read does not guarantee leadership or quorum for the next operation.

| Failure outcome | Caller action |
| --- | --- |
| `NOT_SUBMITTED` | No mutation was submitted; inspect reason/current leadership and apply the application's bounded admission policy |
| `INDETERMINATE` | The mutation may later be committed or recovered; reconcile application state before deciding on another submission |
| `NOT_APPLICABLE` | Mutation retry classification does not apply, including reads/lifecycle/maintenance; inspect the operation's contract |

Do not blindly replay a mutation after timeout, cancellation, disconnect or
leadership change. Cancelling a future does not roll back a durable decision.
`observedLeader()` is a hint, not an automatic redirect or proof that a write
is safe to duplicate. Application-level operation identity/reconciliation remains
the caller's responsibility.

Checkpoint and backup are maintenance operations with explicit admission and
resource bounds. A portable application backup is not a copy of replica voting
authority. Close handles before offline storage work, and retain original source
volumes until migration is independently verified.

## Configured V5.0 to automatic V5.1

1. Stop new application submissions. Resolve acknowledged and indeterminate work
   to one complete committed cut; do not export an isolated leader's stale view.
2. Export and independently verify a canonical V4 application backup through the
   supported backup API. Retain it and the old volumes; stop the old group before
   directing application traffic to the new group.
3. Bootstrap **a new GroupId** into three absent automatic targets using
   `VERIFIED_V44_BACKUP`, matching codecs, schema and complete application
   configuration, including startup index definitions. Omitting a startup index
   can cause identity verification to reject the backup before target creation.
   V4 backup formats 1.0–1.2 retain their existing verification semantics. The
   imported sequence is preserved; the new group receives a new application history.
4. Start all three automatic nodes, allow election/recovery, and compare strong
   reads with the backup oracle before enabling new submissions.
5. After successful new writes, reopening the old group does not restore current
   truth. A reverse transfer needs a separately resolved export/new-group procedure.

There is no in-place 1.1→1.2 conversion or rolling upgrade. Replica directories
are not V4 backups. Loss of an automatic voter's disk likewise requires a reviewed
new-group transfer from a fresh resolved surviving cut; it is not permission to
reuse the lost voter's old identity or perform online replacement.

For the full API, reentrancy, storage and failure contracts, see
[API/format compatibility](API_FORMAT_AND_COMPATIBILITY.md) and
[leadership/recovery](LEADERSHIP_AND_RECOVERY.md).
