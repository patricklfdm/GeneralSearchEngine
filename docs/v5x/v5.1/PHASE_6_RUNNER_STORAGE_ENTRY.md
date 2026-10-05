# V5.1 exact-request Runner storage entry

**Status:** implementation candidate after PR #284. The accepted offline storage
protocol now has operator preparation, an explicitly selected native workflow
entry and independent state review. This batch uses offline HTTP and credential
fixtures only. Corrected-source protected CI and separately approved live
qualification remain pending.

## Accepted baseline and scope

PR #284 merged at `69fb188b204feab01ffb6d2fdc37e02ab682c36c`.
[Exact-master CI 37261105426](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37261105426)
passed all 29 jobs. Its [storage transaction](PHASE_6_RUNNER_STORAGE.md) qualified
conditional control updates, eight object probes and interrupted-owner recovery
offline. The actual [Runner permission precheck](PHASE_6_RUNNER_PREFLIGHT.md)
established project/bucket diagnostics; object-name conditions still need actual
Runner requests and independent observations.

This entry performs only GCS storage qualification. Preparation creates two
expendable, request-bound canaries: an existing object inside the attempt prefix
and an object outside Runner's allowed control prefix. Runner then exercises the
accepted storage transaction using its own bound credential exchange. There are
no Compute, IAM, image, SSH or engine operations. The native lease retains all
thirteen resource entries as unattempted. Roles, trust and environment claims are
unchanged; Runner is already enabled and must not be enabled again for this task.

Both preparation and probing require an exact reviewed request. Preparation is
an operator action because Runner must be denied creation of the outside canary.
The canaries contain only test data. The review explicitly covers their possible
overwrite/deletion if actual IAM is broader than expected; that outcome fails
qualification. No permission result authorizes a request against another object.

## Two stages, one append-only budget

| Stage | Identity and operations | Reservation | Completion |
| --- | --- | --- | --- |
| Prepare | Operator: acquire lease, reserve, create canaries, retain completion, finalize ledger, release lease, publish immutable manifest | USD 1 | Native FAIL: storage preparation, no engine workload |
| Probe | Runner: acquire lease, reserve, execute eight exact object probes, retain report/completion, finalize ledger, release lease | USD 1 | Native FAIL: storage probes, no engine workload |

The stages have distinct attempt and sequence IDs. Successful preparation releases
its lease before dispatch so the unchanged observer can inspect a terminal
ledger with no active lease or pending attempt. The Runner requires that exact
post-preparation ledger generation and bytes in its same-run raw observer
evidence. It cannot consume an observer report made before preparation.

The USD 200 cumulative ceiling includes prior failed reservations. With the last
independently verified USD 12 baseline, successful preparation and probing would
retain USD 14; this is **reserved budget, not a measured invoice**. Fresh control
reads determine the actual starting amount. No reset, refund or failed-record
removal is provided. A successful storage check cannot satisfy an engine member
or advance experiment/canonical acceptance.

The immutable plan binds the exact source/configuration, operator, native
requests, initial control observation and price/retention review. Price input is
a reviewed JSON object with these fields:

| Field | Requirement |
| --- | --- |
| `observedAt`, `expiresAt` | UTC epoch seconds; fresh, at most 24 hours apart |
| `pricedThroughSeconds` | At least 6480, covering the existing 5400 + 1080 owner/grace interval |
| `retentionDays` | 30–365 days for retained GCS evidence |
| `stages.prepare`, `stages.run` | Each has positive integer micro-USD estimates for `requests`, `retention`, `actions`, `failureOverhang`; each stage totals at most 1,000,000 |
| `sources` | Official Google Cloud/GitHub pricing page URLs used in the review |

The plan does not fetch prices or enforce a bucket lifecycle rule. Review actual
rates and bucket retention before approving it. Synthetic test prices are not a
live quote. GitHub artifact retention remains 14 days; preserve original artifacts
and their hashes before that deadline. If either reviewed stage exceeds USD 1,
the planner rejects it; do not understate an estimate to fit the reservation.

