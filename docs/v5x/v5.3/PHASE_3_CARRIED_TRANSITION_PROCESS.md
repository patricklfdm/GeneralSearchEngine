# Phase 3 — whole-group death during carried INTENT and FINAL

Phase 3 remains **OPEN**. These development process cases extend the existing
[carried transition pair](PHASE_3_CARRIED_TRANSITIONS.md). Complete interrupted
force/network replay and source-bound cohort admission are still required. The
original storage snapshot reduction described below is now implemented.
The storage callback component also derives the observed force/return ordering;
transient-file and complete TCP/export replay remain separate obligations.
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

## Original storage snapshot reduction

The separate [physical component reader](../../../scripts/v53/native_carried_transition_physical.py)
first requires the complete process component above. It then independently
reduces the admitted prefix again and derives every retained snapshot of all four
owners. It uses observed fresh source UUIDs and the selected voting cohort, but
does not take expected votes, sources, catalogs, generations or ledgers from the
observed snapshots. Both governing majorities are checked before installation.

Cold reopening preserves a current vote's original phase. Transferring an older
vote derives only the exact new ACCEPT for the original entry and payload; it
does not carry over a previous ballot's PROOF or create an application ACK.
The ACCEPT-rename cut changes only the local voter. At the PROOF-rename cut,
the selected peers have accepted but only the local owner has the new proof and
its preceding generation maintenance. Both the interrupted snapshot and the
unchanged dead directories must equal this derived state.

Each successor campaign derives governing FLOOR coverage, peer observations,
generation retirement and source/journal pruning before its fresh grant. The
campaign-only permission preserves the exact transferred context vote. Ordinary
in-slot context maintenance retains its previous source/journal ownership. New
promise/basis/selection records, source packets and generations are then derived
from that state. The confirmation-aware ledger merge uses already-derived
original provenance; older DATA/inherited-future callers keep their strict default
merge. Unselected and removed owners remain part of every full comparison.

The reducer preserves the original carried entry through application and
publication, derives any remaining FINAL, and derives the new stable BARRIER.
All captured applied ends, checkpoints, peer/FUTURE ledgers, ready and close
inventories must match. Staged application crash recovery is still excluded.
The component result stays **PARTIAL**, with `snapshotByteReplay=true` and
`fullForceReplay=false`, `fullWireReplay=false`, `cohortAdmitted=false`.
The unchanged process component's `completePhysicalReplay=false` describes its
own narrower scope. Neither component establishes temporal export authority or
the exact force/deletion prefixes between these snapshots.

The [storage development index](phase3-evidence/carried-transition-physical.json)
retains reader hashes, original inventories and receipts. The same two previously
executed native histories pass snapshot reduction and twenty exact storage
mutations each. The mutations cover cold votes, interrupted peers, original and
reclaimed sources, applied catalogs/ACKs/images, publication ledgers, the fresh
barrier and unselected owners. In two cases both dead-directory copies change
together: their mutual equality still holds, but the derived original state
rejects them. An invalid original or unrelated rejection cannot earn negative
credit. Optimized Python replay after relocation preserves every original byte.
No Java history was rerun for this reader batch; no additional process cases
are claimed. Existing DATA full network replay and uninterrupted FINAL physical
replay also pass after the shared helper change.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_physical \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

## Original storage callback ordering

The [callback reader](../../../scripts/v53/native_carried_transition_forces.py)
first requires the complete snapshot and process components. For both original
JVM lifetimes it then derives cold recovery, campaign grants and installation,
carried voting, application, publication and covered-file deletion order. FLOOR,
generation retirement, source retirement, journal rotation and FLOOR release
callbacks come from the existing independent transaction models. Ledger revision
changes require the corresponding complete original write/force sequences.

Campaign source retirement above the published floor requires the exact
transferred successor vote and all original ACCEPT, entry and payload bytes in
the retained packet. Sources below the floor still require the original floor
authority. The shared retirement helper keeps its strict default for older
callers; only this owning reader supplies the additional successor proof.
Ordinary in-slot maintenance does not gain that campaign permission.

A rename cut cannot imply parent force, return or an ACK. Repeated idempotent
vote ACKs must follow the original complete write. Applied-end callbacks are
derived from their original files; publication must retain and then delete the
exact derived covered end. Storage callbacks outside a cold/campaign/slot
interval, unexpected callback fields and cold vote recovery inserted inside a
fresh slot are rejected. Core replay milestones are ordered, but this component
does not yet derive its complete scratch inventory.

The [callback development index](phase3-evidence/carried-transition-forces.json)
records the two unchanged originals, thirty-one exact negative checks per
original, focused regression results and portable optimized replay. Mutations
change both matching child/merged callback transcripts while preserving all
storage and wire bytes, paths and directory inventory. The unmodified original
must pass first; an unrelated refusal earns no negative credit. Development
failures exposed incorrect callback targeting in the INTENT negative driver:
both cold transfer and the later vote contain ACCEPT writes. The corrected
negative driver targets the actual slot, including its early-ACK mutation.
These tool-development failures remain retained separately from runtime evidence.

Receipts remain **PARTIAL**, with `observedStorageCallbacks=true`,
`transientBytesCaptured=false`, `coreScratchInventoryReplay=false`,
`fullForceReplay=false` and `fullWireReplay=false`. Callback order and final
snapshots do not prove every intermediate candidate/deletion byte or temporal
export authority. No Java history was rerun, no new native case was added, and
the hosted catalogue is unchanged. Existing DATA network replay and uninterrupted
FINAL retirement replay also pass with the shared helper's unchanged default.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_forces \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

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
extend the completed cold-vote and snapshot reduction through every exact
force/deletion prefix, and qualify all original TCP/export lifetimes across
both JVMs. Whole-history admission must
then bind that replay to the exact source, build, tools and original archive.
The application-ACK recovery axis needs its own implementation and evidence;
the campaign-only permission does not authorize it.
