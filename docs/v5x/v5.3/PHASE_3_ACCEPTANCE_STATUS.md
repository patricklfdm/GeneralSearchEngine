# Phase 3 acceptance readiness: 2026-11-15

Status: **OPEN; preparation only**. Source inspected:
`659377b3ea89245fb939d124a0783f5b840492b1`, branch
`feat/v53-cluster-operations`. This review changes no runtime, workflow, frozen
limit, or acceptance decision. It launches no experiment.

At the November 15 audit, Automatic passed all eight jobs, including the complete
exact-attempt aggregate. That selection contained **12 successful families,
two failed and four unexecuted**, across five successful source commits.
The dated follow-up below updates those results. Neither inventory is a
qualifying final-source cohort.

## 2026-11-16 follow-up

At source `b7b378a61ca188919bb12ed04ecf7fe46f629f80`,
[node-renames 43803439569](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43803439569)
passes all ten jobs (attempt 1, 16m10s).
[learner-histories 43803439571](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43803439571)
finishes both originals, but alternating-slot replay fails on 48 retained
nonselected-voter refusals; the aggregate fails downstream. Retained-cancellation
passes original and replay. The updated progress inventory is **13 successful,
one failed and four unexecuted families**, across six sources, not final-source
acceptance. See the [original-byte review and correction](PHASE_3_REMAINING_FAMILIES_REVIEW.md).
The historical sample counts/cost totals below still describe the November 15
selection, not these two additional runs.

## November 15 inventory

The offline planner reads the actual 18 workflows: 565 selected jobs, including
12 history families, four supplemental resource families and two maximum
families. The following table selects the latest run per family, including
failures; it does not replace a later failure with an earlier success.

| Family | Latest result | Run | Attempt | Source | Observed/planned jobs |
| --- | --- | --- | ---: | --- | ---: |
| histories/profiles | SUCCESS | [42699337007](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42699337007) | 1 | `5217a556` | 16/16 |
| histories/joining-reply-loss | SUCCESS | [43123624778](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123624778) | 1 | `defd80d2` | 8/8 |
| histories/remove-process | SUCCESS | [42716178420](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716178420) | 1 | `5217a556` | 106/106 |
| histories/node-renames | FAILURE | [43123631252](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123631252) | 1 | `defd80d2` | 10/10 |
| histories/joining-process | SUCCESS | [43582470815](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470815) | 1 | `a2606899` | 242/242 |
| histories/learner-histories | FAILURE | [43123639693](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123639693) | 1 | `defd80d2` | 6/6 |
| histories/transfer-histories | SUCCESS | [42716179974](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716179974) | 1 | `5217a556` | 6/6 |
| histories/round-histories | SUCCESS | [43123647228](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123647228) | 1 | `defd80d2` | 16/16 |
| histories/carried-data-histories | SUCCESS | [43582470403](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470403) | 1 | `a2606899` | 26/26 |
| histories/carried-transition-histories | SUCCESS | [43653110389](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43653110389) | 1 | `b23242fa` | 34/34 |
| histories/automatic-histories | SUCCESS | [43705461994](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43705461994) | 1 | `659377b3` | 8/8 |
| histories/joint-floor-process | SUCCESS | [43582470481](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470481) | 1 | `a2606899` | 66/66 |
| resources/required-four | SUCCESS | [42699339465](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42699339465) | 1 | `5217a556` | 3/3 |
| resources/maximum-image | NOT_RUN | — | — | `—` | 0/3 |
| resources/capacity-completion | SUCCESS | [42716181225](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42716181225) | 1 | `5217a556` | 3/3 |
| resources/queue-resources | NOT_RUN | — | — | `—` | 0/6 |
| maximum/maximum-native | NOT_RUN | — | — | `—` | 0/3 |
| maximum/maximum-queue | NOT_RUN | — | — | `—` | 0/3 |

