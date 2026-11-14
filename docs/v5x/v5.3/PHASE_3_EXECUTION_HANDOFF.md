# Phase 3 execution handoff

Status: tooling implemented; final-source execution and Phase 3 remain OPEN.
The operator will arrange a qualifying native Linux machine after development.
This entry neither provisions it nor dispatches any workflow.

The [276dcdf5 hosted review](PHASE_3_HOSTED_REVIEW_276DCDF5.md) records two complete
successful families and the remaining infrastructure, native capture and replay
failures. Native capture changes require new-source executions; earlier green
receipts do not qualify the correction.

The [373da301 hosted review](PHASE_3_HOSTED_REVIEW_373DA301.md) separates the
five latest failed aggregates into original failures, dependent failures and
replay defects. It records retained-original corrections and keeps native
deadline investigations and final-source qualification open.

The [2026-11-10 expansion failure review](PHASE_3_EXPANSION_FAILURE_REVIEW.md)
records the first twelve expanded hosted runs at `5217a556`, their retained
failures and the subsequent local corrections. That review does not admit the
cohort or replace the remaining original executions and independent replays.
The [2026-11-12 rerun review](PHASE_3_RERUN_FAILURE_REVIEW.md) records all nine
follow-up runs at `defd80d2`, confirmed replay fixes and still-open original
failures. Successful families do not admit the remaining failed families.

## Generate from the final checkout

The [offline planner](../../../scripts/v53/phase3_execution_plan.py) reads the
existing catalogue and all three workflow-contract readers. It requires a clean
checkout, the exact local source/ref pair, unchanged Git source before and after
inspection, and unchanged actual workflow bytes. Its output must be new, outside
source paths or under ignored `target/`.

```bash
python3 -B -m scripts.v53.phase3_execution_plan \
  --source "$(git rev-parse HEAD)" \
  --ref "$(git branch --show-current)" \
  --output "target/v53-execution-handoff/plan-$(date -u +%Y%m%dT%H%M%SZ)"
```

`plan.json` retains exact job names, dependency roles, matrix group counts,
runner selections, explicit per-job parallel limits and workflow/source hashes.
`EXECUTION.md` contains conditional manual-dispatch commands, creation-only push
commands for existing experimental triggers, and the acceptance order.
The planner only prints those commands. It performs no API request, Maven build,
Git write, dispatch or original replay. Both outputs remain PLANNED and cannot
satisfy a seed or evidence gate.

The current actual contracts expand as follows:

| Set | Workflows | Selected jobs | Scope |
| --- | ---: | ---: | --- |
| History subsets | 12 | 544 | 566 whole histories, 260 execution groups |
| Supplemental resources | 4 | 15 | Five original components |
| Maximum native and queue | 2 | 6 | Two additional original components |
| Total | 18 | 565 | All sets remain necessary |

The three large workflows are maximum-transition (inside the supplemental set),
maximum-native and maximum-queue. The other fifteen use GitHub-hosted runners.
These are scheduling counts, not executed outcomes or a measured duration.
Continuous histories remain indivisible. The Joining process execute/verify
matrices now omit their former eight-job cap; other in-workflow parallel limits
remain unchanged. An unspecified limit is recorded as null, not an invented
concurrency or runner-availability estimate.

## Large runner queue and capacity

