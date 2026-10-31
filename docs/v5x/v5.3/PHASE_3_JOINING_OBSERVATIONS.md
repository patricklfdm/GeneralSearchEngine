# Whole joining observations and execution entry

Phase 3 remains **OPEN**. This batch completes fixture instrumentation and adds
an isolated execution/collection entry. It does not qualify the complete joining
history, every profile, process-death recovery, or public readiness.

The previous [confirmed-ledger history](phase3-evidence/joining-confirmations.json)
completed functional FINAL, BARRIER and stable cold reopen, but its JUnit execution
failed while serializing the global event array. Its missing events cannot be
recreated. The [later whole execution and catalog replay](PHASE_3_JOINING_CATALOG_REPLAY.md)
now pass on `df22c398`; complete physical/force/network qualification remains open.

## Actual observation coverage

`V53JoiningIntentExportTest` now records the new node's real callbacks from learner
plan/admission and typed materialization through pending/published INTENT,
voter staging, custody, placement, retirement, native owner initialization and
subsequent retaining opens. These callbacks share the old nodes' synchronized
event list. The `scope` identifies the callback registration; it is not a claim
that opening succeeded, a capability, a timestamp, or a durable incarnation.

New-node transport observations retain attempted requests (including those with
no reply), actual response reads, and actual receiver response-write boundaries.
Only the receiver adds the wire pair, avoiding duplicate exchanges when the
caller observes the same reply. The actual transport callback precedes the write;
it does not claim the peer received or durably processed that reply. The complete
force/network oracle must still establish those dependencies from original bytes.

The manual SEAL now captures APPLIED and PUBLISHED old-owner snapshots. The joint
continuation captures both actual installations, FINAL/BARRIER APPLIED and
PUBLISHED old-owner snapshots, and corresponding portable fifteen-root joining
snapshots. FUTURE_QUORUM_COMPLETE and round records remain observed in the shared
trace. Stable cold-open/close return markers occur only after those operations
return; an additional snapshot retains the actual post-close files.

The bounded array writer is also used for continuation traces. Existing aggregate
byte limits and per-record format checks remain unchanged. No production Java,
runtime timeout, resource bound, POM, workflow, or frozen format changes.

## One indivisible long execution

With the existing Java 21/Maven dependencies already available, run from the
repository root:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH \
python3 -B -u -m scripts.v53.joining_history_run \
  "target/v53-joining-history/run-$(date -u +%Y%m%dT%H%M%SZ)-$$" \
  --maven /opt/maven/bin/mvn
```

The entry copies tracked source plus untracked V5.3 replication sources, Python
tools and documentation into a new workspace. The exact source manifest, not
`baseHead` alone, identifies that copy; uncommitted source is included. It runs
only `joiningInitializerStartsBeforeOldPreparationAndCompletesNativeHistory`
using offline Maven. Collection runs in a fresh Python process rooted in the
same copy, including its original format/catalog inputs. Source bytes are
rechecked afterward. A source manifest,
Maven/JDK report, compiled-class inventory, execution receipt, JUnit report, raw
history and log remain in the new directory. Existing output is never reused.

Every 60 seconds it emits elapsed time, process ID and the latest log line.
This heartbeat does not retry the history or alter its native deadlines. User
interruption terminates the child process group and retains the failed attempt.
No workflow, remote call, paid cloud execution, push or release is triggered.

The collector requires the exact successful whole JUnit method, all stage
snapshots, global traces, new-node callback scopes and actual cold-return markers.
It checks portable joining inventories and runs the existing original-source
confirmed-ledger reader. Raw file hashes and empty directories are retained and
checked unchanged across collection. Collection is bounded at 65,536 members and
512 MiB; these are evidence-reader limits, not changes to runtime bounds.

Three results remain distinct:

- `executionStatus=PASS`: the single whole JUnit method succeeded, including close.
- `status=PARTIAL`, `collectionComplete=true`: required observations and the
  existing ledger derivation are present. A collection failure preserves a
  successful execution status separately.
- `nativeHistoryQualified=false`, `forceAndNetworkQualified=false`: complete
  physical/history/force/network replay is still required. Neither a fixture
  result file nor this collection receipt substitutes for that replay.

Keep bootstrap, joining, initialization, FINAL/BARRIER and retaining cold reopen
on one original filesystem. Hosted parallelism may run independent whole cases;
it must not split or stitch this history. The older failed attempt remains failed.

## Validation and remaining work

The [batch receipt](phase3-evidence/joining-observations.json) records 11 passing
Java component tests, 46 passing Python tests, the source manifest and retained
archive hashes. It left corrected whole execution pending at that batch; the
newer execution and replay receipt above records its subsequent result separately.

Focused Java tests check callback ordering across threads/owners, attempted writes
without successful wire evidence, distinct scopes and bounded serialization.
Python checks exercise exact JUnit identity, failure/skip refusal, source mutation,
links/byte bounds, duplicate JSON keys, large histories, missing observations,
failure retention and heartbeat behavior. Synthetic collection unit inputs test
collection boundaries only; they are not executed consensus evidence.

The corrected whole history has now passed through this entry. Extend independent
physical and force/network replay to every selection and new-node lifetime.
Complete seven-profile coverage, native process/network cuts and Phase 3 mapping
remain separate required gates. Successful execution does not close those gates.
