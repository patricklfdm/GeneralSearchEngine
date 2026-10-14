# Tiered CI progress

## Authority and baseline

The current task authorizes continuous local T0–T6 implementation and staged local
commits, with one final review. No push, PR, merge, rerun/dispatch, release, cloud or
remote settings mutation is authorized by this development task. Input handoff files
remain unmodified, uncommitted and unnecessary at runtime.

Development branch: `refactor/ci-tiered-t1`; initial HEAD:
`6a65f24023a8f68ca3437096eeacf77a513219fb`.
Fresh read-only observations and raw/paginated API data are retained at
`target/ci-tiered-feasibility/authorized-read/`; comparison review and source hashes
are in `target/ci-tiered-feasibility/`. PR #327 attempt 1 cancellation evidence is
preserved; attempt 2 acceptance is not described as a clean first attempt.

## Stages

| Stage | Implementation | Local validation | New-source hosted |
| --- | --- | --- | --- |
| T0 baseline and frozen acceptance | Complete | Registry/topology and literal command inventory checked | Baseline only; later source pending |
| T1 suite-aware shadow plan | Complete | 130 change-scope tests passed | HOSTED_PENDING |
| T2 plan/Required/workflow, forceFull | Complete | 195 related tests plus 20 extended inventory tests passed | HOSTED_PENDING |
| T3 integration activation | Complete | 166 plan/provenance/interface tests passed | HOSTED_PENDING |
| T4 optional rule review | NOT_ENABLED_WITH_RATIONALE | Closed-policy negatives; see review | No optional tier claimed |
| T5 Nightly/manual/health controls | Complete | 214 related tests and 34 final negatives passed | HOSTED_PENDING |
| T6 full local regression and review | In progress | Build/rollback passed; other lanes running; namespace prerequisite blocked | HOSTED_PENDING |

T0 uses the accepted docs/full implementation unchanged. Differences from the
handoff implementation base are nine documentation files; there is no runtime
drift to undo. No source reset, tag move or Maven clean was performed in T0.

## Evidence and next action

* T0 hashes and full effective command list: `target/ci-tiered-development/t0/`.
* Design: [CI_TIERED_DESIGN.md](CI_TIERED_DESIGN.md).
* Frozen acceptance: [CI_TIERED_ACCEPTANCE.md](CI_TIERED_ACCEPTANCE.md).
* T1: `gse-ci-shadow-plan-v2` retains exact raw diff status, old/new Git modes,
  types and blob identities, registry/validator hashes, plus closed suite recipes
  and dependency closure. The actual classifier and Required are unchanged.
  The frozen eight-module test command passed 130 tests in 19.640 seconds;
  log: `target/ci-tiered-development/t1/tests.log`. New regressions cover raw
  records, dirty registry/validator, grouped matrix recipes and dependency closure.
* T1 self-review: no workflow, policy, runtime, POM, suite or artifact changed.
  The planner still never writes gate outputs. Missing registry yields no suite
  plan and a conservative diagnostic rather than a usable qualification.
* T2: the existing policy is now closed version 2, with forceFull enabled and
  no integration rules. The registry adds explicit integration results; only the
  whole canonical suite may be skipped. `ci_plan` reuses the shadow identity/diff
  logic and emits one source-bound data receipt and five closed outputs. Required
  independently recomputes it from complete Git history before checking all suites.
  Raw output booleans, an old schema, missing receipts or forged/stale identities
  cannot pass. There is no second policy and no shell supplied by JSON.
* T2 checks: the frozen eight-module command plus `scripts.test_ci_plan`,
  `scripts.v51.test_cloud_preflight`, `scripts.v51.test_cloud_runner_artifacts`
  and `scripts.v51.test_phase7_release_fixtures` passed 195 tests in 61.981 seconds
  (`target/ci-tiered-development/t2/tests-complete.log`). Additional complete-history
  and integration-result inventory negatives passed 20 tests
  (`inventory-negatives.log`). Baseline comparison confirms unchanged suite inputs,
  matrices, artifacts, external interfaces and release retention. Inventory parity
  and whitespace checks passed. Two small follow-up policy-type checks are retained
  with the final T2 regression log.