## Native entry and deadlines

The existing `.github/workflows/v51-replication-evidence.yml` is displayed as
**V5.1 Preflight and Storage Qualification**. Its observer job is unchanged. Job
`run` remains in the same protected environment and uses the existing identity
binding. Its display name is `Runner permissions and optional storage qualification`.

| Dispatch input | Default | Meaning |
| --- | --- | --- |
| `check_runner_permissions` | `false` | Existing optional Runner project/bucket diagnostic precheck |
| `runner_storage_request` | Empty | Exact 64-hex plan SHA-256 identifying the prepared GCS manifest |
| `runner_storage_confirmation` | Empty | Exact 64-hex SHA-256 of the prepared manifest, including canary/control generations |

Empty storage inputs preserve the original diagnostic-only behavior. Both storage
hashes and `check_runner_permissions=true` are required to select storage probes.
A partial input pair or disabled precheck is rejected before authentication.
There is no arbitrary URL, object path, payload, command or force-delete input.

The plan expires 900 seconds after creation, or earlier at price-review expiry.
Prepare only after exact-source CI and recent manual evidence are ready. Each
storage stage has at most 300 seconds and also obeys the original plan deadline.
Runner additionally obeys the unchanged observer expiry and native owner
deadline. Queueing and environment approval consume that same time. No operation
renews a timestamp; an expired plan needs a new review and new identities. Manual
cleanup is primary. Schedule remains optional and does not block this sequence.

Before storage requests, the constructor independently verifies the current
run/source/attempt, raw observer report, actual Runner PRECHECK_PASS and bound
credentials. It reads the manifest from
`v5.1-automatic-leadership/control/runner-storage-requests/<plan-sha>.json`, using
metadata and generation-pinned media reads. That prefix is readable by Runner
but outside its write grants. The manifest binds the original plan and exact
prepared ledger/canary bytes and generations. Original storage mutations are
submitted once; uncertain responses never authorize replay.

## Operator sequence after protected merge

These are separate review/execution steps, not instructions to run paid actions
as part of the local development gate. The user retains preparation approval,
workflow dispatch and environment approval. Use fresh output directories.

1. Sync the accepted master source and verify its full protected CI. Obtain recent
   same-source manual cleanup evidence. Review current identity configuration,
   prices and evidence retention; do not wait for a schedule event.
2. Capture control state and generate the review-only plan:

   ```bash
   python3 -m scripts.v51.cloud_cleanup_observation capture \
     --output target/v51-storage-before
   python3 -m scripts.v51.cloud_runner_storage_plan plan \
     --source "$(git rev-parse HEAD)" --operator "$V51_STORAGE_OPERATOR" \
     --prices "$V51_STORAGE_PRICES" \
     --before target/v51-storage-before/observation.json \
     --output target/v51-storage-plan
   ```

   `V51_STORAGE_OPERATOR` is the reviewed active operator account;
   `V51_STORAGE_PRICES` points to the reviewed price JSON above. Inspect
   `plan.json` and `review.json`, including both reservations, current charges,
   exact canary/control scope and expiry. This command grants no write authority.
3. After approval of that concrete plan, submit preparation once:

   ```bash
   python3 -m scripts.v51.cloud_runner_storage_plan prepare \
     --plan target/v51-storage-plan/plan.json \
     --confirm "$V51_STORAGE_PLAN_SHA" --output target/v51-storage-prepared
   ```

   The native constructor rechecks the clean source, protected CI, operator
   account, enabled identity configuration and unchanged control baseline before
   writing. Review the PREPARED receipt and its manifest/confirmation hash. A
   failure is retained and must be investigated before any new plan.
4. The user dispatches the workflow on `master`, selects Runner precheck, and
   supplies the plan SHA and prepared confirmation SHA from that receipt. Approve
   the protected environment while the original plan is still fresh. Keep the
   storage summary and full `v51-runner-precheck-<run>-<attempt>` artifact.
