# Phase 2C4a — retained governing floor

Status: local component qualification; Phase 2 remains **OPEN**. This batch
establishes one retained floor from complete generation copies. It performs no
retirement deletion and does not enable a network ACK or the public runtime.

## Admission and force order

A floor copy contains the original GENERATION, complete capsule, images, promise,
optional selected BASIS/SELECTED and exact owned tail, plus any retained ancestry
or adoption certificate. All inventory members, frame bindings, lengths and
hashes are checked. The producing local owner rechecks the selected generation
and its filesystem identity after forcing/opening it and before returning the
copy observation. A source hash alone cannot stand in for those files or force
observations. Remote admission still needs authenticated ownership observations;
the helper does not authenticate a network peer by itself.

Require distinct permanent identities, the exact selected local generation and
a quorum under the certified cut's **next** authority: stable-old majority before
INTENT, both majorities after INTENT, stable-new majority after FINAL. A removed
owner cannot produce an eligible floor copy. Different cuts, catalog/application
states, duplicate voters and relabelled local generations are refused.

The new explicit `openFloors` mode shares the existing exclusive journal owner.
Legacy storage modes continue to reject its additional directory. Before writing,
reserve every copy using the existing six SOURCE and seven APPLICATION limits;
duplicate physical copies count separately from original BASIS sources and both
generations. The already-held miscellaneous reservation covers the small floor
and proposal records. No extra resource class, hard limit or frozen frame changes.

Persist the exact proposal, then each full generation/image inventory. Force all
copy directories before writing and forcing FLOOR; force its directory and parent
before return. Exact partial writes can resume using the original plan. Another
proposal, changed bytes, linked files, extra paths or live inode replacement fail
closed. While the floor transaction is incomplete, new grants, selection and
prefix installation wait for its completion. No original authority is deleted.

Reopen checks the retained complete copies and governing quorum, seals complete
visible writes, and verifies ancestry to the active generation. Subsequent local
adoption/installation must preserve that floor parent. One existing floor may be
replayed exactly; changing it is refused until explicit bounded floor rotation is
implemented. This safe refusal is not acceptance of repeated full-store progress.

## Evidence and limits

The process matrix covers sizes 3/4/5 at old, joint and final cuts, with clean runs
and halt/SIGKILL at the first occurrence of each of 17 named establishment
boundaries. Actual per-owner directories are opened and forced before their copies
are admitted. Python replay reconstructs the proposed floor from original inputs,
checks all snapshots and force order, binds every owner, and checks the complete
result after copying the evidence to a new path. Exact-reason negative variants
run only after the original evidence passes.

Unit tests enumerate governing subsets and cover duplicate/missing owners,
original-force binding, changed/lost images, partial-file resumption, shared-source
exhaustion before writing, symlinks, extra files, same-byte inode replacement,
selected unresolved tails, removal and preservation of an old floor after adoption.
The 315-case / 1260-fresh-JVM gate, all 14 negatives and portable replay passed
in 716.248 seconds. The reactor ran 142 focused Java tests; the
final floor-only run passed 15, including two lifecycle tests added afterward
(144 distinct tests). All 38 Python/build-contract tests also passed under normal
and optimized Python. The retained [receipt index](phase2-evidence/governing-floor.json) contains actual
counts, hashes, source/JAR/class provenance and log locations.

Historical certificate/transition force observations and application bytes remain
fixtures. The matrix is local filesystem work, not distributed transport or public
service acceptance. It does not qualify arbitrary repeated recovery interruption,
power loss, retirement deletion, source/floor/journal rotation or unlimited history.
Those remain explicit [Phase 2 obligations](PHASE_2_CLOSURE_CHECKLIST.md); the frozen
integrated S/N scenarios have not been replaced by these component counts.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_floor_evidence \
  scripts.test_ci_v51_bundle scripts.test_build_coordinates
python3 -m scripts.v53.floor_qualification \
  "target/v53-phase2-floor/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a fresh output directory and preserve failures. No remote execution or V5.2
Runner change is part of this local qualification.
