# Phase 3: reconcile independent hosted preparations

Status: offline seed provenance entry implemented; Phase 3 remains OPEN.

The twelve hosted subsets in the [qualification plan](phase3-qualification-plan.json)
prepare separately. A common Git SHA alone does not establish identical compiled
classes, JDK/Maven binaries or offline dependencies. Conversely, the profile and
joining-reply readers include an extra frozen-plan file, so requiring all reader
manifest hashes to be identical would reject legitimate preparations.

`scripts.v53.phase3_seed_cohort` resolves this prerequisite before expensive
original-history replay. It calls each existing adapter's seed reader rather
than introducing another interpretation of its catalogue or archive format.
It does not change workflows, execute JVM histories, fetch GitHub data or retry
any experiment. The declared catalogue is twelve subsets / 566 planned
histories, separate from the 3310 frozen Phase 5 scenarios.

## Input contract

Use a clean checkout at the exact source being audited. Supply a separately
selected index with schema `gse-v53-phase3-seed-set-v1`, `source` (full Git SHA)
and `cohorts`. The latter maps **all twelve names** in the qualification plan to
their original context objects:

| Field | Required value |
| --- | --- |
| `kind` | `github` |
| `repository` | `patricklfdm/GeneralSearchEngine` |
| `source` | Same full SHA as the index and checkout |
| `workflow` | That subset's existing exact workflow path |
| `ref`, `event` | Original dispatch branch, or that workflow's dedicated push branch |
| `run`, `attempt` | Original positive decimal strings; no implicit latest attempt |

Choose run/attempts from the intended original runs, rather than treating an
archive's own claimed context as independent approval. This offline entry does
not attest GitHub execution. Retain failed and superseded attempts separately;
they cannot be substituted into a successful seed set.

Place each downloaded seed artifact's **unchanged** `manifest.json` and
`bundle.tar.gz` under `<inputs>/<cohort-name>/`. Extra/missing directories and
extra artifact files fail. Original GitHub artifact names are reconstructed
through the owning adapter and recorded in the output; local directory names
do not replace the run/attempt binding.

```bash
python3 -m scripts.v53.phase3_seed_cohort \
  --index target/v53-phase3-cohort/seed-set.json \
  --inputs target/v53-phase3-cohort/seeds \
  --output target/v53-phase3-cohort/seed-audit-01
```

The output must be new and separate from inputs. Existing evidence is never
overwritten. One seed is unpacked at a time into new temporary scratch below the
output, then that scratch alone is removed. The original archives remain intact.
Small source/build/toolchain/seed manifests, the preparation test report and the
audit receipt are retained; no twelve-way expanded build copy is required.

## What is checked

- Exact workflow, source, event, ref, run and attempt, with one distinct workflow
  run per subset. Archives retain the existing per-artifact capacity and path
  guards. Duplicate JSON keys, symlinks and hard-linked artifact files reject.
- The source manifest equals the **complete actual Git blob inventory** at the
  clean reader checkout. A self-consistent archive with the right HEAD label
  but modified or omitted files still rejects.
- Actual compiled inventories agree across every preparation. Portable JDK and
  Maven binary identities and the retained offline JAR/POM dependency inventory
  agree. Per-host installation paths and kernel diagnostics may differ.
- Every owning seed reader passes. Reader sets may differ, but their hashes
  must be correct and every file must belong to the same complete source; the
  audit records both each reader pin and their union.
- The retained preparation execution succeeded and its sole ballot-allocator
  test report has actual cases with no errors, skips or hidden rerun/flaky nodes.
- Each input is unchanged after its own inspection and after the entire audit.
  Index and checkout are checked again. On failure the overall receipt stays
  FAIL, even if earlier individual seeds were inspected successfully.

Successful output is **PARTIAL**, `seedCohortVerified: true`,
`historiesReplayed: 0`, `workflowExecutionAttested: false`,
`runtimeQualified: false`, `phase3Complete: false`. It qualifies compatibility
of the supplied seed bytes only. Neither a self-reported build/test record nor
the index establishes that GitHub actually ran a workflow.

## Remaining admission and validation

The [history-cohort entry](PHASE_3_HISTORY_COHORT.md) now invokes this seed gate
before replaying all declared original artifacts through their owning readers
and aggregates. Its offline result also remains PARTIAL.

Final admission still needs every required whole original, independent
original-first physical/history/network/resource replay, exact negative results,
workflow execution attestation and explicit coverage. Each original's seed
archive hash remains tied to its own workflow: different archives must not be
rewritten into one seed. Lease/source/history continuity remains indivisible.

The development tests use synthetic source/classes/tools, real archive
packing/unpacking and all twelve actual owning seed readers. A temporary Git
repository separately exercises complete blob reading, dirty checkout and wrong
HEAD rejection. These tests did not execute the then-planned 552 histories or qualify a hosted
cohort. Local results and hashes are retained in the
[development receipt](phase3-evidence/seed-cohort.json).

The combined-resource, frozen-coverage, full cohort-admission and final-source
execution gaps remain OPEN. Later hosted execution requires its own authorized
final-source run; historical successful component data is not relabelled.

The [carried DATA v2 integration receipt](phase3-evidence/carried-process-cohort.json)
records the current expanded catalogue checks. Earlier development receipts
retain their original smaller catalogue and are not rewritten as new execution.
