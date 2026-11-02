# Hosted native carried DATA qualification

Phase 3 remains **OPEN**. The [workflow](../../../.github/workflows/v53-carried-data-histories.yml)
and [adapter](../../../scripts/v53/carried_data_history_hosted.py) prepare remote
execution of the [four-history DATA cohort](PHASE_3_CARRIED_DATA_COHORT.md).
They reuse its original-first physical reader and exact 129-check negative
vector. No hosted execution has been performed by this implementation batch.

## Indivisible histories and job dependencies

One preparation freezes source, compiled classes, tools and an offline Maven
repository. Four execution jobs each run one complete history exactly once:
ACCEPT, PROOF, CERTIFICATE or APPLIED through carried DATA completion and the
next fresh BARRIER. A history's old vote, recovery and publication are never
split between jobs or rebuilt from a successful fragment.

Four separate verifier jobs download the complete originals and seed, check
their provenance, then run the complete original before every exact negative.
Collection and verification receipts remain `PARTIAL`. The aggregate requires
all four executions and verifications to succeed, exact case inventories and
distinct original plans, raw archives and producer receipts. It binds each
receipt to source/build/tools/reader, seed archive, workflow, run and attempt.
Missing, skipped, cancelled or failed members block component acceptance.

Both matrices use `fail-fast: false` and at most four concurrent workers. Failed
originals and diagnostics are retained for 90 days. There is no workload retry,
shared mutable Maven cache, changed protocol limit or shortened native history.
The execution and replay commands retain their once-per-minute progress output.

## Authority and invocation

The entry permits `workflow_dispatch` or push to the dedicated branch
`experiment/v53-carried-data-histories`. Every job checks out the exact workflow
source without persisting credentials. Existing pinned action revisions and the
shared Java 21.0.12 / Python 3.11 / Maven 3.9.11 setup remain in use. Permissions
are limited to repository contents read; this workflow has no cloud credentials,
paid execution, release authority or changes to Required.

After separately authorizing publication and dispatch, use a selected source
containing the workflow. For example:

```bash
gh workflow run v53-carried-data-histories.yml --ref experiment/v53-carried-data-histories
```

A successful component result leaves `phase3Complete`, process-death,
all-membership-profile, combined-peak-resource, competing-owner and power-loss
qualification false. Neither local development receipts nor synthetic adapter
tests fill final-source hosted slots. The source inventory now has nine optional
hosted subsets and **460 planned whole histories**; that is not an accepted count
or a count of covered rows in the frozen S matrix.

## Verification and rollback

The [development receipt](phase3-evidence/carried-data-hosted.json) separates
adapter/workflow tests from the previous actual native four-phase cohort.
Synthetic round trips cover immutable seed preparation, one execution per case,
downloaded replay, failed-original retention, wrong source/attempt/tools/case,
changed classes/dependencies, altered negatives, duplicate plans and incomplete
aggregate inputs. The workflow tests check exact artifact names, bounded
parallelism, read-only permissions, failure uploads and pinned tools/actions.

Rollback removes this optional workflow/adapter, tests and hosted inventory
entry. Keep the local DATA producer/reader and historical originals. No native
history needs to be rerun merely to validate the adapter's topology.
