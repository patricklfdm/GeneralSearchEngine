# Adding CI suites for V5.2 and later

This is an integration procedure, not approval of a future version's design or
an authorization to extend the [tiered path policy](CI_TIERED_DESIGN.md). The
[generated inventory](CI_JOB_INVENTORY.md) lists current ownership;
[consumer contracts](CI_DEPENDENCY_CONTRACTS.md) define compatibility boundaries.

## Review record before implementation

Record these fields in the version's accepted plan or the proposed PR:

| Field | Required detail |
| --- | --- |
| Identity and owner | Stable job ID, display name, version/phase, verification script and responsibility domain. |
| Resources | Runner OS/class, JDK/Python/toolchain, memory/disk demand, process/network needs; explain any change from current Ubuntu runners. |
| Inputs | Source and build domains, exact producer artifact ID, original producing attempt, schema, hash/size/path checks and expiry behavior. |
| Outputs | Success/failure receipts, raw authority/history, negative results, reports, artifact names and retention; identify external readers. |
| Dependencies | For every `needs`, distinguish data, tested-build evidence, shared state and final result aggregation. |
| State boundary | Frozen calls/windows, lease/source/history, sequential handoffs, control rotation and combined budgets. State whether whole suites/cells are independently splittable and why. |
| Execution policy | Full/integration must run and succeed; docs must skip deliberately. Only the existing complete canonical suite is omitted by integration. New/unknown source paths select full. No new allowlist is implied. |
| Initial budget | Job/step ceilings, expected execution, setup/collection/replay costs, sample size and uncertainty; do not shorten frozen measurement to hit a target. |
| Failure handling | Diagnostic step and artifact, owner/investigation path, non-retryable integrity/test errors, any separately justified bounded infrastructure retry. |
| Acceptance | Positive and negative checks, discovered/executed test ownership, source-bound hosted PR/master results and rollback. |

The current registry has a closed schema. Put operational rationale in the plan;
do not add unsupported resource/owner keys to JSON or silently default them.
A new runner/matrix syntax or new local action requires an explicit parser and
external-reader change with negative tests before it is accepted.

## File-level implementation

1. Add the actual verifier and its meaningful positive/negative tests. Preserve
   original failures. A new `scripts/v52/` directory is **not** discovered by the
   existing V5.1-only Python partition: wire its discovery/execution explicitly.
   Within V5.1, `ci_v51_python` assigns every discovered module to exactly one
   partition; union/disjointness tests must still pass, including import errors,
   failed tests and empty suites. Focused gates may intentionally repeat tests.
2. Update [ci.yml](../.github/workflows/ci.yml),
   [ci_suite_registry.json](../scripts/ci_suite_registry.json) and Required's
   explicit `needs` together. Add the ordinary suite condition, explicit
   full/integration/docs results and reviewed
   fixed matrix; preserve failure uploads and `fail-fast: false`. Update the
   exact-count assertions in [test_ci_suites](../scripts/test_ci_suites.py).
   An unregistered job, missing dependency or cycle must fail validation.
3. Choose the correct build domain. Extending the eleven ordinary consumer
   actions requires updating `BUILD_CONSUMERS` and their equivalence tests.
   Specialized rich/owned/canonical/release paths stay inline unless separately
   reviewed. Never import new-version artifacts by widening V5.1's historical
   final/SNAPSHOT allowlist; version migration needs its own contract and tests.
4. Audit both [V5.1 cloud CI](../scripts/v51/cloud_ci.py) and
   [V5.0 preflight](../scripts/v50/cloud_preflight.py), plus
   [runner artifacts](../scripts/v51/cloud_runner_artifacts.py). Job/step names,
   fixed matrix members and exact-master/accepted-attempt checks are interfaces.
   Keep original producer identity when a partial rerun reuses an earlier build
   from the same run. Missing/expired evidence fails; no "latest green" fallback.
5. Keep [release fixture](../scripts/v51/test_phase7_release_fixtures.py) checks
   independent of registry matching: visible literal commands, signing/deploy
   blocks, `validate-evidence --source`, nine JARs/three POMs, six consumers and
   90-day evidence. Existing V5.1 hashes/toolchain/tag remain immutable.
6. Generate the readable inventory with `python3 -m scripts.ci_inventory` and
   update version-specific ownership/plan documentation. The generator validates
   current sources first; its output is documentation, never scheduling input.

## Required local and hosted checks

Run Python 3.11 or later from the repository root; these interface tests use
temporary fixtures and do not run Maven or paid cloud experiments:

```bash
python3 -m scripts.ci_suites
python3 -m scripts.ci_inventory --check
python3 -m unittest \
  scripts.test_ci_changes scripts.test_ci_suites scripts.test_ci_required \
  scripts.test_ci_composites scripts.test_ci_shadow_plan scripts.test_ci_plan \
  scripts.test_ci_v51_bundle scripts.test_ci_v51_python \
  scripts.v51.test_cloud_preflight scripts.v51.test_cloud_runner_artifacts \
  scripts.v51.test_cloud_runner_admission \
  scripts.v51.test_phase7_release_fixtures scripts.v51.test_candidate_artifacts \
  scripts.v51.test_artifact_version
```

Add tests specific to the new suite, not just new expected counts. Check all
selected jobs are reachable from Change scope and all results reach Required;
missing/failing/cancelled/unexpected-skipped results must reject. Matching edits
to registry and YAML alone do not prove that scripts still execute every oracle.

Then obtain normal full PR and exact-master CI, including the new suite and all
existing suites. Capture tested merge vs API head, workflow/policy identities,
accepted vs producing attempts and artifacts. Docs-only green checks do not
qualify runtime; integration is also not full cloud qualification. Any coverage-policy change needs
its own approval and acceptance record; unknown paths stay full.

## Failure and rollback

On failure retain run/attempt, failing step, source, receipts and raw evidence
before deciding whether to rerun. Treat compilation, contract, corruption,
source mismatch and repeatable logical failures as defects to investigate.
One successful rerun does not prove a scheduler root cause.

Rollback the reviewed suite/workflow/registry/Required/parser/docs change
together and revalidate the previous full inventory. Keep evidence and published
inputs. Do not delete Required, disable workflows, move tags or use admin bypass
as rollback. `forceFull=true` is the first rollback for integration. A structural
rollback must include the planner, closed outputs, registry and Required together.
