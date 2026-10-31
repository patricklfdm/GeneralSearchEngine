# Phase 3 — original same-view recovery storage replay

The [same-view execution](PHASE_3_JOINING_SAME_VIEW.md) retained one complete
`3-REPLACE` bootstrap-to-FINAL/BARRIER history. Its joining voter adopted FINAL at
cut 10 while two old voters advanced to cut 11. It then used fresh ordinary grants
and a selected installation to catch up. This reader independently reconstructs
that history's storage; it does not run another workload or accept producer PASS
labels as proof.

## Derivation

`scripts.v53.joining_same_view_physical` starts with the original public bootstrap,
then composes the existing catalog, publication, placement, custody retirement and
joining initialization readers. Actual UUIDs and the selected set are observations;
expected promises, frozen BASIS packets, generation members and ledger revisions
come from the preceding derived state. Every captured grant is compared and must
be consumed exactly once.

The first newer-authority adoption is derived at FINAL, preserving the joining
owner's original lower ancestry and debts. The later same-view campaign derives
its fresh local ballot and exact selected references. Its longest source is the
old voter at cut 11, rather than the proposer at cut 10. Selected peer/learner
retention, required original ancestry, unchanged application bytes, generation,
selector, journal and both installed owners are compared to their original bytes.
The remaining owner and all joining families are also checked through retaining
cold reopen. A success receipt cannot replace any of those states.

For reclamation, derive the smallest healthy known-voter copy set satisfying both
majorities. Do not substitute all live owners: their generation references would
change the original FLOOR. A same-view successor must prove the exact local cut,
catalog and application. The local FLOOR retains its own cut; each source retains
its actual generation/catalog/application reference. A future peer endpoint does
not enter a lagging local peer ledger. Same-cut encoding remains unchanged.

From these preceding copies, derive each governing FLOOR, original source
retirement decision, compacted journal and complete deletion transaction. Compare
all captured prefixes, including intermediate authorities and retained files.
Require the local floor force before retirement and refuse release during that
transaction. No copied FLOOR supplies its own expected value.

## Execution and qualification

```bash
python3 -B -m scripts.v53.joining_same_view_physical /original/raw --qualify
```

The gate validates the unmodified original first. Each of twelve mutations uses a
separate disposable copy. Its semantic history and hash-bound capture collection
must still pass before the exact designated physical rejection. Mutations cover
extra allocation, prematurely lost peer debt, missing retained sources or prior
generations, the old owner's installation, relabeled local floor/copy references,
altered copy members, early journal pruning, missing floor force, premature floor
release and incomplete cold reseal. An unrelated error or failed original cannot
count as a successful negative.

The [batch receipt](phase3-evidence/same-view-physical.json) binds the unchanged
native input, the new reader source, tests and retained replay. The original
derivation compares 19 complete grants, 28 owner snapshots, 15 source-retirement
transactions and 225 intermediate prefixes. Ten focused conditional tests check
the covering-copy/majority boundaries and original-first negative driver.

The frozen original-first matrix passed all twelve exact negatives in 282.937
seconds. All 451 joining Python tests pass. The complete archived storage history
also passes after relocation with Python assertions disabled, producing the exact
original result in 19.747 seconds. The archive checks all 8,681 files and 1,206
directories, including empty directories. Earlier development diagnostics remain
retained and do not count as qualification; the failed native recovery is still
rejected before any negative mutation.

This gate returns **PARTIAL**, with `sameViewStorageQualified=true`.
`sameViewPhysicalQualified`, `completePhysicalQualified`, `forceAndNetworkQualified`,
`processDeathQualified` and `phase3Complete` remain false. Complete transport/export
authorization, every maintenance/installation force lifetime, profile cohorts,
process cuts and frozen acceptance mapping remain required. The healthy copy-order
projection is scoped to this original `3-REPLACE` history; it does not qualify
unobserved failures or other profiles.

There are no runtime Java, wire, POM, workflow, resource or timing changes. No
native workload, paid cloud experiment, push or workflow dispatch is needed for
this replay batch.
