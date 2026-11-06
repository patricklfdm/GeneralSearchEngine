# Phase 3 — resources across carried application-ACK recovery

Phase 3 remains **OPEN**. The application-ACK path now has a dedicated resource
composition reader and four native process methods: INTENT/FINAL, each with
`Runtime.halt` or external SIGKILL at `APPLY_ACK_DIRECTORY_FORCED`. They reuse
the admitted four-owner REMOVE preparation, original directories and existing
630-second child budget. No runtime, resource limit or protocol format changes.

## Original lifetimes

The first JVM retains all four original ownership locks through the declared
application-ACK cut. It never records a successful close. A second JVM reopens
those same stores, retires the superseded application result under its original
certificate, finishes the inherited command and fresh stable barrier, then
closes all four owners. The experiment records no client calls.

The existing observer supplies per-owner transition journals, storage identities,
registration points, complete storage/TCP event checkpoints and actual close
invocation/return markers. The new adapter first requires the complete
[application ownership chain](PHASE_3_CARRIED_APPLICATION_OWNERSHIP.md), including
physical state, process boundaries, callbacks, TCP, export capabilities, complete
FLOOR copies and continuous peer/future ledgers. Only then does it invoke the
shared resource decoder. The ACCEPT/PROOF entry retains its own prerequisite;
it does not silently accept application-ACK originals.

The shared decoder binds each of the eight owner lifetimes to its original PID,
storage identity and event stream. It replays every resource delta, checks each
callback's derived usage and keeps the original configured limits: 384 MiB
metadata, 16 GiB staging and 64 MiB queue for these default-bound fixtures. Crash
prefixes must remain open with no close markers. Each surviving owner must end
at its own final empty sequence, with both real close markers and no subsequent
owner event. Another process's close or a stale empty checkpoint cannot satisfy
that obligation.

## Rejection and evidence

All 23 existing resource mutations run after the unmodified application chain
passes. They cover wrong PID/storage/registration, changed limits, truncated or
failed observers, missing transitions, changed charges/checkpoints, omitted
events, relabelled crash/close, missing or reordered close markers, unlinked
traces and extra files. Each mutation preserves the entire original history and
must fail for its exact reason. A failed prerequisite or unrelated error earns
no rejection credit. Originals are checked again after qualification.

The application-file projection also gains an explicit ACK-force stop. It keeps
the complete forced end but emits no `APPLY_BEFORE_RETURN`. Callback binding
accepts that unfinished transaction only for the declared owner at the final
`APPLY_ACK_DIRECTORY_FORCED` event. A different owner, earlier boundary, later
event, nonvoting end or another unfinished transaction rejects. The default
projection and callback reader still require normal completion. This prepares
the interrupted-end oracle; it does not manufacture captured intermediate files.

The focused tests use synthetic journals to check composition and refusal; they
do not manufacture native application evidence. Native execution and independent
portable replay are recorded separately under
`target/v53-carried-application-resources`. The producer freezes source files,
compiled classes, toolchain and unretried JUnit results. Its baseline commit is
not an assertion that uncommitted test/reader additions already belonged to that
commit; the retained source inventory identifies the actual development bytes.

The [development receipt](phase3-evidence/carried-application-resources-development.json)
records two unretried native methods: FINAL/SIGKILL (583.620 seconds) and
INTENT/halt (624.684 seconds). Both passed; reactor execution including build
took 1,223.284 seconds. The source snapshot contains the unchanged `ab01c028`
files plus the three new resource adapter/test files, and retains its exact
compiled classes and toolchain. This is development execution, not a final-source
hosted cohort.

Copied INTENT and FINAL originals passed their complete application chains and
23 exact resource negatives each in 71.970 and 68.185 seconds respectively.
All 16 owner lifetimes are checked: eight crash prefixes and eight actual normal
closes. Both copied originals are explicitly refused by the unchanged
ACCEPT/PROOF entry. All 10,719 original files (89,737,486 bytes), compiled classes
and 391 earlier evidence indexes remain unchanged. The new application-stop
model separately matches the 32 original application callbacks and exact final
forced end in each history; intermediate captured files are still pending.

The accounting journals identify concrete overlap targets: two generations,
six sources and seven application slots coexist in six owner lifetimes per
history. These are same-owner/same-sequence observations, not a sum of unrelated
peaks. They do not bind every charge to physical files or qualify the full
metadata envelope: the largest observed metadata reservations are 36,115,531
and 36,243,990 bytes, below the configured 384 MiB limit.

The 239 related Python tests, 54 projection/composition regressions, 21 optimized
resource tests and 11 optimized projection tests pass; these suites overlap.
The six new resource-composition tests are included in those counts. Planning,
documentation and whitespace checks also pass. No full reactor suite, remaining
two native axes, hosted dispatch or paid-cloud execution is claimed.

```bash
python3 -B -m scripts.v53.native_carried_application_resources ORIGINAL_RESOURCE_WRAPPER --qualify
python3 -B -m unittest scripts.v53.test_native_carried_application_resources
```

## Remaining work

This component establishes observed accounting after the full original authority
chain, not callback-by-callback physical charge ownership or the simultaneous
resource maximum. Transient capture must also cover the old application's
certificate/replay/retirement boundaries, the interrupted application-end write,
and all existing campaign, vote, ledger, FLOOR and publication families. Reusing
the ACCEPT/PROOF capture envelope without those extra boundaries is insufficient.
Complete source-bound admission and final hosted execution of all application
axes remain pending. Existing `physicalStorageQualified`,
`wholeRuntimeResourcesQualified`, `cohortAdmitted` and `phase3Complete` flags stay
false. The twelve admitted catalogue counts are unchanged by these development
fixtures.

Rollback removes the application-specific adapter, test methods and planning
references together. Preserve the originals and previous ACCEPT/PROOF resource
reader; no persisted state migration is involved.
