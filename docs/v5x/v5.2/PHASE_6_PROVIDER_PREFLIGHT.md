# V5.2 Phase 6AX fixed provider preflight

This stage adds actual read-only wiring after
[original CI/build provenance](PHASE_6_CI_PROVENANCE.md). It observes provider
facts, diagnostic permissions and exact V5.2 control generations under the
dedicated V5.2 workflow credentials. Success remains
`PREFLIGHT_OBSERVED_NOT_ADMITTED`; no native mutation capability, cleanup approval,
resource or workload is created.

## Source and credential boundary

The native entry reads one fixed, tracked configuration path:
`docs/v5x/v5.2/cloud-provider.json`. Its schema is
`gse-v52-preflight-config-v1`, with `provider`, `projectNumber`, `layout` and
`policy` checked by the existing provider/ownership contracts. The file must
match the exact clean Git source before and after observation. There is no
caller-supplied configuration path, transport, clock, token or PASS receipt in the
native entry. This stage does not create that deployment configuration or claim
that any V5.2 identity is deployed; source review and protected workflows remain
required before this command can run against GCP.

`runner`, `manual` and optional `schedule` use their already defined dedicated
V5.2 identities, workflow paths, environments and exact run/attempt checks. Native
token exchange uses `NetworkCredentials`, never ADC or a gcloud account fallback.
Every refresh rechecks the original workflow invocation. The final observation
rechecks source and invocation, and the retained credential receipt must bind its
exact run/attempt to the original run-observation digest. Fixture observations
keep an explicit offline execution domain; they cannot be relabelled as native.

## Provider facts and available capacity

Runner reads the exact project, region, zone, machine type, disk type, network,
subnet and pinned image. Names, numeric resource IDs and self-links are checked.
The bucket's `projectNumber` is checked separately: Compute's project resource
ID is not treated as the Cloud project number. Region/zone must be UP, the subnet
must belong to the configured network/region with Private Google Access, and its
IPv4 range must be within RFC 1918 space with room for three nodes. Loopback,
link-local and unspecified ranges do not qualify.

The fixed image must keep its original name/ID, READY status and X86_64
architecture, and fit the requested boot disk. The existing image policy allows
DEPRECATED with a warning; OBSOLETE, DELETED, changed identity and replacement
selection reject. Queries project only needed fields; project-wide SSH metadata
and IAM policies are not collected.

Required capacity is derived from three copies of the observed machine and the
declared boot/data layout. E2 uses `CPUS`; N2 uses `N2_CPUS`, with the separate
global CPU limit also checked. The current reviewed disk policy is `pd-ssd`, with
SSD capacity, three VM slots and four firewall slots checked. Other machine
families/disk policies require an explicit policy extension. These checks do not
reserve capacity or guarantee zonal availability. The family distinction follows
the [Compute allocation quota documentation](https://docs.cloud.google.com/compute/resource-usage).

## Necessary permission diagnostics

Project probes request only the actual per-role adapter operations, together with
specific forbidden actions. Runner includes disk labels, attached-disk use,
instance labels/metadata/tags, guest attributes and the existing operation
reconciliation reads. Cleanup retains exact-resource deletion and operation
reconciliation but must not gain Runner's creation capabilities. The probes
reject broader IAM administration, service-account keys/attachment, project SSH
metadata and external-IP use. Organization/folder IAM reads are not required.

Bucket probes require bucket metadata access and reject unscoped object
read/list/create/update/delete and bucket administration. They do not establish
conditional access to an individual object. The fixed diagnostic routes use
[project testIamPermissions](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/testIamPermissions)
and [bucket testIamPermissions](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/testIamPermissions).
There is no invented object `testIamPermissions` endpoint, policy modification or
resource creation in this reader. Permission probes are diagnostic, not an
authorization decision or an exhaustive privilege audit.

Image permissions are not demanded across the experiment project when the image
lives elsewhere. The reader performs the exact image GET, leaving actual image
use for real-path qualification. It does not add `compute.images.list` merely to
call the separate diagnostic
[image permission endpoint](https://docs.cloud.google.cn/compute/docs/reference/rest/v1/images/testIamPermissions).
Conditional IAP, named control/evidence access, actual resource creation and
deletion still require their own owned-path qualification.

## Control state and retention

Both control keys are read before and after the provider queries. Existing
objects use metadata, a generation-selected/conditional body read and a second
metadata read under one original exchange deadline. Wrong namespace, domain,
content type, holds, truncation, changed metadata or generation reject. A 403 is
not interpreted as object absence. Returned 404 absence still does not prove
conditional object permissions.

Runner is blocked by any retained lease or pending reservation, including an
expired lease that still needs reconciliation. Manual/scheduled diagnostics can
inspect an active or historical native lease whose source/configuration predates
the current workflow; they do not rewrite it or claim cleanup PASS. Failed costs
remain in the ledger, and exceeding the configured cost budget only reports a
soft warning. The reader never writes, resets or releases control state.

Uniform bucket access is required. Bucket-wide retention/default holds must not
freeze mutable control. Delete lifecycle rules must be prefix-disjoint from the
V5.2 control history; an age threshold is not permission to lose that history.
Rules applying to the separate `v5.2-bounded-follower-reads/evidence/` prefix need
at least 30 days. Other namespaces can retain their own expiry policies. This
does not establish immutable evidence retention: lifecycle changes may take up
to 24 hours to propagate, as documented by
[Cloud Storage lifecycle management](https://docs.cloud.google.com/storage/docs/lifecycle).

## Bounded reads and diagnostics

The only POST is the fixed read-only Resource Manager permission query. All
other requests are fixed GETs. No arbitrary URL/body or resource mutation is
accepted. Each read has a 30-second original deadline, response-byte limits and
at most one refresh after 401, including for the diagnostic POST. Other errors
fail immediately; credentials refresh does not reset the deadline. Control
metadata/body/recheck share one deadline. Collection has no hard stage budget;
the final freshness requirement is 900 seconds, not permission to use stale facts.

The output directory must be new. Successful response bodies and exact generated
queries are retained without authorization headers. Error bodies are discarded;
closed phase/error codes, HTTP status and known credential codes are retained.
Partial reads are preserved, owned transports close on success/failure, and
existing evidence is never overwritten. A missing tracked configuration fails
before credentials are opened.

## Validation and remaining integration

`test_cloud_preflight` joins the existing measurement unit gate. It exercises
all three credential roles, synthetic provider facts and permissions, original
generation reads, soft cost handling and the fixed native entry with mocked
network IO. It does not query real GitHub/GCP, acquire real credentials or run a
Java workload. Initial and corrected results, source indices and two reproduced
review failures remain under `target/v52-cloud-preflight/`.

Final local validation passes **827 V5.2 Python tests in 317.243 seconds**,
**100 CI/V5.1 preflight/permission/image-policy tests in 136.971 seconds**, and
**28 targeted tests in 1.367 seconds**. The complete suite runs with the actual
local UID; installer ownership checks remain enforced. Executable source stays
unchanged during validation. Documentation contract, 197 local links, Python
AST, shell syntax, CLI help and whitespace checks pass. No original verification
command is removed. Workflow, Java, POM and frozen workload parameters are unchanged.

Recent actual manual reconciliation still must be collected independently;
schedule remains optional. Connect those results with fresh original CI/input
provenance, exact preparation review and a concrete native owner. Then qualify
owned IAP/guest identity, verified evidence retention, complete members and their
independent aggregate, and prepare the protected operator workflows. Deployment,
push/merge and paid execution remain separate from this local stage.
