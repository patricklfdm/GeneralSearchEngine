# Phase 2C4b — governing-floor retirement

Status: local component qualification; Phase 2 remains **OPEN**. This batch
reclaims an inactive generation only under an already retained governing floor.
It does not rotate the floor or journal, retire original BASIS sources, enable the
public runtime or issue network acknowledgements.

## Admission and durable deletion

`openRetirement` extends the same private exclusive storage owner. Before deletion,
verify the complete inactive generation, original promise/selected records, exact
current selector and retained floor quorum. The floor's full local copy must prove
ancestry to the inactive cut, and the current generation must preserve the floor's
proven parent. Refuse an inactive generation above the floor. An above-floor owned
ACCEPT is allowed to leave that slot only if its exact ACCEPT, ENTRY and payload
bytes are already in the forced active generation; unresolved ownership must also
remain in its manifest.

Force the verified old files and reserve a complete saved original using the
existing shared SOURCE/APPLICATION limits before writing the exact RETIREMENT
proposal and saved original generation. Force all saved files/directories before publishing the
RETIREMENT record. The existing frozen record binds root, owner, floor, selector
and the sorted exact path/length/hash inventory; no format or resource increase.

Check **all** remaining original and saved bytes, filesystem identities and current
protected authority before the first deletion and before each subsequent delete.
Delete only listed inactive-generation files, forcing the directory after each
one. Delete the empty generation directory, then the saved copy and proposal;
clear RETIREMENT last and force the parent. A pending retirement keeps the slot
owned and blocks other authority mutations, even after the old directory is gone.

Fresh open never treats a partially deleted generation as a new empty source.
With a retained authority and remaining old files, reconstruct the exact original
plan from the saved complete copy and reseal the authority before resuming. Once
all old files are gone, only bounded saved-copy cleanup remains; partial saved
cleanup cannot authorize further original deletion. Repeated completed calls are
no-ops. A later generation may use the released slot, but an older floor cannot
retire a newer generation.

## Corrections found by regression

- An older SELECTED generation left behind by later prefix adoption was incorrectly
  treated as a still-pending install. Compare its cut with the active cut before
  blocking progress. The regression fails when the prior predicate is restored.
- An initial retirement draft checked the current owner but omitted the saved
  retirement copy from each original-delete guard. A same-byte saved-file inode
  replacement was detected too late. The injected replacement now fails before
  deleting the first original file; both failed and corrected logs are retained.

## Qualification and limits

The process matrix uses sizes 3/4/5 and old/joint/new cuts. It qualifies clean calls,
25 named halt/SIGKILL boundaries, second/fourth original and saved-file deletions,
and another interruption during authority resealing after the original manifest
has already been deleted. Source grants are captured in actual distinct local
owner directories. Python independently reconstructs the selected generation,
floor quorum, exact retirement record and every expected intermediate inventory.
It verifies original evidence before accepting any exact-reason mutation rejection,
and replays the complete result from a different directory.

All **549 cases / 2214 fresh JVMs**, **18 exact-reason negatives** and
portable replay passed in **1665.544 seconds**. The focused reactor
passed **155 Java tests**, including 11 retirement tests. All **39 Python/build
contract tests** passed under normal and optimized Python. The [source/build/hash
index](phase2-evidence/retirement.json) points to the retained raw evidence and
failed development probes under `target/v53-phase2-retirement/`.

The saved original consumes a SOURCE slot and counts duplicate physical images.
Capacity exhaustion refuses before retirement writes; it does not delete evidence
for space. This finite component does not qualify repeated floor/source/journal
rotation or the complete physical S/N acceptance inventory. Historical membership
certificate force observations and application images are still fixtures; local
halt/SIGKILL is not a power-loss or distributed-service claim.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_retirement_evidence \
  scripts.v53.test_floor_evidence scripts.v53.test_adoption_install_evidence \
  scripts.test_ci_v51_bundle scripts.test_build_coordinates
python3 -m scripts.v53.retirement_qualification \
  "target/v53-phase2-retirement/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Preserve failed runs and use a fresh output directory. No cloud operation, workflow
change, release or V5.2 Runner action is part of this batch.
