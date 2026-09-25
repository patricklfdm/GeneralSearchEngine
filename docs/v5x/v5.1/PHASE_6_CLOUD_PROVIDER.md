# V5.1 Phase 6C3B: guest package and provider request adapters

**Status:** implementation candidate on master
`2db3ebb645907eaa8b02fa849302c35accb03ff4`, following PR #230. Its
[exact-master CI 36105310891](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36105310891)
accepted the [6C3A control-only gate](PHASE_6_CLOUD_CONTROL.md).
This batch requires its own protected CI. Full 6C and paid admission remain open.

## Scope and execution boundaries

The source-exact guest package contains five application JARs, three independently compiled
adapter classpaths, the frozen workload, published pins, verification-build
manifest and the pinned Temurin jlink runtime (including its own `jrt-fs.jar`). The provider adapters translate the
existing controller's operations into GCS/Compute HTTP requests. An offline HTTP
server double exercises those adapters through encoded URLs, request bodies,
status codes, operation objects and generations. Diagnostic guest commands still
use the actual local persistent command store and binary collection.

The HTTP qualification makes no network requests or credential calls. The actual
network transport permits only GET; POST and DELETE require the explicitly offline
transport. Real adapters also carry an unqualified execution tag rejected by the
controller. Neither a synthetic approval nor a CLI flag enables paid execution.
Guest code-source checks execute Java but do not execute an engine workload or
qualify multi-host behavior. All receipts retain `paidCloud=false`,
`fullRemoteQualification=false` and `engineWorkloadExecuted=false`.

## Immutable guest package

[cloud_bundle.py](../../../scripts/v51/cloud_bundle.py) validates the current
checkout/toolchain against the existing successful verification-build manifest,
then verifies candidate JAR and prerequisite test-report hashes. The three published
JARs retain the reviewed [published hashes](published-controls.json). Adapter
sources are compiled independently for V4.4 local, V5.0 configured and V5.1 automatic
mode; a shared classpath cannot accidentally substitute a candidate for a control.
No production JAR contains these probes.

The package binds source, checkout bytes, build manifest, adapter source digests,
complete file inventory, executable bits, JVM flags and workload bytes. Local dirty
builds remain explicitly marked. `guest.tar.gz` has its own SHA-256; the future
admission request must pin that complete archive digest, not just the JARs.
This is a verification package, not a released or signed artifact.

[cloud_package.py](../../../scripts/v51/cloud_package.py) authenticates the complete
archive before extraction, bounds compressed and unpacked bytes to 256 MiB and
members to 10,000, and rejects traversal, duplicates, links and nonregular entries.
It verifies every retained byte after relocation before a process may execute.
A failed extraction remains an unqualified directory. The standalone `guest.py`
uses only Python's standard library. Its launch entry points are closed to the
three reviewed workload adapters; it does not accept an arbitrary Java main class.
A launch is not cloud admission and does not provision resources.

The build gate moves the archive into a new temporary directory, runs the packaged
standalone verifier, then launches each isolated classpath with the packaged Java.
The Java probe checks exact vendor/runtime and actual public-class code sources.
The local control also checks that replication classes are absent. This detects
missing runtime modules and classpath/package errors at that startup boundary;
full remote engine startup, command wiring and lifecycle remain separate work.

## Provider request semantics

[cloud_gcp.py](../../../scripts/v51/cloud_gcp.py) accepts one closed configuration
bound into the request digest and one 13-resource inventory. The frozen machine,
zone, disk type and image selection remain unchanged. Each boot-disk insertion
checks the exact image name/ID/READY observation before POST. Instances are private,
use no attached service account, retain the fixed lifetime, and set disk
`autoDelete=false` so deleting an instance cannot implicitly delete a disk without
a separate ownership check. Guest SSH key installation is not enabled in this
candidate. Network/IAM/quota readiness belongs to the future trusted preflight.

GCS object creation uses `ifGenerationMatch=0`; updates/deletes carry the observed
generation. Metadata and media reads pin the same generation, so a concurrent
lease replacement cannot silently supply different bytes. JSON and binary parts
have separate content types and an 8-MiB object bound. Uploads require exact
read-back. Keys are confined to the separate V5.1 control prefix. These conditions
follow Google's [object insertion API](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/insert)
and [request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions).

Compute request IDs are deterministic nonzero UUIDs derived from the retained
intent. A lost POST response is never resubmitted: reconciliation queries the
original client operation ID and checks operation type, target, status and numeric
ID. Missing, pending, paginated or ambiguous operation results retain the lease.
Deletion first verifies ownership and the expected numeric identity, then addresses
the numeric ID rather than the reusable name, and verifies absence. There is no
fallback to a name-based DELETE. The official
[Compute v1 discovery document](https://www.googleapis.com/discovery/v1/apis/compute/v1/rest)
permits numeric identifiers in instance/firewall get/delete parameters and disk
get/delete patterns. The offline race test replaces a name between the identity
read and DELETE and proves that the replacement is untouched. Actual service
acceptance of these requests is **not established by the fake server**; a rejected
numeric request must fail closed during future provider qualification.

[cloud_http.py](../../../scripts/v51/cloud_http.py) bounds request/response time and
size, restricts hosts, rejects redirects, and omits credentials/response bodies
from errors. Tokens renew before their cached lifetime ends. An explicit GET 401
may renew once under its original deadline; mutations are submitted once even on
401. Interrupted writes remain unresolved for operation/generation inspection.
No general network, workload or measurement retry is introduced.

## Qualification and CI

```bash
scripts/verify-v51-phase6-cloud-provider.sh
python3 -m scripts.v51.cloud_bundle target/v51-guest-package \
  --source "$(git rev-parse HEAD)" \
  --build-manifest target/ci-v51-build/manifest.json
```

The second command requires exact-source verified build inputs and pinned Java.
CI reuses the restored verification build in `V5.1 foundation and runtime`;
packaging has a 240-second process backstop. `Cloud runner (no GCP)` runs the short
HTTP qualification with a 120-second backstop. Both always upload diagnostics.
No additional Maven build or Required job is added; docs-only behavior and all
existing verification steps remain unchanged.

Focused regressions cover conditional JSON/binary storage, metadata/media races,
namespace/configuration drift, token renewal, write non-replay, host/redirect
restrictions, bounded responses, original deadlines, operation mismatches,
name reuse during deletion, private resource shapes, image drift, live-adapter
rejection and package tampering. The five retained HTTP lifecycle cases cover
success, lost insertion reply, pending insertion, denied deletion and changed image.
A correctly rejected injected failure is qualification PASS, never a successful
workload member. Failed attempts retain their conservative charge; unresolved
cleanup holds the lease and active manual reconciliation remains WAITING.

Local results and commands are retained under `target/v51-cloud-provider-review/`.
Corrected-source protected CI remains required before accepting this candidate.

## Next integration

6C3C must wire the persistent JVM workload across the three real hosts, upload and
verify the immutable package before executing it, install attempt-specific SSH
access and data mounts, and exercise the actual remote command/collection transport
without blindly repeating commands. Trusted image/IAM/quota/retention/GitHub/pricing
observations, V5.1 WIF/environment configuration, separate manual and scheduled
cleanup workflows, and fresh exact-source qualification remain required before
paid admission can open. The historical image pin may need a separately reviewed
refresh if it is no longer available. Cloud experiments remain manually triggered
by the user after confirmation of the exact prepared request.
