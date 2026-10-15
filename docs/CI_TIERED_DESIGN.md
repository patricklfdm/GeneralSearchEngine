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

The first enabled rule, `travel-demo-content-v1`, is the exact TravelSearchDemo
Java source already examined in [the core-policy review](CI_CORE_POLICY_REVIEW.md).
The renewed review below is “本轮委托自主审查”; the user did not individually
approve a list of paths. This rule is applied only from a byte-identical trusted
base policy. Its own rollout PR is full.

| Rule boundary | Evidence / retained coverage |
| --- | --- |
| Exact path | `examples/travel-search/src/main/java/example/travel/TravelSearchDemo.java` only. |
| Status and type | Git `M`, regular file at both ends, identical modes, different blob IDs. No addition, deletion, rename, symlink, gitlink or execute-bit change. |
| Reverse dependency | Re-read the example and its POM: standalone core API only, no replication/processor dependency, deploy skipped. The reactor includes the example module. |
| Retained execution | Reactor compilation/tests; independent build domains; `Soak and examples` including `scripts/run-travel-example.sh`; compatibility, release, all protocol/resource/recovery/fault suites, rich shards/aggregate, five tapes, complete experiment and failure drill. |
| Omitted execution | Only three complete owned canonical repetitions. Their package contains core/replication JARs and explicit adapters, not example classes. No old build/PASS is reused. |
| Escalation | Any accompanying non-doc path outside the exact rule, changed policy/CI/build/package dependencies, unknown/new-version paths, old/invalid policy, missing history or forceFull select full. Master always full for non-doc changes. |
| Remaining risk | This is a reviewed dependency argument, not proof of universal independence. Changes to packaging/dependencies must re-review the rule; protected full and Nightly remain required. Historical sampled traffic had zero eligible PRs, so no daily savings are claimed. |

The candidate can coexist with permitted documentation changes. The complete PR
diff, not its last commit, controls selection. There is no directory-wide example
or Python allowance. `forceFull=true` restores full for an eligible candidate;
the observer may still report the integration candidate separately from execution.
Optional consumer/python-isolated rules require separate evidence; otherwise record
`NOT_ENABLED_WITH_RATIONALE`. Do not invent tiers to meet a count.

## Operational controls

Stage migration with forceFull enabled before activating integration. Keep a
versioned forceFull rollback. Nightly runs the complete existing no-GCP workload;
there is no new paid-cloud schedule or empty Weekly workload. Isolate concurrent
scheduled/manual/master runs from PR cancellation. Failed, stale or unavailable
full-health evidence upgrades eligible PRs to full. The
[hosted report](CI_TIERED_HOSTED_ACCEPTANCE.md) retains the first real integration
timing sample; actual Nightly/concurrency and reliable timing distributions remain
unobserved.

Nightly is `17 10 * * *` (10:17 UTC daily) in the same CI workflow. Manual dispatch
is always full. Only PR runs cancel previous runs on the same PR ref; other event
groups include run ID, keeping master/manual/Nightly isolated. Existing verification
commands and time ceilings are unchanged. There is no unchanged-source or
recent-full-success deduplication: every schedule event selects full. Nightly is
expensive: the baseline full
execution totaled about 400 runner-minutes; scheduling it is not a claim of reduced
total daily CI usage.

Before selecting integration, the planner reads the newest matching CI run on
master for the **exact protected PR base SHA**, including failed/cancelled/pending
runs. It requires the same control-plane bytes, all 46 expanded jobs successful
at the accepted attempt, visible complete canonical and experiment qualification
steps, stable paginated observations, and completion within 36 hours. This is
deliberately stricter than using an ancestor's green result: a new docs-only master
without a full run also upgrades eligible PRs to full until a full manual/Nightly
or non-doc master run establishes health at that source. No API access, truncated
pages, incomplete matrices and ambiguous data also select full.

Required rechecks an integration plan's health observation. A changed/stale/failed
health record cannot grant integration acceptance. A plan already upgraded to full
keeps its conservative recipe if external health later improves, because all full
suite results are still required. No automatic rerun/dispatch or settings mutation
occurs. The GitHub token has only contents/actions read access; no cloud token is
introduced. These health observations are not cloud/release admission receipts;
`cloud_ci.py` still rejects schedule and integration.

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

The [hosted drill](CI_TIERED_FORCE_FULL_DRILL.md) now records actual override routing
and the restoration to `false` through PR #333. The enabling PR/master used the
user's one-time skip; the routing probe was accepted without awaiting all workloads;
the restoration PR and master passed full. This is not a general skip-CI policy.
