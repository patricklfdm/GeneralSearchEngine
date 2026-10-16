# V5.2 Phase 6AE persistent voter services and clock-domain edges

This stage moves JVM ownership out of the whole-history controller into three
independent local Python services. Each service owns exactly one original voter
JVM and its pipes. It is a local lifecycle qualification, not three-host placement
or cloud admission. The [SSH history transport](PHASE_6_SSH_HISTORY.md) still
controls a whole local history; SSH routing of these per-voter streams is next.

## Persistent ownership, bounded transport

`remote_voter.py` provides a private Unix-domain stream per receiver. A forced
launch/configuration claim and a forced service identity precede voter startup.
Complete or partially published start records prevent another service launch.
The service checks the original source, delivered JAR/helper bytes, topology,
receiver root, boot, UID and private directory device/inode before startup.
Service and JVM PID/start-ticks identities are separately retained.

The original controller continues to own offered times and Futures. The stream
carries existing public commands and asynchronous responses; it does not establish
SSH for each operation. Commands have one monotonically consumed identity per
voter, with at most 4,096 calls, 128 outstanding operations, 16 KiB public requests,
64 KiB frames and a 32 MiB dispatch/result journal. Journal space for outstanding
responses is reserved before dispatch. Duplicate, reordered, oversized or changed
commands cannot invoke the public API again. No arbitrary shell/argv is accepted.

Disconnecting a stream leaves the service and JVM alive. Explicit reattachment
presents the same configuration digest and last observed event sequence and reads
only the original retained responses. It does not resend commands, reset counters,
replace Futures or restart the voter. A dead service, partial journal or missing
response remains uncertainty/failure. The journal is flushed for inspection and
forced before its terminal receipt; it is not a restart/replay log. Graceful stop
retains every outcome, original JVM trace and process exit. Failure cleanup targets
only the still-owned local child session and never treats forced termination as PASS.

Operational observation emits progress each minute. Original finite public-call,
startup, exchange and shutdown limits remain. This entry currently admits only
whole untimed smoke histories; M01–M04, declared restart and partition controls
cannot silently enter an unqualified lifecycle backend.

## Separate clock domains

`remote_voter_evidence.py` adds exact message correlation across controller,
service and JVM observations. It checks request equality, response equality,
sequence completeness, process binding and clean stop. Monotonic ordering is
checked separately in each process domain. No timestamp from one domain is
subtracted from another or used to sort the combined history.

This supplemental validator deliberately does not establish cross-host replication
causality. The unchanged physical/query validators still run and the placement
must remain `local-no-gcp`, with the same observed boot. Provider identities,
independently delivered packages, cross-host process namespaces and replication
message ordering remain prerequisites for three-host qualification.

## Operator qualification

After a current runtime package:

```bash
scripts/verify-v52-phase6-persistent-voters.sh --skip-build
```

The entry runs the original candidate-minimum untimed history with three real
service processes and three JVMs. It deliberately drops the first completed
update response, reconnects to that original service, and checks that only the
original three updates and eleven reads occurred. All existing physical/query
checks and exact negatives run at both original and relocated evidence paths;
message-edge validation runs at both paths as well. All service/JVM processes
must exit normally. No full measured cohort, paid run or GitHub workflow is
triggered. The optional real gate is not added to every PR; its lightweight
regression tests join the existing measurement test entry.

All receipts retain `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`. Current local validation
records belong under `target/v52-persistent-voters/`. Protected exact-source
acceptance and complete owned cloud members remain open.

## Retained local validation

Final gate `target/v52-persistent-voters/run.ymAN75/evidence/receipt.json`
passed in 58.772 seconds. Three independent service processes each owned one JVM;
all six exited normally. The first update response was discarded and recovered
through a second stream to node 1. The history still contains exactly eleven
reads and three updates. Its 274 total operations include status, probe and
sampler controls; 548 request/response message edges validate at both original
and relocated locations. All 24 existing physical/query negatives pass at each
location (48 total).

The run binds base `58f6f9cae6e9b7e7583d385544ab50236f6cbb28` and executed
working-tree fingerprint
`90055ff1508982d7bbd0b9b5124d5339a7d5b02c1f9d9298024f9058a583c26b`.
These result paragraphs were added afterward. All 344 V5.2 Python tests,
including 22 new service/evidence tests, and 21 CI suite tests passed. Coverage
includes twelve retained-metadata corruption variants with refreshed inventories,
partial launch claims, operation/resource bounds, the callback lock boundary,
message completeness, independent clock offsets and per-domain regressions.
The final gate requires the explicit voter-control binding; missing service
metadata cannot fall back to the earlier receiver-pipe evidence path.

An earlier development probe `run.VYrgr2` also passed, before mandatory service
metadata binding was added. It remains separate and is not substituted for the
final gate. Existing unchanged Java artifacts were reused and helper classes
compiled afresh. No reactor rebuild, full 28-history cohort, GitHub dispatch or
paid cloud execution ran. Raw receipt and changed-file hashes are retained in
`target/v52-persistent-voters/validation-summary.json` and
`validated-worktree-files.json`.
