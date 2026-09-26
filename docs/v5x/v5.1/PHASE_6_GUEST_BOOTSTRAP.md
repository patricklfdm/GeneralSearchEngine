# V5.1 Phase 6C3C2: exact-path bootstrap and startup preparation

**Status:** accepted through PR #233, master
`d27da43086406384ab41cab6704541015aa0a1bf`, exact-master CI `36149275698`
(all 27 jobs, including isolated bootstrap). The preceding
[guest service slice](PHASE_6_GUEST_SERVICE.md) was accepted through PR #232 and
CI `36124423253`. The following [owned startup slice](PHASE_6_GUEST_STARTUP.md)
was accepted through PR #234 / master CI 36185893530 attempt 2. The subsequent
[helper delivery slice](PHASE_6_GUEST_DELIVERY.md) is accepted through PR #235 /
master CI `36206334728`. The [deadline candidate](PHASE_6_GUEST_DEADLINES.md) follows it.
Full 6C3C and paid admission remain open.

## Source distribution and local public bootstrap

[guest_bootstrap.py](../../../scripts/v51/guest_bootstrap.py) distributes only the
immutable V4.4 source backup and exact topology/configuration. Bootstrap seals
bind the parent filesystem identity as well as absolute paths. Copying a seal to
a different host is therefore invalid, even at the same path. The isolated
qualification exposed this restriction; its original failed bytes remain at
`target/v51-bootstrap-review/qualified/isolated/`. No path or seal is rewritten and
no production admission check is relaxed.

The transfer descriptor binds source, complete package digest, package manifest,
frozen workload, attempt, node, mode, group, endpoints and absolute cell path.
The controller supplies its independently retained digest. Binary part digests
and the complete closed source inventory are checked before publication. Existing
authority, runtime generations, operation directories and credentials are never
imported as bootstrap state.

Source installation requires an empty destination. An exclusive staging directory
and forced claim consume it before extraction; files/directories are forced before
the ready descriptor. Partial installation cannot be overwritten or retried into
that destination. Each receiver then makes a separate forced local-bootstrap claim
and invokes the **existing public bootstrap API on its own filesystem** against
that same backup, group, endpoints and frozen configuration.

The public API prepares all three offline voters. Each guest keeps its assigned
voter at the live path and retains the two never-started sibling copies plus the
operation receipt under its private agent diagnostics. Their bytes are retained,
not deleted or rewritten, and they are never launched. This preserves the local
parent identity in the assigned voter's original seal. The controller checks exact
manifest, genesis and source digests across all receivers **before starting any
voter**. A mismatch fails the cell. V4.4 local mode only restores the imported backup.

Before the first JVM start, the guest verifies the import and local-bootstrap
claims, topology, complete initial inventories, and absence of neighbours at live
paths. Java's public admission independently checks its locally produced seal.
This is initial bootstrap only; partial local bootstrap is retained and cannot be
silently repeated, and runtime recovery/replacement remains a separate protocol.

## Qualification in independent filesystem views

The existing real packaged guest qualification also supports `--isolated`.
[guest_isolation.py](../../../scripts/v51/guest_isolation.py) prepares one source
per mode in a producer mount namespace, distributes seven source bundles across the three
modes (one local control, three configured and three automatic voters), and mounts
each retained backing directory at the same cell path for local sealing and startup. Each voter sees
only its own storage at the paths used by its JVM configuration. Independent
filesystems no longer accidentally satisfy a missing peer-file dependency.

The original same-filesystem qualification remains. The isolated gate exercises
the same three real JVM modes, frozen 10-call experiment warmup, discarded submit
reply, original receipt queries, graceful shutdown and binary collection/replay.
It preserves the bounds and does not retry workload calls. Both gates reuse the
same verified build and package in the existing foundation/runtime CI job.

Linux mount namespaces share loopback networking and process identities. They
are a file-layout qualification, not VM, network, disk-performance or hostile-user
isolation. The gate prefers an unprivileged user/mount namespace. CI explicitly
permits a sudo mount-namespace fallback where unprivileged namespaces are blocked;
that helper makes mounts private, mounts only retained qualification directories,
and drops to the original user before executing the guest CLI. It never formats a
disk or changes the host mount table. The selected backend is retained in receipts.

```bash
python3 -m scripts.v51.guest_qualification target/v51-guest-bootstrap \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" --isolated
```

All qualification receipts remain `paidCloud=false`, `fullRemoteQualification=false`.
Incomplete process runs and install claims remain retained. The collection still
qualifies closed guest journals; full authority/history validation is unfinished.

## Attempt SSH access and volume planning

[guest_setup.py](../../../scripts/v51/guest_setup.py) generates a fresh Ed25519
key in an exclusive private directory. Only the public key and attempt-derived
username form an access descriptor whose digest is bound to the version-2
control request. The base provider configuration stays unchanged across a sequence;
attempt credentials rotate without weakening its existing identity check. Version-1
requests still work without guest access. Unbound or mismatched access is rejected. Private keys never enter the guest package or evidence inventory.
The adapter rejects an access attempt different from its request. Instance
metadata blocks project keys, disables OS Login and enables guest attributes; its
exact key set and values are checked during resource inspection.

The provider reads the Ed25519 host key through authenticated
[getGuestAttributes](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/getGuestAttributes),
bracketed by exact numeric-instance checks under one deadline. A replaced instance,
missing/duplicate key or malformed wire key fails. The resulting known-hosts file
is private, non-overwriting and bound to the existing SSH builder's instance-ID
alias. This follows Google's
[guest host-key publication](https://docs.cloud.google.com/solutions/connecting-securely)
and [instance SSH metadata](https://docs.cloud.google.com/compute/docs/connect/add-ssh-keys)
contracts. Guest attributes rely on the trusted image/guest agent; they are not
hardware attestation. Live IAP/SSH execution remains disabled.

A pure data-volume planner checks instance/disk identity fields, attempt/node,
100-GiB size, the assigned stable by-id device, a distinct boot device, and an empty,
writable, unmounted disk without partitions or signatures. It emits a bounded
ext4/mount/ownership command plan without force-format flags. It does **not** execute
those commands or infer that observations are trustworthy. Live provider/disk
observation, privileged execution, mountpoint creation and post-mount verification
remain required before the planner can be used on GCP. The current tests feed
explicit observations and exercise wrong identity, boot disk, signatures, readonly,
mounted, nonempty and size failures. They do not claim actual block-device testing.

## Remaining integration

The [accepted owned startup slice](PHASE_6_GUEST_STARTUP.md) adds provider fact reads,
Linux observation parsing and a one-shot offline startup path in the controller.
Real SSH/privileged delivery remains open, followed by remote failure cells, combined multi-guest evidence
budgets and independent physical/history replay. Afterwards integrate trusted
image/IAM/quota/retention/GitHub/pricing observations, V5.1 WIF/environment and the
separate runner/manual/scheduled cleanup workflows. Provider mutations and live
SSH remain disabled; paid experiments are manually triggered by the user after
exact-request confirmation. No runtime Java, storage format, sealed workload,
resource limit or paid-budget change is included here.
