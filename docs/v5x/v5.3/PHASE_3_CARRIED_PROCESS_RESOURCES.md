# Phase 3 — original carried-process resource observations

Phase 3 remains **OPEN**. This component binds the actual node budgets to the
[carried INTENT/FINAL process histories](PHASE_3_CARRIED_TRANSITION_PROCESS.md).
It qualifies observed accounting and successful owner close; it does not replace
transient physical-file capture, whole-runtime resource qualification or cohort
admission. The twelve hosted subsets and their frozen counts are unchanged.

A separate [retirement-prefix component](PHASE_3_CARRIED_PROCESS_PREFIXES.md)
now adds writer-held generation/source/journal bytes to this same original
resource wrapper. The resource-only receipts below retain their original scope;
the new component requires the full resource replay before comparing its files.

## Actual owners and observation boundaries

`MembershipNodeOwner` has a package-private opt-in for the existing bounded
resource observer. The default path keeps observations disabled. The observer
uses the actual owner's leases and limits; there is no parallel accounting pool
and no observer I/O under the resource monitor. The existing 262144-change bound
is enforced. Truncated or failed observation cannot earn acceptance.

The [process fixture](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedResourceProcessTest.java)
retains two original child lifetimes in a wrapper with `history/` and `resources/`.
The original process format, snapshot layout, TCP history, exact crash cuts and
group lock checks are unchanged. Each of four owners registers before opening,
at sequence zero with an empty budget. Every original storage/protocol callback
and wire response receives a resource sequence and usage checkpoint. Checkpoints
are observations of the live budget, not permission to infer physical bytes.
The required bootstrap/admitted-prefix replay supplies storage authority; this
child observer does not supply resource observations for that earlier preparation.

Before the first child's cut is acknowledged, the fixture writes its observations
as **CUT_PREFIX**. The prefix ends before actual halt/SIGKILL and claims no normal
drain. Later unobserved allocation changes are explicitly outside its scope.
Only the second child's successful `close()` return can produce **CLOSED**:
each original owner has an actual invocation/return pair, a final sequence and
zero leases. Closing one owner may overlap the other owners' remaining work;
its own event boundary remains exact. Close markers never stand in for a crash.

The limits remain 384 MiB metadata, 64 MiB queued control bytes and the configured
16 GiB default snapshot staging allowance. These are the existing
[resource contract](RESOURCE_AND_LIFETIME_LIMITS.md) values, not measurements of
free disk or resident memory. Reported maxima are per owner, not a simultaneous
whole-group sum. No timing limits, retry policy or capacity limits are increased.

## Independent replay and rejection checks

The [reader](../../../scripts/v53/native_carried_resource_evidence.py) first
requires the full existing original-process, physical-snapshot, storage-callback,
network, temporal-export, complete-copy FLOOR and continuous-ledger chain. It then
binds resource manifests to the original root, PID, incarnation, storage identity
and first opening event. Resource sidecar events must exactly equal the original
child events; their hashes, sequences, usage and complete inventory are checked.
Canonical identity/event equality preserves numeric types; a boolean or floating
point replacement cannot pass as an original integer through Python equality.

The existing independent resource reducer reconstructs every reservation, release,
claim, expansion and transfer. Callback checkpoints must match the reconstructed
usage. Original `NODE_OPEN` counts require a live budget. Normal close must end at
the final resource sequence, with empty usage and no later owner event. Invocation
and return checkpoints must also agree with their positions in the original
event stream. A crash prefix remains live and supplies no close markers.

Twenty-three targeted negatives cover process/storage substitution, late owner
registration, relabelled limits, truncation, observer failure, missing/gapped
changes, altered charges, omitted or type-substituted events, checkpoint substitution, false crash
close, missing/reversed/early normal close, mismatched close event boundaries,
unlinked traces and extra files. Each must fail for its exact declared reason.
The unmodified full original must pass before any mutation. Disposable copies
preserve the entire `history/` inventory byte for byte; only resource sidecars
change. The unchanged prerequisite is not rerun for each resource mutation, and
an unrelated failure earns no negative credit.

The [development index](phase3-evidence/carried-process-resources.json) records
native logs, original inventories, producer source/build hashes, exact negative
receipts and relocated optimized replay. Tool-development failures remain in
the local evidence directory and are not counted as successful native histories.
The two fresh JVM pairs contain 16 observed owner lifetimes, 31634 resource
changes and 15857 original child events. Eight crash-prefix owners retain live
charges; eight normally closed owners end empty. All 46 resource negatives reject
for their intended reasons. The earlier retained originals remain unchanged.

The new INTENT original exposed an earlier network-reader assumption: one of
15 offered heartbeat ACKs has no client delivery. `MembershipHeartbeatRound`
returns after a governing majority and cancels remaining callers; a server's
already offered reply need not be received. The reader now retains an exact
unreceived heartbeat ACK without granting contact credit. It still checks the
original send/read/reply phase, envelope and reply cut, and requires an actually
delivered majority on both sides of the governing view. Control responses still
require delivery, and a delivered heartbeat cannot cross a phase or group death.
The corrected receipt distinguishes 14 delivered replies from the one unreceived
reply. Removing a whole heartbeat sample's deliveries must still fail the
governing-contact check. The failing original is preserved and replayed without
rerunning its JVMs or changing its bytes; the runtime protocol is unchanged.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedResourceProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_resource_evidence \
  general-search-engine-replication/target/v53-native-carried-resources/run-<id> \
  --qualify
```

These two development cases are FINAL/PROOF rename with SIGKILL and
INTENT/ACCEPT rename with halt. The remaining six declared carried-transition
process cuts, application-ACK/staged recovery, transient storage/scratch capture,
full resource composition and final-source hosted acceptance remain pending.
Receipts remain **PARTIAL**, with `observedAccountingQualified=true`,
`postCutTailObserved=false`, `physicalStorageQualified=false`,
`wholeRuntimeResourcesQualified=false`, `cohortAdmitted=false` and
`phase3Complete=false`. No new hosted or paid-cloud execution is performed.