* T3 command: `python3.11 -m unittest scripts.test_ci_plan scripts.test_ci_observation scripts.test_ci_shadow_plan scripts.test_ci_suites scripts.test_ci_required scripts.test_ci_changes scripts.test_ci_composites scripts.v51.test_cloud_preflight scripts.v51.test_cloud_runner_artifacts scripts.v51.test_phase7_release_fixtures`.
  All 166 tests passed in 65.795 seconds; log:
  `target/ci-tiered-development/t3/final-tests.log`. Earlier pre-provenance run:
  101 tests passed in 43.835 seconds. Generated inventory and whitespace passed.
* At this stage the next work was T4 optional rule decisions and T5 operation;
  their completed implementation and local checks are recorded below.

T4 [review](CI_TIERED_OPTIONAL_REVIEW.md) leaves consumer/python-isolated rules
disabled: no separately justified safe and useful further coverage reduction was
found. Integration remains the required implemented tier. The added negative test
rejects optional rule names, globs, duplicate rules and unsupported profiles; no
existing checks are removed and this decision does not block T5.
Command: `python3.11 -m unittest scripts.test_ci_plan.ExecutionPlanTest.test_optional_tiers_remain_explicitly_disabled`;
one test passed (0.006 seconds), log `target/ci-tiered-development/t4/tests.log`.

T5 adds daily full no-GCP scheduling at 10:17 UTC, keeps manual and non-doc master
full, and separates non-PR concurrency by event/run. Integration requires complete
recent exact-base full health and Required rechecks it. The API is GET-only,
pagination is complete/bounded, latest failed/pending/docs outcomes are not hidden
by earlier green runs, and all uncertainty escalates to full. This health check
does not change the independent cloud reader; schedule remains rejected there.

T5 full related command is the T2 command plus `scripts.test_ci_observation` and
`scripts.test_ci_health`: 214 tests passed in 71.108 seconds, retained at
`target/ci-tiered-development/t5/regression.log`. The first focused run exposed a
test-fixture URL replacement bug (`per_page` was accidentally changed with `page`);
the production pagination was unchanged. Its failed log remains in `focused.log`.
Final review added original-scope step time/event checks and forged-health negatives.
`python3.11 -m unittest scripts.test_ci_observation scripts.test_ci_health scripts.test_ci_suites`
passed 34 tests in 3.871 seconds (`final-negatives.log`). The literal-command audit
confirmed every verification command in all 36 suites unchanged from T0
(`command-parity.json`); only Change scope's classifier/tests changed. Generated
inventory and whitespace checks passed. Next: T6 self-review, rollback exercises,
remaining executable local verification and explicit environment-gap accounting.

T3 candidate review is recorded in the design under “本轮委托自主审查”. The
exact example content rule is active in versioned policy; this CI/policy PR itself
is full. Positive tests execute the actual planner and Required CLIs in temporary
Git repositories. They simulate job results and do not claim hosted scheduling.

Self-review found the partial-rerun boundary: Required now verifies a carried
Change scope execution against original/accepted attempt API data before replaying
its source-bound plan. The implementation preserves the same original-runner/time/
step-copy boundary as the existing artifact consumer. Historical raw run
`38522705456` provides the observed carried-check shape; synthetic negative tests
exercise corruption, pagination and changed executions. CI adds only `actions: read`.

## Local environment gap (must not be hidden as hosted pending)

The pinned Temurin JDK is available at `/tmp/gse-v51-phase7b-jdk` and Python 3.11 is
installed. The existing complete owned qualification requires a native-UID mount
namespace with `--allow-sudo-namespace`. The minimal probe
`sudo -n unshare --mount --propagation private true` failed with
`sudo: a password is required`. No directory was mounted or host setting changed.
Full canonical local verification is currently `LOCAL_VALIDATION_BLOCKED`;
continue independent implementation and tests, but final local readiness cannot be
claimed until that required verification actually runs successfully.

## T6 verification underway

