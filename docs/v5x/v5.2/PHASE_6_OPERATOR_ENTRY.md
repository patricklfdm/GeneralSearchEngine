# V5.2 protected operator workflow

Phase 6BJ adds the source-controlled **V5.2 Replication Runner** workflow and
prepare/run/verify-set operations. This is local implementation, not deployment
or paid acceptance. Provider configuration and dedicated identity/environment
setup review remain next. The current branch has not been pushed or dispatched.

## Preconditions and operation boundaries

The workflow accepts only manual dispatch on `master`. Its one `runner` job uses
the `v52-cloud-benchmark` environment and the dedicated `gse-v52-runner` identity.
Before authentication, the bootstrap validates the clean source, actual workflow
bytes, repository/owner, job/environment and original in-progress run/attempt.
Inputs pass through environment variables and strict JSON parsing; input text is
never interpolated into a shell command. There is no force mode or rerun fallback.

Before any native operation, the exact source must include reviewed
`docs/v5x/v5.2/cloud-provider.json`; its absence rejects at identity bootstrap.
The setup review must cover the dedicated WIF/IAM identities, environment and
secret, private networking/image, conditional object permissions and evidence
retention. Protected exact-master full CI and recent successful manual cleanup
are independently checked for preparation and again at original Runner admission.
Scheduled cleanup is optional and cannot substitute for missing original data.

| Operation | Input JSON | Effect | Public artifact |
| --- | --- | --- | --- |
| `prepare` | `member`, `sequence`, dated `estimate` | Original CI/build, package, controls, cleanup and provider/control observations; no resource/ledger/lease mutation | `v52-prepared-<run>-<attempt>` |
| `run` | `preparedRun`, `preparedAttempt`, `confirmation` | Execute that exact approved whole member once, retain evidence, close resources, then seal | `v52-runner-<run>-<attempt>` |
| `verify-set` | All five member names mapped to `requestSha256`, `runId`, `runAttempt` | Independently restore originals, authenticate their invocations and replay complete histories | `v52-cloud-set-<run>-<attempt>` |

The five members are `experiment`, `failure-drill`, `canonical-1`, `canonical-2`
and `canonical-3`. Any can be first. All five must share the same source,
configuration, sequence, build and controls. Original failures and their charged
reservations remain in the ledger; a member already passed in that sequence is
not executed again. A rerun is never used as a substitute for a selected original.

Time and accumulated cost budgets remain soft warnings. Each operation prints
progress at least every minute, including during prepared-artifact download.
The workflow uses GitHub's 360-minute hosted-job limit; that platform ceiling is
not a new per-stage timeout. Request/parser/storage bounds, approval expiry,
credential freshness and lease/grace checks remain hard. Cancellation/interruption
still requires the original lease's safe cleanup path; active leases are not
force-deleted.

## Prepare an explicit estimate

The draft helper reads the committed provider configuration locally and renders
the required hashes. It does **not** query live prices or derive a charge estimate.
The operator supplies an estimate including three VMs, both disk types, controls,
evidence, cleanup and failed attempts, with its priced coverage duration.
`$V52_ESTIMATE_MICROUSD` and `$V52_COVERAGE_SECONDS` must be set from that review.

After the readiness review and merge, from the exact clean master checkout:

```bash
V52_SEQUENCE=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
python3 -m scripts.v52.cloud_operator prepare-request \
  --source "$(git rev-parse HEAD)" \
  --member canonical-3 --sequence "$V52_SEQUENCE" \
  --cost-microusd "$V52_ESTIMATE_MICROUSD" \
  --coverage-seconds "$V52_COVERAGE_SECONDS" \
  --output target/v52-request-1
```

Use a new output directory for each draft, keeping earlier requests intact.
The default estimate validity is four hours; `--valid-seconds` may be explicitly
set up to one day. Actual preparation creates a plan valid for at most one hour,
bounded by estimate expiry. The same sequence is used for the remaining members;
each preparation generates a fresh attempt/access identity.

The `V52_EXPERIMENT_SSH_KEY` environment secret must contain one valid, unencrypted
Ed25519 OpenSSH private key. Preparation derives its public key; run checks the
same key against the authenticated original plan. Rotation between those steps
rejects before acquiring resources. The secret is removed from the Python process
environment before child commands run, written only into a private temporary
directory and removed on scope exit. It is never an artifact input or report field.

