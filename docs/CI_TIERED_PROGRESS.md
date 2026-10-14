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
| T6 full local regression and review | Resumed after user-provided namespace setup | Original 25 passing / five failing instances retained; missing checks and one controlled serial recheck underway | HOSTED_PENDING |

**Acceptance status: `LOCAL_VALIDATION_IN_PROGRESS`; final readiness is unproven.**
T0–T5 implementation is committed. The original execution ended with
`BLOCKED_WITH_PARTIAL_DELIVERY`; its results below remain retained. The user has
since supplied the missing namespace prerequisite, and T6 has resumed as recorded
at the end of this document. New-source hosted acceptance is separately pending.

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

## T6 local verification

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
* Executable lanes ran in bounded independent sequences alongside the Python/cloud
  partitions. Their final results are below. No new-source hosted runs were
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
That failure prevents accepting the entire lane. Subsequent public qualification
and fault commands passed in a separately recorded partial execution. These runtime
behaviors are outside the authorized CI-only production-change boundary. No test
threshold, deadline or runtime assertion was changed to obtain a pass.

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

## Original local accounting (through `92a3d4b`)

The full workflow has 46 expanded jobs, including Change scope and Required.
The local workload index covers its **44 non-meta instances**. Local planner and
Required tests are accounted for separately; no hosted job success is implied.

| Outcome | Instances | Meaning |
| --- | ---: | --- |
| PASS | 25 | All literal run commands in that local instance passed. |
| FAIL | 5 | Original failures retained; see the table below. |
| BLOCKED_NOT_RUN | 12 | Whole guest/owned jobs need the unavailable native-UID mount namespace. This includes five tapes and all three canonical repetitions. |
| BLOCKED | 1 | Rich aggregate lacks its successful published-controls shard. No old/partial shard was substituted. |
| NOT_RUN as a whole job | 1 | Provider verifier and evidence packing passed separately using verified pre-existing OpenSSH; the workflow's sudo installation step was not run. |

Passing instances include all three V5.1 Python partitions, cloud preflight/cleanup/
storage, V4 regression, V5.0 authority, V5.1 foundation/admission/protocol/reclamation/
full-size/public recovery/hardening, remote faults, rich inputs and both automatic
rich shards, compatibility, soak/examples and release artifacts. Release validation
includes candidate artifact checks, both pinned Docker reproducibility builds and
`validate-evidence --source`. The successful shared producer does not erase a failed
independent reactor build.

| Failed whole instance | Observed failure / retained limit |
| --- | --- |
| reactor-core | Query callback entry latch exceeded 30 seconds; Future outcome was not retained before the assertion. |
| v50-recovery-workload | Prerequisite reactor test `V50ReadyTest.incrementalCatchupReplaysOnlyTheMissingTailOfAPublishedPrefix[5]`: no valid remote voter for COMMIT_PROOF. Later lane commands did not run. |
| v51-public-reads-faults | Initial public-runtime write failed with QUORUM_UNAVAILABLE; proof-force interval was 1,885.489 ms against the existing 1,200 ms request bound. |
| v51-candidate-crashes | `before-write-halt` did not reach PROMISE_BEFORE_WRITE; the other 13 cases passed, but the suite failed. |
| rich published-controls | Published V4.4 warmup call 18 took 1.430698 s against one-second spacing; the next call was LANE_BUSY. |

These observations establish failed checks, not a universal host-scheduling or
production-defect diagnosis. No Java, POM, frozen parameters or oracle changed.
Original evidence is retained with hashes at `t6/failures/manifest.json`; analysis
is `t6/runtime-failure-review.json`. No measurement was retried until green.

Six selected-step receipts are kept separately. The initial provider check failed
because OpenSSH StrictModes rejected the `/tmp` ancestor. A fresh checkout under
the user's HOME passed the complete original provider verifier and packing command;
StrictModes and host directory permissions were unchanged. The first guest-service
prefix and the independent public qualification/fault commands passed. A second
guest-service run in HOME failed a published V4.4 warmup (1.639985 s / one-second
spacing); its failure remains retained. Its already-built package subsequently
passed the separate SSH delivery and owned startup/idle checks. These partial
results do not close the guest mount-namespace requirement or any failed whole lane.

Final evidence root: `target/ci-tiered-development/`.

* `t6/local-validation-index.json`: every expected instance, source, receipt hash,
  partial result and verified log hash. Regenerate with
  `python3.11 target/ci-tiered-development/tools/local_index.py`.
