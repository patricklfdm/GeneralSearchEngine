# Maximum image joint queue hosted entry

Status: **implemented, execution pending**. This optional manual workflow
transports the [maximum queue entry](PHASE_3_MAXIMUM_QUEUE_ENTRY.md). No maximum
history has been executed or accepted through it. The operator will arrange a
suitable native Linux environment after development.

## Execution contract

[`v53-maximum-queue.yml`](../../../.github/workflows/v53-maximum-queue.yml)
accepts only `workflow_dispatch` on `experiment/v53-maximum-queue`. Its context
requires the exact repository, source, workflow path, workflow source, run and
attempt. Ordinary push/PR/Required CI, existing queue profiles and the five-member
resource cohort are unchanged. No dispatch, runner provisioning, paid cloud
operation or repository setting change is part of this implementation.

| Job | Required work | Result |
| --- | --- | --- |
| Prepare | Freeze one source, compiled classes, reader, portable toolchain and dependency repository | `PARTIAL` seed; no maximum history |
| Execute | One unretried `V53MaximumQueueQualification#maximumImageFinishesAfterJointQueuePressure` on the seed source and dependencies | `PARTIAL` complete original, or retained failure |
| Verify | Download the seed and original from this attempt, validate pins, replay the complete original and all 15 exact negatives in one fresh interpreter | Component-only result and measured process memory |

The history preserves bootstrap, INTENT, joint activation, pressure/refusal and
identical-request recovery, FINAL, final activation, BARRIER and close. It is
never sharded, replayed as a replacement execution, reduced to a rehearsal or
silently substituted into the old JSON/small segmented slots. The source is the
calibrated 67,108,832-byte image with its independently checked four-member v2
bootstrap binding. Explicit segmented wire and default 16 GiB staging remain
required; runtime metadata, queue, chunk and lifetime limits are unchanged.

Artifacts include run, attempt and source in their names, retain for 90 days and
use immutable archive manifests. Source, class bytes, reader, toolchain,
dependencies and original inventories are rechecked after execution/replay.
Wrong attempts, sources, profiles, partial producers, failed jobs, altered
archives and missing/incorrect negative outcomes cannot qualify.

## Capacity and failure retention

Prepare runs on `ubuntu-24.04`. Execute and verify use
`[self-hosted, Linux, X64, gse-v53-large-evidence]`, serialized with the existing
maximum-transition/native workflows. No suitable host is currently available.
The existing shared capacity checker is reused without relaxing its limits:

| Admission point | Minimum free disk |
| --- | ---: |
| Before seed download and execution | 280 GiB |
| Before downloading the original for verification | 416 GiB |
| Before verification extraction | 288 GiB |
| Inside the complete reader after extraction | 144 GiB |

All large stages also require native Linux and 8 GiB available memory. Direct
capture still requires 272 GiB. The transport ceiling is 128 GiB original plus
1 GiB source/classes; this does not increase the protocol's resource limits.
Streaming inventories and archive extraction reject links, traversal, duplicate
members, excess bytes and changed identities. Neither archive metadata nor a
receipt can select its own size allowance.

Failed originals and diagnostics are retained. A packing failure records both
itself and the primary execution error; oversized failed private work remains
on the runner and cannot be trimmed into a passing archive. Large-runner
checkout uses `clean: false` so a later stage does not delete originals. The
workflow does not clean previous attempts to satisfy disk admission.

## Independent replay and memory scope

`scripts.v53.maximum_queue_reader` starts exactly one fresh child interpreter.
It checks the complete original before the 15 negative mutations and binds the
verified receipt to the child's PID, CPU/elapsed time and retained Linux
`/proc/self/status` peak RSS (`VmHWM`). The shared parser rejects missing or
mismatched PID/units and changed measurement bytes. `getrusage` peak RSS is
retained only as a diagnostic because inherited accounting can include a
parent's earlier peak. The minute progress reporter remains active while the
child runs. Failed replay, missing child result or measurement failure fails
the observed entry and preserves its diagnostics.

A successful run means `maximum-image-joint-queue-component-only`.
`workflowContextBound` describes the checked in-workflow context;
`externalRunAttested` remains false within this producer/reader workflow. The
[external observer and ZIP-byte binder](PHASE_3_MAXIMUM_EXTERNAL_ATTESTATION.md)
now check both maximum workflows and their exact API artifact digests; composition
with the owning readers remains pending. Receipt claims alone cannot enter the
existing cohort.
`wholeReaderMemoryQualified`, `combinedResourcesQualified` and `phase3Complete`
also remain false. One observed process peak does not prove all maximum-input
memory bounds or simultaneous pressure across every owner.

## Development verification and rollback

The [development index](phase3-evidence/maximum-queue-hosted-development.json)
records the targeted transport, measurement, capacity and compatibility tests.
Synthetic orchestration inputs prove rejection behavior, not maximum physical
execution. The workflow structure is checked for fixed tools/actions, exact
artifact names, before-download admission, no retries and retained failures.

Rollback removes this optional workflow and its queue-specific transport/reader
modules. Existing originals, shared helpers, runtime Java, Required CI and the
older resource slots are unchanged. Long positive execution, external
attestation, combined-resource evidence and final-source cohort qualification
remain outstanding.
