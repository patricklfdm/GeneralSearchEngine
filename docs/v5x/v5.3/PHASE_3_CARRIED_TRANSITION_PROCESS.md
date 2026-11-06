# Phase 3 — whole-group death during carried INTENT and FINAL

Phase 3 remains **OPEN**. These development process cases extend the existing
[carried transition pair](PHASE_3_CARRIED_TRANSITIONS.md). Complete interrupted
storage/network replay and source-bound cohort admission are still required.
They do not add accepted members to the twelve hosted subsets.

## Original history and process ownership

The [eight explicit cases](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedTransitionProcessTest.java)
cover INTENT and FINAL at ACCEPT rename and PROOF rename, each with `Runtime.halt(73)` and external SIGKILL. Each case starts with an
actual four-voter offline bootstrap and the existing admitted REMOVE preparation.
The initial ACCEPT is the original command, not a fabricated pending image.
Preparation is shared with the existing transition driver fixture.

The [shared process fixture](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedProcessTest.java)
starts all four original owners in one child JVM. Only node 1 starts its automatic
service; protocol exchanges use actual TCP. At the selected command and storage
callback, the parent verifies every original file lock is still held, retains
the interrupted files, and acknowledges the observation. Death bypasses close.
The parent checks that the dead JVM released all four locks before starting the
second child on the same replica, materialization and scratch directories.
There are no surviving parent voters and no client resubmission.

Both children initially refuse readiness. The successor must complete the
original command, any remaining FINAL, and a fresh stable BARRIER. The parent
checks the completed three-voter view, inactive operation, unchanged application,
and final cut 7. Entry and payload bytes remain original. Successful final close
requires every original owner to drain its process-local leases. SIGKILL is
process-failure evidence, not hardware power-loss evidence.

Transition cases retain the existing transition request timeout of 30 seconds
and enclosing 600-second service budget. The derived automatic election policy
waits 90–150 seconds before an initial campaign; this is expected idle waiting.
The parent's 630-second observation bound includes a diagnostic margin. Existing
DATA cases keep their original defaults, 180-second service and 210-second
observation bound. No production policy, resource bound or retry rule changes.

## Independent component replay

The [reader](../../../scripts/v53/native_carried_transition_process.py) first
replays the actual bootstrap, admitted prefix and old ACCEPT using the existing
transition physical reader. It then binds the two original child transcripts to
exact process identities, exit codes, original path specifications, all-group
lock observations and their merged event/response files. Responses are checked
against their recorded byte hashes; this is not full protocol network replay.

The reader requires the exact crash callback and unchanged dead directories,
original entry/payload at the interrupted vote, complete fresh round ordering,
and the final readiness receipt bound to its original publication inventory.
Every installation and snapshot must appear in order; readiness must follow the
final observed barrier and its snapshot. Fourteen exact negative
mutations run only after an unmodified original passes. Copies are disposable;
original files and failed development attempts remain retained.

A successful component receipt is **PARTIAL**. Original prefix replay and process
observations do not prove the complete interrupted storage reduction, temporal
export authority, every ACK's force ordering, or simultaneous resource bounds.
Those remain explicit false fields. In particular, matching a final generation
inventory does not establish all intermediate protocol authority. The full
process reader must be completed before extending the hosted carried-transition
catalogue. The existing 552 native histories / 246 groups / 486 archives and
516 workflow jobs remain unchanged.

## Development checks and reproduction

The retained [development index](phase3-evidence/carried-transition-process.json)
records the exact selected cases, source hashes, logs, original directories and
reader results. Unexecuted cases are not reported as passing. The full eight-case
matrix is deferred to final hosted qualification after complete reader integration.

The selected `killFinalProofRename` and `haltIntentAcceptRename` histories both
failed on the original runtime with source-capacity exhaustion, then completed
on the corrected runtime. Each corrected original passes the scoped reader and
fourteen exact negative checks (twenty-eight total). The other six declared
histories have not run. These are component development results, not final-source
hosted acceptance or a failover timing guarantee.

Run a selected development history, preserving the entire preparation and both
children together:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53NativeCarriedTransitionProcessTest#haltIntentAcceptRename' test
python3.11 -B -m scripts.v53.native_carried_transition_process \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

Do not shard individual campaigns, slots, process lives or negative variants.
The distinct whole histories can later run independently. No workflow dispatch,
cloud execution or Phase 3 closure is part of this batch. The runtime correction
below is restricted to campaign maintenance.

## Fresh-campaign source maintenance correction

The first original FINAL/PROOF-kill case reached the declared death but failed
on restart with `activation source failed` / `resource ownership/count`. The
installed exact carried vote and two original same-cut sources survived the
crash. Existing pre-grant maintenance recognized only DATA/BARRIER; fresh
campaigns therefore accumulated sources until the receiving reservation failed.
This original remains a failure and is not counted as a negative pass.

A separate campaign-only maintenance permission now admits an exact transferred
INTENT/FINAL vote with no pending context, staged application or unfinished
acceptance. Both the local campaign and incoming PREPARE use the existing
complete governing-floor path. Each source deletion still requires its original
retirement plan; installed and floor-referenced sources remain protected. The
permit pins the original generation, latest fence and complete vote bytes.
Ordinary in-flight context-command maintenance keeps its previous permission and
source lifetime. The source scheduling hint also recognizes an accepted old
tail only when the exact transferred vote can preserve it; the existing
retirement planner still decides whether each source can be removed. No
source/image limit is increased and no operation is retried.

Application-ACK crash recovery remains a separate missing axis: staged application
work is deliberately excluded from this new permission. The eight declared
cases cover the earlier exact ACCEPT/PROOF cuts only.

Before these eight cases enter the hosted catalogue, the owning reader must
derive every cold-open vote transfer and interrupted file prefix, replay each
fresh campaign's complete governing copies and source retirements, and qualify
all original TCP/export lifetimes across both JVMs. Whole-history admission must
then bind that replay to the exact source, build, tools and original archive.
The application-ACK recovery axis needs its own implementation and evidence;
the campaign-only permission does not authorize it.
