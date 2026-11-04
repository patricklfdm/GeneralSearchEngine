# Pinned-floor process interruption and cold recovery

Status: **36 process cases and independent physical replay PASS**. This gate extends the
[conditional pinned-floor lifecycle](PHASE_3_PINNED_FLOOR.md). It does not replace
the required-four native history or the full final-source qualification.

## Process and original-file contract

The preceding membership certificates remain conditional fixture inputs. Two
real selected installations leave the original current, inactive predecessor and
two original BASIS sources. Every case begins with identical, retained seed
bytes. The local original is retained in place; three peer originals are copied.
The complete FLOOR still contains four voters and satisfies both majorities.

Eighteen boundaries each run once with `Runtime.halt` and once with external
SIGKILL: floor directory creation, forcing the local original, local selector
write/force/parent force, proposal force, first remote image force, FLOOR parent
force/return, retirement parent force/first member deletion/directory deletion,
source journal compaction, and release parent force/relinquishment/first member
deletion/local marker removal/authority removal.

Each of the 36 cases uses three distinct JVMs: the interrupted owner, recovery in
the same directory, and a second cold inspection. The SIGKILL driver waits for
the exact callback marker, checks the original owner lock from a separate JVM,
and records the actual exit. Only processes created by the driver are killed.
The history retains seed, crash, reopened, final and cold inventories; callback
logs, PIDs, exit statuses and lock-probe results remain associated with each case.
There is no power-loss claim.

Recovery derives authority from forced original bytes. An incomplete floor cannot
authorize predecessor deletion. Completed floors retain the exact local generation
until release; predecessor retirement and source compaction resume their existing
authority. Release never lists or deletes the current generation. Final/cold
inventories preserve the original selected grant and leave one SOURCE owner and
two APPLICATION owners; closing releases all leases.

## Independent qualification

`scripts.v53.pinned_floor_process_evidence` derives the expected floor, retirement,
source compaction and release from the seed, not from produced snapshots. It
checks every crash/reopen/final/cold inventory, exact force order, original current
lifetime, unchanged peers, process identities and actual exit outcomes. Every
projected boundary stays within six SOURCE and seven APPLICATION owners; observed
callback counts are separately checked. These component bounds do not qualify
every simultaneous network/control/waiter/publication maximum.

The unmodified complete evidence must pass first. Eleven copy-only mutations then
require exact rejection reasons: absent pin, changed local image, deleted
predecessor, changed retirement backup or reopened original, changed cold selector,
invented premature FLOOR, missing force, false kill exit, reused process identity,
and missing case. Inventories reject symlinks/hardlinks and bound input size. The
original directory must remain unchanged through validation and negative replay.

The original matrix passed in **177.751 seconds**, with 108 worker
executions and 18 additional lock probes. Independent replay accepted all 36
original cases, then rejected eleven mutations for their declared reasons.
The related Python reader suites passed 34 tests. The
[retained evidence index](phase3-evidence/pinned-floor-process.json) binds raw
inventories, reports, readers and the implementation used. Production Java was
unchanged from `25d80cb3`; this batch adds the process producer and reader.

## Reproduction and remaining scope

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.pinned.floor.process=true \
  '-Dtest=V53PinnedFloorProcessTest' test
python3 -m scripts.v53.pinned_floor_process_evidence "$ORIGINAL" --qualify
```

Retain the printed original directory and Maven log. This opt-in component matrix
adds no frozen native history, hosted subset, release admission or Phase 4 API.
The existing twelve subsets / 544 planned histories and original-source binding
remain unchanged. Full native floor/maintenance/network replay, combined resource
maxima and final-source qualification remain required. Phase 3 is OPEN.

Rollback removes only the optional test/worker, reader and evidence references.
It neither reverts the storage correction nor makes an incomplete history pass.
