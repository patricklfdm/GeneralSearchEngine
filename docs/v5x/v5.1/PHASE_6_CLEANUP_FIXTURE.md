# V5.1 Phase 6 — single-disk cleanup qualification preparation

**Status:** local review and offline rehearsal candidate. No cloud fixture,
control-object write, paid experiment or new identity is executed by this batch.
Protected CI and separately reviewed real-provider preparation remain pending.

## Accepted starting point

PR #274 deployed the manual cleanup entry at master
`b0a0173584d499a06abce870f8f0f2e46202c7b9`.
[CI 36951936364](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36951936364)
passed all 29 jobs on attempt 2. Original attempt failures remain distinct from
this accepted result. The previously approved manual provider, pool and service
account were enabled in that order, with independent inspection after each of
the three requests. Complete readback passed all 17 groups / 33 observations;
runner/scheduled objects remained disabled and unrelated observations unchanged.

[Manual run 36957603644](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36957603644)
attempt 1 then passed real credential exchange and the project/bucket permission
precheck. Independent permission replay passed at the original observation time.
The source-bound before/after review returned `STATE_MATCH / NO_LEASE`, unchanged
ledger and zero retained cost. Evidence is retained under
`target/v51-manual-cleanup-activation/` and `target/v51-manual-cleanup-36957603644/`.
These results qualify the manual empty path, not resource deletion or current
cleanup freshness. No ledger was reset.

## Smallest useful resource scope

Use exactly the existing `n1-data` resource shape: **one 100 GiB pd-balanced disk
in us-west4-a**, no VM, firewall, boot disk or network-policy change. Keep all
13 native lease inventory rows, with only this one marked attempted. This is a
partial interrupted allocation already expressible in the accepted native format;
it does not change the workload topology or introduce a reduced benchmark preset.

Use a new qualification-only sequence and attempt with member `experiment` and a
bundle digest of the qualification manifest. Never present it as an engine
workload artifact. The native request's public SSH-format binding remains required,
but no VM, SSH access or private-key distribution is involved. A cleanup-created
completion remains `FAIL`, `engineWorkloadExecuted=false`. Preserve all previous
ledger events and the approved reservation, even after successful resource cleanup.

The local matrix uses an explicit offline public-key fixture and offline project.
Those records must never be uploaded, relabelled or used as real cloud authority.
Real preparation needs fresh exact request/context bytes and separate approval.

## Timing and evidence

| Case | Actual elapsed time from lease start | Required result |
| --- | --- | --- |
| Active | Before 5400 seconds | WAITING; unchanged control generations, bytes and resource ID |
| Grace | At least 5400 but below 6480 seconds | WAITING; same preservation |
| Expired disk | At least 6480 seconds | PASS; original operation/numeric ID absent, correct terminal ledger and lease release |

The 5400-second lease and 1080-second grace remain frozen. Real execution must
wait at least **108 minutes**; no backdating, shorter expiry or caller-supplied
cleanup time is allowed. This is an eligibility threshold, not a scheduler SLA.
Manual dispatches are separate short jobs, not a hosted runner sleeping for two
hours. The operator must be available to approve and inspect the expired cleanup.
Do not allocate the disk if that attendance cannot be provided while schedule is
disabled. Record exact UTC boundaries at actual fixture preparation.

Acquire the empty lease with generation-match 0, append the reviewed reservation
using the observed ledger generation, and retain context before create intent.
Before the single insert, durably mark the data-disk row attempted. Keep its
deterministic requestId and inspect the original operation after an uncertain
response; do not blindly repeat the insert. Before/after observations, exact run
attempt, permission receipt and provider principal/operation audit evidence are
required. The successful resource case must show exactly one attempted and one
previously present disk. A zero-resource finalization is insufficient.

On failure, retain the lease, operations, context, failure/completion and original
charge. Inspect and reconcile the same authority. A partial failure is not grounds
to clear the ledger, release the lease or delete a resource by name.

## Object-scope qualification design

The project/bucket diagnostic precheck cannot establish conditional object rights.
The actual manual identity needs a separately reviewed probe driver operating on
dedicated canaries. This batch records the design; it does **not** add that driver,
deploy probe steps or claim these cases passed on Google Cloud.

| Probe | Required observation |
| --- | --- |
| New canary within the dedicated attempt prefix | Actual identity can create once and read matching bytes/generation |
| Attempt-canary replacement/deletion | Authenticated permission denial and independently unchanged original object |
| Existing canary outside the V5.1 control prefix | Read/write/delete denial and independently unchanged original object |

Never target real completion, context, historical evidence or arbitrary caller
paths. Establish dedicated negative canary existence first. Guard overwrite/delete
with `ifGenerationMatch=0`: an existing live object cannot meet that condition.
The [delete API](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/delete)
documents the generation guard; [request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions)
define mismatch as 412. **412 does not prove IAM denial**. Only an authenticated
403 with the expected identity/scope and unchanged independent state can qualify
the specified denial. 400, 401, 404, 409, 412, throttling, unavailable or malformed
responses are inconclusive. Do not loosen the guard or grants to force a result.
Unexpected success stops qualification and requires state inspection.

## Cost review remains required

The proposed reservation is **USD 1**, to be appended under the [approved USD 200](PHASE_6_CLOUD_CONTROL.md#approved-cumulative-ceiling-amendment--2026-10-01)
cumulative ledger if approved. It is not a price quote, allocation approval,
automatic shutdown or hard provider spending cap. Include regional disk pricing,
control/canary requests and storage, at least 30-day evidence retention, Actions
and failure overhang. Disk charges continue until absence is confirmed.

The [official disk pricing table](https://cloud.google.com/compute/disks-image-pricing)
was consulted on 2026-10-01. Its rendered default region was us-central1, so this
review deliberately does **not** treat that number as a verified us-west4 quote.
Before requesting allocation approval, retain the current regional SKU/price,
bounded request/object inventory and overhang estimate. `priceQualified=false`
and absence of a live preparer/probe driver remain explicit blockers. No additional
organization IAM permission or runner enablement is needed merely to prepare this
review; do not grant either as a shortcut.

## Generated package and offline rehearsal

```bash
python3 -m scripts.v51.cloud_cleanup_fixture generate \
  --source "$(git rev-parse HEAD)" --output target/v51-cleanup-fixture-review
python3 -m scripts.v51.cloud_cleanup_fixture validate \
  --source "$(git rev-parse HEAD)" --output target/v51-cleanup-fixture-review
```

The create-only package contains `plan.json`, `REVIEW.md` and `review.json`.
Validation recomputes trusted plan bytes from source/configuration rather than
trusting user-updated hashes. Changed limits, accounting, admission claims,
preconditions, source/configuration, inventories or symlinked files are rejected.
There is no apply/enable/dispatch command and no native request/lease is emitted.

The existing preflight gate retains an eight-case offline single-disk rehearsal:
active, grace, expired disk, lost insert response, missing context, reused name,
delete denial and generation conflict. It uses the existing native reconciler and
HTTP model, original operations and numeric deletion. It checks that failure cases
keep the disk/lease, WAITING makes no writes, successful cleanup retains a failed
completion and earlier charges, and an empty rerun leaves terminal state unchanged.
Snapshots, requests and original expected FAIL receipts remain in each case's
directory. `PASS` on the matrix means the expected behavior was observed offline.

Next implementation: finish the narrowly scoped real fixture preparer and actual
identity canary probe driver, review regional pricing/exact request/rollback,
then obtain fixture-specific approval. Real failure-path and instance/firewall
coverage, scheduled identity qualification and full Phase 6 remain open. Existing
manual deployment approval does not cover allocation or fixture control writes.
