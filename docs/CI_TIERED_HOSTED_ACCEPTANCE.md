# Tiered CI hosted acceptance observations

## Scope and source identity

This report records read-only GitHub observations through PR #333's in-progress
routing probe `38692089814` on 2026-10-15 UTC.
It supplements [the frozen acceptance checklist](CI_TIERED_ACCEPTANCE.md) and
[development progress](CI_TIERED_PROGRESS.md). It does not mark T6 closed or turn
the five retained local failures into passes.

[PR #329](https://github.com/patricklfdm/GeneralSearchEngine/pull/329) deployed the
profiles. [PR #330](https://github.com/patricklfdm/GeneralSearchEngine/pull/330)
exercised the existing integration rule with comments in the exact allowed Java
example plus permitted Markdown. No policy, workload or runtime changes were
needed for that acceptance.

| Run | Event and exact source | Observed result |
| --- | --- | --- |
| [38661192806](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38661192806) | Branch manual; `ce8b5d15346683db8b12f282e30b579f1926fc78` | Full, attempt 1: 46 successes. |
| [38665872994](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38665872994) | PR #329; API head `ce8b5d1` | Full, accepted attempt 2: 46 successes. Attempt 1 failed public reads/faults and Required. |
| [38674338594](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38674338594) | Master push; `8f72b529fea901836a1b828b9ae8688f9f7eccf6` | Full, accepted attempt 2: 46 successes. Attempt 1 failed automatic-healthy canonical tape and Required. |
| [38681060125](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38681060125) | PR #330; tested merge `a28d3891eb6c3a93a1ca03d7ad3d3eccdb61d7bd` | Integration, accepted attempt 2: 43 successes, one skipped canonical placeholder. Attempt 1 failed guest services and Required. |
| [38683792757](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38683792757) | Master push; `938958bfc42c13de5dd4854fcec3ec844d291749` | Full, attempt 1: 46 successes. |
| [38689603696](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38689603696) | PR #331; tested merge `78beee985a75395f650eadcf484943f5353097de` | Docs, attempt 1: two successes, 36 skipped suite placeholders. |
| [38689790501](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38689790501) | Master push; `535add252b43b674a951710393e93d844add2fb1` | Docs, attempt 1: two successes, 36 skipped suite placeholders. |
| [38692089814](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38692089814) | PR #333; tested merge `2c7b3e7592b154f6e40aff2431189448306360b9` | ForceFull routing confirmed on attempt 1: integration candidate, full plan, all three canonical repetitions running. At capture: 44 visible jobs, 12 successful, 31 in progress, one failed automatic-healthy workload. Full qualification not passed. |

PR #330's head is `e22f2c993f564a9da0352b6b0ae904a1c92d5a3c`, and its protected
base is `8f72b529fea901836a1b828b9ae8688f9f7eccf6`. The PR run API reports the
head; its downloaded execution plan reports the actual tested merge. They are
different identities. The integration plan was produced in attempt 1 and accepted
by Required in attempt 2 after checking its carried provenance and full health.
The exact-master plan independently selects full. An integration result never
stands in for full cloud or release qualification.

PR #331's head is `825b003e644b266baa4b720bfe9fdc9b590fe642`. Both its PR and
master downloaded plans select docs; Change scope and Required are the only
executed jobs. These observed executions complete the docs-routing check. They
do not establish full health for the new master source.

All original attempts and complete job pages were retained. Integration's single
skipped UI row represents the entire unexpanded canonical matrix; it does not
mean that two canonical repetitions ran. All 41 selected non-meta instances and
both meta jobs succeeded at acceptance. Recovered runs establish their accepted
outcomes, not a root-cause fix or a successful first attempt.

## First timing sample

The following numbers come from API job timestamps for PR #330 and its subsequent
master. Execution span means earliest actual job start to latest completion in
the specified set. Runner-minutes are the sum of actual job execution seconds
divided by 60; they are not billing minutes, prices or charges.

| Observation | Executions counted | Execution span | Summed runner-minutes |
| --- | ---: | ---: | ---: |
| Integration attempt 1, failed | 43 | 20:43 | 260.82 |
| Integration attempt 2, newly executed jobs only | 2 | 7:53 | 7.85 |
| Integration through accepted completion | 45 unique executions across both attempts | 29:45, including the gap before rerun | 268.67 |
| Master full attempt 1, passed | 46 | 47:15 | 387.72 |

Attempt 2 exposes 43 successful jobs, but 41 are carried executions. Deduplication
compares unchanged name/run/source/runner/start/end/status/steps, and validates
the later creation timestamp when GitHub assigns a different job ID. Carried
executions are counted once. The latest run API's `run_started_at` describes the
rerun, so it is not used as the original start. The 69-second interval between
the first attempt's last completion and the second attempt's first start is part
of the 29:45 accepted elapsed observation, not runner execution.

This is one integration PR, with a failure and rerun, and one successful master
full run. Their source/event and execution conditions differ. The observed
difference is not a causal speedup estimate, a guaranteed 20-minute successful
integration run, a P95, or evidence of lower total daily cost. Nightly full adds
execution, and the historical candidate-rule review found little eligible traffic.

### Observed limiting dependency chains

The following chain is traced backward from Required through the latest finishing
prerequisite at each step of the first attempt. It describes the observed run;
it is not a counterfactual schedule with jobs removed.

| Profile | Observed chain, with execution durations |
| --- | --- |
| Integration attempt 1 | Change scope 1:26 → verification build 5:24 → owned failure drill 13:33 → Required 0:12 |
| Master full attempt 1 | Change scope 1:27 → verification build 5:26 → canonical repetition 3 40:09 → Required 0:05 |

Dependency readiness is the latest prerequisite completion. Time from that point
to job creation is reported separately from creation-to-start and start-to-end
execution in the retained per-job data. On these chains, readiness-to-creation
was 0–1 seconds and creation-to-start was 1–3 seconds. The latter may include
queueing and runner provisioning; the API does not isolate scheduler-only waiting.
Dependency waits overlap across jobs and cannot be added as workflow wall time.

## Rules and remaining acceptance

The read-only `rules/branches/master` response includes pull-request enforcement,
deletion/non-fast-forward protection, and a required-status-check rule with:

* check context `Required`, integration ID `15368`;
* `strict_required_status_checks_policy=true`;
* `do_not_enforce_on_create=false`.

This confirms the API check context, distinct from the UI's `CI / Required`
workflow/check label. No setting or bypass policy was changed, and no bypass was
exercised by this audit.

| Remaining item | Current state / acceptance |
| --- | --- |
| Docs PR and its master push | Observed in PR #331 and its master push: docs plans, two successful meta jobs and all 36 suite placeholders skipped; both passed on attempt 1. |
| Nightly | The schedule-event listing returned `total_count=0` at 05:51 UTC, before the first 10:17 UTC slot following deployment. Manual execution is not a scheduled-run observation. |
| Concurrency isolation | Configuration and local negative tests passed; actual overlapping-event behavior still needs a hosted observation. |
| forceFull | PR #333's plan and canonical starts confirm the override. The user accepted routing without awaiting a full workload pass; the existing failed workload remains recorded. The [restoration revision](CI_TIERED_FORCE_FULL_DRILL.md) sets `false`; merge/master verification remains pending. |
| Local regression gaps | Five original failed instances remain documented in the progress record; neither the hosted pass nor a different successful repetition replaces them. |
| Timing confidence | First measured sample recorded above; further naturally occurring samples are needed before making reliability, percentile or daily-cost claims. |

After a docs-only master merge, the new exact source has docs acceptance, not full
health. A later integration candidate must conservatively run full until the new
base has a qualifying manual, Nightly or non-doc master full result. There is no
automatic extra run or older-green substitution to bypass this requirement.

## Retained evidence and reproduction

Small raw API JSON, downloaded execution-plan artifacts and attempt summaries are
retained locally under:

* `target/ci-tiered-hosted-review/` — rollout manual/PR/master observations;
* `target/ci-tiered-integration/hosted-pr330/` — both PR attempts, master attempt,
  artifact metadata and exact execution plans;
* `target/ci-tiered-docs-acceptance/` — rule/schedule observations and derived
  `timings.json`, including per-input SHA-256 and per-job execution/wait breakdown;
  `hosted-pr331/` contains the subsequent docs PR/master pages and execution plans.
* `target/ci-tiered-force-full-probe/hosted-38692089814/` — PR #333's source/attempt,
  complete API pages at capture, downloaded routing plan, automatic-healthy failure
  log and evidence hash index. This is a partial observation, not a full pass.

The retained read-only analysis script
`target/ci-tiered-docs-acceptance/tools/measure.py` regenerates the timing JSON from
the captured pages. It uses the unchanged versioned suite dependencies, requires
complete unique job pages and consistent identities/timestamps, and does not call
GitHub or schedule work. These local files are not CI inputs or substitutes for
hosted artifact provenance. Source/workflow identities remain in the original
receipts rather than being relabeled as this documentation commit.
