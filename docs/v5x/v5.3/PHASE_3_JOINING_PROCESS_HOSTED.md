# Hosted joining initialization process qualification

[`v53-joining-process.yml`](../../../.github/workflows/v53-joining-process.yml)
connects the [360-case process matrix](PHASE_3_JOINING_PROCESS_MATRIX.md) to one
immutable prepared source and independent downloaded replay. It is an opt-in
entry, not an existing Required gate. Adding this workflow does not qualify a
native cohort or close Phase 3; **corrected-source hosted qualification remains
pending**. The completed frozen-source run and its failures are recorded in the
[expansion review](PHASE_3_EXPANSION_FAILURE_REVIEW.md).

## Complete coverage within the hosted topology

The workflow has four stages:

| Stage | Jobs | Work |
| --- | --- | --- |
| Prepare | 1 | Freeze exact source, reference classes, tools and offline dependencies |
| Execute | 120 | Three whole histories sequentially per group; no workflow matrix parallel cap |
| Verify | 120 | Independently download and replay those three complete originals; no workflow matrix parallel cap |
| Aggregate | 1 | Check all same-attempt verifier receipts and exactly 360 distinct histories |

The 120 ordered groups contain consecutive triples from the immutable matrix
catalogue. Each group stays within one profile. Grouping amortizes runner/tool
setup and the seed download; each history still has its own original workspace,
raw archive, manifest and qualification result. No death/recovery/FINAL/BARRIER/
cold-open boundary is divided between jobs. Cases are never retried or replaced
with another member's success.

The former `max-parallel: 8` setting is removed from both matrices at the
operator's request. GitHub account/runner capacity still determines actual
concurrency; the change does not promise that all 120 jobs start together.
Per-group ordering, `fail-fast: false`, source/attempt bindings and aggregate
requirements are unchanged. Fresh producers enable connection identities in
both parent and halt/kill/resume JVMs so overlapping retry callbacks remain
attributable to their original attempts.

The topology generates 240 matrix jobs and 242 jobs overall. Each matrix is
below the documented 256-job ceiling. The platform's six-hour hosted-job limit
is retained as `timeout-minutes: 360`; native command/service bounds are unchanged.
These limits were checked against [GitHub's official limits](https://docs.github.com/en/actions/reference/limits).
Three histories per job is a scheduling choice, not measured proof that every
larger-profile verification will fit; final-source hosted timing remains open.

## Exact source and attempt authority

Only `workflow_dispatch` or a push to `experiment/v53-joining-process` can trigger
the workflow. Context checks require this repository, exact workflow path,
workflow SHA, branch ref, checked-out SHA, run ID and attempt. Existing CI,
Required, release and paid-cloud workflows are unchanged. No secrets or OIDC
permissions are requested; the workflow has only `contents: read`.

Preparation reuses the existing process setup and source-preparation code. It
executes the existing allocator reference test, not a membership history. The
prepared artifact binds all 360 cases, their fixed groups, the complete recorded
source, compiled class inventories, portable toolchain identity, reader manifest
and offline dependency hashes. Every worker rebuilds its own source copy and
must reproduce those exact classes. Each history uses a private offline Maven
repository copied from the seed, with dependency hashes checked afterward.

Execution and verification matrices use `fail-fast: false`. A handled failure
within a group records the failure and attempts the other members exactly once;
it does not retry the failed history. Its original is packed in the failure path.
Cancellation stops the group and attempts to retain the current original;
platform termination can still prevent final artifact upload. Missing evidence
always blocks acceptance. Raw archives are uploaded with `always()` where the
runner can execute that step.

Verification runs in separate jobs and downloads the seed and raw artifacts
from this exact attempt. It verifies the artifact schema, role, case, archive
hash and inventory before the [matrix member gate](PHASE_3_JOINING_PROCESS_MATRIX.md)
rechecks producer metadata and all three original-first readers. All 150
negative slots are required, with only original-backed conditional absences
allowed. A missing or failed raw member cannot count as a negative-test success;
the remaining group members are still independently checked.

The final aggregator requires both execution and verification job sets to have
succeeded. It accepts exactly 120 verifier artifacts, each containing exactly
the three declared cases in order. Every member must bind the same source,
build, tools, reader, seed and attempt and contain the complete qualification.
Original plan and raw archive hashes must be distinct across all 360 members.
Partial reruns cannot import seed/raw/verifier artifacts from an earlier attempt.

Verifier artifacts retain full qualification results. The final aggregate
retains compact per-case identities/counts plus each verifier artifact name and
receipt hash; it checks the full receipt before summarizing. It does not download
all 360 raw archives onto one runner. Complete acceptance may set
`declaredJoiningProcessMatrixQualified`, while all-profile observation coverage
and `phase3Complete` remain false pending the separate closure audit.

## Artifact bounds and observability

Artifacts bind run ID, attempt, source SHA and group ID in their names and are
retained for 90 days. The raw group directory contains exactly one separately
bounded bundle per case. Existing archive checks enforce a 1 GiB bundle bound,
256 MiB member bound and 65,536-member inventory bound, rejecting links, traversal,
duplicate entries and modified inventories. Grouping does not multiply these
limits for an individual history or silently drop files to fit.

The CLI prints a heartbeat every minute, plus each case's start and terminal
status. Verifier negative results are streamed and retained in per-case
`progress.jsonl`. Separate diagnostics artifacts retain execution logs, producer
receipts and verification progress. The Actions summary includes the exact
source/run/attempt, group, all three case names, status and qualification counts.
Actions use immutable SHA pins and the existing Java 21.0.12, Python 3.11 and
Maven 3.9.11 setup without a mutable shared dependency cache.

## Development verification and remaining work

The [development receipt](phase3-evidence/joining-process-hosted.json) records
synthetic execution/download/aggregation checks, archive/context refusal,
failure/cancellation retention, workflow/shell checks and Python regressions.
The tests exercise all 360 aggregate keys and 54,000 negative slots; this is
orchestration coverage, not 360 real executions or 54,000 executed negatives.

A retained historical producer is also packed and unpacked through the actual
artifact code. Its original physical/authority replay must match the earlier
diagnostic result and leave the original unchanged. The new cohort gate still
rejects that producer because the current reader is absent from its source.
This portable diagnostic does not upgrade the old source to final-source evidence.

The initial workflow-development batch did not run a new native workload,
hosted dispatch or paid-cloud experiment. Subsequent diagnostic executions are
recorded in the expansion review. The complete final-source process campaign, other required
cohorts, combined resource limits and frozen requirement-to-evidence mapping
remain open. Rollback removes this optional workflow, wrapper and tests without
changing runtime Java, protocol formats, the matrix readers or existing workflows.
