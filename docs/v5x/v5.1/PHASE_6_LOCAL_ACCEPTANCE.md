# V5.1 Phase 6A local measurement review

**Status:** accepted through PR #222, master
`33aa89bf8a6b4b0587fa6a127e481d73671a60ec`, exact-master
[CI 35937300754](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35937300754).
All nineteen jobs and 24 V5.1 verification steps passed, including the portable
replay correction and inherited hardening/retry fixture corrections. The original
measurement/calibration source below remains PR #219; it is not relabelled as
PR #222. The [6B contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) is also accepted;
paid execution requires the remaining 6C/6D gates.

## Exact source and gates

[Master CI 35920225478](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35920225478)
passed all nineteen jobs and all 24 `Verify V5.1` steps. Specifically:

- The public capacity/admission gate executed all fifteen cases, including
  `document-limit`, with 89 evidence negatives.
- The resource gate executed all six internal and both public cases. Both
  exhausted-voter cases retained successful majority service, bounded-voter restart
  and leader restart, with thirty public evidence negatives in total.
- The three-mode performance gate executed 270 healthy calls, nine calls around an
  actual idle-leader SIGKILL/rejoin, thirty performance negatives and owned-process
  shutdown. Compatibility and all earlier public gates also passed.

PR #218's green PR CI and failed master CI remain historical records; its skipped
resource step is not counted here. PR #219 fixed the single-permit driver ordering
without changing production Java. The corrected activation-peer scheduling runtime
is the one measured by this source.

## Retained raw evidence and independent replay

The CI performance artifact is
`v51-performance-54e203eeca6c087b7ba03954d546c7682e8338f2`, artifact ID
`10776619460`. Its raw root is `run.uMX9h3/evidence`, with complete JARs, compiled
external adapters, source inventory, force/wire traces, samples, calls, source/export
backups, stopped authorities, immutable pre-reopen archive and hashed bundle index.
The existing independent model/physical/history/timing validators replayed all three
modes and the complete fault history after download. No voter JVM was started for
that replay, and no downloaded authority was admitted for execution.

The first download replay exposed local-path assumptions: the artifact validator
tried to open the original runner's absolute JAR paths; retained authority inspection
also compared the downloaded directory to its original sealed path. The correction
keeps the recorded classpath/code-source relationships, resolves actual artifact
bytes only inside the downloaded bundle, and requires the complete member inventory
before explicitly inspecting displaced evidence against the original sealed paths.
Normal live-path inspection remains unchanged. No original record or seal is rewritten.
A copied directory still cannot become a valid live replica merely by passing this
read-only evidence path.

Local replay files:
`target/v51-phase6-cloud-contract/master-performance-revalidation.json`,
`master-performance`, `master-resources`, `master-bounds`, `master-jobs.json` and
`master-artifacts.json`. The [calibration record](phase6-cloud-calibration.json)
retains exact source, original receipt/member-index hashes, toolchain, observed
resources and timing. GitHub artifact retention is fourteen days; that metadata
is not a substitute for the raw artifact after expiry. Later cloud qualification
requires its own retrievable raw evidence and thirty-day retention.

## Observed local measurements

The exact CI toolchain was Eclipse Adoptium `21.0.12+8-LTS`, using the accepted
512-MiB heap and two-active-processor arguments in all modes.

| Observation | Result |
| --- | ---: |
| Performance Actions step, including wrapper/packaging | 88 seconds |
| Controller receipt elapsed | 83.058 seconds / 900-second ceiling |
| Preparation | 6.883 seconds |
| V4.4 local mode | 0.821 seconds |
| V5.0 configured mode | 3.700 seconds |
| V5.1 automatic mode | 22.823 seconds |
| Separate SIGKILL/rejoin history | 14.261 seconds |
| Independent validation/negative/bundle stage | 34.541 seconds |
| Automatic measured 20-call windows | 2.303–2.552 seconds |
| First post-kill durable write, from confirmed exit | 4.478 seconds |
| First post-kill strong read, from confirmed exit | 4.580 seconds |
| Kill request/confirmed-exit uncertainty bracket | 7.956 milliseconds |
| Automatic sampled RSS peak across voters | 179,519,488 bytes |

Each healthy mode has eight measured samples per operation. These are diagnostic
local results, not a throughput, p99 or failover SLA. V5.1 reads use fresh quorum
barriers; control reads have their published semantics. The modes are not equal
consistency services. The maximum observed latency is a sample, not a hard bound.

ABBA aggregate measured-window B/A was 0.958 for V4.4, 0.914 for V5.0 and 0.948
for V5.1. Ratios below one do not establish a speedup from instrumentation: the
small sequential windows include warmup/order/noise effects. Correctness evidence
and resource sampling remain on in A; B additionally records force/queue timings.
Raw per-operation/window values and sample counts remain in the artifact.

## Exit review

The frozen [local plan](PHASE_6_LOCAL_MEASUREMENT_PLAN.md), independent rich semantics,
isolated published controls, concurrent three-process modes, forced-record/read-cut
validation, bounded history, resource sampling, cleanup, negative fixtures and
exact-master regression prerequisites have been reconciled. The current correction
also makes downloaded evidence replayable with strict identities.

The new [6B cloud contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) retains the measured
corpus and uses conservative initial offered loads. Its complete remote schedule,
current provider readiness and any paid sequence require subsequent gates. The
64-document local measurement does not establish larger-corpus scalability, WAN
behavior, cloud capacity or indefinite recovery guarantees.

## Validation of this review candidate

- The downloaded master performance bundle passed independent artifact, physical,
  semantic, history and timing validation without reopening any voter.
- A fresh complete local three-mode gate passed at
  `target/v51-performance/run.zSeX79/evidence`: 270 healthy calls, nine fault-history
  calls, thirty evidence negatives and clean process shutdown.
- All 337 V5.1 Python tests and nineteen CI change-classification tests passed.
  The foundation gate discovers the new cloud-contract and artifact tests; the
  performance gate also explicitly runs the relocated-artifact regressions.
- Documentation contracts, changed local links, shell syntax and whitespace passed.
  No production Java or workflow changed in that review candidate. Its protected
  acceptance is now recorded above at PR #222; original measurements remain bound
  to the earlier PR #219 source.

Local validation receipts and file hashes are indexed in
`target/v51-phase6-cloud-contract/validation-summary.json`.
