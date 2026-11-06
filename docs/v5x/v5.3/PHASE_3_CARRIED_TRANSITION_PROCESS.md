# Phase 3 — whole-group death during carried INTENT and FINAL

Phase 3 remains **OPEN**. These development process cases extend the existing
[carried transition pair](PHASE_3_CARRIED_TRANSITIONS.md). Complete interrupted
force/network replay and source-bound cohort admission are still required. The
original storage snapshot reduction described below is now implemented.
The storage callback component also derives the observed force/return ordering.
Separate transport and temporal export components now bind the two retained
originals. The complete-copy maintenance component also binds their acquisition
and FLOOR lifetimes. Continuous peer/future revision replay now composes those
same originals across both JVMs; transient-file capture remains separate.
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

## Cross-lifetime transport and control replay

The [network component](../../../scripts/v53/native_carried_transition_network.py)
requires the original snapshot and callback readers before interpreting any wire
message. Its phase schedule retains the first interrupted campaign/slot and all
successor campaigns/slots. Each request uses the independently reduced current
view for that phase. Every send, server read, response and client delivery must
belong to that phase and the correct original JVM lifetime; a trace cannot be
reused across phases or group death. Unanswered writes remain unanswered.

The existing transfer validator checks every original offer, chunk, offset,
extent, digest and commit. The existing grant/installation and slot readers
bind delivered PREPARE, SELECTED, ACCEPT, PROOF, APPLY, FUTURE and PUBLISH responses
to original storage and force ordering. This includes three-voter joint-view
quorums and the final stable pair, rather than assuming the older DATA fixture's
fixed pair. The interrupted PROOF-rename history must retain both original peer
ACCEPT replies; ACCEPT-rename cannot have peer voting success. Slot sequence
numbers and reported recording quorums must match the actual governing view.

STATUS and heartbeat cuts follow the original selector/publication timeline.
Heartbeat samples require actual contact with both governing majorities; they
grant no voting or readiness authority. Each unanswered retention attempt must
name an independently derived original intent, its actual recording trace,
unselected recipient and bounded write interval. Unanswered heartbeat requests
are also retained separately. Other unexplained unanswered requests are refused.

The [network development index](phase3-evidence/carried-transition-process-network.json)
binds the same FINAL and INTENT originals, with 751/1,109 responses and 760/1,125
request writes respectively. The 9/16 unanswered attempts remain distinct from
ACKs. Twenty exact wire/event mutations per original reject after the unchanged
original passes; stored authority, applications, directory inventory and process
metadata are protected from those mutations. Child transcripts and their merged
wire/event projections change together, so a projection mismatch cannot earn
network-negative credit. Optimized replay after relocation preserves the original
inventories. These are replay checks, not new native executions.

Results remain **PARTIAL** with `fullWireReplay=false` and
`exportAuthorityQualified=false`. Complete transfer bytes and control ACKs do
not establish the temporal ownership of every exported object, its original
capability lifetime or the complete-copy maintenance source inventory. Those
bindings, transient storage captures, application-ACK recovery and final-source
hosted admission remain required. The hosted catalogue is unchanged.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_network \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

## Temporal export authority across group death

The [temporal export reader](../../../scripts/v53/native_carried_transition_exports.py)
requires all three original process/storage/callback and network components
before deriving availability. Every selected installation and publication ends
the previous generation at its selector rename. The next generation becomes
servable only after the actual completion callback. All four owners have two
separate open intervals. A transfer must finish, including delivery of its
commit reply, within the original sender's and receiver's same lifetime.

The parent-captured snapshots and actual grant/retirement callbacks bind each
immutable frozen source. A durable source surviving death is available to a new
successor transfer; it does not keep the dead JVM's original borrow alive.
Current generation manifests, original packets, exact image reuse, journal
records, native receipts and local applied checkpoints use the shared temporal
authorizers. Control payloads are reconstructed from the installed original
catalog, then checked against the retained ENTRY digest.

The interrupted phase has its own derivation. An ACCEPT rename without a complete
return supplies no receipt. At the PROOF-rename cut, the already completed local
and peer ACCEPTs can serve their exact records, payload and ACCEPT observations.
The unfinished PROOF does not become a receipt or application ACK. A fresh promise
ends the live vote capability; group death ends every process-local capability.
The complete successor slots retain their separate original force boundaries.

The [process export index](phase3-evidence/carried-transition-process-exports.json)
records the same two original histories, their unchanged inventories, reader
hashes and portable optimized replay. Nine exact byte/timing mutations per
history must first pass the full physical and attempted-network precondition.
They cover aliases, generation bytes, source ballot/promise, native receipt
identity and force timing, and completed checkpoint identity. Invalid originals
and unrelated rejections never count as negative success. A wrong-view mutation
is already refused by the transport precondition and earns no export-negative
credit. Focused regressions separately exercise retirement, selector gaps and
cross-death windows without claiming additional native histories.

Receipts remain **PARTIAL**, with `observedExportAuthorityQualified=true`.
Complete-copy floor composition, transient force bytes, application/scratch
inventory and simultaneous resource accounting remain separate obligations.
Callback observations do not establish unrecorded wall-clock expiry behavior.
No Java history, cloud run or hosted catalogue entry is added by this reader.
Six declared process cases and the application-ACK crash axis remain outstanding.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_exports \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

## Complete-copy maintenance through restart

