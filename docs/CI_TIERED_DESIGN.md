# Tiered CI implementation contract

## Baseline and scope

The local development baseline is `6a65f24023a8f68ca3437096eeacf77a513219fb`.
PR #327 full attempt 2 (`38540436241`) and exact implementation-master run
`38548426916` passed 46 jobs. The subsequent master run `38556252577` passed
the documentation lane (two executed jobs, 36 skipped suites). That last run
does not establish full cloud qualification for its different source.

Reuse the existing 36-suite registry, 38 static jobs, three fixed matrices,
shared verification build, rich shards, independent aggregate, Python partitions,
source/producer/attempt-bound artifacts and optimized replay. These are implemented
baseline features. This work adds execution selection; it does not rebuild them.

## Profiles and trust

* `docs`: retain the conservative documentation classifier and its contract checks.
* `integration`: full coverage except the complete `v51-owned-canonical` suite
  (all three repetitions). Keep all other suites and their dependencies.
* `full`: all 36 suites, 46 expanded jobs including the two meta jobs.

Integration has 43 executed instances; the canonical matrix remains present with
skipped results. Required retains all static dependencies. Unexpected success for
an unselected suite is also an error. Integration success is not full qualification.

Policy is closed JSON data from the protected PR base, never executable commands.
Bind the plan to base, head, actual merge parents, tested source, workflow, registry,
planner, complete diff and run/attempt. Exact regular-file content changes may be
reviewed; additions, deletions, renames, mode/type changes, unknown and mixed risky
paths require full. A policy change cannot authorize its own PR. Old or unavailable
policy can yield a valid conservative full plan; missing/invalid execution plans fail
Required. Master non-documentation pushes, manual runs and Nightly remain full.

The legacy `run_full_ci` output, if retained, means “run ordinary suites” under
integration; only the explicit profile/plan can assert complete full coverage.
The independent cloud consumer continues to require exact-master, exact-attempt,
all-success full inventory and its named visible step. Schedule is not cloud admission.

## Candidate and optional tiers

The first candidate is the exact TravelSearchDemo Java source already examined in
[the core-policy review](CI_CORE_POLICY_REVIEW.md). T3 must renew that review as
“本轮委托自主审查”, record retained reverse-dependency coverage and test the real
selection path. Do not use directory-wide example or Python rules.
Optional consumer/python-isolated rules require separate evidence; otherwise record
`NOT_ENABLED_WITH_RATIONALE`. Do not invent tiers to meet a count.

## Operational controls

Stage migration with forceFull enabled before activating integration. Keep a
versioned forceFull rollback. Nightly runs the complete existing no-GCP workload;
there is no new paid-cloud schedule or empty Weekly workload. Isolate concurrent
scheduled/manual/master runs from PR cancellation. Failed, stale or unavailable
full-health evidence upgrades eligible PRs to full. Hosted scheduling and runtime
improvement remain unmeasured until actual new-source acceptance.

The historical counterfactual integration critical paths are 21:23 (PR) and 20:37
(master timings), compared with roughly 48-minute full runs. These are estimates,
not integration measurements or billing estimates. Historical full summed job
execution was 399.95 and 404.77 runner-minutes, respectively.

## Rollback and release boundaries

First rollback: enable forceFull; the policy-editing PR itself must run full.
Structural rollback must revert workflow, planner, Required, registry contracts and
tests as a group; never restore only a conditional or Required parser. Preserve
published tags, production Java/POMs, frozen hashes/toolchain, release fixtures,
nine JARs/three POMs/six consumers, 90-day release evidence, and continuous
lease/source/history and full canonical windows.
