# V5.2 Phase 6BB native IAP and guest identity

This stage connects [the native Runner resource scope](PHASE_6_NATIVE_RUNNER.md)
to owned private SSH routes. It does not format disks, install the runtime, run an
engine history or certify a cloud member.

## Authority and credential ownership

`Session.open_guests(key, output)` accepts the original attempt's private-key file
and an evidence directory. It creates the three routes itself from current exact
provider observations. Offline owners, caller-supplied clients, copied host facts
and cleanup-role APIs cannot enter this factory. `cloud_identity` now derives its
ledger domain and observation scope from the concrete validated provider API;
previous offline behavior remains offline.

Every node's numeric VM ID, boot/data disk identities, attachments, private address
and published Ed25519 host key are observed on both sides of the original host-key
read. The current ACTIVE lease and pending charge must match the stable allocation.
Only a missing host key is a readiness condition; denial, malformed keys and ID
changes fail. Pending observations have an original finite allowance, not a new
experiment duration cap.
A native loopback target selects a 240-second SSH connection allowance for its IAP
admission; existing local targets retain 10 seconds. Endpoint/command deadlines
still bound each original exchange, so this option cannot extend them.

Before the SDK process exists, admission permits at most two attempts, each
bounded by 90 seconds and the same original 240-second connection deadline, with
one interruptible one-second backoff and 59 seconds left for SDK/SSH startup after
two complete attempts. Direct identity observations also allow 90 seconds; the
original host-key readiness ceiling remains 300 seconds. Only typed timeouts, plain provider
connection interruptions and the exact credential-context `DEADLINE` code permit
another attempt. Each attempt repeats ownership, resource identity and fresh
credential checks, releasing locks and removing its private directory first.
Denials, changed identities/leases, malformed replies and unknown failures stop
immediately. An SDK process is started at most once; its errors and all business
operations are outside this retry loop. The original 30-second half-close drain
and running stream lifetimes are unchanged.

Queue and identity-observation expiry now raise `TimeoutError` instead of a
generic validation error. The scoped HTTP adapter distinguishes late successful
responses from explicit HTTP denials; a late denial cannot trigger timeout retry.
The private diagnostic and public summary retain closed admission phases, attempt
counts, elapsed/phase milliseconds and allowlisted source module/line locations.
Credential/provider error codes survive projection. No exception message, token,
SDK stderr, arbitrary path or raw request is exported.

Each route listens on an exclusively owned ephemeral loopback port. A new local
SSH connection creates exactly one SDK stdin tunnel to the original VM's SSH port,
with explicit project/zone and a fresh runner-role token. Before starting it, the
owner rechecks source/run credentials, lease/charge and provider identity, including
a new provider observation after token refresh. Credential files and SDK config
are private and removed after the process is reaped. The child receives a closed
environment without ambient credentials, ADC, impersonation, API overrides or
GitHub tokens.

The [SDK command reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/start-iap-tunnel)
describes the IAP forwarding entry. The installed SDK's SSH stdin implementation
and credential loader were also inspected: access-token files are loaded into
credential objects, so replacing a file is not proof that a running SDK process
has refreshed. A fresh process per accepted SSH connection avoids that assumption.
The source/version observations are retained in the local validation directory.
No SDK cloud command was executed during this implementation's validation.

## Original streams and shutdown

The bridge forwards each byte once, with bounded input/output buffers and bounded
diagnostics. It owns every socket, child process and process group. A finite
original connection allowance covers admission/authentication and initial remote
data; it is not applied as a duration cap after the stream starts. TCP half-close
still drains the original response. New queries may open new connections through
the existing original-result protocols; the bridge never repeats a business
request, a detached launch or engine measurement. Per-node concurrent and total
connection bounds prevent an unbounded subprocess queue.

Authentication and identity errors fail the route scope. A transient connection
loss is recorded with a closed code and does not automatically start another SDK
process. Raw stderr, provider bodies and token values never enter retained channel
records. Existing control-layer retry/failure thresholds still govern original
queries. Host-key or local-key changes and renewal/ownership failure close active
routes. A background watcher checks local ownership/pins and periodically checks
the durable lease and charge; every new connection also performs its own checks.

The Runner closes guest routes before stopping renewal and deleting resources.
Failure to close a guest scope is retained and cannot bypass fenced resource
cleanup. A failed route close still attempts all other route closes. Existing
evidence directories are never overwritten by the cleanup of a rejected open;
diagnostics are restricted to the directory actually created by this scope. Failed context entry closes the acquired guest scope. Neither closing a
route nor successful resource deletion can create a workload PASS.

## Actual guest identity and remaining mount boundary

A fixed standalone Python probe is sent over pinned SSH. It accepts only the
expected instance ID, private address and original attempt's public SSH identity.
It uses bounded reads of fixed metadata URLs, rejects redirects and environment
proxies, and compares effective UID/GID with the unprivileged invoking account.
It observes the Linux boot UUID. The controller checks provider identity before
and after the probe and requires distinct boot IDs, private addresses, VM IDs and
host keys across all three nodes. Successful observations also form a session
baseline: reopening routes for another whole history cannot silently accept a
changed guest boot, UID or provider identity under the same resource owner.

`GUEST_IDENTITIES_VERIFIED_NOT_QUALIFIED` retains the original allocation,
provider/guest observations and public pinned routes. `binding(group_id)` repeats
those checks and produces the expected `remoteHostDomains`, private peer topology
and SSH route identity for the existing installed Placement. It remains identity
data: mounted storage and installed package validation must precede workload use.
The native entry has no CLI or workflow trigger in this stage.

Next connect one-shot, exact-data-device preparation and mount verification,
followed by the source-bound Python installation and complete histories through
Placement. Keep initialization claims and query-only recovery on lost replies;
never reformat or repeat original launches. Then finish immutable qualified member
retention, independent five-member set replay and the protected Runner/operator
entry. Time/cost budgets remain soft, while source/approval freshness, lease/grace,
connection exchanges, decoder and resource bounds remain enforced.

## Validation scope

Local tests exercise real TCP/pipe forwarding, byte integrity, half-close,
subprocess termination, bounded diagnostics, terminal/transient failures and a
real isolated OpenSSH server with strict pinned host verification. Native factory
tests execute the actual native admission/control, provider and credential logic
with external GitHub/GCP/credential/SSH I/O replaced at explicit local boundaries.
They do not establish effective cloud IAM, three real VMs, mounted storage or paid
acceptance. All logs and source hashes are retained under
`target/v52-native-guests/`, including the initial StrictModes test-path failure.

The completed Python 3.11 regression run passes all 948 V5.2 tests in 1070.913
seconds, including 28 new probe, route and native-factory cases. The 96 related
CI/V5.1 transport, startup and process-generation tests pass in 48.696 seconds
against the same executable source. AST, shell syntax, 201 local documentation
links, the documentation contract and whitespace checks pass. All 1,846 frozen
executable file hashes remain unchanged through the completed run.

An earlier full-suite session ended without a retained terminal summary; its
exit status and cause are unknown. Its incomplete log remains separate. Only the
new complete run supplies the 948-test result. These checks establish local
implementation behavior, not live provider or workload qualification.
