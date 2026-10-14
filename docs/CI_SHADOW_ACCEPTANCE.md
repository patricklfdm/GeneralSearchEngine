# CI PR2/PR3 hosted acceptance and docs-only follow-up

Observation: 2026-10-14 UTC (2026-10-14 America/Los_Angeles collection date).
[PR #325](https://github.com/patricklfdm/GeneralSearchEngine/pull/325) merged the
step reuse and shadow planner as `563dfe290326945d9cf0cda2b556b609d3be85a7`.
Both full CI accepted views are successful. The **docs-only follow-up is pending**;
this document prepares its acceptance criteria, not an already executed result.
Core remains disabled, with an empty allowlist.

## Runs, attempts and failures

| Run | Event / attempt | Actual observation |
| --- | --- | --- |
| [38516949749](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38516949749) | PR #325 / 1 | All 46 jobs succeeded in their first execution. |
| [38522705456](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38522705456/attempts/1) | master push / 1 | 44 succeeded; `V5.1 full-size runtime` and Required failed. |
| [38522705456](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38522705456/attempts/2) | master push / 2 | Accepted view has 46 successes: two new executions and 44 reused executions. |

The [first failed runtime job](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38522705456/job/115717599845)
completed both composite restore/provenance steps successfully, then failed
inside `Verify V5.1 public automatic 512-slot runtime boundary`.
`full_size_runtime.py`'s `fill(480)` called an update that returned
`INDETERMINATE` / `QUORUM_UNAVAILABLE` (`node-1-g1-1033`, key 31, revision 2).
The runtime evidence upload still succeeded. Required rejected that failure.

Attempt 2 reran the full-size runtime and Required, and both succeeded. This
observation locates the failure after restoration; it does **not** establish
whether scheduling, storage, networking or runtime timing caused it. No runtime
fix or root-cause conclusion is claimed in this documentation-only task. The
original failed attempt and its log are retained, not replaced by the final
green result.

The eleven migrated consumer jobs each show successful restore and provenance
steps in all three API attempt views. Their qualification steps remain visible.
The observed failure also confirms the later runtime-evidence upload runs after
a qualification failure. A hosted failure *inside* the composite was not injected;
that path remains covered by the previously recorded local contract/negative tests.

## Shadow artifacts and actual source identity

| Field | PR execution | master execution |
| --- | --- | --- |
| API `head_sha` | `8a9f8a736e4ab3783499c2ab952bef2bbc989743` | `563dfe290326945d9cf0cda2b556b609d3be85a7` |
| Reported actual tested SHA | `045a8af4984e003ff0ab5891e034689c93c82c41` | `563dfe290326945d9cf0cda2b556b609d3be85a7` |
| Policy baseline | `62b104e914e690be860a8c7a770d4de39ef797ec` | Same |
| Artifact ID | `11872460989` | `11875170055` |
| Artifact name | `ci-shadow-plan-38516949749-1` | `ci-shadow-plan-38522705456-1` |
| Actual / recommended profile | full / full | full / full |
| Reason | `POLICY_UNAVAILABLE` | `POLICY_UNAVAILABLE` |
| Producing attempt | 1 | 1, reused during accepted attempt 2 |

The PR report distinguishes its test merge commit from its branch head. Both
reports bind the workflow SHA to their tested SHA. Their complete changed-path
sets contain the same 19 paths and match the local three-dot PR / two-dot push
comparison. The GitHub Git commit object independently confirms the PR merge's
base/head parents, and its tree matches merged master `563dfe2...` exactly.
Workflow bytes have SHA-256
`096d555b001dd37b5209cb79ae8ad8ca34a41a2515662c65f793635d036a8bbb`;
the recorded planner hash also matches the merged source bytes.

The baseline predates the policy, so the observed full recommendation is the
expected first-rollout fallback. Baseline/tested policy hashes are null because
the planner stops at that missing-baseline condition. This has **not yet**
exercised a hosted recommendation with a valid baseline policy. Current master
now contains that policy, enabling the next docs-only PR to test it.

The downloaded ZIP digests match GitHub's artifact metadata:

- PR: `8dc13848672c227dc480bbdba572e4bc5576087469dd79e4a0bf6a4d060db4a9`.
- master: `cb530df5ad9b549f7087ac2136b07bf331afa11f1fd1ce89e8838c72bbf4ac23`.

Both artifacts contain `plan.json` and `summary.md`, with recorded expiry on
2026-10-28 UTC (14-day retention). There is no attempt-2 shadow artifact for
master because Change scope did not execute again. Its reused API job record
must not be mistaken for a second observation or a newly produced artifact.
This does not alter cloud admission's separate exact-attempt checks.

## Timing and execution accounting

| Execution | First fresh job to Required completion | Fresh job executions | Elapsed runner-minutes |
| --- | ---: | ---: | ---: |
| PR / attempt 1 | 54:15 | 46 | 438.28 |
| master / attempt 1, failed | 53:43 | 46 | 410.60 |
| master / attempt 2, partial rerun | 16:04 | 2 | 16.03 |

Master's total is **426.63 runner-minutes**, including its failed first attempt
and two rerun jobs. First job to final accepted Required spans **71:29**, including
the interval before the operator's rerun. Across these two runs, 138 API job
records represent **94 actual executions** and **864.92 runner-minutes**.
The other 44 records are cloned executions with new job IDs/attempt numbers but
identical run/source/name, runner, step records and execution timestamps.

Both first attempts' last dependency path remains Change scope → V5.1
verification build → canonical repetition 1 → Required. For the PR this is
34s + 3s gap + 309s + 2s gap + 2900s + 2s gap + 5s = 3255s.
For master attempt 1 it is 35s + 2s + 297s + 3s + 2879s + 2s + 5s = 3223s.
The gaps are dependency-ready to job-start observations, not measured pure
runner queue time. Attempt 2's fresh critical path is the rerun runtime → Required.

These are two source/event observations, with one fresh all-successful full run,
one failed full run and a partial rerun. They do not establish a speedup, P95 or
billed cost. A shorter failed run is not a performance improvement. Existing
[PR0 timing samples](CI_BASELINE.md) remain separate; none is overwritten.

## Pending docs-only acceptance

The current `docs/ci-shadow-acceptance` change edits only Markdown under `docs/`.
After the operator creates its normal PR, check the following; do not use a
manual full dispatch or a `[skip ci]` commit as the docs-only acceptance sample.

1. **PR Change scope:** `run_full_ci=false`; both documentation contract checks
   execute successfully. Summary and artifact show actual `docs`, recommended
   `docs`, reason `DOCS_ONLY`, and `coreEligible=false`.
2. **Trusted identity:** the policy source is the event's master base (initially
   `563dfe290326945d9cf0cda2b556b609d3be85a7`, or the actual newer base if master
   advances). Baseline and tested policy hashes match. The complete path set is
   documentation-only; actual test merge SHA remains distinct from PR head.
