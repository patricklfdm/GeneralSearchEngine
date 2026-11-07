# Phase 3 execution handoff

Status: tooling implemented; final-source execution and Phase 3 remain OPEN.
The operator will arrange a qualifying native Linux machine after development.
This entry neither provisions it nor dispatches any workflow.

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
`EXECUTION.md` contains individual dispatch commands and the acceptance order.
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
Continuous histories remain indivisible. Existing in-workflow parallel limits
remain unchanged; an unspecified limit is recorded as null, not an invented
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
Manual dispatch may use the same branch for all eighteen workflows: the existing
adapters bind the workflow to that branch and exact SHA. The named
`experiment/v53-*` branches additionally enable the corresponding push triggers;
creating eighteen moving refs is unnecessary for manual dispatch.

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
The focused suites passed 115 distinct Python tests, including the existing
workflow observers and hosted adapters. All three changed YAML files and their
14 shell blocks passed local syntax checks. Runtime Java, frozen protocol
parameters and existing Required workflows are unchanged.