All three large workflows share `v53-maximum-transition-large-runner`, now with
`queue: max` and `cancel-in-progress: false`. GitHub's default queue permits only
one pending run and replaces that pending run when another arrives, even when
the active run is protected. The explicit max queue retains up to 100 pending
runs while executing one at a time. Overflow can reject new runs, and dispatch
order does not guarantee execution order. See the
[GitHub concurrency contract](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

The two existing workflow readers now require this shared queue policy for all
three entries. This prevents a later workflow edit from silently dropping the
queue protection while passing source-contract validation. Failed or cancelled
attempts still remain failures in the observer; queue policy provides no evidence
credit and cannot erase them.

The planner imports capacity values from the existing admission implementations:

| Stage | Free disk required at that point |
| --- | ---: |
| Direct large capture | 272 GiB |
| Direct large verification | 144 GiB |
| Maximum-native/queue hosted execution | 280 GiB |
| Maximum-native/queue before verification download | 416 GiB |
| Maximum-native/queue verification | 288 GiB |
| Complete attested replay, after all inputs are present | 448 GiB |

Each large stage also requires native Linux and at least 8 GiB available memory.
WSL remains rejected. These values are **free space, not disk capacity**; original
downloads, retained failed runs and other workspace contents need additional
space. They are per-stage admission requirements, not measured peak usage or a
promise that concurrent unrelated work cannot fill the disk. No limit changes.

## Execution and remaining closure work

After explicit authorization, push a frozen ref and verify that its remote SHA
matches the plan and that the workflows are dispatchable. The offline planner
does not verify remote existence, runner availability or GitHub permissions.
GitHub requires the workflow definition on the default branch before
`workflow_dispatch` can trigger it; merely publishing a new development branch
does not establish that condition. See
[manual workflow prerequisites](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
After registration, manual dispatch may use the same branch for all eighteen workflows: the existing
adapters bind the workflow to that branch and exact SHA. The named
`experiment/v53-*` branches additionally enable the corresponding push triggers;
creating eighteen moving refs is unnecessary for registered manual dispatch.

### Before default-branch registration

The [2026-11-07 read-only startup review](phase3-evidence/remote-startup-review.json)
found zero V5.3 workflow definitions on `master` and zero V5.3 registrations among
all 21 API workflow records. The remote development branch was still at the
Phase 2 source `f0d4dcaf0eaab7bc8a7ca5d86facc052260e5b1a`. No matching V5.3
experimental refs existed. These are dated observations, not assumptions to
reuse after another push or repository change.

Fourteen existing workflows have exact experimental push triggers: the twelve
history subsets, required-four resources and capacity completion. Their 550
selected jobs can start from the same frozen commit without first enabling
manual dispatch on master. The planner derives the trigger from each actual
workflow and checks it against the owning adapter; it does not invent a branch
name or broaden a trigger. The generated Git command has an empty expected lease,
so it can create an absent remote ref but cannot overwrite an existing one.
An already identical ref returns success as an up-to-date no-op; that does not
start another run. The commands request porcelain output: require `*` / new
branch, then inspect the actual Actions run. Publishing each new ref starts its
corresponding experiment and still requires explicit authorization. Do not follow
that push with a duplicate manual run.

Queue resources and the three large workflows are manual-only: four workflows,
15 selected jobs. They remain mandatory and pending until the workflow definitions
are registered on the default branch; the large three also need the native host.
This entry does not modify master, create a registration PR, change repository
settings or weaken their manual-only guards. Do not replace their missing results
with the fourteen available workflows.

Keep the selected ref fixed throughout the cohort. Provision the large runner
before dispatching its three workflows. Retain explicit run/attempt IDs, original
artifact ZIPs and all earlier failed or cancelled attempts. Independent groups
may run in parallel; no measurement is retried by this planner.

Reconcile matching source, classes, toolchain and dependency pins, then invoke
[the complete v4 attested replay](PHASE_3_WORKFLOW_COHORT.md) with all twelve history
subsets, all five supplemental originals and both maximum originals. Even a
successful replay remains PARTIAL until the separate actual coverage,
combined-resource and prior-failure review is complete. The five original gaps
remain OPEN; a generated plan or an additional passing component cannot close them.

Local validation covers the actual eighteen workflow contracts and synthetic
source/ref drift, missing dispatch inputs, preservation of prior outputs,
unacceptable branch strings and removal/change of any large queue policy. It
does not demonstrate a live hosted run or maximum-history execution.
The initial handoff suites passed 115 distinct Python tests, including the existing
workflow observers and hosted adapters. All three changed YAML files and their
14 shell blocks passed local syntax checks. Runtime Java, frozen protocol
parameters and existing Required workflows are unchanged.
The startup correction adds checks of all actual push adapters, exact trigger
branches and creation-only commands. An isolated local bare Git repository checks
new-ref creation, identical-ref no-op and rejection of an existing-ref update.
Remote observation and command generation
are not a live test of workflow execution.