The unchanged implementation commit `4090b57afc90d429fed6c9d4bfd24b2f27b59ed2`
is checked out independently for each local build/consumer lane below
`/tmp/gse-tiered-local-4090b57/`. Maven caches are independent copies, the existing
workspace target is untouched, and the pinned Temurin JDK is used. Local transfers
are explicitly file copies from this run's producer; they do not claim hosted
artifact IDs or acceptance. Every consumer still runs the original source/JDK/hash/
Surefire restore verifier. Commands come from the actual effective workflow.

* Verification build passed: **923 Java tests, zero failures/errors, four existing
  skips**, 179 Surefire reports. The exact-source verification bundle was created.
  Counts: `target/ci-tiered-development/t6/reactor-test-counts.json`; logs and
  receipts: `target/ci-tiered-development/t6/local/`.
* Structural rollback passed in an isolated clone: all six T0–T5 commits were
  reverted together without modifying the development workspace; resulting tracked
  files match baseline `6a65f24023a8f68ca3437096eeacf77a513219fb`. All 126 original
  CI-contract tests passed. Receipt: `t6/structural-rollback/receipt.json` under the
  evidence root. An additional real committed-policy generation test confirms
  forceFull restoration and that disabling it cannot downgrade its own rollout.
* Documentation contract checks passed: V5.0 accepted contract and V5.1's
  114 documents/860 links; the changed-doc review additionally checked 595 links.
  Production Java/POM/frozen release files and release workflow have no diff.
  Input package `SHA256SUMS` still verifies; its files remain unmodified/uncommitted.
* Remaining executable lanes are being run in two bounded independent sequences,
  alongside the Python/cloud unit partitions. No new-source hosted runs have been
  triggered. Native-UID mount qualification remains a separate local environment
  gap; fake Python canonical fixtures are not counted as complete canonical runs.

Stage commit IDs are available from Git history for this file; each stage records
its exact checks and evidence before committing. Final readiness has not been claimed.

### Retained local failures

The independent `reactor-core` build failed at
`V51PublicRuntimeTest.concurrentPublicReadsKeepTheirInvocationIdentityThroughCaptureAndRelease`:
the 30-second wait for entry into the query callback expired. The same source's
verification producer had passed all 923 tests. The failed test is byte-identical
to the baseline; no production Java changed. The failed test does not retain the
query Future's outcome before asserting, so the available evidence cannot assign
this failure to host load or runtime read admission. This remains an unresolved
local acceptance gap, not an infrastructure retry success.

The `v51-public-reads-faults` lane subsequently failed in the public-runtime gate's
initial write with `INDETERMINATE / QUORUM_UNAVAILABLE`. Its original evidence and
logs are retained. The follower trace brackets proof force at 1,885.489 ms, beyond
the existing 1,200 ms request bound. This explains the missing timely proof ACK;
it does not distinguish disk latency from scheduling delay within that interval.
That failure prevents accepting the entire lane; subsequent independent commands
must be reported separately if run. These runtime behaviors are outside the
authorized CI-only production-change boundary. Independent lanes continue; no
test threshold, deadline or runtime assertion has been changed to obtain a pass.

Review and raw logs: `target/ci-tiered-development/t6/runtime-failure-review.json`,
`t6/local/reactor-core/04.log` and `t6/local/v51-public-reads-faults/05.log` under the
same evidence root. The sudo prerequisite and these failures must be resolved
before final local readiness; none is described as merely `HOSTED_PENDING`.

### T6 control-plane self-review correction

The complete related CI/consumer command passed **216 tests in 80.648 seconds**
(`t6/final-ci-contracts.log`). A subsequent review found that an incomplete API
timestamp could raise `AttributeError` instead of producing the promised
conservative full fallback. A new test failed for ten missing/wrong-type timestamp
variants on the original code. Explicit timestamp type validation now routes them
to `HEALTH_UNAVAILABLE` and full. All **178 affected planner/Required/routing/cloud/
release tests passed in 94.082 seconds**; original red and corrected logs are
`t6/health-timestamps-before.log` and `t6/health-timestamps-after.log`.

The long-running workload lanes remain pinned to the earlier implementation source
`4090b57`; they are not relabeled as qualification of this follow-up correction.
The correction touches only CI metadata parsing and its tests. Local readiness
still requires the unresolved full-regression and environment gaps to be closed.