5. Once that exact attempt is complete, download the original artifact and
   independently observe state. Assuming it was extracted to
   `target/v51-storage-runner`:

   ```bash
   python3 -m scripts.v51.cloud_runner_storage_entry observe \
     --manifest target/v51-storage-runner/storage/manifest.json \
     --output target/v51-storage-after
   python3 -m scripts.v51.cloud_runner_storage_entry review \
     --receipt target/v51-storage-runner/storage/receipt.json \
     --after target/v51-storage-after/observation.json \
     --precheck target/v51-storage-runner --output target/v51-storage-review
   ```

   The observer uses operator credentials and reads only the fixed inventory,
   twice, to reject a changing snapshot. Review checks both protected canaries,
   retained report/completions, original manifest generation, exact append-only
   terminal ledger and lease absence. It replays original raw preflight/precheck
   evidence at the recorded entry time and verifies the completed exact GitHub
   attempt/jobs/steps. Historical review never refreshes admission.

## Results and interrupted owners

Runner success is `PROBES_RECORDED`; the independent comparison produces
`OBJECT_SCOPE_MATCH`. Neither grants paid engine admission. Receipts keep
`objectPermissionsQualified`, `paidAdmission`, `engineWorkloadExecuted` and
`fullRemoteQualification` false. The comparison explicitly reports
`artifactProvenanceVerified=false` and `providerAuditVerified=false`: verify
original artifact provenance and actual provider identity/audit evidence
separately before recording live permission acceptance. An offline fixture or
locally edited JSON cannot establish effective IAM.

Failures retain the stage, bounded request metadata and HTTP/credential reason
codes, with no credential bodies or access tokens. If a response is lost, inspect
retained control state; do not rerun the old preparation or storage write. A
committed reservation remains charged. Use the existing manual cleanup for an
interrupted owner: active/grace leases remain WAITING, and only expired leases
with the original grace and identity checks may be finalized/released. No new
cleanup algorithm or bypass is introduced. Lost manifest submission can leave
valid retained objects despite an original FAIL; that does not authorize replay.

## Offline qualification and remaining work

The existing cloud-preflight gate includes focused entry tests and a new nine-case
preparation/Runner fixture. The healthy case preserves USD 12, appends two USD 1
reservations, checks terminal bytes and releases both leases. Eight preparation
lost-response cases replay the same native expired-owner reconciler in 16 fresh
processes across manual and schedule triggers. The accepted storage interruption
fixture still covers nine cases and 48 active/grace/expired process checks.

Entry regressions cover actual constructor wiring through simulated credentials
and HTTP, raw evidence replay, exact attempts/hashes/expiry, stale generations,
denied API bypass, workflow drift, independent-state mutations and sanitized
failure receipts. No cloud is contacted by these tests. CI lane count and reactor
builds are unchanged. The retained local evidence directory is
`target/v51-runner-storage-entry/`.

Local validation passed the complete preflight wrapper: 229 unit tests, 61
source/identity/permission negatives, eight single-disk, five preparation-driver
and 24 topology cases, plus both storage qualifications (nine cases each and
64 fresh-process cleanup checks combined). A final CLI filename correction and
native-preparer wiring regression passed the focused 12-test preparation suite;
all 20 new entry tests also passed under Python 3.11 (18 + two focused additions).
The initial tuple/list serialization and synthetic fixture setup failures remain
retained; plans now round-trip through canonical JSON before hashing/readback.
Logs, final receipts and source-file hashes are indexed in
`target/v51-runner-storage-entry/validation-summary.json`. Protected CI for this
entry remains required.

After protected acceptance, prepare and review one actual storage qualification.
Actual resource/image/IAP access and native owned-workload/provider failure paths
remain later steps. Full Phase 6 and paid engine execution remain open.
