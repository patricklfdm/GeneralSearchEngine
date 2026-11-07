# Externally bound maximum component replay

Status: **implemented, native execution and live acceptance pending**. The
entry composes [external workflow/artifact binding](PHASE_3_MAXIMUM_EXTERNAL_ATTESTATION.md)
with both owning fresh-process physical readers. Two separate maximum histories
remain two separate component results. Their peaks are never added together.

## One complete acceptance invocation

```bash
python3 -B -m scripts.v53.maximum_resource_attested \
  --index /evidence/maximum-workflows.json \
  --zips /evidence/zips --bundles /evidence/bundles \
  --output /evidence/maximum-attested-replay
```

The index and local input layout are exactly those of the external artifact
binder. Use a new output directory and the exact source checkout. No Maven,
producer execution, workflow dispatch, retry, paid cloud action or repository
mutation is invoked. GitHub access consists only of the existing GET observation
calls. Inputs are never deleted or rewritten.

The complete sequence is:

1. Admit the native Linux workspace and validate the exact two-component index.
2. Observe both workflows and all attempts, then authenticate all four retained
   ZIP/bundle pairs against live API digests. Keep every prior failed/cancelled
   attempt and the full raw API pages.
3. Unpack both small seed artifacts. Use their owning readers, require the
   unretried successful preparation JUnit report, and compare the complete source
   inventory with the checkout. Require identical source, compiled-class,
   portable-toolchain, dependency-repository and reader pins **before either long
   physical replay**.
4. Invoke the native required-four reader and the maximum joint queue reader
   once each, against the same externally bound bundles. Each complete original
   must pass before its exact **150** or **15** negative results can count.
5. Revalidate the actual fresh-child command, successful exit, pins, measured
   memory record, complete owner-specific result and producer/raw inventory.
   Preserve each owning receipt and its complete output inventory.
6. Repeat live attempt/job/artifact observation and ZIP/bundle byte binding
   after both readers finish. Compare outcomes, step observations, metadata,
   source, prepared seeds and all original/result inventories across the whole
   replay interval.

A later rerun, still-green but changed step observations, changed artifact ID,
changed retained API page, mixed build/dependencies, missing negatives or altered
first output during the second replay rejects the composition. A parent PASS
label cannot replace a complete child result or its physical owner checks.

## Storage and memory admission

This composition requires native Linux, **448 GiB free workspace disk** and the
existing **8 GiB available memory** admission. WSL remains ineligible. The input
ZIPs and bundles must already exist; their occupied space is not counted as free.
The operator will arrange the acceptance environment after development.

The reserve covers two retained unpacked originals (up to 129 GiB each), the
preflight and owning-reader seed copies (up to 4 GiB in total), the existing
144 GiB direct reader allowance, and 42 GiB for retained observations and margin.
Both readers run serially, so the process-memory allowances are not multiplied.
The existing per-owner capacity checks still run at their normal boundaries;
other processes can consume free space, so initial admission is not a guarantee
that every later check will pass. Old failed work is never pruned to make room.

This is a composition workspace reserve, not a protocol-resource increase.
Application size, 16 GiB staging, 384 MiB metadata, 64 MiB CONTROL queue, chunk
sizes and lifetime limits are unchanged. Whole-reader memory observations stay
separate and do not become a proof of every possible maximum-input peak.

## Retained authority and failure behavior

The output retains `binding-before/`, both `seeds/`, both `replay/` trees,
`binding-after/`, preparation/replay inventories, capacity observations and the
root receipt. Minute progress covers long observation, hashing and reader work.
The root receipt records the active component and completed component summaries
before moving forward. If a reader fails, later readers are not substituted or
retried; the partial original/result directories and primary failure remain.

Successful composition has status `PARTIAL`, with
`workflowExecutionAttested`, `artifactBytesBound` and
`maximumComponentOriginalsReplayed` true. `wholeHistories` is exactly two.
`priorAttemptsRequireReview` remains visible and `priorFailuresResolved` remains
false. `combinedResourcesQualified`, `wholeReaderMemoryQualified`,
`finalSourceCohortQualified` and `phase3Complete` also remain false.

These outputs cannot replace any of the five existing supplemental cohort slots.
They cannot prove simultaneous metadata/image/queue pressure across one owner
history. That evidence, the full frozen coverage, final-source execution and
requirement-by-requirement closure audit remain separate requirements.

## Development verification

The [development index](phase3-evidence/maximum-attested-replay-development.json)
records the composition and compatibility checks. Tests use actual archive,
seed, API-observation, negative-result and memory-record readers around synthetic
native producer/child boundaries. They exercise mixed preparation, skipped
preparation, incomplete negatives, wrong child commands, late reruns, metadata
changes, output mutation and failure retention. They do **not** execute or qualify
a maximum JVM history.

No workflow or paid cloud experiment was dispatched. The new entry and its tests
can be removed independently; existing workflows, frozen plans, runtime Java and
previous component evidence are unchanged.
