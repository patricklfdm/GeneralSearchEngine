# V5.2 Phase 6AW original CI and build provenance

This stage connects the [prepared input checks](PHASE_6_PREPARED_INPUTS.md) to a
fixed read-only GitHub collector. It checks the current master source and the
original shared-build artifact. Its result remains
`BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED`: it creates no provider capability,
resource, lease, approval or workload result.

## Temporary V5.2 cloud admission policy

The operator explicitly suspended the **whole master full-CI completion/pass**
prerequisite for V5.2 cloud experiments. `scripts.v52.cloud_ci.REQUIRE_FULL_CI`
is currently `False`. Preparation and original Runner admission therefore require
only a successful exact-source build producer and all of that job's required
steps, including the original build and upload. Other jobs may
still be running, fail, be cancelled or be skipped without blocking admission.
This policy does not change normal CI triggers, Required, V5.1 cloud admission,
release checks, workload acceptance, cleanup, permissions or operator approval.

The producer and original artifact must still exist. After skipping normal CI,
the operator can use the separate manual build below. A missing, failed, cancelled,
skipped or unfinished producer blocks admission. Local JARs cannot replace the
original authenticated artifact.

The collector brackets its observations with the current master SHA. It reads
both workflow run inventories for that exact source and prefers the latest
`v52-cloud-build.yml` manual run. If that source has no manual build, it selects
the latest `ci.yml` run (master push, manual or schedule). A failed/pending manual
producer never falls back to CI or an older green build. It never selects a PR
build. A new selected run, changed attempt, different source/repository, changed
producer execution or invalid build/upload step still rejects. Unrelated job and
overall-run status transitions during collection are allowed.

The source-controlled registry still validates the complete workflow structure,
names, matrices and shared-build contract. The current workflow, registry,
manual build workflow, release workflow and two shared-build composite actions are compared with
GitHub's source bytes and Git blob hashes. Repository and owner IDs stay pinned.

Receipts use `BUILD_CI_VERIFIED_NOT_ADMITTED`, `fullCiRequired: false`, and a
one-job verification digest. Raw complete API inventories remain retained, but
are not certified as successful full CI. Public Runner summaries also expose
`fullCiRequired: false`. The inspection also records the selected `workflow`.
Source/build provenance is revalidated at preparation
and original execution; no copied PASS receipt grants admission.

### Restoring the full-CI prerequisite

Set `REQUIRE_FULL_CI = True` in a reviewed source change. The original complete
CI validator remains available and tested: it requires a completed green latest
run, all registered jobs/required steps, and stable complete job inventories.
There is no workflow input or environment override. Retained build-only evidence
cannot assert full-CI verification after restoring the policy. Fresh preparation
must use the restored source and its regular CI build; the standalone workflow
cannot substitute for full CI under that policy. This temporary admission exception
does not close any pending full-CI or release qualification.

