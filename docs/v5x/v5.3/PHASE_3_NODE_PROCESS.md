# Native node process loss and original-disk recovery

This gate covers two whole three-node histories at one completed-operation cut.
It does not close Phase 3 or claim autonomous failover, torn-write coverage or
host power-loss durability. The [receipt](phase3-evidence/node-process.json)
binds exact producer/reader sources and retained original evidence.

## Implemented history

`V53NodeProcessTest` performs public offline bootstrap and initializes the actual
retention ledgers. Node 1 runs in a separate JVM using `MembershipNodeOwner`;
nodes 2 and 3 keep their original native TCP/storage owners in the parent JVM.
The parent starts only node 1's automatic service. No synthetic vote, original
source, application image or network response is supplied to that service.

Each independent history performs:

1. Fresh election, original selection and BARRIER 1, followed by DATA 2.
2. After DATA's actual publication returns, verify node 1 still holds its
   original storage lock. Either `Runtime.halt(73)` or external SIGKILL terminates
   the child without running owner close. Retain the observed exit code and
   verify the same lock is now available.
3. Start a distinct child JVM with the same original replica, materialization,
   scratch and endpoint paths. Its service starts NEW; readiness is unavailable.
4. Complete a fresh higher-ballot election and BARRIER 3 before DATA 4, then
   drain the successor and both surviving followers.

The whole bootstrap/death/reopen history stays on one original filesystem.
There is no copying of a checkpoint into a replacement runtime directory and no
mutation replay. Each leader lifetime retains the existing 180-second fixture
budget and default transport bounds. The parent waits are test watchdogs.
These finite observations do not establish a failover latency guarantee.

## Independent evidence

Child observations are streamed through an acknowledged instrumentation pipe.
The parent retains each complete line before acknowledging it; actual replication
continues over TCP. This preserves event ordering and crash diagnostics, and
adds instrumentation overhead that must not be interpreted as a benchmark.

`node_process_evidence.py` validates the original bootstrap, all sixteen snapshot
groups and complete request/response histories before inspecting process claims.
It binds the child configuration to the original bootstrap paths, checks distinct
process IDs, halt/SIGKILL exit codes, the pre-death lock probe and post-death lock
release, and compares every child event, wire response and snapshot boundary
against its exact lifetime in the merged original history. A normal close cannot
stand in for process death; an old READY cannot stand in for the new barrier.

The new execution exposed an unselected PREPARE response racing cancellation.
The peer's exact original response was written, but no arrival was observed.
The network reader now accepts only bounded, identical, correctly scoped
unselected replies of that form, and forbids a source pull depending on them.
Selected PREPARE replies still require actual delivery. No delivery, vote or
source authority is inferred from an attempted response.

The qualification includes two native JVM tests, 21 focused Python tests,
15 exact evidence negatives per process history and the prior cold-reopen
history's 48 negatives. Invalid originals are rejected before negative mutation;
an unrelated failure cannot count as the intended rejection. Original transcripts,
failed reader diagnostics, source snapshots and test reports are retained without
JARs or class files.

## Remaining gates and rollback

This is a completed-DATA process restart, with parent-controlled successor
startup. The subsequent [in-flight gate](PHASE_3_NODE_INFLIGHT.md) adds ACCEPT
and PROOF parent-force cuts; it does not enlarge the scope of this receipt.
Other install/publication cuts, competing automatic
candidates, membership transitions and the full profile matrix remain required.
Independent whole histories may later run in parallel; the two lifetimes of one
history must not be split across runners. Public runtime and paid cloud remain
disabled for this gate.

Rollback removes the process fixture and reader plus the optional process-scope
parameters in the existing cold-reopen readers. No production Java, public API,
workflow, persisted format, POM or frozen timing/resource limit changes here.
