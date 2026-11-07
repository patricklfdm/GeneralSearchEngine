# Maximum component external execution and artifact binding

Status: **implemented, live observations and owning replay pending**. This is an
additional prerequisite for the maximum native and maximum queue components.
The existing five-member resource cohort and its workflow set are unchanged.
No runtime, maximum-input memory or Phase 3 qualification follows from this
entry alone.

## Exact two-workflow observation

`scripts.v53.maximum_resource_workflows` requires one explicitly indexed pair:

| Component | Workflow | Native history |
| --- | --- | --- |
| `maximum-native` | `v53-maximum-native-resources.yml` | Complete maximum native required-four history |
| `maximum-queue` | `v53-maximum-queue.yml` | Complete maximum image joint queue completion |

The index schema is `gse-v53-maximum-resource-workflow-set-v1`, with exactly
`schema`, `source` and `cohorts`. The source is one full commit SHA. `cohorts`
contains both component names, each with the existing context fields: `kind`
(`github`), `repository`, `source`, `ref`, `event` (`workflow_dispatch`), `run`,
`attempt` and `workflow`. Run/attempt values are decimal strings. Refs are the
owning modules' explicit experiment branches. Both runs must be distinct and
must refer to that same source. The observer verifies the actual checkout's
source inventory and workflow bytes.

Each workflow has three indivisible jobs: prepare, execute, verify. Source-derived
contracts bind their exact names, dependency graph, owning commands, pinned
checkout, large-runner labels, capacity admission before downloads, artifact
names including run/attempt/source, and 90-day retention. The observer requires
all six selected jobs and all critical shell/upload/download steps to succeed.
A job-wide green result with a skipped critical step is insufficient.

The shared collector reads every attempt from 1 through the selected attempt,
fully paginates jobs, retains failed/cancelled observations, and verifies that
the selected attempt is still the latest. It queries again at the end. An older
green attempt cannot replace a newer failed/running one. Prior failures remain
explicitly unresolved and require review; the observer never reruns anything.

```bash
python3 -B -m scripts.v53.maximum_resource_workflows \
  --index /evidence/maximum-workflows.json \
  --output /evidence/maximum-workflow-observation
```

Every output directory must be new. This command only reads GitHub metadata.
It neither downloads large evidence nor triggers execution.

## Bind the actual retained bytes

`scripts.v53.maximum_resource_artifacts` surrounds local byte verification with
fresh workflow observations and artifact listings. Artifact pages include old
attempts and diagnostics; selected seed/raw names must each occur exactly once.
Metadata must bind the repository, run, source, branch, ID, size, SHA-256 digest
and live retention interval. GitHub's artifact API supplies these fields. The
Actions toolkit computes/verifies the digest over the uploaded/downloaded stream,
so the original GitHub ZIP must be retained; recompressing its extracted contents
is not equivalent. See the [artifact API](https://docs.github.com/en/rest/actions/artifacts)
and [download implementation](https://github.com/actions/toolkit/blob/main/packages/artifact/src/internal/download/download-artifact.ts).

The input layout is deliberately explicit:

```text
zips/
  maximum-native/{seed.zip,raw.zip}
  maximum-queue/{seed.zip,raw.zip}
bundles/
  maximum-native/{seed,raw}/{manifest.json,bundle.tar.gz}
  maximum-queue/{seed,raw}/{manifest.json,bundle.tar.gz}
```

Obtain original ZIP bytes using the selected artifact IDs from the API, for
example `gh api --method GET repos/patricklfdm/GeneralSearchEngine/actions/artifacts/ARTIFACT_ID/zip > seed.zip`.
Use `gh run download RUN --name EXACT_ARTIFACT_NAME --dir BUNDLE_DIRECTORY` for
the corresponding unpacked bundle. Do not fabricate IDs/names, copy another
attempt, edit manifests or repackage a ZIP. These are future operator collection
steps, not commands executed during development. Keep enough free storage for
both ZIPs and bundles; this binder streams them without making another copy.

```bash
python3 -B -m scripts.v53.maximum_resource_artifacts \
  --index /evidence/maximum-workflows.json \
  --zips /evidence/zips --bundles /evidence/bundles \
  --output /evidence/maximum-artifact-binding
```

The ZIP size/digest must match the live API. Its two regular members must exactly
match the retained manifest/tar bytes, and the manifest must bind the owning
workflow context, artifact role and maximum profile. Links, path changes,
duplicates, encrypted/unsupported members, mismatched sizes, absent digests and
expired artifacts fail closed. Limits come from the owning transport, not an
artifact's own declaration. API JSON is bounded and the client issues only GET
requests to fixed repository endpoints; it does not follow metadata-supplied
URLs or fetch credentials from inputs.

After all four ZIP/bundle pairs are bound, both artifact metadata and all workflow
attempts are observed again. Changed attempts/selected metadata, changed local
inputs or modified retained API observations reject the result. Minute progress
continues during long hashing. Original API pages, attempt history, failure
receipts, file inventories and byte bindings are retained.

## Acceptance boundary and remaining work

Success is `PARTIAL` with `workflowExecutionAttested` and `artifactBytesBound`
true. `originalHistoriesReplayed`, `priorFailuresResolved`,
`combinedResourcesQualified` and `phase3Complete` remain false. A ZIP's authentic
origin cannot prove that its stored history is valid; this binder intentionally
does not accept producer PASS receipts as physical evidence.

The next composition must invoke both owning fresh-process readers against these
same bound originals, preserve the before/after external observations across the
entire replay, and check common source/build/toolchain pins. That composition,
large-host execution, memory observations, combined-owner pressure and final
source cohort audit remain pending. Existing in-workflow receipts retain their
current scopes and cannot substitute for this external byte binding.

The [development index](phase3-evidence/maximum-external-attestation-development.json)
records synthetic API/ZIP tests, shared observer compatibility and contract
checks. No GitHub experimental run was queried, dispatched or rerun, and no
maximum history was executed in this batch. Removing the two new CLI modules
removes this optional prerequisite entry without changing runtime or existing
cohort/workflow behavior.
