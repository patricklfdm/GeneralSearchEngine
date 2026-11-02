# Hosted transfer lifetime and recovery matrices

Phase 3 remains **OPEN**. The optional
[workflow](../../../.github/workflows/v53-transfer-histories.yml) connects the
[complete local transfer entry](PHASE_3_TRANSFER_HISTORY_COHORT.md) to isolated
execution and downloaded original-first replay. It has not been dispatched.
The earlier local native result remains tied to its own recorded source; it is
not an execution of this new workflow or its final-source cohort.

## Stages and boundaries

1. `prepare` freezes one clean source, reference classes, actual portable tools
   and an isolated Maven dependency repository. It reuses the existing pinned
   setup and preparation build, without running either transfer matrix.
2. Two `execute` jobs each reproduce the reference classes offline and run one
   complete existing matrix exactly once. `tcp-lifetimes` keeps all nine service
   lifetimes on each of its three original owners. `process-recovery` keeps all
   eighteen two-process histories. Neither retries nor per-case filtering are
   enabled. Failed originals are packed and retained alongside diagnostics.
3. Two separate `verify` jobs download the seed and original artifacts from this
   exact run/attempt/source. They independently validate source, classes, tools,
   reader and receipt bindings, then replay each original before its complete
   negative catalogue. Producer assertions do not count as this replay.
4. `aggregate` requires both workflow stages to succeed, exactly two verifier
   artifacts, all 21 distinct original plans, distinct raw archives/producer
   receipts, and the exact 48 rejection results. It rejects missing, failed,
   cancelled, aliased or mixed-attempt inputs. Its PASS qualifies only these
   declared transfer matrices; `phase3Complete` remains false.

The two execute jobs and two verifier jobs each have `max-parallel: 2` and
`fail-fast: false`. Their histories remain indivisible. The portable manifests
bind the seed/archive contents; names include the full source, run and attempt.
Both success and failure artifacts retain 90 days. Summaries show the source,
run/attempt, matrix, scope, hashes and completed case/negative counts. The shared
progress reporter emits a heartbeat every minute. The existing hosted platform
job limit remains 360 minutes; no native budget or acceptance deadline changes.

## Invocation and authority

The workflow runs only on explicit `workflow_dispatch` or a push to
`experiment/v53-transfer-histories`. It does not run automatically for ordinary
feature branches or PRs. Permissions are `contents: read`; there is no cloud
identity, paid experiment, release authority or change to Required. Checkout,
workflow source and artifact context must agree. Existing action SHAs and the
Java/Python/Maven toolchain pins are reused.

A partial rerun with a new attempt cannot silently reuse the prior attempt's
seed or verifier receipts. A new complete execution is needed for a complete
same-attempt cohort. Preserve failed originals; a subsequent successful run
never relabels them.

This implementation does not authorize push or dispatch. Long independent
experiments can later be grouped with the other prepared hosted entries after
execution is authorized. The qualification inventory now has seven hosted
subsets and **449 planned ownership histories**, adding 21 histories in two
execution groups. These are planned component histories, not accepted S rows,
not 449 completed runs, and not a Phase 3 completion percentage.

## Validation and limits

The [development receipt](phase3-evidence/transfer-history-hosted.json) records
local adapter/workflow/plan tests. These use labelled synthetic native results to
exercise real archive download, source/build admission and verifier aggregation.
They establish orchestration behavior only. They cannot establish hosted runner
availability, scheduling, new native timings or final-source qualification.

Regressions cover exact workflow/source/attempt bindings, tool/dependency drift,
extra or linked downloads, failed original retention, archive failures, all
required negatives, missing/duplicate/foreign original plans, stage failure and
the complete execute/download/replay/aggregate path. Source-plan tests keep each
complete matrix in one execution group. YAML and embedded shell blocks are also
checked locally. Native transfer behavior was separately exercised by the
preceding local component batch; no paid-cloud or hosted experiment is run here.

Rollback removes this optional workflow, adapter/tests and its qualification
inventory entry. The local transfer gate and previous hosted cohorts remain
independent. Complete automatic lifecycle/competition, other component entries,
combined resources, exact frozen coverage and final-source phase-wide admission
remain outstanding.