All lists are paginated, checked for changing totals, truncation and duplicate
IDs, and bounded at 1,000 records. Filtered run searches reject the 1,000-record
boundary because GitHub caps those searches. This follows the documented
[workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
and [explicit-attempt job API](https://docs.github.com/en/rest/actions/workflow-jobs).

## Independent manual build

After the workflow is merged into master, run:

```bash
gh workflow run v52-cloud-build.yml --ref master
```

`V5.2 Cloud Build` only accepts manual dispatch and its job only executes on
master. It uses a GitHub-hosted Ubuntu runner with read-only repository permission;
it has no cloud environment, WIF token permission or GCP operation. It checks out
the dispatch SHA, runs the existing Maven reactor `clean package` with Java tests,
and uses `scripts.ci_v51_bundle` to prepare and create the original manifest and
archive. It does not execute the long regression or cloud experiments. The build
job has a 60-minute execution limit; cloud experiment time/cost budgets remain soft.

The workflow is generated from the current regular CI producer by
`python3 -m scripts.v52.cloud_build_workflow`. Contract tests reject drift in
commands, toolchain, pinned actions, master restriction or permissions. Both
producers retain the same artifact format and internal step names. The independent
workflow retains its bundle, Java test reports, provenance and infrastructure
attempt logs for 90 days, including failure diagnostics where available.

Wait for `V5.2 cloud build` to succeed, then obtain recent manual cleanup PASS
and prepare/run the selected member. One build can serve all fifteen execution units of the
same source/sequence; do not rebuild between preparation and execution. A newer
manual run or attempt changes selected provenance and requires fresh preparation.
This workflow does not disable ordinary push/PR CI or change branch protection;
any operator-approved CI skip/bypass is a separate repository operation.

## Original artifact and producing attempt

The producers are `V5.1 verification build` in `ci.yml` (which already builds
V5.2) and `V5.2 cloud build` in the standalone workflow. Their artifact remains
`v51-verification-build-<source>-attempt-<original-attempt>`. The collector finds
exactly one artifact in that accepted build's original upload interval. It
requires the exact run/source/repository, an unexpired artifact and its API
SHA-256 digest; it never downloads an arbitrary URL from a supplied receipt.

A partial CI rerun can carry a successful build from an earlier attempt whose
overall result failed. That original attempt is queried separately. The original
build job must itself have succeeded with the same steps and execution times.
When GitHub presents a new copied Job ID, the original earlier attempt, runner
identity and creation ordering must also match. The copied job is not described
as a new build. These checks preserve the existing V5.1 carried-build contract.

The retained original ZIP must match both its API size and digest. Its inventory
is exactly two regular files: `manifest.json` and `build.tar.gz`. Duplicate,
linked, encrypted, unexpected and oversized entries reject before arbitrary
extraction. The build manifest, original archive, every member and executed-test
report prerequisites are then checked by `cloud_inputs` against the separately
observed clean checkout and Java binding. A local JAR or copied PASS receipt is
not a replacement for the original artifact bytes. Artifact metadata/listing and
the source/producer observation are repeated after download to detect changes.

The [GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts?apiVersion=2022-11-28)
provides the digest, expiry and fixed artifact-ID download endpoint. The adapter
uses that endpoint through `gh api --method GET`; it does not accept a caller's
download host, token, transport, observation or clock in its native entry.

## Bounded reads and retained diagnostics

Each JSON read allows at most three 30-second exchanges within one fixed
100-second deadline and a 16 MiB streamed bound per response.
The single original ZIP download has a 300-second deadline and its exact API
size bound, at most 288 MiB. Its expanded build archive retains the existing
256 MiB bound. The fixed client permits at most 256 physical requests, including
download attempts. A failed subprocess is stopped and reaped, with partial output retained.
These are individual read/decoder limits, not a hard whole-experiment duration
or a change to soft cost/time policy.

An individual read-only GET may make at most three attempts for HTTP
408/429/500/502/503/504 or recognized transient transport failures. A JSON
exchange timeout may retry within the remaining read window. The 1-second and
2-second backoffs and all attempts share the original 100/300-second JSON/ZIP
deadline; an exhausted total deadline is terminal. Credential-context reads
continue to use only their caller's original remaining deadline. Every attempt
counts toward the request bound and keeps its own partial body and closed request receipt. Downloads
publish only a complete single response and never concatenate partial bodies.
Authentication/authorization failures, 404, unknown failures, byte bounds,
invalid JSON, incomplete successful downloads and all source/attempt/hash/
inventory validation failures exit without retry. Rate-limit responses do not
start a blind retry loop. No entire collection, workflow or cloud operation is
retried by this client. Existing cleanup, prepared-artifact and runner-provenance
readers inherit this transport behavior while retaining their own path allowlists.

The client drains stdout and stderr concurrently. Stderr has a 16 KiB memory
bound and is discarded after classification. HTTP diagnostics recognize the
CLI's closed status suffix or plain HTTP status; unknown formats fail closed
([GitHub CLI API implementation](https://github.com/cli/cli/blob/trunk/pkg/cmd/api/api.go)).
Raw exception messages, credentials, signed URLs and stderr never enter public
progress or diagnostic receipts. Only a request kind, ordinal, attempt count,
closed reason/stop code, HTTP status, allotted/elapsed seconds and received
byte count are exposed. The [read-retry incident and contract](PHASE_6_READ_RETRIES.md#github-source-read-timeout-recovery)
record the two source-read stalls that motivated separating exchange and total
JSON deadlines; repeated source/attempt checks remain mandatory.

Use a fresh ignored output directory on the exact clean master checkout, with
the same Java toolchain as the shared build:

```bash
python3 -m scripts.v52.cloud_artifacts --source "$(git rev-parse HEAD)" \
  --output target/v52-github-provenance-new
```

This requires existing GitHub read access and does not run CI, download cloud
credentials or contact GCP. The local source is checked before and after reads.
The output retains raw API responses, original ZIP, repeated observations,
original producer identity and inspection results. Failure retains a closed
`V52_PROVENANCE_<PHASE>_REJECTED` code without copying exception text into the
failure receipt. The last owned check's module and line identify a failed
validation without copying its exception text or locals. The operator's existing
diagnostic artifact and summary expose the nested original-build subphase and
these safe details, including failures in the independent preparation replay.
Diagnostic retention failure does not replace the original exception. Existing
output directories are never overwritten. Replay of
a retained collection is an integrity check; it does not establish freshness or
provider admission, and a failed collection cannot be replayed as success.

### Repeated preparation failures on 2026-10-20

Original prepare runs `39486934560`, `39487956554` and `39488959713` all reported
only `V52_PREPARE_ORIGINAL_BUILD_REJECTED` on source
`be4aa3e1d3f1434cd811735ba98456bad1b700c1`. Their public diagnostics did not retain
the nested check or HTTP response, so their exact causes remain unproven.
A local read of the exact-attempt jobs endpoint observed `Server Error`; a later
complete read-only collector replay passed the 62-job CI attempt and original
build artifact checks. That replay used the authenticated manifest's hosted
Java binding; it did not execute hosted Temurin or establish native admission.
The change adds actionable diagnostics and bounded transient read retries; it
does not claim that all three original failures had the same network cause.

## Validation and next connection

The existing measurement unit gate adds `test_cloud_ci` and
`test_cloud_artifacts`. Tests use synthetic API records, original archive bytes
from the local build fixture and owned local read subprocesses. Coverage includes
all current CI jobs, source/attempt changes, carried builds, complete pagination,
artifact substitution, unsafe ZIPs, post-download drift, bounded reads and
sanitized failure receipts. No current-source GitHub provenance or Java workload
execution is claimed by those fixtures.

The retained first test run includes one incorrect fixture assumption about
original/copied Job IDs; that assertion was corrected while preserving the
original-inventory binding. Two additional tests reproduced unrelated repository
metadata causing false drift and an unescaped workflow filename in the GET path
allowlist; both reject/accept the intended inputs after correction. All original
failure logs remain under `target/v52-cloud-provenance/`.

Final local validation passes **799 V5.2 Python tests in 317.027 seconds**,
**64 existing CI/producer-contract tests in 48.850 seconds**, and the **43 new
targeted tests in 1.658 seconds**. The full suite uses the actual local UID,
preserving installer ownership guards. The frozen executable-source index stays
unchanged during testing. Documentation contract, 195 local links, Python AST,
shell syntax, CLI help and whitespace checks pass; all original gate commands
remain, with only the two new unit modules appended. No Maven build, actual
engine measurement, GitHub API request or cloud credential exchange ran here.

Next connect fresh necessary provider permissions, project/network/image and
manual-cleanup observations to this original provenance, prepared approval and
concrete native owner. Owned IAP/guest identity, all whole members and independent
set qualification remain required. Actual protected CI and cloud execution stay
operator-triggered after push and merge.
