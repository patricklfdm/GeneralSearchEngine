# Tiered CI forceFull drill

## Purpose and current state

Verify that the existing rollback switch forces an otherwise eligible integration
PR to run the complete CI recipe. The checked-in policy is temporarily `true` for
this drill; hosted override and restoration are **pending**. No workflow, suite,
Required rule, planner, runtime or workload change is needed.

`forceFull` upgrades integration candidates only. Docs stays docs, and non-doc
master, manual and Nightly execution stays full. The switch is reviewed, versioned
policy. The user authorized a one-time CI skip for this enabling PR and its master
merge, using the existing administrator bypass. That skipped validation is not a
hosted pass; the later probe and restoration still require their actual checks.

## Hosted sequence

1. For this explicitly authorized exception, put `[skip ci]` in both the enabling
   commit and the merge commit, then merge using the existing bypass. The policy
   changes from `false` to `true`; if executed, its plan would select full with
   `POLICY_CHANGED`. Record PR/master validation as skipped, without claiming full
   health or a hosted `FORCE_FULL` observation. Other enabling changes normally
   require PR and exact-master full checks.
2. From that master, create a small ordinary content/comment change in the existing
   `examples/travel-search/src/main/java/example/travel/TravelSearchDemo.java`.
   Permitted Markdown may accompany it. Keep policy, workflow, tests and other
   inputs unchanged; do not rename, add, delete or change the example's file mode.
3. Inspect the downloaded PR execution plan and complete job inventory. It must
   record `candidateProfile=integration`, `profile=full`, reasons exactly
   `REVIEWED_INTEGRATION, FORCE_FULL`, and `health=null`. All 46 expanded jobs,
   including the three canonical repetitions, must pass and Required must accept
   them. A `HEALTH_UNAVAILABLE`, self-change or unknown-path fallback does not
   qualify this override check. Record failed attempts and carried executions.
4. Retain the successful probe's exact source/base/attempt and plan before updating
   the probe PR. On that same branch, restore only the switch to `false` and add
   the observed evidence record. The new revision must again run full with
   `POLICY_CHANGED`; it cannot downgrade its own validation. Merge that revision
   after its checks pass, then verify the resulting master full run. This combines
   the probe and restoration in one follow-up PR while keeping their executions
   distinct. If the base changes, refresh and recheck all identities.
5. Read back the merged policy to confirm `forceFull=false`. Subsequent eligible
   PRs may select integration only with qualifying recent exact-base full health.
   Preserve the normal fail-closed health behavior and the complete full recipe.

Do not treat a manual dispatch as the eligible-PR probe: it always selects full.
The one-time skip above does not apply to the probe or restoration. Do not disable
their checks or count an earlier source's plan as the new revision's qualification.
Workflow dispatch, commits, pushes and merges
remain operator actions; this preparation does not trigger them automatically.

## Local checks and failure handling

The existing committed-policy generation test checks override and policy-change
protection. The new CLI regression commits the actual checked-in policy into a
trusted temporary base, then checks docs and eligible example PRs through the real
planner and Required. It validates both legal switch settings when run against
their corresponding checkouts. Forced full must work without a healthy API result
and Required must reject skipped canonical work.

Scenario fixtures explicitly use the integration-enabled baseline; they must not
inherit an operational rollback setting. The repository policy contract still
requires exactly the approved fields and an actual boolean switch, not `0`, `1`
or a string. The original failures from toggling the policy before correcting
these tests remain in `target/ci-tiered-force-full/before-fixture-fix.log`.

If the enabling or probe CI fails, retain the failure and diagnose it; a fallback
full run or rerun is not by itself evidence that the override worked. While `true`
remains merged, eligible PRs continue using full coverage. Restoration uses the
reviewed `false` change above, preserving all new test coverage. No production
rollback, branch protection edit or frozen release change is part of this drill.

See [hosted observations](CI_TIERED_HOSTED_ACCEPTANCE.md) and
[the frozen acceptance checklist](CI_TIERED_ACCEPTANCE.md) for remaining Nightly,
concurrency and local regression gaps. This drill does not close those gaps.
