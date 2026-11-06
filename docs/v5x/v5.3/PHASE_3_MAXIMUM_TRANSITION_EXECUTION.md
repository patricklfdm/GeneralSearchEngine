# Maximum-image transition execution and portable replay

Status: **execution tooling validated; complete maximum-image execution pending**.
This entry carries the [maximum-transition component](PHASE_3_MAXIMUM_TRANSITION.md)
through immutable source preparation, one complete original and independent
downloaded replay. It does not split the original receiver refusal, REMOVE,
FINAL, retirement or stable continuation across jobs. All five Phase 3 gaps
remain OPEN in the [qualification plan](phase3-qualification-plan.json).

## Manual execution entry

[`v53-maximum-transition.yml`](../../../.github/workflows/v53-maximum-transition.yml)
contains three jobs:

| Job | Work | Acceptance scope |
| --- | --- | --- |
| prepare | Freeze source, reference classes, dependencies and pinned tools | PARTIAL seed |
| execute | Rebuild offline, run the exact whole-history method once and collect originals | PARTIAL producer |
| verify | Download the same attempt's seed and original, replay the whole history, then sixteen exact negatives | Maximum-image storage transition only |

Only `workflow_dispatch` can start this entry. There is no push, pull-request,
schedule, Required integration or paid-cloud authority. The workflow grants
only `contents: read`, uses the existing checksum-pinned V5.3 process tools,
and checks out the exact source with persisted credentials disabled. Artifacts
and their internal manifests bind source, workflow, run and attempt. A failed
execute job cannot qualify through a successful replay or another attempt's
original.

The executor accepts only
`V53MaximumTransitionQualification#maximumImageRefusalThenRemovalCompletes`,
offline Maven and the existing 4 GiB heap. Exactly one passing, unskipped,
unretried JUnit test is required. Diagnostic methods and shortened commands
are rejected. The source, reader, generated classes, portable toolchain and
original inventories are checked before and after independent replay.

The accepted replay must retain the exact 67,108,832-byte native image, all ten
slots, the measured seven-image floor, real receiver refusal and completed
removal. The complete original must pass before all sixteen receiver mutations;
each mutation must match its exact name, order, rejection status and reason.
`maximumImageTransitionQualified=true` does not imply admitted learner,
automatic-runtime, full metadata pressure or complete resource-envelope
qualification. `combinedResourcesQualified` and `phase3Complete` remain false.

## Workspace capacity and retention

Execution and replay select a dedicated native Linux runner with labels
`self-hosted, Linux, X64, gse-v53-large-evidence`. This batch neither registers
that runner nor changes the existing V5.2 runner. No maximum-image execution
has been dispatched. A machine carrying this new label must be provisioned
and checked before later execution.

| Stage | Required free workspace bytes at admission | Required available memory |
| --- | ---: | ---: |
| execute, before copying source or starting Maven | 272 GiB | 8 GiB |
| verify, after artifact download and before extraction | 144 GiB | 8 GiB |

These are conservative workspace readiness checks, not measured maximum-run
requirements or runtime pool limits. Execution reserves room for up to 128 GiB
of raw history, a source/build-containing archive and spare space. Verification
also checks its 144 GiB threshold before downloading the original so the bounded
129 GiB archive cannot consume the last free bytes. It checks remaining free
space again after the downloaded archive already occupies disk.
It still needs room for the extracted original. Existing failures are never
deleted to meet these thresholds. WSL guest free space alone does not prove
backing-volume capacity, so this entry requires native Linux. The memory check
is a minimum admission condition, not a demonstrated maximum-run peak.

The new raw inventory has a 128 GiB aggregate bound; transport has a 129 GiB
bound including source/build files. Each member remains bounded to 256 MiB,
with at most 65,536 inventory entries and bounded directory depth. Inventory
hashing reads fixed 1 MiB chunks and checks file identity, extent and physical
type before and after reading. Links, special files and changed inputs fail.
It does not allocate a buffer sized to the aggregate bound. The shared archive
helper accepts this inventory function explicitly; all existing callers retain
their default inventory and bounds. The runtime's 512 MiB staging and other
resource limits are unchanged.

The workflow emits progress every minute and retains diagnostics and originals
for 90 days. Paths include run and attempt; self-hosted checkout uses
`clean: false` to preserve previous generated evidence. Concurrency does not
cancel an in-progress original. Execution and verification use a finite
1,380-minute job ceiling; this is not unlimited execution or a measured duration.
There is no workload retry. Failed capture and replay receipts are preserved;
packing failures are recorded without masking the original execution failure.
An abrupt runner/job termination can still prevent artifact upload; local
originals must be recovered separately in that case.

## Validation in this batch

Synthetic orchestration tests cover source/build/tool/attempt mismatches,
failed or shortened producers, strict JUnit results, altered original bytes,
malformed archives, output separation, capacity rejection before execution,
and exact negative/scope checks. They provide no native acceptance credit.
All 92 focused tests pass, including the existing REMOVE, required-four and
capacity-completion transport consumers. All 68 selected optimized-Python
tests pass, including qualification-plan checks. Documentation contracts,
workflow YAML, four shell blocks, ten Python syntax trees and whitespace checks
also pass.

The prior successful small-image diagnostic was packed, unpacked into a new
directory and independently replayed without rerunning the workload. All
10,110 files and 35,254,274 raw bytes retained identical hashes. The archive
contained 6,764,172 bytes; transport and complete diagnostic replay took 9.851
seconds. All sixteen negative results passed, with `maximumBytes=false` and
`status=DIAGNOSTIC`. These timings and sizes describe this diagnostic only.

Initial tests exposed an oversized allocation in the historical inventory
helper when given a 128 GiB aggregate bound, even for a one-byte file. The new
streaming inventory fixes this entry without changing the historical callers.
The failed test output remains under
`target/v53-maximum-transition-execution/` alongside corrected tests, static
checks, diagnostic transport receipts and their hash index.

No complete maximum workload, GitHub execution, runner registration, cloud
experiment or full reactor suite was run in this batch. This supplementary
three-job entry is outside the unchanged catalogue of 566 histories, 260
execution groups, 500 raw archives and 544 selected jobs. Final-source native
execution, downloaded replay and cohort admission remain required. Rollback
removes this entry, workflow and tests, and restores the shared archive helper's
prior signature; the component fixture and runtime semantics are unaffected.
