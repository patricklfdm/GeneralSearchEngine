# V5.1 Phase 6C3C8 — owned startup and idle service admission

**Status:** implementation candidate on accepted PR #238 master
`ef7562bc60a0a15ab4202367c5e286fe6250cbdb`, exact-master CI `36302498537`
attempt 2 (27 jobs). This candidate still requires protected qualification.
Full 6C, native cloud execution, block writes and paid admission remain open.

## Owned preparation order

The [startup bridge](../../../scripts/v51/guest_startup.py) optionally connects the
existing volume preparation to [owned services](../../../scripts/v51/guest_owned_services.py).
The controller acquires its lease and reserves the full attempt charge before
allocating exact resources. All three volumes must finish preparation before any
package transfer. Each mount is then freshly observed against its retained startup
receipt: provider instance/data-disk identity, resolved device, major/minor numbers,
filesystem UUID, mount location/options, boot exclusion and unprivileged owner/mode.
Readiness issues read-only observations; it never repeats format or mount.

The controller verifies the complete source-bound package, workload, access
identity and build manifest, then delivers all three packages before starting any
service. It rechecks provider facts, the authenticated host key and the mount
before delivery, after delivery, before launch, after readiness and once more for
the complete group. A changed observation stops admission. These checks are
observations at explicit boundaries, not an atomic lock against host administration.

Every configuration binds its attempt/node, package manifest, group, private peer
addresses and frozen port. Each launch has a forced local intent before dispatch.
A lost launch response permits readiness queries only, requiring the exact
configuration hash and an observed process ID. Delivery and readiness share the
original preparation deadline; reconnect does not grant extra time. The default
package endpoint remains disabled. Only explicitly offline adapters can enter
this bridge; a local-path mapping is recorded when qualifying on one machine.

## Failure, retention and cleanup

The runner stops its workload probe, collects its diagnostics, then attempts to
stop every attempted service, including a launch with an uncertain reply. It
records one stop claim and sends at most one shutdown per member. A lost shutdown
reply permits status queries only. One shared 30-second stop allowance is bounded
by the current stage deadline. An interrupted stop claim cannot be silently
replayed. Service failures do not prevent exact-ID provider cleanup.

Collection failure still attempts service shutdown and startup-diagnostic retention.
If validation cannot enter its budget stage, shutdown and diagnostic retention are
attempted during cleanup under that existing stage deadline. The original lease,
control, preparation, cell, validation and cleanup accounting is unchanged.
Required upload/read-back failure preserves the lease for expired reconciliation;
a completed cleanup still requires exact absence checks. Failed attempts retain
the full reserved charge. A stop error remains a failed attempt even when provider
cleanup proves all resources absent.

The closed startup inventory adds at most 31 service JSON files (256 KiB each):
plan, completion, stop claim/result, and nine records per member. It retains
package descriptors, transfer diagnostics, launch intents, readiness, all six
mount/provider rechecks per node and stop outcomes. Private keys stay outside the
artifact tree. Unknown files and symlinks are rejected.

## Qualification

[Regressions](../../../scripts/v51/test_guest_owned_services.py) use the actual
package receiver and owned lifecycle with independent provider/block fixtures.
They cover mount/provider/key drift, source-bound delivery, lost transfer/start/stop
responses, partial launch, mismatched readiness, expired preparation and validation,
collection/upload failures and continued cleanup. Volume tests also reject a
replacement filesystem UUID and altered retained mount evidence.

[The retained gate](../../../scripts/v51/guest_owned_qualification.py) uses a real
loopback OpenSSH daemon, three separately installed complete packages and three
persistent idle Python services. It drives the owned runner through modeled
allocation/volume preparation, fresh admission, actual SSH delivery, readiness,
stop, immutable diagnostic retention, cleanup and terminal accounting. For each
member it discards the first completed part reply, final install reply, launch
reply and shutdown reply. Writes are not replayed. Exact observed PIDs are reaped.

This gate launches no workload JVM. Its probe cells are controller diagnostics,
not measured workload cells. It reports `realSshExecuted=true`,
`engineWorkloadExecuted=false`, `realBlockDeviceWritten=false`, `paidCloud=false`
and `fullRemoteQualification=false`. Provider IDs, accounts, disks and cloud
storage remain modeled; local directories explicitly map the three guest mounts.
The accepted three-mode JVM/service and isolated bootstrap gates remain separate.

The foundation job reuses its already built exact-source package, adds a
720-second outer guard and retains `v51-owned-services` for seven days with
compression level 1. Job topology, required results, docs-only classification,
Maven settings, frozen workloads and paid-cloud workflows are unchanged.

```bash
python3.11 -m unittest scripts.v51.test_guest_owned_services scripts.v51.test_guest_startup
# Requires a complete package built from this exact checkout and pinned toolchain:
python3.11 -m scripts.v51.guest_owned_qualification target/owned-services \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)"
```

Next connect distributed workload execution, faults and independent evidence
validation to the owned service set. Native mounted cloud execution, trusted
preflight, V5.1 workflow/configuration qualification and separately confirmed,
user-triggered paid experiments remain subsequent work.
