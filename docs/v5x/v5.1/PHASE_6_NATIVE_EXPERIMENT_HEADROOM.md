# Native experiment first-run headroom

**Status:** headroom correction accepted through PR #303 at master
`366e379455ad7628a81160db604e09b09ffe9e0e`,
[CI 37703102993](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37703102993).
The subsequent [native run 37706121942](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37706121942)
stayed within every time budget but failed the healthy final durable-cut check.
The [shutdown correction below](#healthy-shutdown-correction) is a local candidate;
corrected-source protected CI and a fresh explicitly approved experiment remain required.
This supersedes the current native timing in the
[preparation budget amendment](PHASE_6_PREPARATION_BUDGET.md); that document retains
the historical v1 limits. It does not retrospectively qualify the failed run.

## Earlier observation-budget failure

Preparation completed in about 1398 seconds. Healthy's published V4.4 mode passed
in 151.876 seconds. The published V5.0 mode reached its 300-second ceiling during
its final durability observation, after all 90 workload calls and backup succeeded.
The original query `98721d1c1f04416e8b6f34bcf52e8f75` started with approximately
3.9 seconds remaining. The guest retained a successful READY/proven-index-73
response, but the controller did not obtain a terminal receipt within that budget.
This is a controller observation timeout; it is not a complete healthy PASS.
The candidate V5.1 mode and the three fault cells did not execute.

Validation/retention then exhausted 600 seconds. It attempted collection from
unstarted fault groups and repeatedly used a shared 30-second service-stop budget
for three serial members. Cleanup confirmed all thirteen resources absent, but
retention was incomplete and the lease was not released. The complete run-step
duration was approximately 45 minutes, below the outer 100-minute timeout.

Original artifact SHA-256:
`98e649a16b2fc846ff4de8f5bc73b86546759a5585d6cf5d3976560b3187e72e`.
Downloaded evidence and diagnosis remain under
`target/v51-native-failure-37689820061/`. These observations establish this run's
failure path, not a guarantee about future network or engine performance.

## New fixed native request profile

A fresh `gse-v51-native-request-v2` includes
`timingProfile: owned-experiment-v2`. The request digest and reviewed plan bind the
profile, source, original package, SSH identity, prices and reservation. Only the
native four-cell `experiment` accepts it. The fake domain, canonical and failure
drill keep their existing limits. Old native v1 requests remain valid for ledger
inspection and expired cleanup with their original 5400-second lease and
1080-second grace. No stored lease is extended or migrated.

| Boundary | Previous native seconds | New native seconds |
| --- | ---: | ---: |
| Complete preparation | 1800 | 3600 |
| Each healthy mode | 300 | 900 |
| Healthy category, all three modes | 900 | 2700 |
| Leader loss | 120 | 600 |
| Maintenance | 240 | 900 |
| No quorum | 120 | 600 |
| Validation and evidence retention | 600 | 1800 |
| Exact-resource cleanup | 600 | 900 |
| Control and final completion | 540 | 900 |
| Allocated total | 4920 | 12000 |
| Absolute lease and per-VM maximum run duration | 5400 | 14400 |
| Unallocated lease reserve | 480 | 2400 |
| Expired-cleanup operation grace | 1080 | 1800 |
| Outer Runner process | 6000 | 15000 |
| Runner job | 7200 | 16200 |
| Manual/scheduled cleanup job | 900 | 1800 |

The outer process/job allow exit, cleanup and upload overhead; they never extend
the owner's absolute lease. A stage cannot borrow another stage's allocation.
The cumulative ledger ceiling remains **USD 200**, without resetting or refunding
prior attempts. Fresh pricing must cover at least **19800 seconds** (preparation plus VM lifetime plus
grace). VM lifetime starts when the VM is created; including preparation also
covers a VM allocated late in that stage. The 900-second approval freshness is still an admission check, not an
execution lifetime. Existing prepared requests must be replaced after merge.

Controller observation ceilings also move together: activation, final durability
convergence, retained rejoin and a three-member service shutdown receive 180
seconds each; fault progress and maintenance pin observation receive 300 seconds.
The native fault JVM receives the same closed profile and allows a 300-second
paused read; the ordinary test worker keeps its 60-second emergency release.
Independent replay binds the exact JVM arguments as well as the elapsed witness.
The native isolation watchdog releases after at most 180 seconds; any watchdog
release still fails qualification. Native no-quorum keeps the 15-second minimum
isolation and allows both original refusal observations to finish before healing,
with a 120-second controller maximum. Guest-local isolation evidence must still
show at least 15 seconds. Request counts, arrivals, workload windows, resource
limits, original outcomes and independent physical/history oracles are unchanged.
These are first-run control allowances, not a failover SLA.

## Reduce control overhead and preserve fast failure

- Reuse private pinned SSH/IAP connections during runtime and collection, as well
  as preparation. Every exchange still runs its retained lease/ledger and exact
  provider/host identity guards. Distinct guests use distinct connections.
- Limit each exchange, including guards, to 120 seconds. Connections use at most
  900-second credential epochs; rotate the token/config and affected connection
  before that epoch expires. A four-hour lease does not require a four-hour token.
  Credentials remain private and are removed when the original scope closes.
- Submit each workload command once. Only query that command ID after a lost
  reply. Native observation stops after three consecutive transient failures,
  three uncertain/missing replies, 256 queries, or its original 180-second command
  deadline, whichever comes first. RUNNING is progress, not an uncertain reply.
  A command with a terminal failure is never rerun.
- Authentication, host identity and permission rejection fail immediately.
  Service readiness/shutdown also stop after three consecutive transport failures;
  readiness gets 180 seconds, instead of consuming the full preparation hour.
  Existing bounded native session initialization recovery remains intact.
- Final convergence uses the first active-member observation and checks the two
  followers without repeating the active-member query.
- Skip workload collection for fault groups that never attempted their cell;
  retain their preparation records and still stop their services. Missing cells
  still prevent experiment acceptance. Keep original service-stop failures.
- Emit a safe stage START, a RUNNING heartbeat every 30 seconds, and DONE/FAIL with
  elapsed/limit seconds. Healthy mode transitions are also logged. Fixed failure
  codes distinguish unresolved commands, exhausted observation retries, shutdown
  failure and incomplete finalization without exposing provider/token text.

## Qualification and next operation

Local regressions cover old/new lease expiry, profile spoofing, extended evidence
windows, price coverage, slow shutdown, unstarted collection, terminal rejection,
query-only recovery and exhaustion, token rotation and simultaneous guest queries.
The original source/build and independent evidence checks remain required.
Validation results are retained in `target/v51-native-headroom/` and summarized
in the PR body. No paid workload or ledger operation is performed by this change.

After protected CI and merge: use the current manual cleanup result, prepare a
new request with fresh prices and sufficient reservation, review its new timing
and exact digest, then explicitly trigger the experiment. Keep the result even if
it fails. After the first complete run, use phase/mode/connection timings to review
smaller limits; do not automatically shrink or renew a running lease. Phase 6,
canonical repetitions and release qualification remain open.

## Healthy shutdown correction

Native run `37706121942` completed all four cell executions and all healthy mode
tapes. Preparation took 1356.752 seconds; healthy 805.559; leader-loss 182.830;
maintenance 271.802; no-quorum 248.472; validation/retention 781.432; cleanup
245.857. Every stage remained within its fixed v2 allocation. Execution completion
does not qualify the experiment: independent replay rejected candidate V5.1
healthy with `voter missing final durable cut`.

Before shutdown, all three voters reported proven index 92, with node 1 the
observed leader. Serial shutdown used startup order (1, 2, 3). Each remote stop
observation took approximately 9–11 seconds. After node 1 closed, nodes 2 and 3
formed epoch 9 and forced activation NO_OP 93. The final retained cuts were
92/93/93. The all-voter final-cut validator correctly rejected those bytes.
This is a controller shutdown ordering defect; increasing the time limit would
not remove it.

The correction closes followers before the observed issuer, preserving relative
follower order and the original startup/collection inventory. All stops retain
their original shared deadline and once-only command identity. A failed stop
remains failed, other attempted members still receive cleanup, a second close
does not resubmit, and backup restore requires every original stop to succeed.
Partial startup without an issuer still cleans all attempted members. A mode
must close successfully before the next mode starts. The same healthy controller
serves offline and native execution, including configured V5.0 and single-node
V4.4. Fault cells already close their remaining voters concurrently; that separate
path is unchanged. No final-cut, physical/history, read or negative oracle is relaxed.

Original artifact SHA-256:
`e1045a669bd5cac03334c6ede72aa304edcdbb9db2de7b73ae8ce170bb1f933e`.
Diagnosis and unmodified failed evidence remain in
`target/v51-native-failure-37706121942/`. Independent diagnostic replay of its
leader-loss, maintenance and no-quorum cells passed all 22 negatives; it does not
upgrade the failed aggregate. Cleanup confirmed all thirteen resources absent,
retention verified and the lease released. The ledger remains USD 50 / 200.

Shutdown regression receipts, including a local real-JVM comparison with delayed
stop acknowledgements, are retained in `target/v51-owned-shutdown-order/`.
With ten seconds between stop acknowledgements, the unchanged original method
produced cuts 4/3/4 after all voters had reached 3; the corrected method kept
3/3/3. Independent retained-storage inspection and quorum ACCEPT observations
confirmed the extra activation NO_OP only in the original run. This is a finite
local reproduction, not native experiment qualification or a failover SLA.
This correction leaves the v2 timing, workload calls and budget reservations
unchanged. Fresh native acceptance remains pending after protected CI and merge.