3. **Required:** all 36 suite dependency results are `skipped`; Change scope and
   Required succeed. Check matrix skip placeholders/aggregate results rather
   than expecting the 46 expanded full-execution job names. No Maven, packaged
   workload or cloud experiment should execute on this docs path.
4. **Retention:** the correctly named run/producing-attempt artifact contains
   the full report and summary. Reused attempts must retain their original
   producing identity; an absent report is a gap, not acceptance.
5. **After merge:** perform the same read-only verification on the exact master
   push. Its report binds `testedSha` to the merge/push SHA and uses the complete
   `before..after` comparison. Preserve every attempt if a rerun occurs.

Record those run IDs, producing/accepted attempts and hashes in the progress
record once observed. Until then, docs-only hosted acceptance remains pending.
PR4 has not started: any omission of canonical repetitions requires a separately
reviewed path policy and explicit approval. There is no approved core path yet.

## Retained data and checks

Raw paginated API responses, all three attempt/job/step views, artifact metadata,
both ZIPs and decoded reports, the original failure log, and normalized timing
and clone mappings are retained at:

```text
target/ci-shadow-acceptance/observations-20261014T075021Z/authorized-read/
```

The existing PR0 GET-only collector and timestamp/deduplication analyzer were
reused by byte-for-byte copies in that directory's `tools/`. All endpoint totals
and run identities were checked; no attempt/pagination gaps remain. The original
restricted-network connection failure is retained in the parent directory;
the authorized read-only collection subsequently completed.

Local checks for this docs change cover both documentation contracts, the suite
registry, changed-path classification, Required's expected docs result, local
links and whitespace. Local expected outcomes are not hosted results. No source,
workflow, POM, policy, frozen input or runtime evidence was changed; no new CI,
cloud experiment or release was started by the audit.
