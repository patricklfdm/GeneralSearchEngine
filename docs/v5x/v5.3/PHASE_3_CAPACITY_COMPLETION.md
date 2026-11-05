# Phase 3 — completion at the membership metadata boundary

Phase 3 and combined-resource qualification remain **OPEN**. This is a
conditional-prefix storage continuation, not an execution of the historical
membership changes or their learner operations.

## Fixed boundary and original owners

The [publication capacity regression](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53PublicationCapacityTest.java)
now includes the last admissible operation in its fixed five-voter REPLACE
history. With this exact encoding, RESERVE after 230 completed changes still fits
its complete publication reservation. The continuation starts from that
operation's conditional SEALED prefix. Three original, common voters then force
INTENT, install a fresh joint selection, force FINAL, install a fresh stable
selection, publish BARRIER and retire the completed operation. They reopen the
same directories throughout; they are not reconstructed from each new catalog.

The next RESERVE must return CAPACITY_EXCEEDED / NOT_SUBMITTED without changing
any original bytes or live reservation, and repeat that refusal on reopen.
Actual typed DATA then publishes and is read back from all three original
owners with the application sequence incremented exactly once. The whole path
keeps the frozen packet, generation, source, image and staging limits.

The complete packet/envelope of SEALED, INTENT, FINAL and the following stable
control publications must fit the initial RESERVE estimate. This check uses
actual encoded packets. It does not establish every peak allocation or that all
independent category maxima can coexist under the shared staging budget.

## Retained evidence and limits

The fixture retains complete directory snapshots for SEALED, INTENT, joint
installation, FINAL, stable installation, BARRIER, RETIRE and DATA. It also keeps
before/after refusal copies and a final stopped snapshot, including on a thrown
continuation failure. Stage progress is printed after each retained snapshot.
A success receipt is written only after the continuation and final retention
finish. The existing refusal-only reader and its directory contract are unchanged;
completion evidence uses a separate sibling directory.

The original historical capsule, its earlier observations and learner receipt
remain conditional inputs. This test exercises real storage owners after that
prefix, with explicit orchestration in one JVM. It does not qualify native TCP,
process death, forced hardware durability, independent whole-history replay,
full simultaneous physical maxima or a final-source hosted cohort. The
552-history / twelve-subset Phase 3 inventory is unchanged.

## Development observations

The first calibration incorrectly chose the prefix after 231 completed changes
as an admissible starting point. Its sizing assertion failed before creating a
storage owner. The retained scan locates operation 231 (after 230 completed
changes) as the fixed boundary; the final tests pin that boundary rather than
searching for any passing smaller history.

One complete development continuation passed in 1128.117 JUnit seconds. It
published cuts 1616 through 1620 on all three original owners, including the
final typed DATA read. Its original refusal receipts nevertheless fail the
unchanged independent receipt reader: the fixture inspected the current floor
*after* checking the empty admission event list, adding `FLOOR_COPY_BEFORE_RETURN`
to the retained list. That original evidence failure remains retained and is
not a qualified history.

The current fixture inspects the cut before delimiting admission and also checks
the exact reason/outcome, unchanged resource usage and empty event list on
reopen. The corrected isolated refusal regression passes in 91.678 JUnit seconds;
its three original before/after inventories pass the unchanged reader. Four
bounded sizing regressions, 48 Python checks, documentation contracts and the
source-selector audit also pass. A retained-packet extent check is separately
recorded; it is not a replacement for physical authority or force replay.

The final producer additionally retains BARRIER, RETIRE and stopped snapshots,
prints stage progress and checks actual packet extents against the initial
reservation. This final complete producer has not been rerun as a new full
history. That expensive execution and independent whole-history/resource
qualification remain pending for the hosted acceptance. The
[development receipt](phase3-evidence/capacity-completion.json) distinguishes the
successful storage execution, failed original evidence and corrected narrow
checks. Original failures are not rewritten or converted into negative passes.

Run the complete bounded continuation against a recorded source and retain the
log and original evidence (no GCP):

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53PublicationCapacityTest#lastAdmittedChangeCompletesAcrossReopenedOwnersThenRefusesNewMembershipAndPublishesData \
  test
```

The test deliberately verifies a large immutable prefix on every owner reopen;
its duration is not a failover or throughput measurement. Longer final-source
qualification remains eligible for the planned hosted parallel acceptance.
Removing this test and its fixture continuation methods is a test-only rollback;
production Java, persisted formats, bounds, POMs and workflows are unchanged.
