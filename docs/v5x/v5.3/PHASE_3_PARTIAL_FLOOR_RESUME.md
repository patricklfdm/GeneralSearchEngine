# Phase 3 explicit recovery of an original partial floor

This component qualifies completion of the partial floor retained by the
[failed resource probe](PHASE_3_COMBINED_RESOURCE_PROBE.md). The original failure
remains FAIL. Unlike the [unassisted cold observation](PHASE_3_COLD_RESOURCE_CONTINUATION.md),
the required node-2 now participates in every subsequent campaign and reaches
the stable barrier. Missing-copy discovery is still supplied explicitly by the
test; autonomous recovery and complete Phase 3 admission remain open.

## One original history

`V53PartialFloorResumeTest` uses the same admitted 4-REMOVE preparation and native
pressure failure. The extra receiving files are released and every old endpoint,
transport and journal closes. The same replica/materialization directories and
bootstrap identities remain in use.

The test reopens the actual four original owners and reads their complete current
generation copies. It does not use a retained evidence snapshot as runtime input,
bootstrap again, alter a generation, discard the pending ACCEPT, or enlarge a
resource/time limit. These are explicit in-process storage-copy observations,
not TCP transfers or automatic peer discovery.

1. The original node-2 proposal requires node-1/node-2/node-3. Offering the real
   same-cut node-1/node-2/node-4 quorum must refuse. All four directories remain
   byte-for-byte unchanged. The refused owner closes before another open.
2. Offering the exact original three copies completes that same proposal through
   the existing `establishFloor` transaction. It forces every original member,
   copy directory, FLOOR authority and parent in the prescribed order.
3. A second cold storage open validates the completed original floor. Seven
   physical application images remain present and charged. Node-1's original
   unresolved INTENT remains unchanged; no preceding authority is deleted.
4. A new native driver opens those same stores. The required node-2 participates
   in the two node-1/node-2/node-3 selections and the node-1/node-2 stable selection.
   The original INTENT bytes survive; FINAL and BARRIER complete at indices 6/7.

The native run passed in 333.039 seconds including its isolated build. Its exact
source, actual toolchain, logs and collected artifacts are bound in the
[development receipt](phase3-evidence/partial-floor-resume.json).

## Independent storage replay

`scripts.v53.partial_floor_resume_evidence` first diagnoses the retained pressure
prefix. It independently reconstructs the admitted installed generations, then
requires the supplied copy bytes to equal those originals. It derives the exact
proposal and complete floor inventory, matches all four owners before rejection,
after rejection, after resume and after cold reopen, and checks force order and
resource observations. Thirteen original-first mutation cases cover altered
originals/proposals, rejection side effects, missing copies/ACCEPT/force events,
changed cold authority, invented headroom and overclaimed scope. Originals remain
unchanged throughout negative replay.

This is a **PASS for explicit-original-copy storage resume**. The later native
continuation is an observation, not full independent selection/retirement/network
replay. The reader and receipt keep `automaticRecoveryQualified=false`,
`completeContinuationReplayQualified=false` and `phase3Complete=false`.
Normal-runtime reachability of the original externally held pressure overlap is
still unproved. This test does not establish the maximum metadata envelope,
SIGKILL/power-loss behavior or every interrupted-floor position.

## Next implementation boundary

On this historical source automatic maintenance rejected pending floor storage.
The subsequent [automatic recovery change](PHASE_3_AUTOMATIC_FLOOR_RESUME.md)
implements sequential acquisition for complete original proposals. It must acquire
missing originals under its existing fence and original deadline, using the
persisted proposal as an exact locator, never as deletion/vote authority. The
final existing floor transaction remains responsible for full copy validation
and publication of authority. Equal-cut replacement generations or another
available majority cannot replace that proposal.

Partial files and every receiving copy must stay charged during acquisition.
In particular, a floor containing three complete copies but lacking its final
FLOOR record can leave less metadata/source capacity than the one-copy prefix
used here. Automatic recovery must handle or safely refuse that state without
inventing capacity, prematurely deleting a physical copy or using a partial
proposal as remembered remote force authority. Missing/torn proposal bytes,
advanced peers and changed proposals need explicit refusal/recovery coverage.

No production implementation, POM, workflow, Required job or hosted cohort is
changed by this component. Eleven optional subsets still describe 512 planned
histories; final-source cohort execution remains pending.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.partial.floor.resume=true \
  -Dtest=V53PartialFloorResumeTest test
python3 -B -m scripts.v53.partial_floor_resume_evidence "$ORIGINAL_HISTORY" --qualify
```
