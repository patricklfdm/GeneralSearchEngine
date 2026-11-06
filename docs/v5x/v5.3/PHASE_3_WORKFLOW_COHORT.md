# Phase 3 workflow observations around original replay

Status: read-only entry implemented; final-source execution and Phase 3 closure
remain OPEN. Development tests use synthetic API responses, not hosted results.

The [workflow observer](../../../scripts/v53/phase3_workflow_cohort.py) fills the
execution-observation prerequisite left separate by the
[offline history cohort](PHASE_3_HISTORY_COHORT.md). It reads the same complete
twelve-subset seed index. Its selected source, workflow, branch/event, run and
attempt must match each original context; no search chooses a convenient green
run. A selected attempt must be the latest attempt of that explicitly selected
run. An earlier successful attempt cannot hide a newer failed or active rerun.

## Source and execution binding

Run from a clean checkout of the index's exact SHA. The entry checks full Git
source through the existing seed gate and reads the actual workflow bytes. A
closed parser recognizes the existing four-job graph: prepare, whole-history
execute matrix, downloaded verify matrix and aggregate. Matrix IDs come from
the owning artifact naming functions and complete source catalogues. Development
tests compare these with every actual hosted `plan` command.

The current twelve subsets expand to **516 selected Jobs** for **246 execution
groups**. The underlying **552 histories / 486 archives** are unchanged. A group
remains indivisible; no lease, source, crash segment or measurement is split.
The supplemental conditional capacity workflow is not one of these twelve and
does not become qualified through this entry.

For every selected job, the observer requires exact run/attempt/source/branch,
unique identity and name, completed success, and successful ordered shell and
artifact-upload steps from the source workflow. A green aggregate cannot hide
an omitted, duplicated, skipped or failed member. Composite setup internals and
platform post steps need not have fixed names. The source `needs` graph defines
dependencies; timestamps from different runners are retained telemetry, not a
new runtime deadline or cross-runner clock gate.

## Complete attempt collection

The collector uses only GitHub GET requests, through `gh api --hostname
github.com`. It reads the run, every attempt from 1 through the selected attempt,
and all job pages for each attempt. The 242-job joining-process attempt requires
three pages; the 106-job REMOVE attempt requires two. Page totals, page lengths,
job IDs and attempt identity must agree. Missing historical attempts, partial
reruns that reuse old jobs, truncated pages or changing run state reject.

All raw JSON responses are written exclusively to a new output directory before
semantic interpretation. An API inventory binds endpoint, hash and size. Failed
or cancelled selected attempts are retained and then rejected. A missing API
permission or network failure leaves a FAIL receipt and all fetched observations;
it never becomes a workflow success. Earlier failures and cancellations remain
listed even when the selected complete attempt succeeds. `priorAttemptsRequireReview`
stays true when earlier attempts exist; their original failed histories still
need review and are not replayed by this API observer.

The REST interfaces are GitHub's
[specific workflow run attempt](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt)
and [attempt job listing](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt),
using 100 jobs per page. This implementation bounds collection to 100 attempts,
1,024 jobs per attempt, 16 MiB per response and 512 MiB of raw observations.
Exceeding a collection bound fails with retained evidence; it does not truncate
or change any protocol/resource limit. Nothing dispatches, cancels or retries
a workflow, changes repository settings or starts a cloud experiment.

```bash
python3 -B -u -m scripts.v53.phase3_workflow_cohort \
  --index target/v53-phase3-cohort/seed-set.json \
  --output target/v53-phase3-cohort/workflow-observation-01
```

A complete observation returns PARTIAL with `workflowExecutionAttested=true`,
`originalHistoriesReplayed=false`, `runtimeQualified=false` and
`phase3Complete=false`. This is an observation of the specified workflow stages,
not proof that a downloaded PASS receipt or arbitrary local archive is authentic.
Retain the original downloaded seed/raw artifacts for their owning replay gates.

## Observe, replay originals, observe again

The [attested cohort entry](../../../scripts/v53/phase3_attested_cohort.py) calls
the real collector, then the complete original-first history entry, then the
collector again. Both observations and all original-reader diagnostics are kept.
It compares normalized execution identities, statuses, times and steps for every
attempt; harmless JSON formatting or unrelated actor metadata is not execution
drift. A new attempt or changed execution during the long replay rejects. It
rechecks raw inventories and seed bytes after the final API observation as well.

```bash
python3 -B -u -m scripts.v53.phase3_attested_cohort \
  --index target/v53-phase3-cohort/seed-set.json \
  --seeds target/v53-phase3-cohort/seeds \
  --inputs target/v53-phase3-cohort/raw \
  --output target/v53-phase3-cohort/attested-replay-01
```

The output must be new and outside all inputs. Progress appears at each collected
cohort and every minute during the enclosing entry. No producer or Maven build
is invoked. A successful result remains PARTIAL: the current complete workflow
and history set has been checked, while exact coverage, combined physical resource
maxima, historical failure review and final Phase 3 closure stay separate.
Neither command authorizes hosted execution or supplies missing originals.

The [development receipt](phase3-evidence/workflow-cohort.json) records actual
source-contract inspection and synthetic collection/orchestration tests. No
GitHub cohort has been collected or attested by this implementation yet. Existing
workflows, Required checks, runtime Java, POMs and frozen limits are unchanged.