* `tools/local_ci.py`: extracts literal commands/composites and records isolated
  workspaces, pinned tools and local file transfers; `tools/home_ssh_checks.py` and
  `tools/guest_ssh_remaining.py` record the explicit SSH environment correction and
  independent remaining commands. No hosted artifact identity is fabricated.
* `t6/active-sessions.json`: every started queue completed; no test is left running.
* `t6/structural-rollback-8c74390/`: all eight implementation/review commits reverted
  together in an isolated clone; tracked tree equals the initial baseline and all
  126 original CI tests passed in 21.773 seconds. This supplements the earlier
  six-commit rollback, which is also retained.
* `t6/final-shell-inventory.json`: all 170 effective shell blocks pass `bash -n`.
  The 36-suite literal command comparison is `t5/command-parity.json`.

The long workload receipts bind to `4090b57`; the timestamp correction and subsequent
documentation/rollback tests bind to later commits. No result is relabeled as a
full regression of a different source. Test counts above overlap and must not be
summed as unique test cases.

## Commit sequence and resumption

| Commit | Scope |
| --- | --- |
| `7ee397c` | T0 baseline and frozen acceptance |
| `089e327` | T1 suite-aware shadow / exact raw diff |
| `20d45ab` | T2 execution plan / Required / forceFull rollout |
| `3182f07` | T3 integration and carried-scope provenance |
| `2a19bc7` | T4 optional tiers explicitly disabled |
| `4090b57` | T5 Nightly/manual and exact-base health |
| `1858645` | T6 malformed health timestamps safely select full |
| `8c74390` | Contract documentation and actual forceFull rollback test |

The final accounting is a subsequent documentation-only commit; use `git log` for
its identifier. No push, PR, merge, workflow trigger or paid cloud action occurred.

Next is **T6 acceptance**, not a new tier or V5.2: obtain an already suitable Linux
environment for native-UID mount checks, resolve the retained runtime failures
within separately authorized scope, and complete the frozen full local acceptance.
An unanswered environment question is not permission to change sudoers or bypass
the existing isolation checks. Only after required local checks pass can the user
review and push the accumulated branch for the hosted checks in
[CI_TIERED_ACCEPTANCE.md](CI_TIERED_ACCEPTANCE.md). The rollout PR must select full;
later eligible PRs may select integration after exact-base full health is established.

Draft review commands and PR description are in
`target/ci-tiered-development/review-commands.sh` and `pr-body.md`; they have not been
executed and do not claim merge readiness. First rollback is `forceFull=true`;
structural rollback reverts all task commits together, including their contracts,
with a new revert commit rather than resetting or rewriting the branch.

## T6 resumed after local namespace setup

The user configured the two existing sudo command routes and reported both probes
passing. A new native check independently confirmed noninteractive execution,
then exercised the existing `guest_isolation.Views(preserve_uid=True)` helper:
the child kept UID/GID 1000, used a different mount namespace, wrote its sentinel
only into the backing directory, and left the host cell and parent namespace
unchanged. Receipt: `target/ci-tiered-development/t6-resume/namespace-probe.json`.
No agent change to sudoers or sandbox policy occurred.

The predeclared continuation contains 19 job instances: the 13 not previously run
as whole jobs (provider plus 12 namespace-dependent instances), one serial recheck
of each of the five failed instances, and the blocked rich aggregate. Each is
executed at most once in this continuation. Independent jobs are now serial to
reduce competing host load; frozen workload scheduling, windows, limits and
assertions are unchanged. A later pass does not prove the root cause of an earlier
failure. There is no retry-until-green loop.

Workload source remains `4090b57`, with its original verified build and source-bound
rich inputs. The final metadata changes are separately tested and are not relabeled
as old-source workload results. Each new checkout is under HOME, preserving SSH
StrictModes, and has its own Maven/output paths. New receipts never overwrite old
ones. The original rich shard must pass this execution before aggregate can run;
other same-source shards come from their recorded executions, with receipt hashes.

Plan, logs and combined attempt index: `target/ci-tiered-development/t6-resume/`.
The plan is frozen before execution. `tools/resume_ci.py` and `tools/resume_index.py`
under the evidence root retain literal commands and reconcile original and resumed
attempts. `resume_index.py --verify` checks log hashes and every passing instance's
complete run-command list. Full readiness remains pending until the outcomes and
remaining acceptance requirements have been reviewed.

The first resumed whole job, `cloud-provider-tests`, passed all three original run
steps in 487.911 seconds, including OpenSSH setup, the complete qualification script
and evidence packing. Receipt: `t6-resume/receipts/cloud-provider-tests/receipt.json`.
This supersedes its earlier not-run-as-a-whole status without erasing either partial
provider attempt. Guest and owned qualification are still in progress.
