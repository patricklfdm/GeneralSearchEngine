# Maximum native history: dedicated transport and reader observation

The [maximum native entry](PHASE_3_MAXIMUM_NATIVE_ENTRY.md) now has a separate,
manual-only three-job workflow,
[`v53-maximum-native-resources.yml`](../../../.github/workflows/v53-maximum-native-resources.yml).
This workflow has not been dispatched. No qualifying native Linux runner is
currently available to the operator; environment setup is deferred until after
development. The transport and measurement components do not establish a
successful maximum native history or close Phase 3.

## Indivisible history and independent replay

1. `prepare` freezes source, compiled classes, readers, tools and offline Maven
   dependencies on the existing pinned Ubuntu preparation environment. It
   returns PARTIAL and does not execute the native history.
2. `execute` runs the complete maximum-image required-four history once on a
   dedicated `[self-hosted, Linux, X64, gse-v53-large-evidence]` runner. Collection
   remains PARTIAL. Failed originals stay failed; there is no measurement retry,
   smaller fallback profile, history splitting or stitching.
3. `verify` downloads that attempt's seed and original, then starts a fresh Python
   process for the whole source-bound resource verification. Acceptance requires
   the calibrated maximum seed, complete original history, all 150 exact
   negatives and the [seven-image same-callback storage observation](PHASE_3_NATIVE_IMAGE_STORAGE.md).
   It rechecks source, classes, reader, tools and the downloaded
   inventory. The child result, original producer receipt and measurement record
   are bound together; missing, failed or killed child execution cannot qualify.
   A failed execution job is rejected without downloading its large original
   again; the execution artifact and local failure workspace remain retained.

Artifacts bind workflow, source SHA, run ID and attempt, with 90-day retention.
Small-backup, EMPTY and maximum-storage artifacts cannot substitute for this
profile. The new entry does not change the frozen five supplemental cohort slots,
Required CI, V5.2 cloud workflows, credentials or paid-cloud admission. It shares
the existing maximum-transition workflow's concurrency group, so the two large
workflows cannot compete for the same scarce runner. Checkout keeps prior target
evidence, and each attempt uses a fresh output directory.

## Disk and host admission

The raw archive and extracted payload each have a caller-owned 129 GiB ceiling:
128 GiB of original observations plus 1 GiB for source/classes/receipts. This is
a transport envelope; individual owners retain their existing runtime limits.
Streaming inventories enforce member sizes, total bytes, no aliases, and stable
identities. Unpacking also rejects traversal, links, duplicate members, unexpected
artifact files and mismatched digests. No artifact controls its own byte limit.

| Check | Minimum free disk | Purpose |
| --- | ---: | --- |
| Before seed download and hosted execution | 280 GiB | Existing 272 GiB capture allowance plus preparation margin |
| Before verification downloads | 416 GiB | Compressed original, extracted original, existing 144 GiB reader allowance and margin |
| Before verification extraction | 288 GiB | Extracted original, existing 144 GiB reader allowance and margin |
| Inside the complete reader | 144 GiB | Existing direct verification admission, checked again after extraction |

All large stages require native Linux and at least 8 GiB available memory.
WSL remains ineligible; guest sparse-volume space is not backing-volume proof.
These transport checks are deliberately stricter than the direct entry and do
not reduce or silently consume its capacity allowance. Previously failed work is
never removed to satisfy a check. Preparation remains a small independent job.

The Java producer retains failed private bootstrap/replica work on the dedicated
runner. If that private work makes a failed attempt exceed the archive envelope,
packing fails and records both the original error and the artifact error; the
local workspace remains intact. A missing/incomplete archive cannot become a
successful execution. Operator recovery of an oversized failed workspace is
separate from qualification; the workflow does not silently trim it to fit.

## Reader memory observation

`maximum_native_reader` runs the complete verification in one fresh interpreter,
records process CPU time, elapsed time, process ID and Linux's post-exec
`/proc/self/status` `VmHWM`, and retains the original status text and its digest.
The result digest binds this observation to the complete verification receipt.
RSS includes interpreter imports; elapsed/CPU intervals cover the verification
call. The parent also retains child execution time and logs, including startup.
Minute progress continues while the child runs.

An initial `getrusage(RUSAGE_SELF).ru_maxrss` implementation passed isolated
tests but failed in the broader suite: a parent's earlier high-water RSS could
survive fork/exec accounting and hide both child allocations. The corrected
reader uses the new address space's `VmHWM`; the getrusage value is retained only
as a separately labelled diagnostic. A regression deliberately keeps 128 MiB
resident in the parent before starting two independent children with different
touched allocations, and verifies the measured child peaks remain distinct.

Linux documents `VmHWM` as peak RSS and notes that scalable RSS accounting can
be approximate. These are kernel-reported observations, not exact allocation
accounting or a proven upper bound for every input. They exclude other processes
and host-wide memory, and do not replace runtime lease/queue/resource checks.
See the [kernel proc documentation](https://docs.kernel.org/filesystems/proc.html).
The receipts therefore keep `wholeReaderMemoryQualified`,
`combinedResourcesQualified` and `phase3Complete` false pending the complete
maximum execution and final resource audit.

On a primary replay error, measurement still runs and the original error is
retained. If measurement also fails, its separate error cannot replace that
primary cause. A successful replay with failed measurement still fails the
observed entry. Process death without a measurement file is a failed observation,
not a zero-memory result.

## Development validation and next work

The [development receipt](phase3-evidence/maximum-native-hosted-development.json)
separates synthetic orchestration/measurement tests, retained real source-image
transport and pending physical qualification. Cross-attempt/source/profile
rejections, exact negatives, failed-job rejection, source/build/tools/dependency
binding, late mutation, safe archives and retention failures are covered.
Workflow checks cover manual triggering, pinned tools/actions, dedicated runners,
before-download capacity, exact artifact names and retained child diagnostics.

No maximum native experiment, complete maximum reader or paid/cloud execution
was run. Simultaneous same-owner metadata/image/queue pressure with refusal and
recovery, broader frozen coverage, final-source cohorts and all five Phase 3
closure gaps remain open. The operator will arrange the acceptance environment
after development. Rollback removes this optional workflow and its transport/
measurement modules; existing workflows, source originals and runtime formats
remain unchanged.
