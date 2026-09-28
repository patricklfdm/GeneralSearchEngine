# V5.1 Phase 6C3C6 — root helper admission

**Status:** accepted through PR #237, master
`de3264cb41e594e10e641748d1cdd75fe7c3a8ad`, exact-master CI `36281785824`
attempt 1 (all 27 jobs successful, including evidence packing/upload).
This does not close full 6C3C/6C or paid admission.

## Controller and root boundary

[guest_root_admission.py](../../../scripts/v51/guest_root_admission.py) binds the
exact request, access descriptor, retained attempted instance/boot/data IDs, node,
source, workload, complete-bundle digest and helper bytes. Shared
[policy checks](../../../scripts/v51/guest_root_policy.py) reject extra fields,
caller-selected paths/commands and execution-enable flags. The pure plan and its
assessment remain `execution=offline-root-admission-only`, with privilege, native
writes, paid cloud and full qualification flags false: a plan is not an execution
capability or proof that a modeled observation occurred.

[guest_root.py](../../../scripts/v51/guest_root.py) sends trusted controller code
over the existing pinned SSH command using `sudo -n -u root -g root -- python3 -I`.
The receiver and its two dependencies travel in the authenticated command; no
receiver code is imported from the SSH user's writable staging area. Native cloud
routing remains disabled. An explicit offline adapter is required for qualification.

The [root receiver](../../../scripts/v51/guest_root_receiver.py) observes actual
real/effective UID/GID zero, the exact nonroot attempt account and sudo invoker,
fixed link-local instance/SSH metadata, and nonsymlink root-owned non-writable
ancestors. Metadata requests disable proxies and redirects, require the Google
response header and cap each response at 4096 bytes. Only the fixed instance ID,
SSH keys, block-project-ssh-keys and enable-oslogin metadata fields are read.

The destination parent is `/var/lib/gse-v51-helper`, owned by root with mode 0700.
Under it, `<attempt>-node-N.claim/admission.json` records the complete plan,
observation and original boot-bound deadline **before** payload consumption.
Verified helper bytes go to `<attempt>-node-N/`, through the existing closed
20-file receiver. Claims are exclusive and forced; partial/failed installations
are preserved. A crash between admission and installation is uncertainty, never
permission to resume or reinstall. Reconnection queries use the same plan and
deadline; a new clock sample cannot renew a consumed claim.

Only the verified helper's existing no-argument, no-write self-check executes.
Installed bytes are verified before and after it. Root operations retain the
original guest deadline, including a process alarm for stalled input/metadata.
Transport receipts bind the root plan, root UID, delivery and deadline. The startup
bridge rechecks provider facts before and after delivery and retains bounded
diagnostics before entering the existing offline volume adapter. No actual volume
formatting or mounted service execution is enabled by this slice.

## Qualification and evidence

The isolated root qualification runs eleven receiver cases: success, lost receipt,
metadata drift, writable ancestor, symlink parent, account drift, partial claim,
SIGKILL after durable admission, corrupt payload, changed installed bytes and a
changed deadline ticket. Negative cases require their specific rejection reason;
an unrelated process failure cannot qualify them. Three additional owned-controller
cases cover success, node-2 metadata rejection and lost install response. They
check no repeated installation, failure before the affected node's modeled format
or workload, retained/read-back diagnostics, exact-ID cleanup and the full charge.

[guest_root_isolation.py](../../../scripts/v51/guest_root_isolation.py) creates a
private mount namespace/chroot with recursively read-only system binds. Root file
operations and the helper subprocess are real; account and cloud metadata are
explicit fixtures. Local qualification uses mapped namespace root, without host
sudo. Hosted CI may use the explicitly authorized sudo namespace fallback, returning
only its private fixture tree to the original owner after unmounting the binds.
The exact-master job passed; its selected namespace backend is not inferred from
the job result alone. Host accounts, SSH configuration,
mount table and disks are untouched. This is qualification tooling, not a sandbox
for hostile code, and it is excluded from the deployable helper inventory.

The isolated receipt declares `namespaceRootExecuted=true`,
`metadataAndAccount=modeled-fixtures`, `realSshExecuted=false`, `paidCloud=false`,
`realBlockDeviceWritten=false`, `nativeWritesEnabled=false`, and
`fullRemoteQualification=false`. The existing ten-case loopback OpenSSH gate remains
separate; these results do not claim a real GCP/IAP/sudo round trip. Six pure modeled
admission/lifecycle cases remain as an independent policy layer.

Startup's diagnostic allowlist grows from 34 to 37 files by adding one closed
`root-node-N.json` per node, still at most 256 KiB per file. Private keys stay outside
evidence. Controller source hashes, dirty status, case receipts, transport failures
and original deadline tickets are retained by the existing provider artifact.

Provider evidence is uploaded as `v51-cloud-provider.tar.gz` inside that artifact.
Packing preserves symlinks as link metadata and never follows their targets; the
original fixture tree remains unchanged. This matters for the negative case whose
helper parent points to `/var`: after the chroot exits, a recursive artifact glob
would interpret that link against the runner host. Packing also runs after a failed
qualification; only a complete archive is published at the upload path.

PR #237 CI `36274635097` (merge source
`08d988d52b56aef10c6928e763e74afc1a0ad542`) completed the entire provider/root/SSH
qualification successfully, then failed artifact upload with `EACCES` while following
that fixture link into the runner's `/var/cache/apparmor`. The correction changes
evidence packaging, not root admission or workload logic. Corrected-source protected
CI `36281785824` subsequently passed the entire job, including packing and upload.
The original failed upload remains recorded; a successful test step alone is not
full job acceptance.

```bash
python3.11 -m unittest scripts.v51.test_guest_root_admission scripts.v51.test_guest_root
scripts/verify-v51-phase6-cloud-provider.sh
# Hosted Linux, explicit fallback if user namespaces are unavailable:
scripts/verify-v51-phase6-cloud-provider.sh --allow-sudo-namespace
```

## Existing delivery permission correction

Every intermediate payload directory now explicitly uses mode 0700. Previously
recursive mkdir applied it only to the final component; umask 0002 created 0775
intermediates and correctly triggered the receiver's ownership rejection. The
regression covers umasks 0000, 0002, 0022 and 0077. The SSH qualification's ancestor
also explicitly uses 0700. Ownership checks remain enforced and the receiver does
not alter the process-wide umask.

## Remaining Phase 6 work

The [6C3C7 slice](PHASE_6_PACKAGE_DELIVERY.md), subsequently accepted through
PR #238, connects complete source/build
package transfer and persistent services over loopback SSH. Mounted cloud startup,
distributed faults/oracles and evidence
budgets, then integrate trusted preflight and separate V5.1 workflows. Paid runs
retain exact-request confirmation and user-owned triggering. Java/POM versions,
frozen workloads, measurement retries and cloud admission are unchanged.
