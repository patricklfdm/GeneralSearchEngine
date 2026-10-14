# CI refactor handoff and remaining acceptance

Implementation base: `d12d682e2a16eb2c9a96b326f2875e97768ddd7f` (PR #326).
The operator combined PR4 review, PR5 replay optimization and PR6 documentation/
integration checks in one branch. **Local implementation is ready; new-source
hosted PR/master acceptance is pending.** This is not a claim that the whole
refactor is closed or that V5.2 development has started.

## Current architecture and operating entry points

- [Generated inventory](CI_JOB_INVENTORY.md): actual workflow/registry agreement,
  36 suites, 38 static IDs, 46 full jobs, fixed matrices and dependency ownership.
  It is generated with `python3 -m scripts.ci_inventory`; `--check` and the existing
  Change scope test module reject stale documentation or invalid source contracts.
- [Operations](CI_CD.md): full/docs classification, stable Required result,
  build domains, six compatibility consumers and release separation.
- [Consumer contracts](CI_DEPENDENCY_CONTRACTS.md): action expansion, visible
  job/step names, exact producer IDs, accepted/producing attempts, source-bound
  cloud admission, release validation and retention.
- [Suite onboarding](CI_SUITE_ONBOARDING.md): file-level workflow/registry/gate,
  build and version boundaries, negative tests, failure evidence and rollback.
- [Progress](CI_REFACTOR_PROGRESS.md): per-stage source and validation history.

All existing suites still reach Required and require success in full; docs has
explicit skips. No suite is orphaned, no matrix or negative set was removed,
and no paid-cloud/release/admin setting changed. Continuous canonical histories
retain one lease/source/history and sequential handoffs; rich shards still need
the independent combined aggregate. Core is disabled and
[activation remains deferred](CI_CORE_POLICY_REVIEW.md).

## Source and acceptance ledger

| Stage | Source / run identity | Status and remaining boundary |
| --- | --- | --- |
| PR0 | Read-only audit; anchors 38457745089 and 38482900297 | Complete; original external audit retained. Historical SNAPSHOT vs final release semantics remain separate. |
| PR1 / #324 | Merge `62b104e914e690be860a8c7a770d4de39ef797ec`; PR 38499699430 attempts 1–2; master 38505983953 attempt 1 | Required/registry implementation accepted. PR initial failure retained. API PR head was recorded, but its tested merge SHA was not recovered in that metadata observation. |
| PR2/PR3 / #325 | Merge `563dfe290326945d9cf0cda2b556b609d3be85a7`; PR 38516949749 attempt 1; master 38522705456 attempts 1–2 | Full hosted paths accepted; master's original runtime failure retained, root cause unproven. Tested PR merge `045a8af4984e003ff0ab5891e034689c93c82c41` differs from API head. |
| Docs / #326 | Merge `d12d682e2a16eb2c9a96b326f2875e97768ddd7f`; PR 38532075143 and master 38532208752, both attempt 1 | Normal docs-only PR/master accepted; completes PR1–PR3 full/docs rollout. Does not qualify runtime for that docs-only master. |
| PR4 | Same base plus current review | Complete local scope review; no approved core activation. 30 merged-PR diff sample: 2 docs, 0 proposed core, 28 full. |
| PR5 | Same base plus current inspector/test changes | Same-byte full replay and focused tests passed; new-source full live PR/master qualification and hosted timing remain pending. |
| PR6 | Same combined branch | Current inventory/operations, future-suite procedure and static contracts prepared; final hosted reconciliation waits for the two new full paths below. |

The [baseline](CI_BASELINE.md) records the successful complete V5.1 release run
38488481320 and publication. That release source, tag and frozen artifacts remain
separate from this refactor. No release was rerun or Central artifacts redownloaded.

## Measured outcomes and limits

| Cohort | Actual samples and outcome | Time accounting |
| --- | --- | --- |
| PR0 historical audit | 30 runs / 40 attempts, including failures/cancellation/reruns; 35 full, 2 docs, 3 unknown attempts | 10,988.50 elapsed runner-minutes, including 408.23 rerun minutes. Not one comparable success distribution. |
| Final-coordinate anchor | Master 38482900297 / 1 | Required span 50:33; 433.63 runner-minutes. One successful final-source sample. |
| PR1 master | 38505983953 / 1 | Span 57:38; 436.23 runner-minutes. Different implementation from PR0; no causal speedup claim. |
| PR2/PR3 full | Two runs / three attempts; 94 fresh executions after clone deduplication | PR 54:15 / 438.28 minutes; master attempt 1 failed, 53:43 / 410.60 minutes; partial retry 16:04 / 16.03 minutes. Combined 864.92 minutes. |
| PR5 original canonical logs | Six successful jobs across PR/master producing attempt 1 | Independent replay 349.40–648.81 seconds; median 548.09. Six jobs are not six independent runs. |
| PR5 local replay | One sequential before/after pair over the same 2291 raw files | 361.929 → 143.271 seconds; identical complete results and budgets. No new workload execution; uncontrolled machine load/OS caches. |

For PR2/PR3, both initial critical paths were Change scope → verification build →
canonical repetition 1 → Required. Master attempt 2 reused 44 jobs and executed
only full-size runtime and Required. End-to-end accepted span was 71:29, including
the operator delay; retry execution cost is already included in the total above.

The failed full-size runtime **step** finished 7:19 after the first job started;
the failed job finished at 7:24. Required was available only at 53:43. This is
the earliest recorded failed-step completion, not the exact time a human saw
the error or the first causal fault. Earlier successful checks are useful for
their own contracts but do not grant full qualification. In successful attempts,
failure latency is absent, not zero. Original logs remain retained.

Ready-to-start gaps, dependency wait, execution and operator rerun delay are
different quantities. The API does not isolate pure runner queue delay. Observed
runner-minutes are not billing charges. There is no sufficiently comparable
post-optimization sample set for P50/P95 or an end-to-end savings claim; the local
60.41% replay reduction must not be applied to the whole workflow. Earlier
counterfactual canonical omission estimates are not implemented results.

## Remaining hosted acceptance after submission

1. Run normal full PR CI on the actual test merge. Verify Change scope selects
   full, Required sees every suite, and the three complete canonical repetitions,
   rich aggregate, release fixtures and evidence uploads succeed. Preserve a
   failure before deciding whether a rerun is appropriate.
2. After the operator merges, verify the exact-master full CI. Record the actual
   merge SHA; do not substitute the PR head, a docs-only receipt or old success.
   No bypass or automatic workflow dispatch is part of this handoff.
3. Read all pages and all attempts for both runs. Retain original job/step IDs,
   workflow/source/policy hashes, artifact IDs/digests and expiry, copied-job
   execution timestamps, and accepted versus producing attempts. Count reused
   executions once; keep failed/cancelled executions in cost accounting.
4. Measure canonical phase envelopes and original monotonic cell durations,
   Required span, critical dependency path, earliest failed step and total fresh
   execution. Compare only compatible sources/events/semantics. Full PR/master
   correctness can be accepted without inventing a statistically stable speedup.
5. Append those observations and any gaps to progress/handoff, then mark PR5/PR6
   acceptance complete. PR4 stays an explicit decision to defer core. New runtime
   or oracle edits in response to failures require qualification of that new source.

PR1–PR3's normal docs paths were already exercised by #326. This batch preserves
their conditions, but the local full/docs and stale-inventory checks still run
against the combined source. Neither archive replay nor mock Required results
can satisfy steps 1–2. No new paid-cloud experiment is needed for this CI task.

## Failure triage and rollback

Read the first failing step and retain its logs/authority/receipts before rerun.
Separate setup/download/API errors from compilation, oracle/history, source/hash
and lease failures. A successful retry records a second observation; it does not
erase the original failure or prove GitHub scheduling caused it. Missing or
expired artifacts require a new authorized qualification, not a guessed cache.
Failed exact-master full CI blocks cloud/release admission for that source.

The current policy already executes full CI for all build inputs and unknown
changes. There is no reduced-coverage mode to switch off. If the optimization is
suspect, revert the relevant combined commit(s), restoring uncached parsing and
matching tests/docs while retaining measurements; keep all suites and Required.
For an ordinary commit the operator uses `git revert <commit>`; for a merge use
`git revert -m 1 <merge>`. Recheck registry/inventory/Required/planner/bundle/cloud/
release contracts and obtain full PR/master CI for the revert. Do not reset master,
disable workflows, alter branch protection or move published tags.

## Retained local evidence

Final local interface group: **222 tests passed in 43.409 seconds** using Python
3.11, including generated-inventory, Required/planner/composite, bundle,
partition, cloud source/attempt and release contracts. Static inventory and the
independent cloud catalog agree on 46 full jobs; all 36 suites have a Required
owner. Existing test methods remain and nine are added across PR5/PR6. Both
documentation contracts, generated-inventory freshness, 634 changed-document
local links and whitespace passed. These are local results, not hosted execution.

The original PR0 directory is unchanged. Earlier full/docs API evidence remains
at the paths in [hosted acceptance](CI_SHADOW_ACCEPTANCE.md). The combined branch
retains PR4 review in `target/ci-core-policy-review/`, PR5 raw logs/profiles/archive/
comparison in `target/ci-canonical-hotspot/`, and PR6 inventory/contracts/coverage
receipts in `target/ci-refactor-closeout/`. Target files are local review aids, not
portable CI prerequisites. No Git add/commit/push, PR creation or hosted execution
is performed by these tools.
