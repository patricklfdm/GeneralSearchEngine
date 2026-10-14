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
| T3 integration activation | Pending | Pending | HOSTED_PENDING |
| T4 optional rule review | Pending | Pending | HOSTED_PENDING |
| T5 Nightly/manual/health controls | Pending | Pending | HOSTED_PENDING |
| T6 full local regression and review | Pending | Pending | HOSTED_PENDING |

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
* Next: T3 exact-path candidate review/activation and real Git event selection tests.

Stage commit IDs are available from Git history for this file; each stage records
its exact checks and evidence before committing. Final readiness has not been claimed.
