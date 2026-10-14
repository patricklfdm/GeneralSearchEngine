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
`target/ci-v51-step-reuse/pr1-*.json`. Post-PR1 **docs-only hosted behavior remains
pending**; local full/docs parity passed. PR2 does not replace that pending item.
For the PR row, API `head_sha` is the branch head; the actual tested merge SHA
was not recovered in this metadata observation. Do not substitute the branch
head for tested-source evidence. The push row identifies master source.

## PR2 — merged; full hosted paths observed, docs-only pending

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
The later full hosted observations are recorded below; docs-only is still pending.

## PR3 — merged with PR2; rollout observation verified, trusted docs path pending

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
all attempts, original failure details, artifact hashes, timing and the remaining
docs-only checklist.

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

The current `docs/ci-shadow-acceptance` branch only updates Markdown and prepares
the normal PR/master **docs-only hosted acceptance**. That future result remains
pending: expected classifier false, both documentation contracts successful,
actual/shadow docs with a valid unchanged baseline policy, all 36 suite dependency
results skipped, Required successful, and an attempt-bound report retained.
Matrix skip placeholders must not be checked as if 46 full jobs executed.

Local checks use the existing documentation contracts and registry plus changed
path, links, whitespace and expected docs-result validation. No workflow or
runtime change, new dispatch, rerun or paid-cloud action is part of this follow-up.
Both documentation contracts passed (the V5.1 check covered 114 documents and
860 local links); registry validation still reports 36 suites / 46 full jobs.
All seven changed Markdown paths classify as docs and the local expected
Required docs result passes. These are local results; the PR/master hosted
docs outcomes above remain pending. The staging list, local receipt and PR text
are under `target/ci-shadow-acceptance/`.
PR4–PR6 and V5.2 development have not begun here; core has no approved paths.
