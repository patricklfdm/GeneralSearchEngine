# Phase 3 — carried-process retirement file prefixes

Phase 3 remains **OPEN**. This component extends the original
[resource-observed process cases](PHASE_3_CARRIED_PROCESS_RESOURCES.md) with
writer-held file inventories during generation retirement, source deletion and
the source transaction's nested journal rotation. It does not qualify every
transient storage operation or the full runtime resource composition.

## Original collection

The [native fixture](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedPrefixProcessTest.java)
uses the same INTENT/ACCEPT-rename halt and FINAL/PROOF-rename SIGKILL cases,
same directories, original group lock checks and successor completion. It adds
an outer wrapper with `observed/` (unchanged history and resource layouts) and
`retirement/life-1/`, `retirement/life-2/`. The optional recorder runs before the
original storage callback returns, while its journal writer remains held.
It never supplies an authority or modifies an original replica file.

Every matching callback captures the complete replica inventory, including empty
directories, exact sizes and content hashes. Content-addressed objects retain the
actual bytes. Inventory checks before and after copying reject concurrent change.
The existing recorder bounds remain 2048 captures per child, 512 files per replica,
64 MiB per file and 256 MiB of retained objects/metadata per child. This observer
adds file-copy overhead; these development cases do not measure performance.

Each collection binds the original root, PID, lifetime, terminal state and hash
of the same event bytes retained by the resource observer. Capture indices are
child-local original event indices, including intervening wire-response rows;
they are not capture ordinals or a merged index spanning both children.
Generation and source transactions cannot overlap on one owner, and a finished
collection cannot contain an unfinished retirement transaction.

The first collection ends at the acknowledged **CUT_PREFIX**, before actual
process death. It claims no later bytes or clean shutdown. The INTENT cut may
precede the first retirement: an explicit empty collection is valid only when
independent replay derives no retirement callbacks in that child. The successor
collection is **CLOSED** only after actual owner closes and drained accounting.

## Independent replay

The [reader](../../../scripts/v53/native_carried_retirement_prefixes.py) first
requires the complete original process, physical storage, force ordering,
network, temporal export, complete-copy FLOOR, continuous ledger and resource
replays. It derives expected generation/source transaction states from those
unchanged original snapshots and authority records. Captured objects never
supply expected bytes. Exact callback coverage and owner/kind/point binding
precede comparison of each complete captured inventory with its derived state.

The shared bounded content decoder preserves the existing REMOVE and carried
retirement formats. The new process collection header has its own schema;
original process transcripts and per-capture metadata are unchanged. Numeric
identity fields and sizes reject boolean substitution. Extra files, unreferenced
objects, changed objects, symlinks and missing or reused callbacks fail closed.

Qualification validates the complete unmodified original first. It then mutates
only disposable copies of the retirement sidecars, retaining the original
process/resource files and independently derived plan. Every mutation must fail
for its exact declared reason. Header identity changes, missing lifetimes and
callbacks, object corruption, borrowed-prefix corruption, wrong FLOOR authority,
early/late generation deletion, early journal rotation and leftover files all
have targeted rejection checks. An unrelated prerequisite failure earns no
negative credit. Final inventories must equal the original inventories.

The [development index](phase3-evidence/carried-process-retirement-prefixes.json)
retains both original inventories, producer source/class hashes, reader sources,
native logs and exact qualification receipts. The two original JVM pairs pass
without retries. All 1572 captured inventories match the independent states;
44 targeted mutations reject for their declared reasons. The focused Java suites
pass ten tests, and 141 related Python tests pass (50 also under optimization).
Both complete originals also replay from relocated directories under Python
optimization, yielding receipts identical to their original qualification.

| Original | First child | Successor child | Total prefixes |
| --- | --- | --- | --- |
| FINAL / PROOF rename / SIGKILL | 47, CUT_PREFIX | 548, CLOSED | 595 |
| INTENT / ACCEPT rename / halt | 0, CUT_PREFIX | 977, CLOSED | 977 |

The empty INTENT crash collection is checked against exact original callback
absence. It is not a missing-evidence waiver. The shared decoder also reads all
1176 captures from the earlier non-process INTENT/FINAL originals; the force
reader's default receipt is unchanged when prefix collection is disabled.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_retirement_prefixes \
  general-search-engine-replication/target/v53-native-carried-prefixes/run-<id> \
  --qualify
```

The scope remains generation/source/journal retirement prefixes in two process
cases. Transient FLOOR creation/release, grants, installation, votes, application
and core scratch bytes still need complete composition. Six other declared
carried process cuts, application-ACK recovery and final-source hosted cohort
acceptance remain pending. The twelve subsets and frozen workload counts are
unchanged. Receipts remain **PARTIAL**, with
`transientRetirementBytesQualified=true`, `fullTransientBytesQualified=false`,
`postCutTailObserved=false`, `wholeRuntimeResourcesQualified=false`,
`cohortAdmitted=false` and `phase3Complete=false`. This batch changes test and
independent-reader code; it changes no runtime protocol, configured limit,
workflow or paid-cloud behavior.
