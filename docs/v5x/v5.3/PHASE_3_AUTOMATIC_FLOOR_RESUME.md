# Phase 3 automatic resumption of an original partial floor

Native generation maintenance can now resume a complete original proposal left
by interrupted floor construction. The proposal selects the exact owner and
generation references; it does not attest to remote force or authorize deletion.
Maintenance discovers and fetches each original through the existing transport,
validates its full materialization and authenticated force observation, and
rejects an equal-cut replacement generation or a different available quorum.

Each freshly verified remote copy is forced into the retained floor directory,
including both parents, before its receiving scratch is drained. The local copy
is staged last. All existing partial files remain charged. Only the final
existing `establishFloor` transaction writes FLOOR authority after validating
every original. Fresh PREPARE remains blocked until required maintenance finishes.
The original campaign deadline, fencing checks, close/drain ownership and fixed
resource limits are unchanged.

Missing original owners produce a bounded unavailable outcome. Missing/torn
proposal bytes, release/retirement in progress, conflicting retained bytes and
changed local generations remain fail-closed; this change does not reconstruct
an unknown proposal. Full proposal reconstruction and other interrupted states
remain separate obligations.

## Evidence and tests

`V53FloorResumeCopyTest` exercises one, two and three retained copy prefixes;
three retained copies plus two other SOURCE leases can reacquire originals one
receiver at a time within the six-slot bound. It also exercises a different
same-cut generation/proposal, interrupted force boundaries, revocation at force,
torn proposals and changed member bytes. These storage fixtures are not claims
about simultaneous native maximum metadata occupancy or process power loss.

`V53CombinedResourceRecoveryTest` retains the original admitted 4-REMOVE pressure
failure, closes every original actor, and opens the same directories. It now
requires native maintenance to recover node-2 without the explicit in-process
copy injection used by `V53PartialFloorResumeTest`. Node-2 must participate in
the next three selected cohorts and reach the stable BARRIER at index 7; the
original unresolved INTENT bytes and origin must survive. The prior externally
extended pressure lifetime remains an injected failure, not proved normal-runtime
reachability. Historical failed and surviving-majority evidence remains unchanged.

`scripts.v53.automatic_floor_resume_evidence` independently derives the original
installed generations, proposal, complete node-2 floor inventory and force order.
It checks unchanged before-network directories, the captured native event prefix,
storage resource callbacks through FLOOR return, seven physical images and the
subsequent required-voter observations. Original-first mutation replay rejects
missing originals/forces, changed preconditions/commands and invented scope or
headroom. The reader does not independently reduce every remote force reply,
selection, retirement or subsequent publication. It reports automatic discovery
and continuation as **OBSERVED**, not full Phase 3 admission.

The [development receipt](phase3-evidence/automatic-floor-resume.json) binds local
source snapshots, actual toolchain, executions and replay results. Eleven hosted
subsets / 512 planned histories remain unchanged. Final-source qualification,
full metadata envelopes, legitimate controller overlap, required joint quorums
and remaining process/fencing lifecycle combinations remain open. No workflow,
Required check, POM, resource limit or paid-cloud path changes in this batch.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.combined.recovery.probe=true \
  -Dtest=V53CombinedResourceRecoveryTest test
python3 -B -m scripts.v53.automatic_floor_resume_evidence "$ORIGINAL_HISTORY" --qualify
```
