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

The current twelve subsets expand to **544 selected Jobs** for **260 execution
groups**, representing **566 histories / 500 raw archives**. A group
remains indivisible; no lease, source, crash segment or measurement is split.
The five [supplemental resource originals](PHASE_3_RESOURCE_COHORT.md) are outside
these counts. The enclosing v4 entry also requires their independent replay and
[four supplemental workflows / 15 jobs](PHASE_3_RESOURCE_ATTESTATION.md).
The two maximum workflows add six jobs. The [offline execution handoff](PHASE_3_EXECUTION_HANDOFF.md)
derives the complete eighteen-workflow, 565-job plan without dispatching it.

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

The v4 [attested cohort entry](../../../scripts/v53/phase3_attested_cohort.py)
requires the twelve history subsets, all five supplemental resource originals
and both [maximum component originals](PHASE_3_MAXIMUM_ATTESTED_REPLAY.md).
The maximum pair cannot be omitted or substituted for the five supplemental slots.
All owning workflows, exact attempts and original bundles retain their existing
contracts; the twelve-subset catalogue and its counts are unchanged.

The entry admits the large host before API calls or hashing original histories,
observes the history and supplemental workflows, prechecks the supplemental
producers and binds their nine seed/raw bundles. It then observes and binds both
maximum components and validates their preparation. All source, build, toolchain
and dependency pins must match across the sets before any physical replay.
Each owning reader manifest must belong to the exact checkout; the two maximum
readers also require their existing identical reader pin.

Inside the maximum observer's before/after interval, the entry replays the twelve
history subsets, the five supplemental originals, then the two maximum originals.
This order prunes only successful temporary extractions of the earlier readers
before retaining the large maximum outputs. Failures keep their original files
and stop subsequent readers. All workflow observations and reader diagnostics remain.
It compares normalized execution identities, statuses, times and steps for every
attempt; harmless JSON formatting or unrelated actor metadata is not execution
drift. A new attempt or changed execution during the long replay rejects. It
rechecks raw inventories, resource producers and seed bytes after the final API
observation as well. Missing resource or maximum inputs reject; v1–v3 receipts
remain historical and cannot satisfy v4.

```bash
python3 -B -u -m scripts.v53.phase3_attested_cohort \
  --index target/v53-phase3-cohort/seed-set.json \
  --seeds target/v53-phase3-cohort/seeds \
  --inputs target/v53-phase3-cohort/raw \
  --resource-index target/v53-phase3-cohort/resource-set.json \
  --resources target/v53-phase3-cohort/resources \
  --resource-workflows target/v53-phase3-cohort/resource-workflows.json \
  --resource-artifacts target/v53-phase3-cohort/resource-artifacts \
  --maximum-workflows /evidence/maximum-workflows.json \
  --maximum-zips /evidence/zips \
  --maximum-bundles /evidence/bundles \
  --output target/v53-phase3-cohort/attested-replay-01
```

The output must be new and outside all inputs. Progress appears at each collected
cohort and every minute during the enclosing entry. No producer or Maven build
is invoked. The enclosing workspace requires native Linux, 448 GiB free disk
after all inputs are present, and 8 GiB available memory, as described in the
maximum composition contract. Each existing reader still checks its own capacity;
the initial reserve does not guarantee space if other work consumes the disk.

A successful result remains PARTIAL: the current workflow and history set,
five supplemental originals and two maximum originals with their observations
have been checked, while exact coverage, combined physical resource maxima,
historical failure review and final Phase 3 closure stay separate.
Neither command authorizes hosted execution or supplies missing originals.

The [development receipt](phase3-evidence/workflow-cohort.json) records actual
source-contract inspection and synthetic collection/orchestration tests. No
GitHub cohort has been collected or attested by this implementation yet. Existing
workflows, Required checks, runtime Java, POMs and frozen limits are unchanged.
The [v4 development index](phase3-evidence/cohort-maximum-development.json)
records synthetic integration checks only. No complete hosted cohort or maximum
JVM history was executed for this change.
