# V5.1 Phase 6C3C3: owned guest startup qualification

**Status:** accepted through PR #234, master
`79344fca6b447a3e77205be36d3d16e597d4bc23`, exact-master CI
[`36185893530`, attempt 2](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36185893530)
(all 27 jobs). Attempt 1's concurrent arrival spread exceeded the frozen 10 ms
limit (63.021587 ms in one burst, with 120 successful callbacks). That failed
measurement remains retained; the rerun establishes this execution's acceptance,
not a scheduling root cause. Full remote qualification and paid admission remain open.

## Provider facts and access

[Compute.guest_facts](../../../scripts/v51/cloud_gcp.py) accepts the retained
lease and its exact request, rather than a caller's asserted disk identity.
Each node needs three recorded, attempted resource IDs: instance, boot disk and
data disk. Two complete numeric-ID read passes under the original preparation
deadline validate ownership, pinned boot image, disk size/type, instance metadata,
private network and both directions of each attachment. The instance must be
RUNNING, disks READY, and each disk's sole user must be that instance. The resulting
private IP and resource identities must remain equal across passes. The adapter
retains the existing GET-only real-provider boundary.

[guest_startup.Prepare](../../../scripts/v51/guest_startup.py) first checks all
three nodes have distinct private IPs, instance IDs and disk IDs. It obtains each
Ed25519 host key through the existing authenticated guest-attribute query, pins
it to the instance ID and validates the native IAP SSH argument builder. The local
private key must have restricted permissions and reproduce the public key in the
request-bound access descriptor. Private key files stay outside retained evidence; the three public host pins are
retained before any modeled formatting.

Provider facts are rechecked before each guest, immediately before its formatting
phase, after its mount verification and once more across the complete group.
These are observations of a trusted guest/provider, not hardware attestation or
an atomic transaction against concurrent infrastructure changes. Privileged delivery
and real SSH admission are still disabled in this candidate.

## Read observations and bounded startup

[guest_volume.py](../../../scripts/v51/guest_volume.py) implements a read-only
Linux backend and a separate one-shot executor with an injected offline backend.
Native reads use explicit columns and bounded output from `lsblk`, `findmnt` and
`wipefs --no-act`, plus stable device-link resolution and the guest metadata
instance ID. No caller-provided `blank=true` flag can produce a startup plan.

The decoded observation must prove all of the following:

- The assigned `google-gse-data-N` link resolves to a dedicated whole disk of the
  frozen size; it differs from `google-gse-boot-N` and the root mount's verified
  boot ancestry. SCSI and NVMe whole-device paths are accepted.
- The data device has no partitions/holders, filesystem metadata, signatures,
  swap use or mounts. Device major/minor numbers and inventory names are unique.
- The mountpoint has no symlink, existing mount, nested mount or contents. An
  existing directory is root-owned and not writable by group/others; native
  inspection also checks its parent directories.
- Device aliases remain unchanged during inspection, and a second complete
  observation still matches immediately before writes.

The executor forces an exclusive claim before observation, and a separate intent
before every write. It emits only mountpoint creation when needed, ext4 creation
without force flags, `nodev,nosuid` mounting, numeric ownership and mode 0700.
Writes use the inspected whole-device path. Postconditions independently verify
major/minor identity, one exact mount, ext4 label/UUID/signatures, mount options,
ownership and mode. One deadline covers all observations and operations.

A lost format or mount response consumes the original path. A second call cannot
re-enter it, even after a successful receipt; no write is retried and no partial
filesystem is adopted as a fresh one. Failed claims, observations, write intents
and receipts remain available to the controller. This is not a hostile-root safety
boundary, nor a guarantee against concurrent hot-unplug. Real privileged writes
are rejected before claim creation; the native backend independently rejects write
commands. This stage qualifies control flow and parsing without formatting a host
or cloud disk.

The explicit column and multi-mount handling follow the
[lsblk interface](https://man7.org/linux/man-pages/man8/lsblk.8.html) and
[findmnt interface](https://man7.org/linux/man-pages/man8/findmnt.8.html).
Signature inspection follows
[wipefs](https://man7.org/linux/man-pages/man8/wipefs.8.html), and disk aliases follow
[Compute Engine persistent disk symlinks](https://docs.cloud.google.com/compute/docs/disks/disk-symlinks).
An unreadable or unsupported observation fails closed.

## Owned lifecycle and retained qualification

The existing [controller](../../../scripts/v51/cloud_runner.py) accepts an optional
qualified startup adapter after all 13 resources have retained create IDs and
before `probe.prepare`. Startup consumes the existing preparation budget. Its
failure still reaches stop, collection, exact-ID cleanup and terminal ledger
accounting. Immutable diagnostic uploads and read-back happen before lease release;
a failed startup never permits a workload cell. Existing callers without startup
keep their original behavior.

Startup retention is a closed set of at most 34 JSON files, each capped at 256 KiB.
Private keys and arbitrary directory contents cannot enter this inventory. The
existing provider gate and its always-uploaded artifact now include startup
qualification; no new job, dependency, Maven build, permission or credential is
introduced.

```bash
scripts/verify-v51-phase6-cloud-provider.sh
```

The independent HTTP/block-state fixtures cover nine retained scenarios:

| Scenario | Expected controller outcome | Formatting / cleanup |
| --- | --- | --- |
| Complete startup | PASS | Three once-only model formats; cleanup PASS |
| Wrong numeric disk response | FAIL | No model format; cleanup PASS |
| Boot device alias | FAIL | No format on the affected node; cleanup PASS |
| Existing signature | FAIL | No format on the affected node; cleanup PASS |
| Changing data alias | FAIL | No format on the affected node; cleanup PASS |
| Lost format response | FAIL | One affected-node format; no retry; cleanup PASS |
| Lost mount response | FAIL | One affected-node format/mount; no retry; cleanup PASS |
| Wrong mounted device | FAIL | Postcondition failure; cleanup PASS |
| Original deadline exhausted | FAIL | No next write or workload; cleanup PASS |

The wrong-ID fixture changes one numeric read response. It does not simulate a
foreign replacement being deleted: the original owned resources remain and are
cleaned by their recorded IDs. Existing controller tests separately reject cleanup
of foreign/reused IDs and retain the lease in that case. Every failed startup's
reservation remains charged; none resets or discounts the ledger.

Receipts explicitly report `paidCloud=false`, `realSshExecuted=false`,
`realBlockDeviceWritten=false` and `fullRemoteQualification=false`. Real local
Ed25519 generation/checking and durable diagnostic file writes execute. HTTP,
metadata, block-device operations and workload cells in this gate are fixtures.
Prior JVM/bootstrap qualification remains separate evidence.

## Remaining work

Deliver and verify the privileged helper on the pinned guest, implement and qualify
actual pinned SSH delivery/receipt queries under the owned controller, and connect
volume readiness to package/source distribution and persistent services. The subsequent [helper delivery candidate](PHASE_6_GUEST_DELIVERY.md) includes the
volume module in the source-bound package and qualifies authenticated loopback SSH
installation and original receipt queries. Keep real SSH
and provider mutations closed until these pieces and paid admission are integrated.
Then finish distributed failure cells, combined evidence budgets, full independent
physical/history replay, trusted preflight/configuration and separate V5.1
workflows. User-owned cloud triggering and exact-request confirmation remain the
paid execution boundary. No frozen workload, runtime, disk size, budget or retry
policy is changed here.
