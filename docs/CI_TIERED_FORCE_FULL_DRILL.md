# Tiered CI forceFull drill

## Purpose and current state

Verify that the existing rollback switch forces an otherwise eligible integration
PR to run the complete CI recipe. Hosted routing is **CONFIRMED** in PR #333;
the user accepted this routing observation without waiting for all workloads to
finish. PR #333 restored the checked-in policy to `false` and merged at
`0ada3ccbbcb9bcab3ef5ddbf25f28861e6cf7b7d`; its PR and exact-master full results
are recorded below. No workflow, suite,
Required rule, planner, runtime or workload change is needed.

`forceFull` upgrades integration candidates only. Docs stays docs, and non-doc
master, manual and Nightly execution stays full. The switch is reviewed, versioned
policy. The user authorized a one-time CI skip for this enabling PR and its master
merge, using the existing administrator bypass. That skipped validation is not a
hosted pass. The subsequent routing-only decision is recorded below; restoration
still requires its normal checks.

## Observed probe and user-directed acceptance scope

[PR #333 run 38692089814](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38692089814),
attempt 1, binds base `3d05a6f660f6819e06dd3e4291eeb5840bd41e9e`, head
`7e8b3bd96d67e6f068fa00cb7624ed1b7c768597` and tested merge
`2c7b3e7592b154f6e40aff2431189448306360b9`. The downloaded plan records
`candidateProfile=integration`, `profile=full`, exactly
`REVIEWED_INTEGRATION, FORCE_FULL`, `health=null`, and 46 planned jobs. Change scope
passed, and all three canonical repetitions were observed running.

At capture, the complete paginated jobs API exposed 44 rows: 12 successful,
31 in progress and one failed. Other dependent jobs had not yet appeared. The
automatic-healthy rich workload failed at `frozen guest window failed`; its raw
log is retained without assigning an unproven scheduling/runtime root cause.
Thus this observation establishes routing, not successful full qualification or
Required acceptance. No cancellation or later outcome is inferred from this
snapshot.

The routing run subsequently ended `cancelled`; that final status does not replace
the captured failed job or establish the outcome of unfinished work.

The user explicitly accepted the routing result and chose not to wait for this
probe to finish before restoration. This narrows the drill's acceptance scope;
it does not turn any failed or unexecuted checks into passes. Raw run/PR/artifact
metadata, every jobs page, the downloaded plan, failure log and hash index are in
`target/ci-tiered-force-full-probe/hosted-38692089814/`.

## Completed restoration

The restoration head `88089b1547aec4965dd1116f704c2cf959029a99` passed
[PR CI 38693534135](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38693534135)
on attempt 1: all 46 jobs successful, tested merge
`97baf7fc9678c981e0f2fa87700755ee4f7b28e5`. PR #333 merged at
`0ada3ccbbcb9bcab3ef5ddbf25f28861e6cf7b7d`.
[Exact-master CI 38699074927](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38699074927)
passed all 46 jobs at accepted attempt 2. Attempt 1 failed the automatic-healthy
owned canonical tape and Required; it is not a clean first-attempt pass or evidence
that the failure's cause was fixed. Carried successes are not new executions.

Both downloaded execution plans select full with `POLICY_CHANGED`. Exact-source
readback confirms `forceFull=false`. This completes configuration restoration and
the user-accepted routing drill. Raw attempt pages, plans, policy readback and
summary are under `target/ci-tiered-force-full-restore/hosted-pr333/`.
Nightly/concurrency observations and the five historical local failures remain
separate open items; this result does not mark full T6 acceptance complete.

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
   them to claim full qualification. For this drill, the user's narrower routing
   acceptance is established by the plan and actual canonical starts above.
   A `HEALTH_UNAVAILABLE`, self-change or unknown-path fallback does not qualify
   this override check. Record failed attempts and carried executions.
4. Retain the routing probe's exact source/base/attempt and plan before updating
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
The one-time skip above does not apply to restoration. Updating this PR may cancel
the still-running probe through the existing PR concurrency policy. Do not count
an earlier source's plan as the new revision's qualification.
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
