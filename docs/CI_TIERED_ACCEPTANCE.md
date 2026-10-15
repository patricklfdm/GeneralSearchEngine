# Tiered CI acceptance checklist

Frozen before implementation on baseline `6a65f24023a8f68ca3437096eeacf77a513219fb`.
This checklist may gain checks; failed checks cannot be removed to claim readiness.

## Local checks required for final readiness

1. All existing change-scope tests plus new planner, Required and scheduling tests.
   Initial command: `python3.11 -m unittest scripts.test_ci_changes scripts.test_maven_infra_retry scripts.test_ci_v51_bundle scripts.test_ci_v51_python scripts.test_ci_suites scripts.test_ci_required scripts.test_ci_composites scripts.test_ci_shadow_plan`.
2. Real temporary Git graph tests: complete multi-commit diff, fork/base/head/merge
   identity, rename/delete/new/mode/type, mixed and unknown paths, new-version
   directories, self-modification, old-policy rollout and malformed/missing plans.
3. Exact docs/full/integration results and dependency closure. Exercise every
   selected suite's failure/cancel/timeout/skip; reject missing/extra/duplicate suites,
   drifted or incomplete fixed matrices and unexpected unselected results.
4. Real local eligible-integration selection, forceFull rollback and structural
   rollback. Test optional tier disabled/enabled boundaries as applicable.
5. Manual/master/Nightly routing, concurrency isolation, full-health failure,
   stale and unavailable evidence. Keep cloud schedule rejection intact.
6. Build artifact corruption, missing files, wrong producer/source/attempt and
   Surefire provenance regressions; cloud and release fixture compatibility;
   exhaustive Python partition discovery and regenerated inventory parity.
7. One complete applicable local no-GCP regression using the literal verification
   commands in the effective workflow. Preserve independent build domains, all
   three canonical repetitions, full windows/calls/history and negative validators.
   Limit concurrency between independent executions if needed, never workloads.
8. Actual diff/self-review, docs/link/whitespace checks, evidence index and staged
   commits; no task-owned uncommitted files at final delivery.

The initial effective run-command inventory and source hashes are retained at
`target/ci-tiered-development/t0/`. It is extracted using the existing closed workflow
parser including local composite expansion, not an invented list of script names.
Final validation must reconcile that inventory against the final workflow and
explain all differences. Existing tests cannot be replaced with report generation.

## Hosted checks (not executed by this local goal)

* Full policy-rollout PR and exact new-master full run, including every fixed matrix.
* Subsequent eligible integration PR, docs PR and forceFull exercise, with complete
  job/step/attempt evidence and unselected-suite results.
* Manual full and actual Nightly scheduling/concurrency/health behavior.
* Stable Required check identity/Ruleset behavior and cloud/release consumers.
* Real critical path, runner waiting and summed runner-minutes; no fabricated P95
  or savings derived from a single counterfactual estimate.

New-source hosted status starts `HOSTED_PENDING`. An unavailable mandatory local
check is `LOCAL_VALIDATION_BLOCKED`, not hosted pending. Final local readiness
requires every applicable mandatory local item to pass.

## Observed hosted progress through PR #333's restoration

The [hosted acceptance report](CI_TIERED_HOSTED_ACCEPTANCE.md) records complete
attempt inventories, downloaded plans and the first measured timing sample.
Manual full, rollout PR/master full, and a real integration PR with its subsequent
master full have passed. The PR reruns and original local failures remain visible;
none is relabeled as a clean first attempt or a root-cause fix.

PR #331 and its master push qualified docs routing on attempt 1: two successful
meta jobs, all 36 suites skipped, and Required accepting that precise recipe.
Read-only rules inspection confirms the stable `Required` check and strict
up-to-date enforcement. This observation does not test an administrator bypass.
The [hosted forceFull drill](CI_TIERED_FORCE_FULL_DRILL.md) now has a verified
integration-to-full plan and actual starts of all three canonical repetitions.
The user accepted that routing result without waiting for complete workloads.
This explicitly narrows this drill's acceptance; the captured automatic-healthy
failure and unfinished jobs are not passes or full qualification. Restoration
merged with `forceFull=false`; PR CI `38693534135` passed all 46 jobs on attempt 1,
and exact-master CI `38699074927` passed all 46 jobs at accepted attempt 2. The
first master attempt's automatic-healthy canonical tape and Required failures
remain recorded. Actual Nightly/concurrency checks remain pending. These observations
preserve the original checklist and do not replace mandatory local acceptance with
hosted success.
