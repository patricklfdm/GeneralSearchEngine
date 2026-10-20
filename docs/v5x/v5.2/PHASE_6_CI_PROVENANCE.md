# V5.2 Phase 6AW original CI and build provenance

This stage connects the [prepared input checks](PHASE_6_PREPARED_INPUTS.md) to a
fixed read-only GitHub collector. It checks the current master source, complete
full CI and the original shared-build artifact. Its result remains
`BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED`: it creates no provider capability,
resource, lease, approval or workload result.

## Source and complete CI

`scripts.v52.cloud_ci` reuses the existing closed `ci_suites` parser and registry.
At this stage the 41 registered suites expand to 51 jobs, including the five
V5.2 lanes and the existing control jobs. Workflow names, matrices, shared-build
steps, Required, tiered dispatch and V5.1 consumers are unchanged.

The collector brackets its observations with the current master SHA. It selects
the latest CI run for that exact source and accepts only master push, manual or
scheduled full CI. A newer failed, cancelled or pending run blocks acceptance;
an earlier green run is not a fallback. PR, docs-only and integration runs cannot
substitute for the complete successful job set.

The latest run, exact attempt and repeated run/job inventories must agree. Every
expected job and unconditional verification step must have succeeded, with
consistent source, attempt and execution times. Composite actions retain their
visible caller-step names while the source contract checks their implementation.
The current workflow, registry, release workflow and two shared-build composite
actions are compared with GitHub's source bytes and Git blob hashes. Repository
and owner IDs are pinned; unrelated metadata such as repository stars is not an
execution identity.

All lists are paginated, checked for changing totals, truncation and duplicate
IDs, and bounded at 1,000 records. Filtered run searches reject the 1,000-record
boundary because GitHub caps those searches. This follows the documented
[workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
and [explicit-attempt job API](https://docs.github.com/en/rest/actions/workflow-jobs).

## Original artifact and producing attempt

The existing producer remains `V5.1 verification build`; it already builds
V5.2. Its artifact remains
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
the complete CI observation are repeated after download to detect changes.

The [GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts?apiVersion=2022-11-28)
provides the digest, expiry and fixed artifact-ID download endpoint. The adapter
uses that endpoint through `gh api --method GET`; it does not accept a caller's
download host, token, transport, observation or clock in its native entry.

## Bounded reads and retained diagnostics

Each JSON request has a 30-second exchange deadline and 16 MiB streamed bound.
The single original ZIP download has a 300-second deadline and its exact API
size bound, at most 288 MiB. Its expanded build archive retains the existing
256 MiB bound. The fixed client permits at most 256 physical requests, including
download attempts. A failed subprocess is stopped and reaped, with partial output retained.
These are individual read/decoder limits, not a hard whole-experiment duration
or a change to soft cost/time policy.

An individual read-only GET may make at most three attempts for HTTP
500/502/503/504 or recognized transient transport failures. The 1-second and
2-second backoffs and all attempts share the original 30/300-second deadline;
an exhausted deadline is terminal. Every attempt counts toward the request
bound and keeps its own partial body and closed request receipt. Downloads
publish only a complete single response and never concatenate partial bodies.
Authentication/authorization failures, 404, 429, unknown failures, byte bounds,
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
closed reason/stop code and HTTP status are exposed.

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