The [maintenance reader](../../../scripts/v53/native_carried_transition_maintenance.py)
requires the complete original process, physical, callback, transport and export
replays. It predicts each required FLOOR and its governing owners from the
independently derived original state, including the exact reaccepted vote and
campaign-only source retirement. Observed FLOOR counts do not define this plan.
Unselected owners remain in the original group comparison.

Each cold JVM starts with one ordered discovery pass over its original peers.
These STATUS replies remain route hints. Each maintenance transaction then has
two actual local-copy callbacks: capture before remote acquisition and recheck
after every complete remote copy arrives. For each required peer, the reader
binds its own fresh STATUS, packet-only transfer, exact local borrowed images,
generation metadata and commit delivery. A startup hint, earlier floor hint,
partial packet, installation ACK or equal terminal hash cannot supply that copy.
Before-grant maintenance checks the original local ballot for the proposer and
the incoming ballot for participating peers; in-slot maintenance uses its exact
selected ballot. Every packet and metadata request must preserve that context.

The copied owner identities, manifests, packets and image inventories must equal
the predicted governing cohort. Both governing majorities remain required. The
existing independent copy model derives every FLOOR write/force, handoff and
release callback. Generation/source deletion must stay inside that forced
authority interval. Each local copy, remote discovery and required floor is
consumed exactly once. Complete network copies stay distinct from direct fixture
calls; these histories have no direct fixture floor.

The [maintenance development index](phase3-evidence/carried-transition-process-maintenance.json)
retains the same two original histories and unchanged full inventories. FINAL
has eleven floors / twenty-nine copies; INTENT has sixteen floors / forty-four
copies. Together they bind forty-six remote acquisitions, twelve separate
startup hints and fifty-four local capture/recheck callbacks. Eleven exact
mutations per original cover missing/duplicate local checks, early local recheck,
late metadata, missing/duplicated startup probes, borrowed startup hints, wrong
acquisition ballots and packet/metadata order. All mutated originals must first
pass physical, callback, transport and export replay; an unrelated earlier
refusal cannot earn maintenance-negative credit.

Focused regressions also reject foreign copy bytes, a wrong governing owner set,
reused floor/hint authority and unconsumed required observations. Relocated
optimized Python replay preserves the original results. These checks add no
native executions, hosted catalogue entries or runtime Java changes.
The component result remains **PARTIAL**, with
`completeCopyFloorLifetimesQualified=true`. Continuous peer/future revisions are
handled by the separate component below. Transient-file capture, full resource
qualification, the remaining six process cases, application-ACK recovery and
final-source admission remain open. Earlier component receipts preserve their
narrower scopes.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_maintenance \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> --qualify
```

## Continuous retention revisions across both JVMs

The [retention reader](../../../scripts/v53/native_carried_transition_retention.py)
requires the complete original process, physical, callback, network, export and
maintenance readers. It derives the admitted prefix once. Every later installed,
applied, published, interrupted, reopened and closed inventory is a comparison,
never a new ledger seed. Each of the four owners has two distinct original open
reseals; the second JVM must preserve the first JVM's exact revision and bytes.
Transaction forces must fit wholly inside one original owner lifetime.

Peer revisions come from the actual governing copies, selected frozen sources
and certified publication targets. Each resulting write has exactly seven
ordered persistence callbacks, the previous ledger digest, unchanged identity and
one incremented revision. Maintenance changes remain after FLOOR completion and
before retirement; selected changes remain after installation force and before
their completion callback. Every captured source contains the then-current
derived ledger. No write or selected completion may remain unexplained.

Future revisions derive each exact applied certificate and target obligation,
bind the original recording request and its forced digest/revision ACK, and
require promotion and clearing in their original publication intervals. The
proposer's record completes before sending; a remote ACK follows its own forced
record. Both retained crash cuts precede future recording, so they demonstrate
unchanged future state across death and subsequent continuous recording, not
an interrupted future-record crash axis. Application-ACK/staged application cuts
remain outstanding.

The [retention development index](phase3-evidence/carried-transition-process-retention.json)
keeps the original runtime source and full inventories. FINAL derives 25 peer
and 13 future writes; INTENT derives 43 peer and 22 future writes. Across the two
originals, 378 comparisons and 32 ledger reseals bind these 103 writes. Original
histories are reused without executing a new JVM or altering any runtime code.
Relocated optimized replay must reproduce the same complete component receipt.

Fifteen peer and thirteen future mutations per original exercise missing or
reordered force, incomplete/unbound writes, resumed reseals, maintenance before
floor or after retirement, selected completion, publication, recording and clear
ordering. The unmodified complete original must pass first; physical bytes,
wire responses, parent actions and every non-target callback stay unchanged.
The mutated callback history is tested directly by its owning ledger reader:
earlier count/order guards overlap these mutations, so the full prerequisite is
not rerun on mutated inputs. Only the declared ledger reason earns rejection
credit. Unit tests separately reject wrong predecessors, owner changes, writes
spanning death and resetting a ledger from a later snapshot.

Results remain **PARTIAL**, with `retentionRevisionCompositionQualified=true`.
This is no claim of transient-file capture, core scratch replay, simultaneous
resource qualification, all eight process cases or final-source cohort admission.
Earlier component receipts and their narrower flags remain unchanged, as does
the twelve-subset hosted catalogue.

```bash
python3.11 -B -m scripts.v53.native_carried_transition_retention \
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
force/deletion prefix, and compose the observed TCP/export lifetimes with complete
maintenance and resource authority across both JVMs. Whole-history admission must
then bind that replay to the exact source, build, tools and original archive.
The application-ACK recovery axis needs its own implementation and evidence;
the campaign-only permission does not authorize it.
