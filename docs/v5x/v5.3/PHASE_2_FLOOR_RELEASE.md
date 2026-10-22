# Phase 2C4c2 — relinquish obsolete governing-floor copies

Status: local component qualification; Phase 2 remains **OPEN**. This release is
allowed only after the inactive generation and its retirement transaction are
gone. It frees old floor-copy reservations so a new full floor can be gathered
without staging two sets of copies above the frozen shared SOURCE/image bounds.
It does not retire original BASIS sources or grant a new deletion floor.

## Exact release and crash recovery

Explicit `openMaintenance` adds release recovery to the same exclusive owner.
Require no inactive generation, selector, retirement or journal rotation pending,
and no uninstalled adoption fence. Revalidate the complete retained floor and
current ancestry. Above-floor owned bytes in the local floor copy need their exact
active copy, including unresolved ownership. An incomplete nonempty floor cannot
be discarded to make room.

Construct an existing-format RETIREMENT frame binding root, owner, selector, old
floor digest and the complete sorted file inventory. Store it as
`floor-copies/release.gsr` within existing MISC; no duplicate source/image set.
Force that record and parent directories before removing `floor.gsr` first.
The remaining copies are cleanup-only. With release pending, floor reads return
no authority and other mutations remain blocked; older open modes reject the file.

Check every remaining file and directory identity and current authority before
and after each deletion. Remove only listed copy files/directories, then the
proposal, release record last, and finally the empty floor directory. Force every
step. Pending physical directories and images retain their resource reservations;
all outstanding leases release on close/error, and new floors wait for cleanup.
A shared-capacity regression fills all six SOURCE and seven image slots before
release and verifies progress without another reservation.

If the old floor remains during reopen, reconstruct the original full decision
and allow only its exact release prefix. After the floor is removed, require a
complete release record bound to the unchanged selector and an exact remaining
subset; never reconstruct quorum authority from partial copies. Reseal release
before resuming cleanup. A completely empty directory after the final record
removal can be cleared; no nonempty evidence is discarded as an empty staging area.

Once cleanup completes, obtaining another governing floor still needs all full
copies and both applicable majorities. The current generation, original grant
sources and journal bytes remain unchanged by release. Journal compaction can
later discard a superseded promise that was referenced only by the removed floor.

## Qualification

All **261 cases / 1062 fresh JVMs**, **14 exact negatives** and portable
replay passed in **806.986 seconds**. The focused reactor passed
**176 Java tests**, including all 11 release tests. **53 Python/build contract
tests** passed normally and under `-O`. The [source/build/hash index](phase2-evidence/floor-release.json)
records retained raw results and logs under `target/v53-floor-release/`.

The independent oracle derives each exact deletion inventory and snapshot from
original per-owner source bytes; validates original evidence before exact-reason
negative mutations; and replays all retained evidence from another directory.
Coverage includes sizes 3/4/5, old/joint/new cuts, first occurrence of every named
boundary, second/fourth copy-file deletions, and another interruption during
recovery after deletion has started. Historical membership force observations and
application images remain fixtures. Process halt/SIGKILL is not power-loss or
network/public-service qualification.

Remaining Phase 2 work includes original-source lifetime, maximal staging and
completion headroom, automatic journal backpressure, actual phased votes and
application/catalog persistence, offline bootstrap/open and the integrated audit.
The public membership factory remains disabled; V5.2 experiments stay separate.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_floor_release_evidence \
  scripts.v53.test_journal_rotation_evidence scripts.v53.test_retirement_evidence \
  scripts.v53.test_floor_evidence scripts.v53.test_adoption_install_evidence \
  scripts.test_ci_v51_bundle scripts.test_build_coordinates
python3 -m scripts.v53.floor_release_qualification \
  "target/v53-floor-release/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Finish packaging before fresh-process probes and retain failed outputs under new
names. This batch changes no workflow, frozen format/resource limit or cloud task.
