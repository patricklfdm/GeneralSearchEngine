# Queue resource histories: opt-in parallel execution

Status: **entry implemented; hosted execution and final-source admission pending**.

The [manual workflow](../../../.github/workflows/v53-queue-resources.yml) exposes
the two existing source-bound queue qualifications as separate whole histories.
It is outside Required CI, has no push/PR/schedule trigger, uses no GCP identity
or cloud runner, and cannot close Phase 3. Adding this file does not authorize or
dispatch a run.

| Member | Exact producer | Independent scope |
| --- | --- | --- |
| `source-queue` | `source_queue_run`, profile `source-queue-64mib` | Six SOURCE caches, actual queue refusal and identical retry; eight exact negatives |
| `queue-completion` | `queue_completion_run`, profile `joint-queue-final-64mib` | Four additional SOURCE traces and seven held sends in the original joint activation, real refusal/retry, same-owner FINAL and stable BARRIER; ten exact negatives |

The [orchestrator](../../../scripts/v53/queue_resource_hosted.py) freezes one
source/classes/toolchain/dependency seed. Each member independently rebuilds and
must reproduce that seed's exact compiled bytes. Each complete history remains
indivisible; its authority, owner lifetimes and crash/control boundaries are not
split into jobs. There are six expanded jobs: one prepare, two execute, two
downloaded verify, and one aggregate. Independent members may run concurrently;
`fail-fast: false` preserves the other member if one fails. There is no retry or
small-profile fallback.

## Artifacts and admission

Every artifact name and archive manifest binds the exact workflow, full source
SHA, run ID, attempt and member. The planner always returns both members. Seeds
and originals use the existing bounded archive transport with streaming
inventories; symlinks, hardlinks, traversal, duplicate entries, substituted
contexts and changed original bytes reject.

The seed archive retains its 1 GiB bound. Raw transport permits each producer's
existing observation limit plus 1 GiB for immutable source/build metadata:
1.25 GiB for isolated SOURCE and 9 GiB for joint completion. These limits cover
copied evidence, not runtime resources. The per-file 256 MiB transport bound,
64 MiB runtime queue, 4 MiB chunks and all other protocol limits are unchanged.

Execution produces PARTIAL and retains the complete original even on failure.
A separate job downloads the exact attempt's seed/raw artifacts, checks original
provenance, invokes the owning physical reader on the unmodified original, and
then requires every exact negative reason. Its result also remains PARTIAL.
Collection success, an empty failure list, or a previous green attempt cannot
replace this replay.

The aggregate requires successful execute/verify job results and exactly both
verifier artifacts. It checks source/build/tools/reader pins, full profiles,
original/seed digests, distinct originals, exact results and all 18 negatives.
It rechecks earlier verifier bytes after the last member. Its successful result
is deliberately PARTIAL: `declaredQueueOriginalsReplayed=true` and
`workflowStagesReportedSuccessful=true` are separate from
`workflowExecutionAttested=false`, `combinedPeakResourcesQualified=false` and
`phase3Complete=false`.

All uploads retain evidence for 90 days, including failed-execution diagnostics.
Job summaries show source, run/attempt, member, pins and result. The existing
minute heartbeat remains active during prepare, execute and verify. Hosted jobs
use the platform's 360-minute maximum; it is not an experiment duration, new
runtime deadline or failover SLA.

## Relationship to final acceptance

The [supplemental resource set](PHASE_3_RESOURCE_COHORT.md) still requires both
original producers separately, alongside required-four, maximum-image and
capacity completion. The new workflow does not change the twelve-subset count
of 566 histories / 260 groups / 500 raw archives / 544 jobs.

An authorized final-source run and independent downloaded replay are still
required. Exact-attempt API observation and binding these supplemental workflow
artifacts into the final attested set remain open. Do not turn environment job
result strings or local synthetic transport contexts into GitHub execution
attestation. Independent component peaks must not be added together to claim a
combined byte maximum.

The [development index](phase3-evidence/queue-hosted-development.json) distinguishes
synthetic transport/orchestration checks, a local isolated SOURCE execution and
pending full joint/hosted execution. Historical failures remain retained.

The local development transport check completed in 92.295 seconds: preparation
29.696 seconds, original execution 46.811 seconds, and downloaded original-first
replay 10.851 seconds. It used actual compiled classes, captured local JDK/Maven
binaries, frozen dependencies, a six-session original with 49 attempts, one real
capacity refusal and one successful identical retry. The original and all eight
exact negatives passed. Peak charged queue bytes were 61,771,102 within the
unchanged 67,108,864-byte bound. The aggregate then rejected the deliberately
incomplete set because joint completion was absent.

This was an explicitly local development context and source snapshot; it is not
a GitHub workflow result, a final-source cohort or execution of the full joint
experiment. The raw producer, seed, archives, downloaded replay and rejected
aggregate remain under `target/v53-queue-hosted/local-original/`.
