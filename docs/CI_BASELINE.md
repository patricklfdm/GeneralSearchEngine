# CI refactor baseline

Recorded on 2026-10-14 UTC. This is the portable summary of the read-only PR0
audit, followed by PR1's implementation baseline. Historical measurements are
not results from the refactored workflow.

## Source and release identity

| Role | Source / observation |
| --- | --- |
| PR0 local checkout | `8c4f54954768a9d42815ae7b35a0ef6bf537c282` |
| PR1 base, rechecked against remote master | `98f2996f896f97a85bf18b0be4b73bb44ad6d2d5` (PR #323) |
| PR #322 final release source | `516fe1efb54ef0787f38209108f322f258f71696` |
| Historical SNAPSHOT measurement | `5c88a2b908347fa3e411e2018876657a21fa0912` |

[Release run 38488481320](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38488481320),
attempt 1, completed successfully as a whole, including all three jobs.
[v5.1.0](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v5.1.0)
was published at `2026-10-14T00:33:12Z`, neither draft nor prerelease.
The v2 input package's in-progress release snapshot is superseded. The change
from PR #322 to PR1's base consists of twelve Markdown publication-closure files.
No runtime, workflow, POM, candidate hash or toolchain change intervened.

Master's docs-only run 38491794493 is distinct from full qualification of the
release source. A docs success cannot authorize exact-master cloud execution.
The audit used GitHub records and the merged publication record; it did not
download or revalidate Central's twelve artifacts.

## Measured sample and cost model

PR0 collected the latest 30 CI runs in a bounded window from
`2026-10-08T23:47:51Z` through `2026-10-14T00:43:42Z`, including both anchors below.
All 40 attempts, job/step records and artifact metadata were paginated, retaining
failures, cancellation and partial reruns: 24 successful, 15 failed and one
cancelled attempt; 35 full, two docs and three unknown (failed classification).
Events comprised 22 PR, 13 push and five manual attempts.

There were 1794 API job records. GitHub cloned 435 already-executed records into
later attempt views, sometimes assigning new IDs and `run_attempt` values while
preserving the old execution timestamps. Deduplication within a run/source/name
also checked timestamps, runner and steps. This left 1177 executed jobs and 182
skipped placeholders. The accepted attempt and original producing attempt remain
separate identities.

Total observed execution was **10,988.50 runner-minutes**, including **408.23**
additional minutes from partial reruns. The retry figure is already included;
it must not be added twice. These are elapsed job minutes, not billed cost.
Billing rounding, multipliers, free allowance and account invoices were not
collected. Job duration includes setup, upload and post steps.

| Full run / attempt | Required span | Runner-minutes | Shared build | Longest canonical |
| --- | ---: | ---: | ---: | ---: |
| [38482900297 / 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38482900297), final master | 50:33 | 433.63 | 5:21 | repetition 2, 44:55 |
| [38457745089 / 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38457745089), historical SNAPSHOT | 52:57 | 435.65 | 5:24 | repetition 1, 47:13 |

The final critical path was Change scope 7s → readiness gap 3s → build 321s →
gap 3s → canonical 2, 2695s → gap 2s → Required 2s = 3033s. Dependency waiting
and job execution were accounted separately. Ready-to-start gaps contain
scheduling/provisioning effects; the API does not provide a precise runner-queue
breakdown. This sample does not establish queue delays as a failure root cause.

Final full master has only one complete successful sample. PR success after a
partial rerun is not a second fresh full execution. Changes in implementation,
workflow and final/SNAPSHOT coordinates prevent treating all samples as one
controlled cohort; no P95 or SLA is claimed.

Removing the three complete canonical repetitions from the final timestamps
would leave an estimated 21:32 span and 303.18 runner-minutes. This is a
counterfactual, not measured core CI, and PR1 does not make that change.

## Evidence and limits

Full reports, API JSON, normalized data, source inventories, scripts and their
lightweight tests remain outside the repository, preserved at the original
operator location:

```text
/home/klfdm/perception/GSE-CI-Refactor-PR0/audit-20261014T011110Z/
```

No unresolved API pagination/attempt gaps remained. Canonical per-stage raw
evidence, every historical failure's logs, detailed billing and a new hosted
PR1 run were not collected. The raw audit directory is not a CI input or a
portable checkout prerequisite. See [progress](CI_REFACTOR_PROGRESS.md) for
implementation validation, and [contracts](CI_DEPENDENCY_CONTRACTS.md) for the
current topology. [PR #325's later observations](CI_SHADOW_ACCEPTANCE.md) retain
their own source/event/attempt grouping and do not replace this historical sample.
