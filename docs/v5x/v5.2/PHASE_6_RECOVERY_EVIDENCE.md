# V5.2 Phase 6S independent recovery evidence

**Status:** M04 member replay and portable negative qualification implemented.
The complete machine execution freeze and fresh formal M01–M04 cohort remain open.

## Process and retained authority

The two [recovery controllers](PHASE_6_RECOVERY_CONTROLLERS.md) now sample resources
per JVM generation. The independent checker admits exactly three clean generation-1
processes for snapshot recovery, or one generation-1 SIGKILL plus its generation-2
reopen and two clean survivors. Every PID is distinct. Other measurement profiles
retain their three-clean-process requirement.

Repeated trace scans reject foreign, omitted, skipped or interleaved generations.
Request IDs, read IDs, promises, proof observations, snapshot transfers and view
ownership are scoped to their process generation. No new process inherits a
previous process's in-memory observation state.

Before admitting generation 2, inspect the immutable pre-reopen directory against
its original sealed path and exact inventory. Enforce 4,096 files, 64 MiB total and
8 MiB per file. Independently reconstruct the proven prefix and latest durable
promise. The observed restoration must match its anchors, application sequence,
full chosen application state and exact terminal proof. Only this inspected state
can seed the restarted process's initial promise and proof authority.

All original business/control calls must complete, and all read ownership must be
released even on the process deliberately killed after preparation. A killed
process cannot claim `CLIENT_IDLE` or `CLOSED`. Any outstanding transport reservations
at its abrupt exit are reported; all cleanly stopped generations must release theirs.
This is the closed M04 schedule, not general admission of arbitrary in-flight crashes.

## Independent fault and query checks

Admission binds the exact source/build/attempt, artifacts, compiled consumers,
actual JVM, fault file and original eight business calls. It validates the command
ledger and aggregate authority budget before general physical reconstruction.

The checker independently verifies the initial strong token, three setup updates,
one progress update, all four fixed queries, original targets, ordered recovery
milestones and final sequence 5. Extra business calls, changed tokens, retries and
wrong targets reject. Successful captures still require public callback lifetime,
ownership accounting, correct policy, fresh strong barriers and local publication.
Actual published V4.4 query replay checks every successful query cut.

Recovery-floor hints must match physical events and independently decoded identical
local/peer packets from distinct voters. The snapshot target must be outside the
observed selected pair, physically lag at the held cut, then install a transferred
and forced snapshot before its two token reads. At least one real dropped frame
must match the declared single-voter partition. Fault configuration is observed
exactly once in each JVM. A selected-pair or install hint alone is insufficient.

## Resource and timing reports

Each process starts a sampler before the fault or immediately after reopen. Clean
processes stop sampling after the final read. The killed process retains only its
observed START/PERIODIC prefix, explicitly marked incomplete; neither a STOP nor a
counter delta through the unknown exit instant is invented. Sampling is bounded
before buffering, and actual start/stop responses must match the retained rows.

Reports retain all eight controller/API/queue timings, four capture/callback
timings, process-wide CPU/allocation observations, sampled peaks, ownership and
abrupt transport counts. Controller milestones describe observed exit/heal through
activation/write/strong/minimum completion. Campaign detection is an upper bound
from the first correlated status observation; campaign-to-quorum uses only the
successor JVM's clock. No cross-origin clock subtraction, speedup target or failover
SLA is introduced.

## Portable replay and validation boundary

Original and relocated complete results and exact negative case/status/reason lists
must agree. Existing inventories are verified before packaging; failed artifacts
and failure receipts remain available. The original evidence must pass before a
mutation can count as a successful rejection.

Negative cases cover hidden calls, changed tokens, forged query answers, missing
fault/proof/generation evidence, premature permit release, changed waits, foreign
process rows, missing/fabricated samples, wrong crash identity or retained inventory,
missing restoration, premature reopen, fabricated abrupt STOP, early heal, changed
snapshot target and fabricated install hints.

Development histories and replay receipts are under `target/v52-recovery-evidence`.
Both fresh histories pass full original and relocated replay with actual V4.4
query answers: eight reads and eight updates across seven JVM generations. The
final four replays reject 60 exact mutations (16 restart and 14 snapshot cases per
location). All 206 V5.2 Python tests pass. Eleven existing minimum/saturation
histories and all five existing short-mode histories preserve their complete
previous validation results under the shared generation changes. CI inventory,
documentation contract, 630 changed local links, shell syntax and whitespace pass.
The initial test-helper import and preserved M01 error-text mismatch were corrected;
their failed logs remain. No production build or hosted CI was rerun for this
Python/controller stage.

They remain development evidence tied to their original source; no business run is
relabelled as a formal measurement. Next commit the complete machine freeze and
execute the fresh 28-history M01–M04 cohort before cloud admission work.
