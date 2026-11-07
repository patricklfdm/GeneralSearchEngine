# Phase 3 supplemental resource originals

Status: **entry implemented; final-source execution and Phase 3 closure OPEN**.
This closes an orchestration omission: the twelve-subset history total did not
require the newer resource supplements. It does not close a runtime obligation.

The [resource cohort reader](../../../scripts/v53/phase3_resource_cohort.py)
requires these five separate, complete originals:

| Input directory | Owning profile | Scope retained by admission |
| --- | --- | --- |
| `required-four` | `5-REPLACE-required-four` | Required-four ownership and completion; 147 exact negatives |
| `maximum-image` | `maximum-application-remove` | Exact maximum application image, receiver refusal and REMOVE completion; 16 negatives |
| `capacity-completion` | `capacity-231` | Operation-231 continuation; 34 negatives; historical prefix remains conditional |
| `source-queue` | `source-queue-64mib` | Six SOURCE caches and real queue refusal/retry; eight negatives |
| `queue-completion` | `joint-queue-final-64mib` | Joint queue refusal/retry, same-owner native FINAL/BARRIER; fifteen negatives |

The required-four member now has one [complete corrected-source development result](PHASE_3_MEMBERSHIP_CONTROL_RESOURCES.md#complete-corrected-source-development-qualification)
at `78403d87`, including portable original-first replay and all 147 negatives.
It qualifies observed ownership and completion at that source; it does not fill
the final-source set or establish simultaneous byte maxima. Its earlier failed
admissions remain retained.

Learner byte pressure remains mandatory in the twelve-subset learner histories;
it is not replaced by this set. All five entries remain outside the catalogue's
566 histories / 260 groups / 500 archives / 544 selected jobs. No count here
adds a Phase 5 scenario or supplies missing combined maximum evidence.

## Exact inputs, independent readers

Use a clean checkout at the final SHA and retain each source-bound producer
directory under its exact input name. Each contains the original workspace,
source/build/toolchain/reader records, JUnit, execution and collection records,
raw history and PARTIAL producer receipt. Transport may relocate directories;
it must preserve their original bytes. A previously downloaded PASS receipt is
not an input substitute.

Select an index with schema `gse-v53-phase3-resource-set-v1`, the full `source`
SHA and exactly the five `members` above. Every member has exactly `profile`
and `pins`; copy the four hashes from its producer's `pins.json`:
`sourceSha256`, `buildSha256`, `toolchainSha256`, `readerSha256`.
The index cannot select a reader module, small profile or arbitrary directory.

Before physical replay the entry validates every producer, compares all recorded
source files with the actual clean Git tree, requires equal source/build/toolchain
pins, and checks that every reader belongs to that source. The enclosing attested
entry additionally compares those common pins with the independently verified
history seeds. Directories alone do not establish a separately attested
dependency archive or workflow. The enclosing v3 entry therefore requires the
[supplemental archive and workflow checks](PHASE_3_RESOURCE_ATTESTATION.md).

Each owning verifier then reads the actual original before its exact negatives.
The aggregate checks the resulting scope, pins, original inventory and complete
owning result. It never adds independent peaks together. Every original, JUnit
inventory, source and index is checked again after all five replays, then again
after the enclosing workflow observation. The output directory must be new and
outside all inputs; links and overwrite attempts reject. Failures retain their
receipt, active member and scratch diagnostics. There is no automatic retry.

```bash
python3 -B -u -m scripts.v53.phase3_resource_cohort \
  --index target/v53-phase3-cohort/resource-set.json \
  --inputs target/v53-phase3-cohort/resources \
  --output target/v53-phase3-cohort/resource-replay-01
```

This command does not execute Maven, fetch GitHub, dispatch a workflow or run a
cloud experiment. Progress prints at each member and every minute during replay.
A successful result is PARTIAL with `allSupplementalOriginalsReplayed=true`.
`resourceWorkflowExecutionAttested`, `combinedPeakResourcesQualified`,
`historicalCapacityPrefixQualified`, `frozenScenarioCoverageQualified` and
`phase3Complete` remain false. Workflow admission of these additional executions,
feasible combined byte occupancy, coverage and prior-failure review remain open.

## Enclosing admission

The [attested cohort entry](PHASE_3_WORKFLOW_COHORT.md) now uses schema
`gse-v53-phase3-attested-cohort-v4` and requires `--resource-index`, `--resources`,
`--resource-workflows` and `--resource-artifacts`, plus the two separate maximum
components' `--maximum-workflows`, `--maximum-zips` and `--maximum-bundles`.
No flag bypasses either set. Its order is:

1. Admit the large workspace and observe all selected twelve-subset workflow attempts.
2. Precheck all supplemental producers and their source, observe their four
   workflows, and bind their four seed/five raw archives to the actual inputs.
3. Observe and bind the two maximum components. Reconcile their seeds and the
   history seeds against the supplemental pins before replaying the complete
   twelve-subset original history set.
4. Replay all five resource originals against those seeds' common pins.
5. Replay both maximum originals, then finish the maximum observer's after check.
6. Observe the history and supplemental workflow sets again; recheck originals,
   archives and receipts.

The existing `workflowExecutionAttested` field covers the twelve observed
workflow subsets. In the enclosing v4 result, `resourceWorkflowExecutionAttested`
and `resourceArtifactsBound` can become true only after the additional checks;
the standalone resource reader retains its offline scope and false workflow
flag. The new `maximumComponentOriginalsReplayed`, `maximumWorkflowExecutionAttested`
and `maximumArtifactsBound` fields describe only the two additional components.
Neither the five-member set nor the twelve-subset catalogue changes. Earlier
v1–v3 receipts remain historical and cannot satisfy v4. Separate peaks are not summed.

## Queue completion producer

The [source-bound queue completion entry](../../../scripts/v53/queue_completion_run.py)
adds immutable capture and independent admission for the
[existing native experiment](PHASE_3_QUEUE_COMPLETION.md). It runs exactly
`V53QueueCompletionQualification#admittedRemoveFinishesAfterRealJointQueuePressure`
once. Small rehearsal JUnit, failed/skipped/retried tests, altered commands,
classes or source, missing FINAL/BARRIER, and incomplete negatives reject.
Its 8 GiB streaming inventory bound limits retained observations, not runtime
resources. Producer and collector return PARTIAL without qualification.

```bash
python3 -B -u -m scripts.v53.queue_completion_run capture \
  target/v53-joint-queue-final/producer \
  --profile joint-queue-final-64mib --maven /opt/maven/bin/mvn

python3 -B -u -m scripts.v53.queue_completion_run verify \
  target/v53-joint-queue-final/replay-01 \
  --profile joint-queue-final-64mib \
  --producer target/v53-joint-queue-final/producer \
  --pins target/v53-joint-queue-final/producer/pins.json
```

The full native component now has one source-bound development original at
`e532f2df`: its unretried execution, independent physical replay and ten exact
negatives pass. The [full-size observation](PHASE_3_QUEUE_COMPLETION.md#full-size-development-original)
records the actual bytes, timings and limits. Final-source execution remains
required. The earlier [development index](phase3-evidence/resource-cohort-development.json)
records the initial orchestration checks, small-profile rejection and path-guard
failure; none is relabelled as the later full result.

The two queue originals now have a [manual shared-seed workflow](PHASE_3_QUEUE_RESOURCE_HOSTED.md)
with parallel whole-history execution and independent downloaded replay. Its
aggregate remains PARTIAL; final-source execution and exact-attempt supplemental
workflow observation are still required.
