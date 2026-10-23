# Coordinated maintenance across process crashes

Status: private local Phase 2 qualification. Full Phase 2 remains **OPEN**.

The [clean repeated publication lifetime](PHASE_2_PUBLICATION_LIFETIME.md) now has
a separate process-crash qualification for one original maintenance request. After
real DATA and BARRIER publications, three local owners capture fresh sources at
cut 2 under ballot 22. The new installation must still authenticate the obsolete
cut-1 source through its original 1→2 ancestry proof. The selected sources,
ballot, application image and ancestry bytes stay fixed through recovery.

## Coordinated sequence

Each child opens the retained inputs and drives the same private storage APIs:

1. Complete installation into the inactive generation and force the selector.
2. Retain a governing floor from the exact local and one other complete copy.
3. Retire the old generation under that floor's original deletion inventory.
4. Retire the obsolete original source, preserving its saved decision while the
   journal rotation and source-file deletion are incomplete.
5. Relinquish the floor only after those deletions finish, then compact the journal.
6. Recheck the exact completed installation receipt after source retirement.

Reopen can complete an existing source-retirement or floor-release decision before
the driver regains control. The driver skips already-completed work; it never
manufactures a replacement floor merely because the old one was released.
Source absence is only a test-driver progress hint: deletion authorization,
original-byte verification and interruption recovery remain inside the storage
owner. No progress flag or new authority format is added to production.

## Process matrix and independent model

The matrix pairs halt and external SIGKILL with nine boundaries:

| First interruption | Recovery interrupted again at |
| --- | --- |
| Installation manifest forced | Installation generation forced |
| Installation selector renamed | Complete floor copies forced |
| Floor authority forced | Generation retirement authority forced |
| Old generation file deleted | Original retirement authority resealed |
| Source retirement decision forced | Journal rotation forced |
| Journal rotation renamed | Saved source decision forced again |
| Old source file deleted | Saved source decision forced again |
| Governing floor relinquished | Original floor-release decision forced again |
| Floor-release authority cleared | Empty floor directory cleared |

Every case uses four fresh child JVMs: first crash, recovery crash, completion and
an unchanged duplicate. The prepared private fixture is copied between cases,
never reconstructed in a child. Those offline copies are not simultaneous live
replicas or evidence of network authentication.

The Python replay starts with both preceding publication snapshots and the exact
original captured sources. It independently derives the selected generation,
quorum floor, old-generation deletion inventory, source retirement decision,
compacted original journal frames and floor-release inventory. It composes the
existing transaction models, comparing complete event order and every retained
crash/final inventory. The final state has one generation, one source and two
physical images; the duplicate does not recreate a floor or rewrite authority.
Negative replay alters originals, observations, force order, deletion timing,
selection and final state. Relocation and Python `-O` are separate checks.

## Reproduce and scope

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53MaintenanceLifetimeTest -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.maintenance_lifetime_evidence <printed-v53MaintenanceLifetimeEvidence>
python3 -O -m scripts.v53.maintenance_lifetime_evidence <printed-v53MaintenanceLifetimeEvidence>
```

The [local evidence index](phase2-evidence/maintenance-lifetime.json) records
18 passing cases, 72 fresh child JVMs and 13 rejected evidence mutations. Both
normal and Python `-O` replay passed, including relocation. It retains source/build
hashes and development failures. Compilation first caught a wrong accessor name in the new
worker. Its first execution then correctly rejected a floor-copy request during
an incomplete installation; the driver now resumes the original installation
before requesting a floor copy. These failures required no production change.

This fixed three-voter, small-image matrix adds coordinated maintenance recovery
to the existing component gates. It does not cover every byte-tear location,
cross-view lifetime, maximal images/journals, same-ballot continuation, offline
public bootstrap or power loss. Historical bootstrap and supplied ownership
observations remain conditional. Public membership runtime stays disabled;
the [Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) remains authoritative.
