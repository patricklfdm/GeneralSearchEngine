# V5.1 Phase 6C3C30 — independent cleanup state review

**Status:** accepted through PR #266/#267, corrected master
`9243bc31dc3727a132b50740430426b3512fc5c8`.
[Exact-master CI 36785256345](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36785256345)
passed all 29 jobs on attempt 1, including the owned complete experiment gate.
The original master CI `36774917431` failure remains retained with its
[outbound admission correction](PHASE_6_LOCAL_PERFORMANCE.md#pr-266-master-failure-unsent-outbound-admission).
[6C3C29](PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md) is accepted through PR #264/#265
and exact-master CI `36756473536`, attempt 1, all 29 jobs. Identity enablement,
workflow deployment, cleanup execution and paid experiments remain separate.

## Why another observation is needed

The cleanup entry's `PASS` alone does not distinguish an empty lease from the
reclamation of an interrupted attempt. Its own absence report is also not an
independent observation. The [new read-only collector and reviewer](../../../scripts/v51/cloud_cleanup_observation.py)
records native state before and after a run and compares it to the entry result.
It never calls the reconciler, modifies a resource or dispatches a workflow.

| Review case | Required independent state |
| --- | --- |
| `NO_LEASE` | Lease absent on both sides; unchanged ledger; no pending reservation; no resource claim |
| `ACTIVE_OR_GRACE` | Run occurred before expiry plus grace; `WAITING`; unchanged lease generation, ledger, retained context/completion and resource observations |
| `EXPIRED_ABSENCE_CONFIRMED` | Run occurred after expiry plus grace; original operations resolved; every attempted name and resolved numeric ID absent; lease released; correct terminal ledger/completion; original charges retained |

An expired reservation with no create intent can be finalized with zero resource
observations. The result records the number of attempted and previously present
resources, so it cannot be presented as a real resource-deletion test. A pending
ledger reservation without a lease blocks the empty-state review even if the
cleanup entry itself returned `PASS` for no lease.

## Fixed read-only collection

The CLI uses the repository's fixed configuration, current checkout SHA and a
hash of the collector's own bytes. Its generic HTTP API permits only GET on the
fixed Google endpoints. An additional wrapper requires GET even for offline test
inputs and caps all calls at one 180-second collection deadline. No configuration,
clock, credential endpoint, resource name or deletion override is exposed.
The existing active gcloud credential supplies read access; the collector does
not switch accounts or impersonate a cleanup identity. Raw credentials and
provider exception text are never retained.

Collection reads generation-bound native lease/ledger objects. If a lease exists,
it reads that request's retained context and completion, resolves each attempted
original insert operation, and inspects both the intended name and known numeric
ID. Provider shape/ownership validation remains in the established adapter.
Finally it rereads the retained objects and control generations; a change or
unavailable read returns `BLOCKED`. A 403 is never interpreted as a 404.

The after observation takes the original before snapshot as its reference. It
continues checking that original inventory even after the lease was deleted, and
rejects a different active request. No project-wide resource listing or arbitrary
caller-selected inventory is used. Only the observed state is collected; active
cloud resources can still change after the sample.

The same collector can be exercised with an offline HTTP model in unit tests;
those records carry `execution=offline-cleanup-observation`. A review requires
both observations to share their execution domain and collector hash. JSON hashes
bind local files to each other, not to a trusted external signer.

## Commands for a separately approved real validation

The first command is read-only and can be used before activation:

```bash
python3 -m scripts.v51.cloud_cleanup_observation capture \
  --output target/v51-cleanup-validation/before
```

After a separately approved manual/scheduled cleanup run completes, keep the same
checkout and collector bytes, download that exact run's diagnostics, then:

```bash
python3 -m scripts.v51.cloud_cleanup_observation capture \
  --before target/v51-cleanup-validation/before/observation.json \
  --output target/v51-cleanup-validation/after
python3 -m scripts.v51.cloud_cleanup_observation review \
  --before target/v51-cleanup-validation/before/observation.json \
  --after target/v51-cleanup-validation/after/observation.json \
  --entry target/v51-cleanup-validation/downloaded/reconciliation \
  --output target/v51-cleanup-validation/review
```

All output directories are create-only. The `--entry` directory is the formal
entry's directory containing `binding.json` and `receipt.json`, not its nested
reconciliation receipt. The before snapshot must finish before the GitHub job
starts; the after snapshot must begin after the job ends. Before/after timestamps
are local clock observations, so correct UTC clock synchronization matters.

The reviewer fetches the latest run, exact attempt, its jobs, then the latest run
again. It verifies the original repository/owner, master source, workflow/event,
trigger-specific service account/provider/environment, completed successful run,
sole cleanup job and successful identity/auth/reconciliation/retention steps.
A rerun, fork, skipped step, changed source or binding from another run blocks review.
No dispatch or cloud request is made by the review command.

The terminal ledger must equal the prior history plus exactly the appropriate
finish event (or remain unchanged if already terminal), with the retained
completion hash. Cleanup-created completions must be `FAIL`; a previously retained
successful owner's completion is preserved. Original operation IDs cannot change,
missing operation history cannot prove absence, and a reused name cannot stand
in for an original numeric resource. Receipt absence checks must match the new
independent observations for every attempted resource.

## What STATE_MATCH does and does not establish

`STATE_MATCH` means the supplied snapshots, entry receipt and observed GitHub run
are consistent under these rules. Every result retains
`artifactProvenanceVerified=false`, `effectiveIamQualified=false`,
`activationAllowed=false`, `cleanupReady=false`, `paidAdmission=false`,
`paidCloud=false` and `fullRemoteQualification=false`.

The reviewer does **not** authenticate the provenance of locally supplied JSON,
verify that the downloaded bytes match GitHub's artifact digest, inspect deployed
workflow bytes, prove the acting cloud principal from an audit log, or establish
an IAM permission boundary. An offline fixture or edited local snapshot cannot
be promoted to admission by this tool. Historical state comparisons also do not
establish current cleanup freshness. The remaining admission gate must perform
those checks independently.

In particular, absence after a run does not identify who deleted a resource.
Retain provider audit evidence for the exact operation/resource ID and principal;
Compute documents its methods and audit categories in the
[audit logging reference](https://docs.cloud.google.com/compute/docs/logging/audit-logging).
If that evidence is unavailable, retain the uncertainty instead of declaring a
real deletion or permission-denial case qualified. No destructive negative is
injected into a running experiment by this collector.

## IAM admission scope amendment — 2026-09-30

**Operator-authorized scope change; accepted through PR #268/#269**, master
`c209383a510ae785244003b8778e5e193cdaf255`,
[CI 36804323832](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36804323832)
attempt 1, all 29 jobs. Original failed evidence remains retained.
This amendment supersedes the earlier requirement to read organization/folder
allow and deny policies before cleanup enablement. It applies to V5.1 only;
published V5.0 acceptance and evidence remain unchanged. The operator authorized
keeping necessary permissions without enabling unnecessary privileges.

The project remains `gse-benchmark` / `266952534277`, under organization
`821373826893` (`uci.edu`). The retained organization read denials remain genuine
observations. Ancestor policies are **UNASSESSED**, not absent or approved.
Optional authorized ancestor-policy information may inform the review, but its
absence or read denial alone does not block deployment, qualification or paid
admission. No account/project migration or organization read/admin role is required
by this amendment. Existing role contents, grants, identities and enable states
are unchanged; this is not authorization to deploy or enable cloud identities.

The bounded review follows the [V5.0 permission-check boundary](../v5.0/PHASE_6_CLOUD_RUNNER.md)
while independently qualifying the new V5.1 actors and native control objects:

| Requirement | Admission rule |
| --- | --- |
| Explicit configuration | Fresh exact project/bucket/account bindings, role permissions, no user keys, WIF repository/ref/workflow/event/environment restrictions and expected enable states must match. Missing/denied required reads or drift still block. |
| Actual workflow identity | Check required access using the observer, runner or trigger-specific cleanup account actually used by that workflow. An operator's access or another version/trigger's success cannot substitute. Retain identity/source/configuration/time and exact queried scopes with the observations. |
| Necessary access | Verify the permissions needed for that identity's real path, including Compute operations and GCS access at the relevant object scopes. Missing permissions, provider denial, unavailable or malformed checks block qualification. No broader grant is added to make a check green. |
| Forbidden access | Cleanup must reject topology creation, guest mutation, IAM changes/key creation and deletion of attempt evidence or objects outside its mutable control scope. Read-only observer probes must reject writes; runner checks preserve its frozen role/scope boundary. Probe without performing destructive forbidden actions. |
| Real cleanup | Independently qualify active/grace WAITING, expired exact-ID cleanup, generation conflicts, name reuse, ambiguous/lost operations, failure retention and original charges. A successful credential exchange or empty-lease PASS cannot qualify the full path. |
| Paid readiness | Preserve fresh manual-or-scheduled cleanup evidence, complete remote qualification, exact-source CI, quota/image/network/retention checks, cumulative budget, current pricing, exact-request confirmation and user-triggered execution. |

V5.1 cleanup may create/replace the **exact lease and ledger** and append attempt
completion/cleanup evidence. Replacing a GCS control object requires create and
delete permission. Unlike V5.0 cleanup, V5.1 appends a terminal ledger event;
a blanket denial of ledger replacement would break that required path. Deleting
attempt evidence stays forbidden. Retained authority, expiry plus grace, original
operation/numeric IDs, generation conditions, immutable completion and append-only
ledger validation continue to guard every mutation.

Bounded positive/negative probes establish only the tested identities, permissions,
resources and observation times. They do not prove absence of every inherited or
resource-level grant; [allow policies can be inherited](https://docs.cloud.google.com/iam/docs/resource-hierarchy-access-control).
Keep this limitation visible. If available observations reveal a grant that
violates a required boundary, it must still be resolved; optional ancestor reads
are not permission to ignore known violations.

Existing `effectiveIamQualified=false` fields remain false: these configuration,
entry and state-review receipts do not establish a comprehensive IAM audit. That
flag is not a separate ancestor-read prerequisite. Do not replace it with true,
change an unavailable read to an empty policy, or interpret the amendment as
`activationAllowed`, `cleanupReady`, `paidAdmission` or full Phase 6 acceptance.
The generated preflight report lists this limitation separately from remaining
required checks. The next [permission precheck candidate](PHASE_6_IDENTITY_PERMISSIONS.md)
adds diagnostic project/bucket queries. Actual-identity execution, object-scope
checks and real provider qualification remain **pending**.

Local validation: 98 focused tests passed. The complete preflight gate passed
its 80 tests, 13 provider/source negatives and 16 identity negatives, and generated
and validated the revised deployment review package. Before/after comparison
confirms unchanged role/grant payloads, 45 staging commands, cleanup enable/disable
commands and workflow bytes. The previously approved 33-file package is intact.
Review logs and comparisons are retained in `target/v51-iam-scope/`; protected
acceptance of the amendment is recorded above.

## Current read-only evidence and remaining validation

The exact-source CI checker accepted `36756473536` attempt 1. Fresh deployment
readback returned `CONFIGURATION_MATCH` in staged state: all three accounts,
pools and providers remain disabled. A genuine GET-only baseline sample found
both V5.1 control objects absent (`active.json` and `ledger.json`). This says
nothing about resources outside that namespace and is not a cleanup execution.

Retained local evidence: `target/v51-cleanup-qualification-review/accepted-ci.json`,
`staged/` and `live-before/`. The capture used the candidate collector hash and the
master checkout as its source base; it is not corrected-source protected acceptance.
The preflight gate exercises the new collector/reviewer against offline native
states, including failures, stale/replaced identities, lost insert acknowledgements,
ledger changes, generation movement, denied reads and missing resources/operations.

After PR #267, the exact-source/attempt checker accepted corrected master
`9243bc31dc3727a132b50740430426b3512fc5c8`, CI `36785256345` attempt 1, all
29 jobs and the executed owned-experiment step. The source-bound observations
and receipt are retained in `target/v51-c30-acceptance/ci-observations.json` and
`ci-receipt.json`. A fresh read-only project/ancestor inspection still reports the
same direct organization parent and denied organization allow/deny reads; the
project deny listing is empty. `iam-reads.json` and its raw outputs retain these
observations. Fresh `staged/receipt.json` readback returned `CONFIGURATION_MATCH`:
all nine account/pool/provider disable states remain true, and the explicit
trust, grants and environments match. No identity or workflow was changed by
this acceptance review.

Next: refresh explicit configuration review, then separately authorize the
prepared workflow/identity deployment and bounded real-provider qualification.
Verify actual-identity required and forbidden permissions before readiness. Capture
both successful and rejected cases, verify artifact/audit provenance, and establish
fresh manual or scheduled cleanup readiness before paid admission. The fixture's
allocation, pricing and exact-request approval remain separate from these reads.
