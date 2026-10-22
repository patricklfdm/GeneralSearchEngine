# Phase 2C4c — bounded exact journal rotation

Status: local component qualification; Phase 2 remains **OPEN**. This transaction
compacts superseded promise-only grants. It retains all physically retained source
identities, every original BASIS/SELECTED, promises referenced by current and local
floor manifests, and the highest durable promise. No record is synthesized and no
source or floor is deleted.

## Storage transaction

Explicit `openRotating` extends the exclusive owner. Rotation requires no inactive
generation, pending selector, incomplete floor or retirement. Retain complete
original grant groups in ballot order. A captured source lacking BASIS still needs
its original PROMISE; retaining only completed BASIS groups would orphan that
source on reopen. A targeted mutant reproduced this error, and the corrected
regression preserves the source and its counted reservation.

Six source groups and current/floor/latest promise-only groups occupy at most
565248 framed bytes under the frozen catalog. The 1 MiB candidate cap fits in the
already reserved 2 MiB miscellaneous envelope. This does not allocate another
32 MiB JOURNAL or waive duplicate-image reservations. All six original sources
remain counted; exhaustion still safely refuses additional source capture.

Write the exact deterministic compact prefix to `grants.rotation.gsr`, force it,
atomically replace `grants.gsr`, then force the parent. Check original owner,
selector, retained floor, sources and candidate inode/hash around each boundary.
Reopen first validates complete authority, then completes only the exact pending
prefix. Pending rotation blocks other authority mutations, and older open modes
reject its extra file. Preserve the highest forced promise and any higher volatile
observation; compaction does not let an incomplete duplicate grant become valid.

## Qualification

All **135 cases / 558 fresh JVMs**, **15 exact negatives** and portable
replay passed in **488.473 seconds**. The focused reactor passed
**165 Java tests**, including all 10 new rotation tests. **46 Python/build contract
tests** passed normally and under `-O`. The [source/build/hash index](phase2-evidence/journal-rotation.json)
retains provenance, regression logs and raw receipt identity at
`target/v53-journal-rotation/`.

The independent Python oracle reconstructs original grants, source/floor/current
inventories and all intermediate candidate/rename snapshots. Coverage includes
sizes 3/4/5, old/joint/new cuts, all six named halt/SIGKILL boundaries and another
interruption during recovery. Negative replay first validates the unmodified
original; rejection must match the exact expected reason. Relocated replay uses
the same retained bytes. Java regressions also cover same-content inode swaps,
changed candidate bytes, higher observation fencing, occupied generation slots,
six retained sources, source capture interrupted before BASIS and explicit bounds.

Historical membership force observations and application images remain fixtures.
Fresh-process halt/SIGKILL is not power-loss or distributed service qualification.
This batch does not establish automatic 32 MiB backpressure, source/floor rotation,
unlimited campaigns, actual phased vote/application storage or public runtime.
The complete storage and pre-cloud checklists remain OPEN.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_journal_rotation_evidence \
  scripts.v53.test_retirement_evidence scripts.v53.test_floor_evidence \
  scripts.v53.test_adoption_install_evidence scripts.test_ci_v51_bundle \
  scripts.test_build_coordinates
python3 -m scripts.v53.journal_rotation_qualification \
  "target/v53-journal-rotation/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a fresh output directory and finish the reactor package before process probes.
No workflow, public factory, frozen format/resource bound or V5.2 Runner change.
