# V5.1 Phase 6C3C4: authenticated helper delivery

**Status:** accepted through [PR #235](https://github.com/patricklfdm/GeneralSearchEngine/pull/235),
master `d40d7d8be1320a3e989ab551536715f4e47795be`. PR CI `36204539682` and
[exact-master CI `36206334728`](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36206334728)
passed; master attempt 1 executed all 27 jobs successfully, including the provider
SSH qualification and packaged guest gates. The preceding
[owned startup slice](PHASE_6_GUEST_STARTUP.md) remains accepted through PR #234 /
CI `36185893530` attempt 2, with its original failed measurement retained.

The sections below describe the accepted 6C3C4 scope. The subsequent
[6C3C5 deadline candidate](PHASE_6_GUEST_DEADLINES.md) replaces the shared-clock
transport assumption; its local checks do not extend this historical acceptance.

## Package and authenticated receiver

[cloud_bundle.py](../../../scripts/v51/cloud_bundle.py) now includes the volume
helper and all its closed dependencies in the existing source/build-bound guest
package. It also builds a separate startup-helper.json payload for delivery before
mount setup. The payload has exactly 20 files, including both frozen plans, and
is bounded to 512 KiB encoded and decoded. No credentials, JVMs, arbitrary archive
paths, symlinks, executable modes or extra files enter this helper inventory.
The complete JVM package remains a separate, larger artifact.

[guest_delivery.py](../../../scripts/v51/guest_delivery.py) binds the payload
digest/size to source, workload, complete guest bundle, attempt, node, numeric
instance/data-disk IDs and the request's public access descriptor. The trusted
controller supplies these identities; a receipt is not provider attestation.
The standalone [receiver](../../../scripts/v51/guest_delivery_receiver.py) is
sent through the authenticated SSH command. It verifies the entire input digest
before decoding or materializing any payload member. It imports no payload code
while installing or checking the retained inventory.

A private parent and exact executing UID are required. Linked, writable or foreign
ancestors are rejected (a root-owned sticky temporary ancestor is allowed).
An exclusive attempt/node directory and forced request consume the installation
before input is read. A missing/partial claim remains uncertain. Truncated input,
digest/source/plan mismatch, storage failure or expiry produces a retained failed
receipt where possible; another submission only observes that original state.
It never fills a partial directory or replaces an installed helper.

Every member and directory is forced before the atomic terminal receipt. Successful
queries recheck the closed file/directory set, ownership, hardlinks and bytes.
Only a complete verified installation can enter the closed helper startup check,
and its inventory is checked again afterwards. Python bytecode generation is
disabled so importing the helper cannot silently mutate its payload.
This assumes a trusted controller and guest owner; it is not a hostile-root sandbox.

## SSH, disconnects and deadline

The native IAP argument builder and the loopback test share explicit Ed25519
host-key pinning, instance-ID HostKeyAlias, isolated known-host files, batch mode
and one explicit identity. Agent authentication/forwarding, host-key updates and
connection multiplexing are disabled. The loopback subclass only replaces the
IAP route with 127.0.0.1 and a private ephemeral port; it does not relax host checking.
See the OpenSSH [host verification options](https://man.openbsd.org/ssh_config)
and [server authentication/forwarding controls](https://man.openbsd.org/sshd_config).

The sender submits once. A lost response permits only fresh connections querying
the same descriptor until the original controller deadline. NOT_FOUND and
UNCERTAIN do not authorize resubmission. A late, foreign, malformed or altered
receipt cannot pass. Query responses are bounded to 4096 bytes.

This qualification uses a single host's monotonic clock, including the SSH receiver.
Connection setup and all queries consume the same absolute deadline. Different
hosts' monotonic clocks are not interchangeable: cross-host budget translation
must be implemented and qualified before the IAP endpoint is opened.
Native IAP execution remains explicitly disabled.

## Qualification and CI

The existing provider gate runs receiver/transport tests, existing HTTP/startup
fixtures, and real local OpenSSH delivery:

~~~bash
scripts/verify-v51-phase6-cloud-provider.sh
~~~

The SSH qualification has a separate 120-second process backstop and retains
its helper input, descriptor, server log, consumed installations and receipt in
the existing provider artifact. Private client/host keys live outside that
artifact tree and are removed on ordinary success/failure/TERM cleanup. Abrupt
runner destruction is not an application cleanup guarantee.

| Case | Required observation |
| --- | --- |
| Complete delivery | Pinned SSH, verified installation, relocated helper import and identical query |
| Lost install reply | Exactly one install and a query of the original terminal receipt |
| Truncated transfer | Failed consumed installation; full resubmission cannot reinstall |
| Wrong host key | Host verification fails before any receiver directory exists |
| Wrong client key | Public-key authentication fails before any receiver directory exists |
| Changed transfer bytes | Digest failure before payload materialization/execution |
| Changed installed helper | Query/check refuses changed bytes before execution |
| Expired controller deadline | No SSH install or local claim |

Unit negatives additionally cover wrong source/workload/owner, descriptor drift,
closed file sets, linked/writable paths, hardlinks, extra/missing/changed files,
partial claims, terminal publication, malformed JSON, late receipts and missing
receipt deadlines. They verify the native cloud endpoint remains disabled.

CI prepares the standard OpenSSH server dependency and its /run/sshd runtime
directory on the disposable runner if needed. The qualification daemon itself
runs as the existing job user, binds only loopback, uses a generated configuration
and ephemeral keys, and is reaped on exit. No user account, ~/.ssh file or host
SSH configuration is edited by the qualification. The existing Cloud runner
(no GCP) job and Required dependency are reused; its ceiling rises from five to
ten minutes for dependency setup and three bounded qualifications. No new job or
cloud permission is introduced.

## Scope and next integration

Receipts explicitly report realSshExecuted=true, privilegedExecution=false,
realBlockDeviceWritten=false, paidCloud=false and fullRemoteQualification=false.
The standalone SSH fixture uses a synthetic complete-bundle binding; actual
source/build qualification remains the existing guest package gate. This is not
a three-VM, IAP, sudo, real-disk or engine workload qualification.

The helper is ready for authenticated distribution and its native write entry
points remain closed. Root-owned installation/admission, different-host deadlines,
complete package/source transfer and mounted-volume service startup must still
be connected under the owned controller, followed by remote faults/full physical
and history validation, trusted preflight and V5.1 workflows. Paid experiments
remain manually triggered by the user after exact-request confirmation.
Frozen workload/timing thresholds, engine Java, resource limits, ledger and paid
budget are unchanged.
