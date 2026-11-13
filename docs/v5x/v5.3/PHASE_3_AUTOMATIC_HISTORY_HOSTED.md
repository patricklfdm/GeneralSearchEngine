# Hosted automatic lifecycle component qualification

Phase 3 remains **OPEN**. The optional
[workflow](../../../.github/workflows/v53-automatic-histories.yml) and
[adapter](../../../scripts/v53/automatic_history_hosted.py) connect the existing
[local cohort](PHASE_3_AUTOMATIC_HISTORY_COHORT.md) to isolated execution and
independent downloaded replay. This implementation batch does not dispatch it.

## Execution and evidence boundaries

One preparation freezes the actual source, compiled classes, pinned toolchain,
reader and offline Maven dependencies. Three jobs run complete execution groups:

| Group | Whole original histories | Execution boundary |
| --- | ---: | --- |
| `competition` | 1 | Three automatic owners, their grants, publication and drain |
| `higher-ballot-restart` | 1 | Two campaigns and the accompanying original lifecycle attachment |
| `reply-revocation` | 48 | The complete size × reply-boundary × revocation matrix in one native invocation |

The 48-case group cannot be filtered, split into jobs or repaired from successful
fragments. No native command is retried or given different workload parameters.
Three separate verifier jobs download the originals and their shared seed. Each
checks source/build/toolchain/reader, exact command, unretried JUnit report,
inventory and attachments, then invokes the complete original-first composition.
Downloaded evidence is checked again after replay.

The aggregate requires all three execution jobs and all three verifier jobs to
succeed, with 50 distinct original plans and distinct raw archive/producer receipt
digests. Every artifact name and manifest binds the workflow, source, run and
attempt. Missing, extra, stale, linked, failed or mixed-attempt inputs refuse.
Preparation, execution and verifier receipts remain `PARTIAL`; only the complete
declared component cohort can become `PASS`. That result retains
`phase3Complete=false`, `fullLifecycleQualified=false`,
`completeExportLifetimesQualified=false`, `allMembershipProfilesQualified=false`
and `combinedPeakResourcesQualified=false`.

The competition reader first validates the entire original, then derives its
supported shape. Pre-grant or local-only-grant loss requires 39 negatives and seven explicit
inapplicable mutations; superseded selection requires 104 negatives and none
inapplicable. Restart requires 73 negatives when an unused source was pulled,
or 72 and one explicit inapplicable mutation when none was pulled. The v2 reply matrix requires 44,
including the [observed resource lifetimes](PHASE_3_TRANSFER_RESOURCE_LIFETIME.md).
The aggregate therefore requires **155/156 or 220/221 exact ordered negative results**,
with case, status and reason checked by the existing composed reader. Inapplicable
mutations are reported separately and never counted as rejected. Unknown original
shapes are retained and refused; operators cannot select a smaller catalogue.

## Invocation and retention

Only explicit `workflow_dispatch` or a push to
`experiment/v53-automatic-histories` triggers this workflow. A later authorized
execution on a published source can use:

```bash
gh workflow run v53-automatic-histories.yml \
  --ref experiment/v53-automatic-histories
```

It uses read-only contents permission, pinned actions/tools, no shared Maven
cache, up to three execution jobs and three verifier jobs, `fail-fast: false`,
and no cancellation of an earlier run. Progress is emitted every minute by the
existing heartbeat. Failed originals and diagnostics upload with `always()`;
all artifacts retain the existing 90-day period. No evidence retry is introduced.
The workflow uses the existing 360-minute hosted Job envelope, not a change to
the protocol's frozen deadlines.

Existing Required CI, release contracts, cloud admission and V5.2 experiments
are unchanged. The source inventory now lists **eleven optional subsets and
512 planned whole histories**. These are scheduling counts, not successful
executions or covered rows in the frozen S matrix. A phase-wide common-source
admission and final execution are still required.

## Development checks and rollback

Synthetic orchestration tests cover both competition vectors, unknown shapes,
complete reply plans, portable restart attachments, bad originals, failed
capture/packing, altered dependencies/classes/tools, exact-attempt provenance
and a complete download/replay/aggregate round trip. They mock native execution
and physical replay, so they cannot qualify a runtime. The source inspector
also rejects dropping or splitting a history from the three groups.

Local checks passed: 70 focused tests in normal and optimized Python, the complete
2,612-test V5.3 Python suite (117.988 seconds), workflow YAML, five shell blocks,
twelve distinct uploaded artifact names, the source inspector and documentation
contract. The existing ten cohort catalogues and frozen acceptance hash are
unchanged. `actionlint` is unavailable locally; no hosted execution substitutes
for that missing tool check. No Maven build or native workload was run in this
orchestration-only batch.

The [development receipt](phase3-evidence/automatic-history-hosted.json) records
local validation separately from remote execution. No new native original or
remote result is claimed by this batch. The older retained-original checks
remain documented under the local cohort and are not rebound to this source.

Rollback removes this optional workflow, adapter, tests and scheduling links.
The local cohort, original readers, historical evidence and runtime remain intact.
