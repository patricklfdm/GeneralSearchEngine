# CI refactor final hosted acceptance

Observed on 2026-10-14 UTC after [PR #327](https://github.com/patricklfdm/GeneralSearchEngine/pull/327)
merged as `c62e4719f8fd346e0f8997f0800e8fbd69414cbf`.
**PR5's new-source full qualification passed; PR6's reconciliation is complete.**
The revised CI maintenance task is closed. PR4 remains a deliberate deferral of
core activation: actual execution is still docs/full. V5.2 implementation is
separate and has not started as part of this task.

## Complete executions and original failure

| Run / producing attempt | Event | Job outcome | First job start to last completion | Elapsed runner-minutes |
| --- | --- | --- | ---: | ---: |
| [38540436241 / 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38540436241/attempts/1) | PR | 44 created: 25 success, 19 cancelled; workflow failed | 11:49; Required not created | 260.52 |
| [38540436241 / 2](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38540436241/attempts/2) | PR rerun | All 46 fresh jobs successful, including Required | 48:14 | 399.95 |
| [38548426916 / 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38548426916/attempts/1) | master push | All 46 fresh jobs successful, including Required | 48:37 | 404.77 |

The first PR attempt's nineteen cancellations share the 09:22:35Z completion
timestamp. Each cancelled check's annotation reports
`GitHub Actions has encountered an internal error when running your job.`
Required and the rich aggregate were never created. This is direct platform-error
evidence for that attempt, not a general explanation for earlier runtime flakes.
Its partial work remains included; the successful rerun does not erase it.

All attempt/job/artifact pages were collected, with no unresolved pagination or
identity gaps. There are **two runs, three attempts and 136 fresh job executions**;
no successful execution was cloned into the rerun. The two successful attempts
sum to **804.72 runner-minutes**; including the aborted attempt gives **1065.23**.
These sums use unrounded job durations. They measure execution, not billing.
Operator delay between attempts is not runner execution. Successful attempts
have no observed failure latency; it must not be recorded as zero.

## Source and shadow-policy identities

The PR API head is `c0b5a7ff890f026bb1451b6fc471402e2a00856b`. The actual PR test
merge is **`8712825bdcaf7af39d889ae8a486c9aecb9caa8d`**, recovered independently
from the shadow report and all three canonical final log receipts.
Master tested **`c62e4719f8fd346e0f8997f0800e8fbd69414cbf`**.
Both commits have tree `294d69f5c9aa11fb6512034934b9f480e2a037ba` and parents
`d12d682e2a16eb2c9a96b326f2875e97768ddd7f` and
`c0b5a7ff890f026bb1451b6fc471402e2a00856b`.

Both reports select actual `full`, recommend `full` and set `coreEligible=false`.
Their policy source is `d12d682e2a16eb2c9a96b326f2875e97768ddd7f`.

| Input | SHA256 |
| --- | --- |
| Tested workflow bytes, both runs | `096d555b001dd37b5209cb79ae8ad8ca34a41a2515662c65f793635d036a8bbb` |
| Shadow planner | `643e78b7173ddcf093421660e6623d944154209f5e6b09ae216ee01b2b6df072` |
| Baseline and tested policy | `24d6831276f0a0d44a1ac591efaea6ec02f17f067aaf978ad922d23a4b326957` |
| Complete changed-path list, both reports | `c06d141d92fe66cd44fdfd5648cbad0b74685e7279fb7df081c489a811d0e2d9` |

| Downloaded shadow artifact | ID | ZIP SHA256, matched to GitHub digest |
| --- | ---: | --- |
| `ci-shadow-plan-38540436241-2` | 11882568821 | `d6347e489fea62941eed24c17a9d9e5f3e509428ec683d73b4c15cb19513797e` |
| `ci-shadow-plan-38548426916-1` | 11885875854 | `155673750935c0bca0d4916793c71e7f05a90159fd0060c6e566329d2eb81c7e` |

The 24 changed paths were 19 Markdown and five Python files. No Java, POM,
workflow, frozen catalog, measurement parameter or release hash changed in #327.
The successful views match all 46 expanded workflow jobs, including rich
aggregation, release fixtures and the three complete canonical repetitions.
Earlier normal docs-only PR/master acceptance remains recorded for
[PR #326](CI_SHADOW_ACCEPTANCE.md); these new runs both exercise full CI.

## Canonical results and measured time

Each final receipt reports 15 qualified cells, 1080 rich calls, physical/history
qualification, `leaseReleased=true`, no cleanup errors and `paidCloud=false`.
All three repetitions remain complete; no continuous lease/source/history was
split. Every log includes seventeen completed replay pairs and collection events.

| Run / attempt | Repetition | Job ID | Job seconds | Qualification-step seconds | Replay log seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| PR / 2 | 1 | 115782826080 | 2468 | 2377 | 242.28 |
| PR / 2 | 2 | 115782826119 | 2512 | 2419 | 240.73 |
| PR / 2 | 3 | 115782825936 | 2099 | 2028 | 138.18 |
| master / 1 | 1 | 115802478675 | 2311 | 2221 | 177.65 |
| master / 1 | 2 | 115802478522 | 2456 | 2364 | 230.47 |
| master / 1 | 3 | 115802478611 | 2549 | 2449 | 271.86 |

The last dependency path is Change scope → V5.1 verification build → canonical
→ Required, ending on repetition 2 for PR and repetition 3 for master. Canonical
dependency wait from attempt start is 376 seconds for PR and 357 for master;
ready-to-start gaps are respectively 2 and 3 seconds. Those gaps include scheduling
overhead and do not isolate pure runner queue time.

| Qualification phase, six jobs | Minimum / median / maximum seconds | Measurement |
| --- | ---: | --- |
| Preparation | 175.27 / 240.84 / 255.57 | Log envelope |
| Three rich cells | 1165.35 / 1195.91 / 1202.82 | Original monotonic cell timers, including 1080 frozen measurement seconds |
| Twelve fault cells | 433.25 / 545.63 / 562.90 | Original monotonic cell timers |
| Collection and service stop | 110.31 / 145.39 / 158.69 | Log envelope |
| Independent replay | 138.18 / 235.60 / 271.86 | Log envelope, including validators and negatives |
| Retention, cleanup and exit tail | 5.63 / 6.37 / 7.73 | Residual log envelope |

[Earlier six-job replay observations](CI_CANONICAL_REPLAY_PERFORMANCE.md) were
349.40–648.81 seconds, median 548.09. The new observations show shorter replay;
the one same-byte local pair separately established exact result equivalence.
Six jobs from two successful runs are correlated samples, with uncontrolled
host load and log ingestion delays. They do not establish a stable population
P50/P95, a causal whole-workflow saving or billed-cost reduction. In particular,
the local 60.41% replay reduction must not be applied to the whole CI workflow.

## Evidence location, checks and closure boundary

Raw GET responses, all attempts/jobs/steps and artifact IDs/digests/expiry,
six logs, two shadow ZIPs, source/tree identities and normalized timings are at:

```text
target/ci-refactor-closeout/hosted-pr327/authorized-read/
```

The first PR attempt's check annotations and diagnosis remain separately at
`target/ci-refactor-closeout/run-38540436241/authorized-read/`.
The initial sandbox network failure is also retained. Analysis uses Python
3.11.15; an initial Python 3.10 timestamp parsing failure is recorded in the local
acceptance note. No original log or evidence bytes were changed.

This observation downloaded small shadow artifacts and logs, not the large
canonical archives; it did not rerun their validators locally. Hosted complete
execution and final receipts establish the recorded result. Target data are local
review aids; this document carries portable identities and limits without making
CI depend on those paths. Previous local equivalence/negative tests remain in
[PR5's record](CI_CANONICAL_REPLAY_PERFORMANCE.md).

This documentation follow-up records acceptance of #327's source, not runtime
qualification of a later docs-only SHA. It changes no gate or execution policy.
Future runtime/oracle changes still require full qualification of their own
source. [Operations and rollback](CI_REFACTOR_HANDOFF.md) remain applicable.
The next mainline task is
[V5.2 Phase 0 replica-read contract design](v5x/NEXT_DEVELOPMENT_HANDOFF.md#next-batch-v52-phase-0).
