# CI refactor progress

## PR0 — complete

Read-only audit completed on 2026-10-14 UTC. The original input package and
working tree were preserved. Portable summaries: [baseline](CI_BASELINE.md),
[dependency/consumer contracts](CI_DEPENDENCY_CONTRACTS.md),
[decision and phase plan](CI_REFACTOR_ADR.md). The baseline records the external
raw-evidence directory and measurement limits.

## PR1 — implemented; hosted acceptance pending

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

Hosted PR full, master full and docs-only behavior remain **pending**. Record
their actual source, run and attempt before calling PR1 accepted. Do not treat
historical release CI as new-source validation. This implementation stops at
PR1; PR2–PR6 and V5.2 development have not begun in this task.
