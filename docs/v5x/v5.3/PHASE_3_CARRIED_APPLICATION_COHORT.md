# Application-ACK histories in the carried-transition cohort

Phase 3 remains **OPEN**. The carried-transition execution, cohort and hosted
schemas are now **v4**. The existing two ordinary histories and eight
ACCEPT/PROOF process histories remain mandatory. Four new whole histories use
`V53NativeCarriedApplicationTransientPrefixTest`:

| Case | Exact method |
| --- | --- |
| `intent-application-halt` | `haltIntentApplicationTransientPrefixes` |
| `intent-application-kill` | `killIntentApplicationTransientPrefixes` |
| `final-application-halt` | `haltFinalApplicationTransientPrefixes` |
| `final-application-kill` | `killFinalApplicationTransientPrefixes` |

Each original includes the application ACK cut, termination of the first group
JVM, recovery from its actual disks, carried completion and the fresh stable
BARRIER. The nine capture families, both resource lifetimes and all four voters
remain in that original. The normal completion capture belongs only to life 2;
the dedicated interrupted application capture owns the life-1 prefix. PID and
terminal-state checks prevent exchanging these two captures.

The [application adapter](../../../scripts/v53/native_carried_application_capture_history.py)
requires the complete unmodified physical, protocol, export, retention,
resource, captured-file and owner chain before **any** negative. It then runs
all four original-first capture stages and balanced owner mutations:

| Stage | Exact rejections per original |
| --- | ---: |
| Votes, recovery completion, peer/future ledgers, control replay | 116 |
| Ordinary retirement, FLOOR and campaign captures | 89 |
| Old application-end retirement | 29 |
| Interrupted first application ACK | 24 |
| Original charge owners, with accounting totals preserved | 10 |
| Total | **268** |

Each stage must reproduce its exact prerequisite result; every negative keeps
its exact case/status/reason. Both original inventories are preserved. The only
callback overlap allowed by the underlying reader is matching old-end/control
REPLAY observations; those bytes and original event identities must agree and
are counted once. This is nine-family capture qualification, not the complete
simultaneous runtime resource envelope.

The existing cohort binds the exact command, single unretried JUnit method,
recorded source, actual compiled classes, portable toolchain, reader, original
plan and raw inventory. No older producer is re-labelled as v4. Collection
returns `PARTIAL`. Full subset acceptance requires **14 originals and 3,354
exact negative rejections** on the same source/build/toolchain/reader; the hosted
aggregate additionally binds run/attempt and all workflow stages. The workflow
matrix is derived from the catalogue, so no parallel handwritten list is added.
The complete Phase 3 inventory becomes **564 histories, 258 execution groups,
498 raw archives and 540 selected jobs**, across the same twelve subsets.

## Bounded receipts and retained evidence

Both the outer nine-family owner projection and nested five-family projection
can contain large callback arrays. After their full positive and negative
replay, each is summarized with its complete canonical SHA-256, eight exact
owner lifetimes, per-owner and snapshot hashes, callback totals and ten original
mutation targets. The raw archive still retains every input file and resource
trace. Summary checks reject missing owners, booleans used as counters, wrong
owner categories, omitted targets and mismatched totals. The existing 8 MiB
JSON reader limit is unchanged. A compact receipt alone cannot replace the
original-first verifier or source/build admission.

## Development validation and remaining work

The retained corrected FINAL/SIGKILL development original from the
[transient-capture batch](PHASE_3_CARRIED_APPLICATION_TRANSIENTS.md) exercises
this new adapter without a new Java execution. Its source remains the recorded
`7e63a097` development snapshot plus explicit changes; it is **not** a final-source
v4 cohort member. The original earlier ownership failure remains retained.
The new entry replayed that retained original in 496.551 seconds: all 268 exact
negatives passed, and all 10,599 files (80,274,926 bytes) remained unchanged.
The complete bounded result, including negatives, is 98,308 bytes and passes
the unchanged JSON reader. Both full owner projections were replayed before
compaction. This is reader validation of one earlier source, not a new native
execution or v4 cohort admission.

All 503 related Python tests passed. The 55 focused entry/hosted/workflow tests
also passed with assertions disabled; the 85-test planning suite is included in
the related total. These suites include synthetic orchestration, not native
acceptance. All 526 preceding evidence indexes remain unchanged. Logs, the
retained-reader result and source-inventory audits are recorded separately in
`target/v53-carried-application-cohort/`; final-source execution of all fourteen
histories and independent downloaded replay remain pending.

Long native runs use the existing [hosted entry](PHASE_3_CARRIED_TRANSITION_HOSTED.md)
after publication/dispatch authorization. This batch dispatches nothing, changes
no Required CI or paid-cloud behavior, and runs no full native matrix locally.
The frozen Phase 5 acceptance plan is unchanged and all five Phase 3 gaps stay
OPEN. Rollback restores v3 adapter schemas, ten-case catalogue, planning hashes,
tests and current scheduling counts together. Preserve the native fixtures,
readers, runtime custody correction and all previous evidence.
