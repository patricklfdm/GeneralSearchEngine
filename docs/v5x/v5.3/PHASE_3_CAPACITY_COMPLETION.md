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

The shared continuation producer now retains the SEALED starting owners and all
ACCEPT, PROOF, CERTIFICATE, applied-end, published and reclaimed files at each of
five slots. Both campaigns retain PREPARE, SELECTED, installed and reclaimed
files; the proposer allocates each new counter through the original owner.
Actual call events and returned ownership observations accompany these files.
The capacity profile also keeps the rejected command and before/after refusal
copies. A stopped snapshot is retained on success or failure, and a success
receipt is written only after final retention. Stage progress is printed after
each snapshot. The existing refusal-only reader remains unchanged.

The [independent continuation reader](../../../scripts/v53/capacity_completion_evidence.py)
derives each vote, proof, checkpoint, catalog, generation, retained source and
reclamation result. It compares every original file, checks both governing
majorities and force-before-return order, and independently decodes the actual
core application image, including document order, sequence and both active
index descriptors. The existing cross-view reader keeps its original single
index expectation; this fixture explicitly uses PREFIX(value) and RANGE(id).

The caller must choose `capacity-231` or `replay-smoke-1`. The same Java producer
and Python continuation logic serve both, but the fixed initial cut, operation
and receipt must match the selected profile. The short profile has no capacity
refusal and returns `capacityBoundary=false`. It cannot satisfy the operation-231
qualification. The reader checks the unmodified original before mutations and
requires the exact rejection reason for every negative. Portable replay reads
unchanged copied originals.

The original historical capsule, its earlier observations and learner receipt
remain conditional inputs. This test exercises real storage owners after that
prefix, with explicit orchestration in one JVM. It does not qualify native TCP,
process death, forced hardware durability, independent historical-prefix replay,
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

The current producer retains every phase rather than only the earlier named
endpoints. Its short original-owner continuation passed in 77.38 JUnit seconds;
independent replay checked five slots, two campaigns, 93 call observations and
54 ownership observations. All sixteen evidence mutations were rejected at the
expected checks, and portable replay passed. This is a reader/producer smoke,
not a full capacity result. An initial reader-development attempt failed by
passing byte dictionaries to a JSON comparison helper; its failure is retained,
and the correction compares original byte inventories directly.

The current complete operation-231 producer has not been rerun. That expensive
execution and independent full-boundary/resource qualification remain pending
for hosted acceptance. The earlier
[development receipt](phase3-evidence/capacity-completion.json) distinguishes the
successful storage execution, failed original evidence and corrected narrow
checks. The [continuation replay receipt](phase3-evidence/capacity-completion-replay.json)
records this batch separately. Original failures are not rewritten or converted
into negative passes.

The final reader gives identical results with Python assertions disabled. Sixty-four
focused Python checks and ten existing Java regressions pass alongside the one
new native smoke. Replaying the unchanged earlier four-profile cross-view
originals still passes all sixty slots and sixteen existing negatives. These
are local development checks, not the final frozen-toolchain hosted cohort.

Run the complete bounded continuation against a recorded source and retain the
log and original evidence (no GCP):

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53PublicationCapacityTest#lastAdmittedChangeCompletesAcrossReopenedOwnersThenRefusesNewMembershipAndPublishesData \
  test
python3.11 -B -m scripts.v53.capacity_completion_evidence \
  general-search-engine-replication/target/v53-publication-capacity/run-<id>-completion \
  --profile capacity-231
```

For the short producer/replay smoke, run `V53CapacityCompletionReplayTest` with
the same Maven options and replay its printed evidence directory using
`--profile replay-smoke-1`. The full boundary and the smoke each remain one
continuous history: do not split their individual slots, campaigns or refusals
into separately scheduled experiments. Their starting prefix and learner
receipt are still conditional.

## Recorded-source execution and admission

The [capacity entry](../../../scripts/v53/capacity_completion_run.py) now runs
either explicit profile in a fresh immutable source copy. It records complete
source hashes, original class inventories, actual Maven/Java tool binaries,
the owning Python reader set, exactly one unretried JUnit method and both
execution/collection process receipts. A failed attempt stays in its own output
directory; collection alone always returns PARTIAL and grants no capacity or
continuation qualification. It prints the current stage, process and latest log
line every minute while a subprocess is running. Collector output uses exclusive
creation and cannot be written into the raw history; verifier output must be
outside the producer. Existing evidence is not overwritten.

Verification checks the caller's source/build/toolchain/reader pins, every
recorded source and class, exact raw directory, complete collection and original
test result. It then replays the unmodified history, all sixteen exact negatives
and an unchanged relocated copy, and checks the producer again. Extra histories,
changed bytes, skipped/flaky/retried tests, missing negatives and profile
substitution are rejected. The complete history stays indivisible.

The 4 GiB collection bound covers repeated evidence snapshots, not a runtime
allowance. All protocol/resource limits remain frozen. This conditional entry
is supplemental to the twelve native network/process subsets; it does not
change their 552 histories or 486 archives and cannot close native historical
authority, combined physical maxima or Phase 3 by itself. The full operation-231
entry is implemented but has not yet been executed and admitted on final source.

Use new directories for each attempt. The generated `pins.json` can be used for
local verification; final hosted qualification must reconcile these identities
with the independently retained source/build seed, not just trust the producer's
own file. No workflow is dispatched by these commands:

```bash
python3.11 -B -m scripts.v53.capacity_completion_run capture \
  target/v53-capacity-final/attempt-1 --profile capacity-231
python3.11 -B -m scripts.v53.capacity_completion_run verify \
  target/v53-capacity-final/replay-1 --profile capacity-231 \
  --producer target/v53-capacity-final/attempt-1 \
  --pins target/v53-capacity-final/attempt-1/pins.json
```

`--maven`, when supplied, names Maven's `bin/mvn` executable rather than a wrapper.
The same entry with `--profile replay-smoke-1` is a short pipeline check;
its successful replay explicitly leaves `capacityBoundaryQualified=false`.
The [entry development receipt](phase3-evidence/capacity-completion-entry.json)
separates that check from the pending full boundary and hosted attestation.
The final development entry passed one original short execution, exact admission,
all sixteen physical negatives and unchanged replay after relocating the entire
producer. Seventy-seven focused Python checks passed. This recorded development
source snapshot is not a final-commit or hosted execution attestation.

The test deliberately verifies a large immutable prefix on every owner reopen;
its duration is not a failover or throughput measurement. Longer final-source
qualification remains eligible for the planned hosted parallel acceptance.
Removing the continuation tests, reader and optional fixture tracing is a test-only rollback;
production Java, persisted formats, bounds, POMs and workflows are unchanged.
