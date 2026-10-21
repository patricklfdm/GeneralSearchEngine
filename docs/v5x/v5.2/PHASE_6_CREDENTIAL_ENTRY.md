# V5.2 Phase 6AT credential context and renewable exchange

This stage adds a dedicated V5.2 credential entry after the
[provider/guest identity adapter](PHASE_6_PROVIDER_GUEST_IDENTITY.md). Its native
factory observes the source, GitHub run and auth-action descriptor. A separate
call performs the fixed OIDC → STS → service-account impersonation exchange.
Local tests replace all external observations/exchanges and contact no provider.

## Closed identities

The entry binds repository `patricklfdm/GeneralSearchEngine`, repository ID
`1341513206`, owner ID `147357093`, `refs/heads/master`, exact source and clean
checkout, workflow path/ref/SHA, event, job, environment, run ID and attempt.
The source must match both GitHub runtime SHAs and the actual checkout. Run IDs
and attempts are bounded positive decimal values; booleans and aliases reject.

| Role | Workflow under `.github/workflows/` | Event | Job | Environment | Account / WIF pool |
| --- | --- | --- | --- | --- | --- |
| runner | `v52-replication-evidence.yml` | `workflow_dispatch` | `runner` | `v52-cloud-benchmark` | `gse-v52-runner` |
| manual | `v52-manual-cleanup.yml` | `workflow_dispatch` | `cleanup` | `v52-cloud-manual-cleanup` | `gse-v52-manual-cleanup` |
| schedule | `v52-expired-cleanup.yml` | `schedule` | `cleanup` | `v52-cloud-cleanup` | `gse-v52-cleanup` |

These are the closed names for future integration. This stage does **not** create
the workflows, IAM identities, provider trust conditions or environments. The
account is derived from the validated project name; the provider is derived from
the explicit numeric project number, dedicated pool and fixed `github` provider.
Their real existence, effective permissions and project name/number correspondence
remain fresh admission checks. Existing V5.1 identity deployment is unchanged.

## Original run and exact attempt

Each token exchange rechecks the actual clean checkout and performs GitHub GETs
in this order: latest run → explicit attempt → latest run. Every response must
match the source, workflow/event, master branch, numeric repository/owner IDs,
run ID/attempt, `in_progress` status and null conclusion. Forked repositories,
cancelled/completed runs, reruns and changed source reject before requesting OIDC.
The entry stores only the observation digest and public identity fields.

The fixed subprocess commands are `git rev-parse`, `git status` and narrowly
scoped `gh api --method GET`; no dispatch, rerun, mutation or fallback login is
implemented. The checks are bounded observations, not an atomic guarantee that
GitHub cannot change immediately afterward.

This binds the original master execution, not a continuously unchanged master
tip. A later commit must not independently disable an already running cleanup or
credential refresh. Exact-master build provenance under the [current CI policy](PHASE_6_CI_PROVENANCE.md)
and paid admission are checked separately before starting work. A credential receipt cannot establish either.

## Fixed exchange and refresh

Only `GOOGLE_GHA_CREDS_PATH` from the auth action is read: an absolute regular
file opened without following its final symlink, limited to 128 KiB and strict
JSON. There is no ADC discovery, gcloud account fallback, service-account key,
caller-selected token supplier or native transport override.

The shared V5.1 descriptor/exchange implementation pins the opaque runtime
GitHub OIDC route, including repeated slashes or suffixes after `idtoken`, its authorization header and exact audience.
It binds the immutable repository subject and all source/run/attempt claims.
Decoding a JWT does not authenticate its signature: Google STS must do that,
followed by impersonation of the one selected account. Federated credentials are
never provider access tokens. The refresh reads and validates the descriptor anew.

Token acquisition is serialized. Lock wait, source/run checks and all three
exchanges share one caller deadline of at most 30 seconds. Individual credential
exchanges have no automatic retry. This is a finite request bound, independent of
the soft total stage/cost budgets. The issuer's one-hour expiry may appear up to
five seconds farther away on a slightly slower runner wall clock. The shared
exchange permits that bounded skew, then clamps the remaining lifetime to the
requested 3600 seconds before subtracting the existing 60-second safety margin.
It never extends usable lifetime by the skew allowance. Expired/near-expiry
tokens and excess beyond five seconds still reject. The generic API can cache
tokens and refresh on expiry or one GET 401; mutation requests are never automatically replayed.

Known failures are rebuilt from closed diagnostic codes, and unexpected failures
become `V52_CREDENTIAL_UNCLASSIFIED` with no original exception chain in formatted
output. The shared exchange also attaches a closed failure kind (`http`,
`timeout`, `transport`, `deadline`, `response`, or `lifetime`) and, only for an
HTTP rejection, the numeric status. V5.2 retains these as `credentialCode`,
`credentialFailureKind` and `credentialHttpStatus` in native admission failures
and public operator diagnostics. These fields distinguish credential service
failures from Compute/Storage `httpStatus`; they never contain an issuer body,
exception message or URL. Unknown codes/fields and forged error types are omitted.
This diagnostic extension does not change accepted identities, requested token
lifetime, the original exchange deadline or retry behavior.

Receipts contain no environment, descriptor, URL query, request token,
JWT, federated token or access-token value. Receipt snapshots and closing share
the exchange lock; closing is idempotent and prevents new acquisition. It does not
revoke already issued tokens or delete the auth action's descriptor file.

## Qualification and boundary

`test_cloud_credentials` is part of the existing measurement unit gate. Its
32 tests cover all roles, field/claim drift, exact-attempt observations, fresh
descriptor checks, fixed native-factory wiring with mocked IO, deadlines, refresh,
closed errors, strict file reads and rejection of fake or mixed-clock adapters.
Native wiring tests are not native credential or IAM evidence. Synthetic JWTs
cannot qualify signature verification or deployed permissions.

The original failed tests and corrected results are retained under
`target/v52-cloud-credentials/`. Two regressions found missing unexpected-error
sanitization and mixed offline clocks. One initial deadline assertion expected a
wrapper code where the shared exchange emits a phase-specific code; the final
test checks a delayed OIDC response and proves the lock wait consumes its budget.

Final local validation passes **671 V5.2 Python tests in 228.078 seconds**, all
**61 combined V5.2/V5.1 credential tests in 21.868 seconds**, and **30 CI
classification tests in 43.288 seconds**. The full suite uses the actual local
UID, preserving installer ownership guards. Documentation contract, changed local
links/fences, Python AST, shell syntax and whitespace checks pass. No Maven or
whole engine-history/cloud workload was rerun; synthetic unit PASS output remains
test-fixture output rather than new workload evidence.

The native credential object has no provider mutation authority. The current
V5.2 provider guard still admits only its concrete offline HTTP adapter. Next
connect independently admitted scoped native storage/resource capabilities,
owned IAP and actual guest boot/user/mount observations, then complete whole
members, independent aggregation and protected operator entry. The existing
33 histories, one-source/sequence rule and manual-first cleanup policy remain.
