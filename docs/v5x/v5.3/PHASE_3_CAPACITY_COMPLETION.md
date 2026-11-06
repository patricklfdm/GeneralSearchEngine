# Phase 3 — completion at the membership metadata boundary

Phase 3 and combined-resource qualification remain **OPEN**. This is a
conditional-prefix storage continuation, not an execution of the historical
membership changes or their learner operations.

## Current local full-boundary result

The complete version-4 `capacity-231` original now passes local recorded-source
admission, not just the short smoke. One unretried execution on `ed6e4378` took
1117.230 JUnit seconds and retained 3,101 files (1,964,253,723 bytes). Three original
common voters completed INTENT, fresh joint selection, FINAL, fresh stable
selection, BARRIER and RETIRE. All three rejected the next RESERVE with
CAPACITY_EXCEEDED / NOT_SUBMITTED, including on reopen, and subsequently published
and read the typed DATA with application sequence 42.

Independent replay of the unmodified original, all sixteen physical negatives,
all eighteen resource/close negatives and an unchanged relocated copy passes.
It checks five slots, two campaigns, 93 call observations, 54 ownership
observations, 163 actual owner lifetimes and 165 publication boundaries. Source,
classes, tools, readers and the complete original inventory are checked before
and after replay. The [development index](phase3-evidence/capacity-boundary-original-development.json)
retains exact pins, timings and observations; earlier failed originals remain
unchanged.

This qualifies the local conditional-prefix continuation at operation 231.
The earlier 230 changes and learner receipt are still conditional; this is one
JVM with original owner reopen/close, not native TCP or process-death evidence.
Resource summary maxima are measured separately per dimension, not a claim that
they occurred together. Complete feasible runtime pressure and final-source
hosted attestation remain OPEN. This supplemental execution does not change the
current native catalogue of 566 histories, 260 execution groups, 500 raw archives
and 544 selected jobs. Older counts below describe their earlier batch.

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

At that earlier batch the complete operation-231 producer had not been rerun.
The current local result above now supplies its original-first continuation and
resource/close replay; final-source hosted acceptance remains pending. The earlier
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

## Complete hosted boundary entry

The version-3 producer/reader additionally requires the original resource
observations described below. Earlier version-2 originals keep their recorded
scope and reader; they cannot be supplemented with reconstructed observations
or admitted as a version-3 run.

The opt-in [capacity workflow](../../../.github/workflows/v53-capacity-completion.yml)
and [hosted adapter](../../../scripts/v53/capacity_completion_hosted.py) now prepare
the longer operation-231 qualification. They are supplemental to the twelve
native subsets; the 552-history native inventory is unchanged. This workflow has
not yet been dispatched and is not a Required, release or cloud gate.

Preparation freezes source, reference classes, actual tools, the owning reader
and an offline Maven repository. Execution must reproduce those classes and
dependencies, then run exactly the full operation-231 method once. It keeps the
same original owners through all five slots, both campaigns, capacity refusal
and subsequent DATA; these steps cannot be sharded. A separate verifier job
downloads the seed and complete original from the exact source/run/attempt,
checks successful execution, and performs original-first physical replay, all
sixteen exact negatives and unchanged portable replay. Failed originals and
diagnostics are retained; neither retries nor the short smoke can substitute.
The version-4 entry requires all eighteen resource/close negatives and the complete
publication-storage, owner-accounting and exact close-interval result. Dropping that result or using
the smoke's owner count for the full boundary is rejected.

The seed retains the shared 1 GiB transport limit. Only this workflow's raw bundle
uses 6 GiB for source, classes, logs and repeated snapshots. The underlying raw
history remains bounded at 4 GiB; individual archive members remain at 256 MiB,
with links, traversal and duplicate entries rejected. These are evidence-copy
limits, not runtime allowances. All other hosted adapters keep their existing
1 GiB transport default. Uncompressed temporary extraction and mutation copies
also consume disk; the 6 GiB limit is not a measured peak disk claim.

All three jobs use the existing pinned tools, print progress every minute during
their Python stages and retain artifacts for 90 days. The 360-minute job timeout
is the existing hosted infrastructure ceiling; it does not change protocol
timeouts or authorize an automatic retry. The only entry points are an explicit
dispatch or a push to `experiment/v53-capacity-completion`; ordinary development
pushes and PRs do not invoke it. No dispatch or push is part of this local batch.

A successful final receipt qualifies only the conditional capacity continuation.
It leaves historical-prefix authority, simultaneous combined resource maxima,
native process/network and Phase 3 completion false. Development checks and the
unchanged real-smoke archive transport are recorded in the
[hosted entry receipt](phase3-evidence/capacity-completion-hosted.json); synthetic
orchestration tests and smoke transport cannot replace the pending full history.

## Observed continuation resource headroom

The [resource reader](../../../scripts/v53/capacity_completion_resources.py) now
follows every real storage-owner budget created after the conditional SEALED
prefix. The producer registers each fresh budget before opening its original
directory, records every charge mutation and binds each writer callback to the
current resource sequence. This covers the maintenance, allocator and final-read
opens as well as the 93 voting/application/campaign calls. It retains 157 exact
lifetimes for the short profile; operation 231 additionally requires the six
initial/reopened refusal lifetimes, for 163. Missing or reordered opens cannot
be replaced by a producer-supplied total.

