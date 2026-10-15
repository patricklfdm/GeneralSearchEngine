# PR4 review: defer core activation

> Historical review of PR #326/#327. Its statement that core was disabled describes
> that baseline. The later [Tiered CI review](CI_TIERED_DESIGN.md) records the
> separately delegated local activation of the same exact candidate as **integration**,
> preserving this original review and its historical observations.

Status: review completed against `d12d682e2a16eb2c9a96b326f2875e97768ddd7f`
(PR #326), 2026-10-14 UTC. **No core policy is enabled or approved by this
document.** Current execution remains full/docs. Recommendation: keep full
coverage and proceed to PR5's single-hotspot investigation before investing in
an active core policy. The implementation proposal below remains available for
separate coverage approval.

## Entry conditions and actual observations

- V5.1 publication was reread through GitHub GET requests: release run
  [38488481320](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38488481320),
  attempt 1, completed successfully with all three jobs successful, on source
  `516fe1efb54ef0787f38209108f322f258f71696`. The published `v5.1.0` release
  remains neither draft nor prerelease. This is a whole-workflow check; Central
  artifacts were not downloaded again.
- PR1–PR3 full and documentation-only hosted paths are recorded in
  [acceptance](CI_SHADOW_ACCEPTANCE.md). The failed first master attempt remains
  recorded separately from its successful partial rerun.
- Actual [shadow policy](../scripts/ci_shadow_policy.json) still has
  `mode=shadow` and `corePaths=[]`; its parser rejects nonempty lists. The
  [Required validator](../scripts/ci_required.py) only accepts the existing
  full/docs output schema. Editing the list alone cannot enable core.
- Approval for a specific reduction in pre-merge coverage is **not yet given**.
  Approval to review CI or merge these documents is not that coverage decision.

## Candidate scope and dependency audit

The sole candidate identified in this review is an existing regular file's
content change at:

```text
examples/travel-search/src/main/java/example/travel/TravelSearchDemo.java
```

This is an exact path, not an `examples/**`, Java-extension or test-directory
allowlist. Its deletion, creation, rename, mode/type change, or any accompanying
non-documentation path outside this candidate would require full.

| Actual source inspected | Dependency and coverage consequence |
| --- | --- |
| [TravelSearchDemo](../examples/travel-search/src/main/java/example/travel/TravelSearchDemo.java), [example POM](../examples/travel-search/pom.xml) | Standalone public core API consumer. No replication/processor dependency; deploy is skipped. POM changes remain full. |
| [Reactor POM](../reactor/pom.xml) | The example **is a reactor module**. Core would still compile it through retained reactor/build lanes; it is not outside the build. |
| [Example runner](../scripts/run-travel-example.sh), `Soak and examples` in [CI](../.github/workflows/ci.yml) | Compiles the example with its dependencies and executes its main class against core classes. This entire lane remains selected, including soak checks. |
| [Shared build layout](../scripts/ci_v51_bundle.py), [guest builder](../scripts/v51/cloud_bundle.py), [adapter compilation](../scripts/v51/performance_harness.py) | Candidate runtime uses core/replication JARs and explicit qualification adapters. Example classes are not shipped to the canonical guest. Checkout hashes still include the example source: any future core run must use its own exact-source build, never old bytes or a previous green run. |
| [Cloud CI reader](../scripts/v51/cloud_ci.py) and [artifact reader](../scripts/v51/cloud_runner_artifacts.py) | Full job/matrix names, workflow bytes, exact master/attempt and specific build/owned steps remain required. No example lane artifact is an input to canonical execution. |
| [Release fixtures](../scripts/v51/test_phase7_release_fixtures.py) | Keep nine JARs, three POMs, six consumers, pinned toolchain, exact-source validation and 90-day release evidence. Example compilation does not authorize changing release qualification. |

The reviewed repository references to the example are its own module, reactor
membership, runner and version-alignment/release fixtures. This is a source
dependency argument for a possible omission of complete canonical repetitions,
not proof of universal semantic independence or a new measured qualification.
If module dependencies, packaging or qualification inputs change, that PR is
full and must also re-review the candidate rule.

Excluded from the candidate: runtime/core/replication/processor source;
compatibility consumers; test fixtures, oracles and evidence validators; scripts
(including artifact cleanup/export); POMs, Maven/toolchains, CI/local actions,
policy and release contracts; cloud IAM/lease/cleanup; JSON plans and frozen
hashes. Unknown paths remain full. Existing permitted Markdown is already docs;
broadening it contributes no new core savings.

## Traffic sample and timing limits

An offline query read the last **30 first-parent merge commits** ending at the
review source. For each, it analyzed the complete original PR `base...head`
diff with rename detection disabled, applying today's proposed rule. Dates run
from 2026-10-07 through 2026-10-14 UTC; exact identities and paths are retained
in `target/ci-core-policy-review/review.json`.

Result: **2 docs, 0 core, 28 full**. This is retrospective classification, not
30 new hosted observations. It excludes direct/squash commits and unmerged PRs;
it is not an estimate of future traffic or all failure rates. It is distinct
from PR0's 30-run/40-attempt sample. Core is also currently 0% by construction.

The already-retained PR #325 observations explain why canonical is attractive
but do not show benefit for this candidate scope:

| Run / attempt | Observed job span | Observed total runner-minutes | Three canonical jobs' runner-minutes | Last noncanonical completion relative to first job start |
| --- | ---: | ---: | ---: | ---: |
| PR 38516949749 / 1, success | 54:15 | 438.28 | 138.37 | 22:39 |
| master 38522705456 / 1, failure | 53:43 | 410.60 | 129.37 | 19:57 |
| Same master / 2, partial rerun | 16:04 fresh span | 16.03 additional | 0 new | Not a fresh full/core comparison |

Both first attempts' final dependency path was Change scope → V5.1 verification
build → canonical repetition 1 → Required. Canonical jobs took 2–3 seconds from
dependency-ready to start in these observations; do not attribute their execution
time to runner waiting. Repetition execution includes package preparation,
qualification and retention. Job minutes are elapsed execution, **not billing**.

Subtracting the three jobs is only a fixed-schedule counterfactual for a
*hypothetical eligible PR*. Neither observed change qualifies; master would
always retain canonical. The 22:39/19:57 values exclude rescheduling and a new
Required execution, and the failed master would still fail without canonical.
Do not promise those as core completion times, daily savings or PR0 improvement.
In this merged-PR scope sample, the proposed allowlist yields zero omissions.

## Ready-to-apply design, conditional on separate approval

Only the three children of `v51-owned-canonical` may be omitted by core. Keep
all five component tapes, three rich shards and rich aggregate, owned experiment
and failure drill, and every other current suite. Keep IDs, names, fixed matrix
members, qualification steps, build/artifact boundaries and Required dependencies.
Component successes do not replace a continuous canonical history.

1. Introduce a versioned execution plan with full source/event identity,
   complete comparison/path digest, trusted policy source/hash, selected suite
   IDs, and exact expected results. Read policy as data from the PR base; require
   byte equality with tested policy. Never execute baseline files as code.
2. Retain the conservative docs rule. Core applies only to a verified PR test
   merge, with a nonempty complete diff whose non-doc changes are exactly the
   approved existing-file modification. Verify both regular-file modes, change
   status, merge parents, workflow source and planner identity. A last-commit
   diff, renames, deleted/new files, missing history or unknown policy cannot
   downgrade coverage. Policy/CI changes classify full themselves.
3. Non-doc master pushes and all manual/unsupported events stay full. Final
   candidate, release and cloud acceptance still demand exact-master full;
   an old full result, a PR core result or docs result cannot qualify them.
4. Preserve legacy `run_full_ci`: false for docs; true for core **and** full,
   meaning all ordinary lanes execute. Add explicit `profile`, versioned plan
   and `run_canonical` outputs. Only the complete canonical job gains the extra
   condition. Required must validate outputs against the plan rather than infer
   full qualification from that legacy boolean. Document this naming limitation.
5. For docs expect all 36 suites skipped; for core expect only the canonical
   suite skipped and all other suites successful; for full expect all suites
   successful. Missing is never skipped. Selected failure, cancellation or skip
   fails Required; an unselected success also contradicts the declared plan.
   Treat an unexpanded matrix skip as the single suite result, not three missing
   successful children. Full matrices retain their independent exact inventory.
6. Update shadow reporting to show the actual explicit profile consistently.
   A missing/unreadable trusted policy produces a valid conservative full plan;
   failure to produce/validate the plan itself fails Change scope/Required.

### Concrete file-level implementation and verification

| Files | Planned change / acceptance |
| --- | --- |
| `scripts/ci_shadow_policy.json`, `scripts/ci_shadow_plan.py`, new `scripts/ci_plan.py` | Migrate to one reviewed versioned policy, add `forceFull`, share checked identity/diff parsing, produce actual plan separately from diagnostic observation. First rollout from an older/missing policy stays full. No generic expressions or arbitrary path globs. |
| `.github/workflows/ci.yml` | Wire closed plan outputs/environment data, add only canonical selection condition. Keep explicit suites/steps/retention and named external interfaces. Preserve the separate observer report. |
| `scripts/ci_suite_registry.json`, `scripts/ci_suites.py`, `scripts/ci_required.py` | Version plan/result contracts, validate core result table and the precise two condition forms; retain the complete `needs` set and fail-closed schema checks. |
| `scripts/test_ci_shadow_plan.py`, new `scripts/test_ci_plan.py`, `scripts/test_ci_changes.py`, `scripts/test_ci_suites.py`, `scripts/test_ci_required.py` | Test complete-history, fork/divergent-base, source/mode/rename/deletion/new-file/invalid-policy cases; each selected suite's failure/cancel/skip; extra/missing outputs, malformed/stale plan; matrix skip and rollout/rollback cases. Keep existing docs/full parity. |
| `scripts/v51/test_cloud_preflight.py`, `scripts/v51/test_cloud_runner_artifacts.py`, existing release fixtures | Explicitly reject a core/doc job view and stale source/attempt; full still satisfies the unchanged cloud parser. Verify producer attempt mapping and all PR #322 contracts. Production cloud acceptance should not need a semantic change. |
| This review, ADR, progress, shadow and dependency documentation | Record the exact approved scope, version, operator decision and observed results. Remove “review only” only after approval and implementation. |

Before approval, none of these executable files is changed. Before enabling,
run local contract negatives and an independent effective-workflow diff. After
enabling, operator-driven hosted acceptance must include a genuinely eligible
core PR, a high-risk full PR, docs PR and exact-master full push; preserve failed
attempts and producing identities. No synthetic docs success or manual dispatch
can replace a PR's required checks. Performance/coverage claims remain pending
until those runs are measured.

### Rollback and failed-master handling

Use one version-controlled policy switch, `forceFull=true`, to restore canonical
for every non-doc PR. Either baseline/tested force-full value or a policy mismatch
must force full immediately; changed policy cannot authorize its own downgrade.
Docs remain docs. Test the old-base rollout and force-full rollback before launch.
For structural failure revert the implementation and matching validators together.
Never disable Required, use bypass, alter tags or select an older green run.

A failed master full attempt blocks cloud/release admission on that source.
Retain its evidence, diagnose the failed stage, and record any authorized rerun
separately; core PR success is no exception to that rule.

## Recommended next batch and retained evidence

Proceed to **PR5 analysis of complete canonical qualification time** with full
coverage retained. First obtain phase-level durations for preparation,
measurement, faults, collection, replay, negatives, cleanup and packing. The
current job/step API cannot apportion time inside the long qualification step.
Do not relabel all non-measurement time as waste. Prefer inspection/replay of
retained evidence before any new workload. Select one demonstrated redundant
parse/hash operation only if positive/negative verdicts, budgets, source binding,
portable evidence and original bytes remain equivalent. Existing shared builds,
rich sharding and joint replay reuse are already implemented.

Review data and the offline analysis script are at
`target/ci-core-policy-review/`; prior full observations remain at the location
in [acceptance](CI_SHADOW_ACCEPTANCE.md). This review changes documentation only.
No new workflow, rerun, Maven workload, paid cloud or release is executed.

The operator subsequently combined this review, the
[PR5 replay optimization](CI_CANONICAL_REPLAY_PERFORMANCE.md) and PR6 handoff in
PR #327. That implementation ran normal full CI;
[both PR and exact-master qualification passed](CI_REFACTOR_ACCEPTANCE.md).
The review's recommended investigation is complete. The combined implementation
did not activate core; a future core proposal still needs the separate approval
and qualification specified above.
