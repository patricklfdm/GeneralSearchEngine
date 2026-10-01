# V5.1 Phase 6C3C31 — workflow identity permission prechecks

**Status:** implementation accepted through PR #270, master
`13393b528bccd47a2d091ad43f3a1530f0aa6c8b`,
[CI 36830413171](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36830413171)
attempt 1, all 29 jobs. Actual observer execution is blocked during credential
initialization; the [diagnostic correction below](#credential-initialization-diagnostics--2026-10-01)
is a new candidate and does not establish successful provider permission queries.

## Scope and API limits

The [permission client](../../../scripts/v51/cloud_permissions.py) checks required
permissions and selected forbidden permissions with the service account actually
used by each workflow. It adds no role, grant, organization read, identity
enablement or resource mutation. The [IAM scope amendment](PHASE_6_CLEANUP_STATE_REVIEW.md#iam-admission-scope-amendment--2026-09-30)
continues to apply: unavailable ancestor policies remain unassessed.

| Query | Fixed scope | Required result | Selected forbidden results |
| --- | --- | --- | --- |
| Resource Manager `projects.testIamPermissions` (POST) | Configured project | Existing observer, runner or cleanup Compute role permissions | IAM/key changes, impersonation, external IP/VM service-account attachment, project SSH metadata, bucket creation and topology writes outside that role |
| Storage `buckets.testIamPermissions` (GET) | Configured evidence bucket | `storage.buckets.get` | Bucket delete/update/IAM changes, object list/create/delete/update at this bucket scope |

Both official methods require no additional IAM permission merely to query:
[project API](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/testIamPermissions),
[bucket API](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/testIamPermissions).
The POST is a permission query, not a mutation. The generic GET-only HTTP client
and the cleanup mutation policy remain unchanged; this separate client permits
only the two generated queries and their exact permission inventories.

Cloud Storage has no object-level `testIamPermissions` method in its
[object API](https://docs.cloud.google.com/storage/docs/json_api/v1/objects).
Bucket results cannot prove object-name conditional grants or denials. In
particular, failure to return `storage.objects.delete` at bucket scope does not
prove denial on every object. Do not invent an `/o/.../iam/testPermissions`
endpoint or broaden conditional grants to make a bucket query pass.

The successful result is **PRECHECK_PASS**, not IAM or cleanup qualification.
`effectiveIamQualified`, `objectPermissionsQualified`, `activationAllowed`,
`cleanupReady`, `paidAdmission`, `paidCloud`, `fullRemoteQualification` and
`artifactProvenanceVerified` stay false. These finite diagnostic queries are not
an authorization decision or an exhaustive privilege audit.

## Identity and execution binding

| Role | Job | Entry integration |
| --- | --- | --- |
| Observer | `observations` | Existing manual read-only preflight, after authentication and provider observations |
| Runner | `run` | Shared CLI available; no paid runner workflow deployed or enabled |
| Manual cleanup | `cleanup` | Deployment-review proposal, after authentication and before reconciliation |
| Scheduled cleanup | `cleanup` | Separate deployment-review proposal with the same checks and reconciliation |

The entry binds numeric repository/owner IDs, master source and checkout,
workflow path/event/environment, job, run ID/attempt, configuration digest,
service account and provider. It verifies the exact in-progress GitHub run before
and after collection using the existing latest/attempt/latest checks. The shared
[credential exchange](PHASE_6_CLEANUP_CREDENTIALS.md) validates the action's exact
external-account descriptor and OIDC claims before STS and impersonation. Operator
credentials, another role, another attempt and offline fixtures cannot substitute.

Collection uses one 180-second deadline, at most 30 seconds per exchange/request,
a 64 KiB response cap and at most one credential-refresh retry per query on 401.
403, 404, rate limits, server errors, malformed or unrequested permissions and
missing required/returned forbidden permissions block the precheck. Denial of a
query is never counted as successful rejection of a forbidden action. Responses
retain only known permission names, error classes and HTTP status; no credential,
raw provider error body or exception text is written to evidence.

The create-only output directory contains binding, observations, recomputed
receipt and a readable summary with identity, scopes, failures and remaining
checks. The observer report requires a matching network-execution receipt from
the same attempt, younger than 900 seconds; missing/offline/stale/altered receipts
block the report. Local consistency is not signed artifact provenance.

Cleanup proposals stop before reconciliation on precheck failure, and state
review requires that exact step to complete successfully. This only checks the
reviewed workflow path; the precheck is not replacement deletion authority.
Lease CAS, expiry/grace, ownership, operation identity and exact IDs still govern
the reconciler. No cleanup workflow is installed by this batch. Existing inactive
proposals, grants and enable/disable commands remain unchanged.

## Qualification and next work

`scripts/verify-v51-phase6-cloud-preflight.sh` exercises the four identities with
offline OIDC/STS/impersonation and exact HTTP requests, plus eight retained
negative cases per identity. Unit coverage also checks every queried required and
forbidden permission, identity/descriptor/plan drift, deadlines, bounded refresh,
malformed responses, secret retention and same-run report/cleanup-step gates.
Offline receipts explicitly say `offline-permission-probes`; they cannot establish
real provider permission qualification.

Original implementation validation passed: the complete preflight gate ran 100
tests, 13 provider/source negatives, 16 identity negatives and all 32 new permission negatives. The
18 new tests also passed under CI's Python 3.11. Generated manual/scheduled review
packages validated; three YAML documents and 14 shell blocks passed syntax checks.
Role/grant generators, credentials, reconciliation, inactive proposals, enable/
disable commands and the main CI workflow match the accepted base. Evidence is
retained at `target/v51-cloud-preflight/run.x28LzB` and
`target/v51-identity-permission-probes/validation-summary.json`. The permission
precheck itself changes no Java or Maven configuration.

The same PR's first CI attempt `36808406642` exposed a separate
[subsequent checkpoint restart defect](PHASE_2_RECOVERY.md#subsequent-checkpoint-restart-correction-candidate)
in the owned experiment. Its correction merged in PR #270, with runtime
regressions and a new reactor validation. The failed hosted evidence is retained;
permission prechecks did not cause the interrupted-generation recovery failure.

## Credential initialization diagnostics — 2026-10-01

The first actual observer preflight on accepted master,
[run 36897530651](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36897530651)
attempt 1, authenticated and collected provider observations successfully. Its
permission entry then stopped with `phase=credentials`, `type=ValueError`, before
writing permission observations or issuing permission queries. The final report
blocked solely on the missing successful same-run permission precheck. This is
not evidence of a denied IAM permission. The rejected credential component cannot
be recovered from that receipt; the original credential file was not retained.

The diagnostic candidate adds 26 fixed reason codes for credential-file loading,
runtime OIDC URL/token shape and exact external-account descriptor comparisons.
Permission and cleanup entries retain only a known `reasonCode`, failure phase
and exception class. CLI output and Actions summaries expose the code; summaries
add a static explanation. Unknown exceptions remain unclassified. Tokens,
authorization headers, credential paths, complete URLs, raw descriptor values
and arbitrary exception messages are never included in these diagnostics.

The existing admitted URL forms, descriptor fields, bound identity, file size
limit, symlink rejection and exchange rules remain unchanged. In particular, this
does not speculate about which field failed or accept an additional provider or
URL form. Initialization failure still stops permission collection and cleanup
reconciliation. The shared file reader also closes its descriptor if inspection
fails before a stream takes ownership.

Regression coverage exercises every code, all four permission identities through
actual credential initialization, both cleanup triggers, safe receipts/CLI/summary
output and rejection before network calls or reconciliation. The new suite is
included in the existing preflight gate. Local evidence and the original failed
receipt are retained at `target/v51-credential-diagnostics` and
`target/v51-preflight-36897530651`. Validation passed: 107 preflight tests and
61 negative fixtures; 53 credential/permission/network tests; 42 related tests
under Python 3.11; 28 integrated cleanup cases and 64 loopback TLS cases. A
79-input comparison with the accepted descriptor validator preserved every
accept/reject result. Corrected-source protected CI and a fresh
user-triggered observer preflight are required to learn the actual rejected field;
this diagnostic candidate does not claim to fix the underlying live mismatch.

## Remaining real-path work

Cleanup deployment and identity activation still need the
[reviewed sequence](PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md). Remaining real-path work
includes exact lease/ledger read and conditional replacement, immutable attempt
evidence creation and prohibited deletion/replacement, out-of-scope denial,
Compute operations, external image access and conditional IAP where applicable.
V5.1 cleanup must replace both lease and ledger; ledger deletion permission cannot
be globally forbidden because object replacement needs create and delete.

Real cleanup state/failure qualification, paid admission and complete Phase 6
remain open. This batch runs no cloud experiment, cleanup or configuration change.