Full SHAs, artifact counts/expiry and failed job IDs are retained in the
[machine-readable review](phase3-evidence/readiness-20261115.json).
A green workflow status is not independent artifact-byte or physical validation
performed by this audit.

## Observation scope and retained evidence

Read-only GitHub collection covered all 63 repository runs returned for the
startup window beginning 2026-11-07; 54 belong to these families (17 successful,
37 failed latest attempts). The two runs with attempt 2,
`42470755638` and `42470755416`, retain both attempt metadata records separately.
Older failed attempts are not erased by later success. This is not an all-time
repository history or a collection of every historical attempt's job logs.

All pages for the 14 selected exact attempts were collected: **550 jobs and
947 artifact records, 19,843,192,024 stored bytes (18.48 GiB)**. No selected
artifact was marked expired; the earliest selected expiry is
`2027-02-07T21:06:36Z`. Large original contents were not downloaded in this
audit. Archive sizes do not measure uncompressed disk peaks.

Selected job intervals sum to **420.66 runner-hours** (Joining process accounts
for 375.10). This sum includes parallel execution and only the selected
attempts; it is neither elapsed cohort duration, complete historical usage,
nor a bill. It is not a forecast for a different machine.

Raw pages, failure logs, the complete artifact/job indexes, historical attempts,
input SHA-256 inventory, offline summarizer and generated execution plan are
under `target/v53-phase3-readiness-20261115/`. They are local, ignored audit
materials; the compact review above is retained in documentation. GitHub's
workflow registry required a read-only `gh api` fallback because the connected
GitHub fetch tool does not support that collection endpoint.

## Remaining work that does not need a large host

1. **Node renames:** four original jobs failed in `43123631252`; their replay
   and aggregate failures are downstream. Logs retain
   `node rename Maven failed; original retained`, not a proven GitHub outage.
   Inspect the retained original Maven/Surefire evidence against current source
   before selecting a correction or rerun.
2. **Learner histories:** the alternating-slot original failed in
   `43123639693`; the retained-cancellation original/replay passed. The
   [earlier retained-evidence review](PHASE_3_RERUN_FAILURE_REVIEW.md) records
   the alternating-slot deadline. The fresh job log confirms the failed original
   but does not independently establish a scheduling root cause.
3. **Queue resources:** the existing two-original/six-job workflow runs on
   ordinary `ubuntu-24.04`. It does not need the maximum host. Its manual-only
   workflow is absent from the current registry.
4. Prepare registration of all four manual-only workflows without dispatching
   or changing Required. The live registry contains 35 workflows, 14 belonging
   to V5.3; queue resources and the three maximum entries are absent. A workflow
   visible after an experimental push does not by itself prove default-branch
   manual-dispatch readiness. Default-branch registration remains separate work.

The three maximum workflows await both registration and a qualifying native
Linux host. See [large-runner preparation and costs](PHASE_3_LARGE_RUNNER_PREPARATION.md).

## Execution order after preparation

* Resolve the two ordinary failed families first, with their originals retained.
* Register the manual entries, then run ordinary queue resources; prepare the
  large machine and perform its capacity/toolchain checks.
* Execute maximum-image transition, maximum-native and maximum-queue as whole
  histories, followed by their independent downloaded replays. Their shared
  concurrency group serializes the large runs.
* Once corrections are stable, freeze a final source/ref and regenerate the
  plan. Assemble all required families with the actual source/classes/toolchain/
  dependencies/reader bindings. Earlier green commits remain historical evidence;
  do not splice them into a same-source final cohort.
* Complete attested replay, actual frozen coverage, combined-resource and
  prior-failure review. The five gaps remain open: component-cohorts,
  combined-resources, frozen-coverage, cohort-admission and final-source-execution.
  Only their acceptance permits progress beyond Phase 3.

The present task prepares acceptance reconciliation and resource execution.
Remaining corrective work, registration, costly execution, final cohort
qualification and subsequent phase work are separate tasks.

