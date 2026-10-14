# CI refactor progress

## PR0 — complete

Read-only audit completed on 2026-10-14 UTC. The original input package and
working tree were preserved. Portable summaries: [baseline](CI_BASELINE.md),
[dependency/consumer contracts](CI_DEPENDENCY_CONTRACTS.md),
[decision and phase plan](CI_REFACTOR_ADR.md). The baseline records the external
raw-evidence directory and measurement limits.

## PR1 — merged; full hosted acceptance recorded

- Added the 36-suite JSON registry, closed workflow checks and structured Required
  result validator. No core profile or lane-selection change.
- Preserved 38 static IDs / 46 full jobs, all 37 Required dependencies, all fixed
  matrices and all verification/artifact operations in the 36 lane bodies.
- Added negative and old-shell equivalence tests. Migrated the existing preflight
  fixture's old per-result expression assertion to the complete `needs` binding
  and explicit required dependencies; its cloud lane checks remain intact.
- Preserved release workflow, runtime, POMs, frozen hashes/toolchain and cloud
  admission implementations. Neither release nor paid cloud was executed.

Local results: **191 tests passed** under Python 3.11, including existing cloud
preflight, build/package provenance and release fixtures. After tightening
literal matrix-value parsing, all **27 registry/Required tests passed** again.
Independent YAML/raw-text comparison confirmed all 36 lane bodies byte-identical
to the base, 169 shell blocks valid, 24 download and 99 upload definitions
unchanged, and the original working tree and release tag preserved. The
registry CLI, changed documentation links and whitespace checks passed.

Local test commands (use Python 3.11 or later, as existing V5.1 tests require):

```bash
python3 -m scripts.ci_suites
python3 -m unittest \
  scripts.test_ci_suites scripts.test_ci_required scripts.test_ci_changes \
  scripts.test_maven_infra_retry scripts.test_ci_v51_bundle scripts.test_ci_v51_python \
  scripts.v51.test_cloud_preflight scripts.v51.test_cloud_runner_artifacts \
  scripts.v51.test_cloud_runner_admission scripts.v51.test_phase7_release_fixtures \
  scripts.v51.test_candidate_artifacts scripts.v51.test_artifact_version \
  scripts.v44.test_phase7_release_fixtures
```

PR1's local logs and comparison receipts are retained under
`target/ci-suite-registry/` in its isolated implementation checkout. These are
review aids, not substitutes for qualification evidence. The first diagnostic
run used Python 3.10 and exposed existing `contextlib.chdir` imports requiring
3.11 plus the old Required assertion; that failed log is retained.