## Dispatch preparation and approve its exact plan

The following commands are operator actions after the merge/readiness boundary;
they are not run by local development or tests:

```bash
python3 - <<'PY' | gh workflow run v52-replication-evidence.yml --ref master --json
import json
from pathlib import Path
print(json.dumps({"operation": "prepare", "request": Path("target/v52-request-1/request.json").read_text()}))
PY
```

Inspect the completed summary's source, member, sequence, request/plan hashes,
expiry, new estimated cost and previous reserved cost. Preparation is
`PREPARED_NOT_ADMITTED`, and its approval template remains `confirmed=false`.
The summary supplies the exact `run` JSON. Selecting operation `run` with that
plan hash is the operator's explicit approval of the displayed request/costs.

The run operation downloads only the selected original preparation run/attempt.
It validates the successful original job and ordered steps, exact workflow Git
blob, repository/source, artifact digest/upload interval and bounded ZIP inventory.
The ZIP must contain exactly `plan.json`, `approval.json`, `preparation.json` and
`inputs.tar.gz`. Missing, changed, expired, foreign or rerun inputs reject before
native acquisition. Original CI/build, package bytes, provider/ledger state,
cleanup and approval are independently rechecked by the native factory.

There is no automatic execution after `prepare`, and no automatic business retry
after a failed `run`. Preserve the original diagnostic and cost record, inspect
the failure and reconcile the expired lease before preparing a new attempt.

## Verify the five original members

Retain each successful run summary's member name, request digest and original
run/attempt. The selected map contains all five names, for example these keys
(replace each value with its original recorded values):

```text
experiment       -> {requestSha256, runId, runAttempt}
failure-drill    -> {requestSha256, runId, runAttempt}
canonical-1      -> {requestSha256, runId, runAttempt}
canonical-2      -> {requestSha256, runId, runAttempt}
canonical-3      -> {requestSha256, runId, runAttempt}
```

Choose `verify-set` with that JSON map. It uses the
[original Runner/set join](PHASE_6_PROTECTED_RUNNER.md), not uploaded success
summaries as proof. Only complete original object/provenance/physical/history
replay can produce a qualified set PASS. The selected reservations and the full
ledger's cumulative reservations are shown separately; they are not a billing
invoice. Each whole history, including M01 offered windows, remains indivisible.

## Artifact and diagnostic boundaries

Successful operation artifacts are retained for 90 days. The workflow uploads
only `target/v52-runner/result`, whose closed contents depend on the operation.
Original workload archives remain in the immutable provider retention path.
Prepared inputs, member seals and final set receipts have different names and
inventories; they are not interchangeable.

An always-run diagnostic upload retains only `target/v52-runner/diagnostics`:
safe status, phase/code, source, declared counts/costs and public identifiers.
It cannot match a successful member artifact. The workflow does not upload the
private work tree, raw SSH/provider diagnostics, credentials or keys. The job
summary prefers a failure record over any earlier report and escapes table text.
Failures after resource acquisition remain subject to the original Session's
cleanup; an upload or summary success cannot make the entire job successful.

## Validation scope

Local evidence is recorded under `target/v52-operator-entry`. Tests use actual
workflow bytes, strict ZIP/JSON decoding and original native preparation code
with external GitHub/GCP/control downloads modeled. Real local `ssh-keygen`
checks cover secret permissions, public-key equality, environment removal and
temporary-file cleanup. No workflow was dispatched, no actual cloud credential
was obtained, no resource was created and no measurement was rerun.

The final 17 preparation/operator/workflow cases pass, including rotated-key
rejection before native acquisition. The original-artifact/provenance group
passes 19 cases and the CI/provenance contract group passes 78 cases. These
groups overlap with earlier local runs. Exhaustive CI discovery contains 1,139
cases across the unchanged eight partitions; this batch did not rerun every
case or the long physical/runtime matrix.

The next batch must finish the source-owned configuration/setup review and
pre-cloud completion audit. Real deployment, full protected CI on final master
and paid experiment dispatch remain operator actions.
