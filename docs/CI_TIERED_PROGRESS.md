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
| T1 suite-aware shadow plan | Pending | Pending | HOSTED_PENDING |
| T2 plan/Required/workflow, forceFull | Pending | Pending | HOSTED_PENDING |
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
* Next: extend the existing shadow planner and its tests. Actual execution remains
  docs/full until the coordinated T2/T3 migration. Do not duplicate the registry.

Stage commit IDs are available from Git history for this file; each stage records
its exact checks and evidence before committing. Final readiness has not been claimed.