[PR #324](https://github.com/patricklfdm/GeneralSearchEngine/pull/324) merged as
`62b104e914e690be860a8c7a770d4de39ef797ec`.

| Execution | API head SHA / attempt | Observed result |
| --- | --- | --- |
| [PR CI 38499699430](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38499699430) | `ef0d2c1cf70069046d9caa64bab8fc3ec4dc4099`, attempt 1 | Reactor tests and Required failed; other 44 succeeded. |
| Same PR CI | Same source, attempt 2 | Accepted view contains all 46 successful jobs; this is a partial rerun, not a fresh full execution. |
| [master CI 38505983953](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38505983953) | `62b104e914e690be860a8c7a770d4de39ef797ec`, attempt 1 | All 46 jobs, including Required, succeeded. |

The first master run spanned **57:38** from first job start to last completion
and used **436.23 elapsed runner-minutes**. This is one sample, not billing or
an attribution of timing differences to PR1. First-attempt failures are retained;
their root cause was not investigated as part of PR2. The two complete job views
from the PR rerun must not be added together as fresh runner work.

The corresponding run and paginated job/step metadata were reread into
`target/ci-v51-step-reuse/pr1-*.json`. At that point post-PR1 docs-only hosted
behavior was pending; local full/docs parity passed. PR #326 subsequently
completed that hosted path, recorded below.
For the PR row, API `head_sha` is the branch head; the actual tested merge SHA
was not recovered in this metadata observation. Do not substitute the branch
head for tested-source evidence. The push row identifies master source.

## PR2 — merged; full/docs hosted acceptance recorded

See [the precise scope and acceptance record](CI_V51_STEP_REUSE.md).
Eleven ordinary consumers now use two small local actions for tested-build
download/restore and independent always-uploaded provenance. The effective
registry stays unchanged. The new action directory requires full CI, including
any Markdown inputs. Owned/rich/canonical/release domains stay inline.

**202 local tests passed.** Independent expansion/diff confirms the same
effective steps, commands and artifact contracts, 26 untouched job bodies,
169 valid shell blocks, 38 static IDs and 46 full jobs. The implementation does
not claim measured time savings. At that implementation boundary hosted
full/composite and docs-only validation were pending. The user subsequently
authorized PR3 in the same batch; the PR2-only local receipts remain intact.
The later full and docs-only hosted observations are recorded below.

## PR3 — merged with PR2; rollout and trusted docs paths verified

See [the shadow-policy contract](CI_SHADOW_PLANNER.md). The observer reads a
closed baseline JSON policy, checks actual test-merge/source/workflow identities,
and retains the full three-dot PR or two-dot push diff. Policy edits, missing
history, unknown inputs and all unclassified build paths recommend full. Core
has no approved paths. Summary shows actual full/docs and recommendation
separately; there is no gate output, changed job condition or reduced coverage.

The first rollout is expected to report `POLICY_UNAVAILABLE` / full because its
base predates the policy. A following docs-only change can exercise the trusted
policy's docs recommendation. Existing qualification evidence is unchanged;
one 14-day attempt-specific observation upload is added to Change scope.

**218 combined local tests passed in 47.458 seconds** under Python 3.11, including
16 new planner tests over real temporary Git graphs, source/path/policy negatives,
the CLI's no-output guarantee and retained historical path fixtures for PRs
#322/#323/#324. Those fixtures are source-history boundary examples, not hosted
shadow executions or representative traffic statistics. Their selected paths
classify full/docs/full; current core eligibility is 0% by policy construction.

```bash
PYTHONDONTWRITEBYTECODE=1 python3.11 -m unittest \
  scripts.test_ci_shadow_plan scripts.test_ci_composites \
  scripts.test_ci_suites scripts.test_ci_required scripts.test_ci_changes \
  scripts.test_maven_infra_retry scripts.test_ci_v51_bundle scripts.test_ci_v51_python \
  scripts.v51.test_cloud_preflight scripts.v51.test_cloud_runner_artifacts \
  scripts.v51.test_cloud_runner_admission scripts.v51.test_phase7_release_fixtures \
  scripts.v51.test_candidate_artifacts scripts.v51.test_artifact_version \
  scripts.v44.test_phase7_release_fixtures
```

Combined static comparison confirms all 37 jobs outside Change scope have the
same effective step sequence as base `62b104e914e690be860a8c7a770d4de39ef797ec`,
including the eleven expanded composite consumers. The 26 unrelated job bodies
remain byte-identical. Change scope retains its existing steps and adds tests,
one observer and one upload. All 170 effective shell blocks parse; the independent
cloud parser still expects 46 full jobs. Suite registry, Required implementation,
release workflow, frozen hashes/toolchain and cloud consumer implementations
remain byte-identical. Combined review scripts, logs and staging/PR files are
under `target/ci-shadow-planner/`; earlier PR2 evidence is under
`target/ci-v51-step-reuse/`.

No full Maven/qualification run, hosted dispatch, cloud experiment, release or
Git commit/push was performed by the implementation agent. The operator later
pushed and merged the batch, producing the hosted observations below. Rollback
reverts the combined implementation and matching contracts together; no tag or
ruleset change is involved.

### PR #325 hosted observation and documentation-only follow-up

[PR #325](https://github.com/patricklfdm/GeneralSearchEngine/pull/325) merged as
`563dfe290326945d9cf0cda2b556b609d3be85a7`. The
[complete acceptance record](CI_SHADOW_ACCEPTANCE.md) retains source identities,
all attempts, original failure details, artifact hashes, timing and completed
docs-only follow-up.

- [PR run 38516949749](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38516949749),
  attempt 1: all 46 jobs succeeded. API head is `8a9f8a736e4ab3783499c2ab952bef2bbc989743`;
  the shadow report identifies actual tested merge `045a8af4984e003ff0ab5891e034689c93c82c41`.
- [master run 38522705456](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38522705456),
  attempt 1: full-size runtime failed on an update returning
  `INDETERMINATE` / `QUORUM_UNAVAILABLE`; Required correctly failed. Restore,
  provenance and failure-evidence uploads succeeded. Root cause remains unproven.
- Master attempt 2: all 46 accepted results succeeded, comprising two rerun
  executions and 44 reused executions. This is not a fresh all-job second run.
- All eleven composite consumer pairs succeeded. Both retained shadow reports
  show actual/recommended `full/full` and `POLICY_UNAVAILABLE`, as expected for
  baseline `62b104e...`. Master's report was produced in attempt 1, not attempt 2.
  Complete changed-path sets, workflow/planner hashes and downloaded ZIP digests
  were checked against source and API metadata.

Two runs / three attempts contain 94 distinct executions and 864.92 elapsed
runner-minutes after clone deduplication. No billing or speedup conclusion is
drawn. Raw/normalized data and the first failure log are retained under
`target/ci-shadow-acceptance/observations-20261014T075021Z/authorized-read/`.

[PR #326](https://github.com/patricklfdm/GeneralSearchEngine/pull/326) subsequently
merged as `d12d682e2a16eb2c9a96b326f2875e97768ddd7f`. Both normal hosted docs runs
passed on their first attempt: PR
[38532075143](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38532075143)
and exact-master push
[38532208752](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38532208752).
Each has Change scope and Required successful, 36 suites skipped, successful
documentation contracts and retained actual/shadow `docs/docs` reports. The
baseline policy source is `563dfe290326945d9cf0cda2b556b609d3be85a7`; full source,
policy/workflow hashes and producing attempts are in the acceptance record.
The PR tested merge is `c7245fe8f2a0e0d085cc2746deab2c80b7df555a`, distinct from
its branch head. Matrix skip placeholders are retained, not counted as full jobs.

Full/docs hosted rollout acceptance for PR1–PR3 is complete. The original failed
full-size runtime execution remains retained; its root cause is unproven. The
docs result does not qualify this newer master SHA for cloud execution.

PR #326's local documentation contracts, registry and expected docs result also
passed; the V5.1 contract covered 114 documents and 860 local links. Its local
receipt/PR text is under `target/ci-shadow-acceptance/`, and its hosted views and
reports are under `target/ci-shadow-acceptance/docs-hosted-pr326/`.

## PR4 — review completed; core activation deferred

[Policy review and conditional implementation](CI_CORE_POLICY_REVIEW.md) audits
actual example/reactor/guest/build/release dependencies and specifies files,
plan identities, Required results, acceptance negatives and a policy rollback.
The only candidate is the exact existing travel-example Java file. Applying the
proposed rule to the last 30 original merged-PR diffs gives **2 docs, 0 core,
28 full**. This is a merged-only retrospective sample, not new hosted core data.

V5.1 release status was reread: the complete release workflow and all three jobs
remain successful; the release is published, not draft/prerelease. PR #325's two
first attempts each end on a canonical dependency path. Their three canonical
executions sum to 138.37 and 129.37 runner-minutes respectively; these are elapsed
execution, not money or savings achievable on those ineligible changes.

Recommendation: retain full/docs and take PR5's phase-level canonical timing
investigation next. No core coverage reduction has been approved or enabled;
this review only prepares that decision. The subsequently authorized PR5 work
is recorded below; V5.2 work has not begun. Local analysis/source identities and the release GET data
are retained under `target/ci-core-policy-review/`.

Local review checks passed: both documentation contracts, the unchanged
36-suite/46-job registry, 12 boundary cases for the offline candidate classifier,
97 changed-document local links, docs classification/Required result, and
whitespace. The 12 cases validate only the review tool, not a future core gate.
The 30 source comparisons and complete three-job release identity were checked.
That PR4 review covered eight Markdown documents. No Maven, hosted workflow,
cloud or release execution was started; its original `validation.json` records
that scope. The combined batch additionally includes the PR5 changes below.

## PR5 — canonical replay optimization; full hosted acceptance pending

The operator requested this next batch together with the PR4 review.
[Phase analysis and equivalence boundaries](CI_CANONICAL_REPLAY_PERFORMANCE.md)
record six successful canonical jobs across PR #325 and its master first attempt.
Independent replay spans 349.40–648.81 seconds in those logs. Frozen measurement,
fault execution, collection/service stop and retention are accounted separately;
log timing does not isolate every nested operation or establish a population P95.

One implementation change reuses parsed format catalogs inside the independent
inspector. Every lookup rereads the source files; private size-one caches are
bound to content, while frames, authority, histories, negatives and budgets are
fully revalidated. Format catalogs, Java, POMs, workflow selection and release
inputs remain unchanged. Tests additionally cover final/SNAPSHOT coexistence
and exact artifact-role/Manifest selection. Full live PR/master CI remains
required; no cloud experiment is triggered by this batch.

Complete local replay of the same hosted repetition passed before and after:
**361.929 → 143.271 seconds**, with exact equality of the complete result and all
2291 original raw files unchanged. This is one sequential local pair, with
uncontrolled machine load/OS caches, not a measured whole-workflow improvement.
All 15 cells, 1080 rich calls, physical/history/negative results and budgets
remain identical. The 312-case frozen-format differential and focused oracle,
release and CI contract test groups passed. An older incompatible archive and
the filesystem-sandbox test failures remain retained with their explanations.

Validation, comparison receipts and original failures are retained in
`target/ci-canonical-hotspot/`. The PR4 staging/description files include both
batches at that boundary: nine Markdown files and three Python files. The
operator then authorized the PR6 work below in the same branch. This combined
change uses full CI; final hosted reconciliation remains pending.

## PR6 — local handoff prepared; final hosted reconciliation pending

The operator requested one more phase before submission. Added the
[generated current inventory](CI_JOB_INVENTORY.md),
[future-version suite onboarding](CI_SUITE_ONBOARDING.md) and
[operations/acceptance handoff](CI_REFACTOR_HANDOFF.md). Current CI/CD references
now use the validated inventory; older 32/34/35-lane counts remain labeled as
historical migration stages instead of being presented as today's topology.
Compatibility's current six consumers and the separate release evidence
retention are explicit.

`scripts.ci_inventory` renders the existing validated registry/workflow/actions
without executing commands or affecting job selection. The existing
`scripts.test_ci_suites` module adds checks for a stale/missing committed
inventory and invalid source contracts, so no workflow edit or new job is needed.
All existing suites retain explicit full/docs results, Required dependencies,
artifact ownership and independent cloud/release checks.

The onboarding procedure covers responsibility/resource domains, new-version
test discovery, fixed matrices, producer IDs, original/accepted attempts,
continuous-state boundaries, budgets, failure diagnosis and rollback. V5.1-only
discovery is not claimed to automatically cover a new V5.2 directory. Unknown
paths remain full; unregistered jobs and missing results fail closed.

The final **222 interface tests passed in 43.409 seconds** under Python 3.11,
including three new generated-inventory regressions, Required/planner/composite,
bundle/source/attempt, exhaustive partition discovery, cloud and release checks.
Static inventory and the independent cloud parser agree on all 46 expanded jobs;
all 36 suite dependencies and full/docs outcomes remain intact. The combined
scope is 19 Markdown files and five Python files; existing test methods are
preserved, with nine additions across the three modified test modules.
The 634 changed-document local links, documentation contracts, generated
inventory and whitespace checks passed. No generated catalog or workload changed.

Static contract results and source/coverage checks are retained under
`target/ci-refactor-closeout/`. No Maven, live workload, hosted dispatch/rerun,
paid cloud, release or repository-setting operation is part of this phase.
Final acceptance still needs the combined source's normal full PR and exact-master
runs, including all three live canonical repetitions. PR5's archive comparison
and earlier PR1–PR3 acceptance do not replace those runs. Core activation stays
deferred; the CI task is not yet marked fully closed.
