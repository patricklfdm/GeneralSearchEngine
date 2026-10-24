# Phase 2: typed bootstrap through repeated process death

This batch qualifies the actual private typed coordinator across all six
3/4/5-voter and EMPTY/verified-backup profiles. Phase 2 remains **OPEN**.

The matrix has six first-cut boundaries per profile, each under `Runtime.halt`
and external SIGKILL: typed source recheck, PREPARED, COMMITTING, first admission
force, first completed seal, and COMMITTED before return. A second fresh worker
dies again during the next seal prefix (or journal recovery if all seals already
completed). A third worker finishes the exact original operation. Planning occurs
once in the parent and retains its original random history; this is not additional
planning-crash coverage.

After COMMITTING, the harness moves the original source and retained projection
away. Recovery uses the committed original authority, without regenerating the
source or selecting a new history. Before that boundary the actual typed checks
still run. Worker requests retain the exact original codecs, configuration,
identities, directories and budgets.

In 24 cases the first voter already has its seal. Its actual admitted store stays
open in the parent, reserves counters, forces a real grant/BASIS/source and retains
a derived core marker while the next two workers recover the rest of the group.
Both recoveries leave that voter's mutable files unchanged. External lock probes
confirm ownership remains held; another counter can be reserved afterwards.
Snapshots never open a second descriptor for a live lock file.

## Evidence

The [local index](phase2-evidence/bootstrap-typed-process.json) records 72 cases,
216 fresh coordinator workers and 48 external lock probes: 264 child processes
in total. All worker exit codes, complete stdout traces and empty stderr are
checked. The independent replay derives the original plan/image, all admissions,
the original transaction, real grant/source/counters, exact first-crash/running/
second-crash/final inventories and returned original result. Sixteen mutations
must fail for their exact expected reason after unmodified evidence first passes.
Normal and optimized Python plus a relocated copy must agree.

Core and replication production JARs are byte-identical to the preceding
[progressed-target recovery](PHASE_2_BOOTSTRAP_PROGRESS_RESUME.md) batch; the index
also binds compiled classes, all producer inputs, raw file hashes and test logs.

## Boundary

The Python replay checks physical and grant authority; application codec semantics
are executed by the actual Java typed reader, not independently reimplemented in
Python. Process death is not a power-loss/filesystem durability simulation.
Public bootstrap entry, transferred pending-context owner lifetime, maximal and
cross-view resource lifetime, and the complete Phase 2 requirement audit remain
open. Online membership and learner operations are still disabled. No workflow,
cloud, POM, legacy-format or frozen-limit change is part of this batch.