Original physical continuation replay runs first. The resource layer then
reconstructs every budget delta, requires the frozen 384 MiB metadata, 512 MiB
shared staging and 64 MiB queue limits, checks callback checkpoints and requires
all recorded budgets to drain. It separately reuses the publication physical
oracle: for each of the 15 original publications, all eleven captured file and
reservation boundaries must match the already-derived before/after generations.
Expected completion image reserves come from the independent protocol model,
not from observed counters. The collector deduplicates equal captured bytes;
it does not keep extra receiving copies alive in the runtime.

The new short original passed in approximately 90 seconds of JUnit execution.
Replay checked 3,622 mutations, 7,897 callback/open checkpoints, 157 lifetimes and
165 publication boundaries. The largest observed reservations were 36,000,334
metadata bytes and 268,465,542 staging bytes. Per-category observed maxima included
two generations, six sources and seven application slots. These are charged
maxima from this history, not a measurement of the full runtime's physical peak.
The independently derived publication snapshots reached six application slots
and one source; the larger accounting observations are outside that physical
publication scope.

The original sixteen negatives still pass. Nine additional coherent mutations
reject missing owners, a foreign root, changed limits, forged checkpoints,
missing open return, unfinished resource release, incorrect publication charges,
missing publication captures and a stale-but-valid resource checkpoint at a
publication callback. Resource manifest hashes are updated where
appropriate so these cases reach their intended semantic check. Portable replay
and original replay with Python assertions disabled agree.

Version-3 final zero accounting established only the observed budget result;
that original did not observe close-call intervals. The version-4 follow-up below
records these intervals on new originals. Every control-message lifetime,
historical-prefix authority and simultaneous full physical maxima remain separate
obligations. The complete operation-231 execution remains pending for hosted acceptance. The
[resource development receipt](phase3-evidence/capacity-completion-resources.json)
separates the actual Java source and original, current independent reader, test
results and retained development failures. No production code or frozen bound
changes in this batch.

The test deliberately verifies a large immutable prefix on every owner reopen;
its duration is not a failover or throughput measurement. Longer final-source
qualification remains eligible for the planned hosted parallel acceptance.
The hosted entry can be rolled back by removing its dedicated workflow, adapter,
tests and the optional shared archive-bound parameter; existing adapters retain
their default. Production Java, persisted formats, runtime bounds, POMs,
Required checks, release and cloud workflows are unchanged.


## Original close invocation and return

Version 4 wraps each journal in a fixture-owned `AutoCloseable` scope. Its close
checks the original live journal, records `RESOURCE_OWNER_CLOSE_BEGIN`, calls the
real journal close and records `RESOURCE_OWNER_CLOSE_RETURNED` only on success.
The surrounding try-with-resources also invokes this path when the body fails.
An already closed journal or foreign scope cannot fabricate a second lifetime.
An exception during close leaves the original incomplete interval for rejection.
This wrapper does not change production close behavior or extend any deadline.

The resource reader reuses the existing independent owner-close replay for each
original budget. It binds markers to the exact mutation checkpoints, requires
quiescent storage ownership at entry, release-only changes until return, exact
released leases and a terminal zero checkpoint. Opening must have returned
before closing begins; no event for that scope may follow successful close.
The original node and scope are checked before normalization into the shared
reader. Publication callbacks and the original 93 primary calls remain bound to
their original resource/event records.

Nine additional coherent negatives cover missing/duplicate/unknown return
markers, a later event, empty/early-return intervals, an empty starting owner,
allocation during close and pending CONTROL ownership at close entry. Updated
hashes and balanced mutations ensure these are semantic rejections. All sixteen
storage negatives and the previous nine resource negatives remain required.
Old v2/v3 receipts and v1 resource indexes cannot supply the missing observations.
Their originals remain intact under their original reader and qualification scope.

This qualifies observed conditional storage-owner close accounting only. It does
not establish OS lock release timing between callbacks, hardware durability or
whole-runtime resource lifetimes. The full operation-231 run and final-source
hosted acceptance remain pending; the short profile cannot replace them. The
[close development receipt](phase3-evidence/capacity-completion-close.json)
records the new original, exact source/classes/reader, validation and retained
failed development attempts separately from the earlier resource smoke.


The new immutable-source short execution and exact pin-bound admission pass:
157 original owner lifetimes, 1,314 release changes, 8,211 event checkpoints,
15 publications / 165 physical boundaries, sixteen storage negatives and eighteen
resource/close negatives. Portable replay and optimized-Python original replay
agree. Three new real-journal close tests, nine related Java regressions and
112 Python tests pass; sixteen close/resource tests also pass under `python -O`.
The first new-test run omitted the seed parent directory and failed before
opening journals. Its original log remains retained; a separate corrected-source
run passes all three new tests. That setup failure is not a protocol failure
or a qualified negative history.
