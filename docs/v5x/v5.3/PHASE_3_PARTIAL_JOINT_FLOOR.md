# Phase 3 partial joint-floor writer order

The [complete-original borrow](PHASE_3_PENDING_FLOOR_BORROW.md) and
[native 5-REPLACE entry](PHASE_3_JOINT_FLOOR_RECOVERY.md) left an important
capacity question: can an incomplete remote original require a seventh SOURCE
during recovery of a four-copy floor?

The actual `MembershipGenerationMaintenance` writer calls the handoff overload
of `establishFloor`. It writes remote copies first, ordered by original generation
digest, and the local duplicate last. Only after each replacement is fully forced
does it release that replacement's receiving scratch. Every already retained
copy keeps its original charge. The overload without handoff and context-storage
helper are outside this argument; the current production maintenance caller uses
the handoff overload. They are not new Phase 3 runtime acceptance entries.

## Interrupted writer coverage

`V53PartialJointFloorTest` exercises all four copy ordinals at four real callback
boundaries: directory creation, manifest force, first image force and first
metadata-member force. The file inventory is produced by the writer; the test
does not truncate or edit the interrupted directory. An injected I/O exception
is followed by close and reopen of the same owned directory. These are incomplete
copy bodies, not simulated partial writes within one file or process-death cuts.

The five-voter joint context uses four originals, node-1/node-2/node-5/node-6,
and two actual `prepareCurrent` calls retain PROMISE/BASIS sources at ballots 20
and 21. The historical generations are conditional fixtures. Both joint majorities
are required; historical certificate ownership is not established by these tests.

Recovery acquires remote originals in the production ordering (joining node-6
first, then node-2/node-5), through the real transfer service and pull implementation
with an in-process link. Complete retained floors use the existing byte borrow;
incomplete or absent copies use the existing receiver and accounted local images.
Each exact generation is forced before its receiver closes. The local duplicate
is resumed last; FLOOR authority is written only after every original is complete.
The clock is fixed for this bounded storage/transfer component. Request deadlines
remain identical, but this is not an elapsed-time or scheduling qualification.

Cold reopen charges `2 + ordinal` SOURCE slots. If all six are occupied, the
interrupted fourth copy is local and every remote original is complete and
borrowable. Earlier incomplete remote copies retain enough receiving capacity.
All sixteen executions finish at six SOURCE slots and seven application images,
preserving both prior PROMISE sources. No production code or limits change.

## Independent replay

`scripts.v53.partial_joint_floor_evidence` checks the original selected generation,
the two actual persisted PROMISE/BASIS pairs, exact conditional peer originals,
joint proposal, transaction-derived interrupted directories and unchanged cold
snapshots. It checks complete final bytes, source retention, resource observations,
force order and the full fresh packet/generation transfer for each permanent peer.
The matrix requires every unique ordinal/cut pair and rejects duplicates.

Each original must pass before eleven evidence mutations are attempted. Changed
scope, original bytes, proposal, cold state, premature/missing authority, lost
PROMISE storage, resource overflow, force order and missing transfers must fail
for the declared reason. The development receipt retains source/build/toolchain
inventories and all intermediate executions:
[partial-joint-floor.json](phase3-evidence/partial-joint-floor.json).

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53PartialJointFloorTest test
python3 -B -m scripts.v53.partial_joint_floor_evidence \
  general-search-engine-replication/target/v53-partial-joint-floor --qualify
```

Use a fresh execution directory for the exact sixteen-member matrix. Historical
outputs cannot be appended to a new source. The JUnit cases are bounded component
regressions; no hosted subset or planned history is added. Full admitted native
partial-body recovery, torn-file/process-death cuts, complete
remote-force/maintenance replay and final-source Phase 3 admission remain open.

The [native sixteen-history entry](PHASE_3_NATIVE_PARTIAL_JOINT_FLOOR.md) now reuses
these writer ordinals in actual 5-REPLACE admission and TCP recovery. Its evidence
is separate from this conditional matrix and does not upgrade these originals.
