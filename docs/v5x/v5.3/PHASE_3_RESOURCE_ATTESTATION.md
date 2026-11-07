# Phase 3 supplemental workflow and archive binding

Status: **implementation complete; final-source observation/execution OPEN**.
This extends the enclosing [cohort admission](PHASE_3_WORKFLOW_COHORT.md) to the
five [supplemental resource originals](PHASE_3_RESOURCE_COHORT.md). It does not
close combined resource maxima, exact coverage, failed-history review or Phase 3.

## Fixed complete workflow set

The [read-only observer](../../../scripts/v53/phase3_resource_workflows.py)
requires exactly four entries under `cohorts` in a
`gse-v53-phase3-resource-workflow-set-v1` index, with one common full `source` SHA:

| Index key | Source workflow | Complete histories | Selected jobs |
| --- | --- | --- | --- |
| `required-four` | `.github/workflows/v53-required-four-resources.yml` | `required-four` | 3 |
| `maximum-image` | `.github/workflows/v53-maximum-transition.yml` | `maximum-image` | 3 |
| `capacity-completion` | `.github/workflows/v53-capacity-completion.yml` | `capacity-completion` | 3 |
| `queue-resources` | `.github/workflows/v53-queue-resources.yml` | `source-queue`, `queue-completion` | 6 |

Each context has the same exact fields as the existing seed index: `kind=github`,
`repository=patricklfdm/GeneralSearchEngine`, `source`, full `refs/heads/...` ref,
`event`, decimal-string `run` and `attempt`, and exact workflow path. Runs must
be distinct. Maximum-image and queue-resources require `workflow_dispatch`;
the other two also support their existing dedicated push branches. No index
can replace an owning module, choose a small profile or omit one queue member.

The observer reads actual workflow bytes from the clean exact-source checkout.
It validates names, owning commands, runners, dependency graphs, ordered shell
and upload steps, and the queue planner's fixed two-member matrix. Maximum-image
execution/replay retain the dedicated native Linux runner, `clean: false` and
capacity precheck; this implementation does not configure that runner.

The shared GET-only collector retains every attempt and every jobs page,
including failure/cancellation observations. Only the explicitly selected latest
complete successful attempt can pass. Missing/skipped jobs, source drift,
changed attempts, missing critical steps or unavailable history fail with all
collected diagnostics retained. Five histories add **15 selected jobs**, outside
the unchanged twelve-subset **566 histories / 260 groups / 500 archives / 544
jobs** counts. Whole histories remain indivisible.

```bash
python3 -B -u -m scripts.v53.phase3_resource_workflows \
  --index target/v53-phase3-cohort/resource-workflows.json \
  --output target/v53-phase3-cohort/resource-observation-01
```

## Retained archives must match actual originals

The [archive binder](../../../scripts/v53/phase3_resource_artifacts.py) requires
an artifact root with exactly the four index-key directories above. Each holds
its seed artifact and complete raw artifacts, under their existing workflow
artifact names. The names bind run, attempt, source and, for queue raw archives,
the exact member. There are **four seed bundles plus five raw bundles**; each
bundle contains exactly `manifest.json` and `bundle.tar.gz`.

For example, the queue seed directory name is
`v53-queue-resources-seed-RUN-ATTEMPT-SHA`, and its raw member directory name is
`v53-queue-resources-raw-RUN-ATTEMPT-SHA-source-queue`. The other prefixes are
`v53-required-four-resources`, `v53-maximum-transition` and
`v53-capacity-completion`; their raw names have no member suffix. Copy actual
run/attempt/SHA values from the retained context; these placeholders are not inputs.

Seed archives use their real owning readers. The binder requires the retained
unretried `V53BallotAllocatorTest` report, source, compiled classes, toolchain,
reader and offline Maven dependency hashes. All four preparations and the
twelve-subset history seeds must share source/build/toolchain/dependency pins.
Reader manifests may differ by owning component but must belong to that source.

Raw bundles are streamed and every member hashed, without extracting another
large evidence copy. The manifest inventory must equal the actual tar contents;
links, traversal, duplicate members, oversized entries and digest mismatches
reject. Full-profile context, seed archive hash and producer receipt must match.
The archived `producer/` subtree must then equal every actual producer file and
directory supplied for replay, including sidecars and empty directories. A
matching PASS label or receipt hash alone cannot substitute different bytes.
Existing per-owner archive bounds are preserved; the default seed limit remains
1 GiB. These are evidence-reader bounds, not new runtime/time budgets.

```bash
python3 -B -u -m scripts.v53.phase3_resource_artifacts \
  --execution-index target/v53-phase3-cohort/resource-workflows.json \
  --resource-index target/v53-phase3-cohort/resource-set.json \
  --inputs target/v53-phase3-cohort/resources \
  --artifacts target/v53-phase3-cohort/resource-artifacts \
  --output target/v53-phase3-cohort/resource-bindings-01
```

The binder is offline. It reports PARTIAL with `resourceArtifactsBound=true`,
but `originalHistoriesReplayed=false`, `workflowExecutionAttested=false` and
`phase3Complete=false`. API observations and archive context/hash matching are
separate checks, not cryptographic proof of GitHub artifact origin. Keep the
original downloaded archives and acquisition records; this entry does not fetch
or attest an arbitrary local archive's remote provenance.

## Enclosing v3 admission

The enclosing entry requires both new inputs, in addition to all v2 inputs:
`--resource-workflows` and `--resource-artifacts`. It observes both workflow sets,
binds all resource archives before expensive replay, replays all twelve history
subsets and five resource originals independently, then observes both workflow
sets again. It compares normalized execution records and rechecks original
bytes, archive identities, seed inputs and retained receipts after observation.

Only that complete chain can set `resourceWorkflowExecutionAttested=true` and
`resourceArtifactsBound=true` alongside `allSupplementalOriginalsReplayed=true`.
Earlier failed attempts remain visible through `supplementalPriorAttempts` and
`priorAttemptsRequireReview`; no failed original is converted into a success.
The result stays PARTIAL with `phase3Complete=false`. Historical v1/v2 receipts
keep their original scope and do not satisfy this v3 prerequisite.

Development tests use synthetic API records and synthetic producer snapshots
with real archive/seed readers. A separate streamed check uses the previously
retained local SOURCE original; it is not GitHub execution or final-source
qualification. Details are recorded in the
[development index](phase3-evidence/resource-attestation-development.json).
No workflow dispatch, paid execution, Java/POM, Required CI or frozen runtime
limit changes are part of this batch.
