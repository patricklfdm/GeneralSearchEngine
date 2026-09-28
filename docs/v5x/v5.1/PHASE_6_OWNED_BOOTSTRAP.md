# V5.1 Phase 6C3C10 — owned bootstrap before service admission

**Status:** implementation candidate based on accepted PR #240, master
`0ef49cb8f5f6c793b9fe03db4b4069dd04e059ac`. The preceding
[guest evidence slice](PHASE_6_GUEST_EVIDENCE.md) passed exact-master CI
`36378226619` attempt 1 (all 27 jobs). This candidate requires its own protected Linux
qualification and exact-master acceptance. No full 6C or paid admission is claimed.

PR #241's first CI run [36384429085](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36384429085)
failed the owned bootstrap step on merge source
`4e3d91651ef7221237adeb8d92ad15bbbdd4ebd6` (PR head `704ea1e`). The backing
directory used default mkdir permissions, so the bind covered the private cell
with a non-private directory. The receiver rejected the first package clock
request with `delivery private parent`; no package or bootstrap mutation was
admitted. Original artifact `10953898421` retains the failure, successful modeled
cleanup, verified retention and released lease. Required failed as a consequence;
the other 25 jobs passed. This is a qualification implementation defect, not a
workload timing failure or a reason to retry the unchanged source.

The correction creates each backing directory with `0700` and checks ownership,
mode and absence of symlinks on every connection. Existing directories and claims
are never chmodded or replaced. Portable regressions reproduce the old receiver
rejection under umasks `0022` and `0002`, then verify admission, unchanged reconnect
claims and rejection of permission drift or links. Receiver admission, timing
limits and workload calls remain unchanged. Fresh Linux CI is still required.

## Cut point and preparation order

[Owned services](PHASE_6_OWNED_SERVICES.md) previously connected owned resource and
volume preparation to complete package delivery and idle Python services. This
slice optionally admits the existing [initial bootstrap](PHASE_6_GUEST_BOOTSTRAP.md)
between all three package installations and the first service launch. It does
not connect the owned runner's diagnostic probe to timed engine workload cells.

The [bootstrap coordinator](../../../scripts/v51/guest_owned_bootstrap.py) requires
three exact attempt/node/package bindings, one replicated mode, one group and
topology, and identical absolute cell paths. It freshly rechecks provider, host
key and mounted-volume observations before source production, before/after each
import, before/after each local seal, and through the existing service admission.
All three imports finish before any seal; all three seals must agree before any
service starts. Observations at these boundaries do not lock out host changes.

The producer exports only the three immutable V4.4 backup files and three topology
files, with the existing 64 MiB bound and closed binary-part manifests. Each
receiver uses its verified installed package, exclusively creates its cell, imports
the original bytes and invokes the existing public bootstrap API locally. The
filesystem-bound authority seals never cross views. Never-started sibling voters
and operation receipts remain in diagnostics, with only the assigned voter at a
live path. Manifest, genesis and source SHA-256 identities must agree across the
group; the source identity must also match the independently retained export.

## Original deadline and consumed operations

[The trusted package receiver](../../../scripts/v51/guest_package_receiver.py)
verifies the installation before importing packaged bootstrap code. Install,
seal and read-only queries must use the retained package's original boot-bound
deadline ticket. Configurations must bind the installed source/attempt/node,
package manifest and exact cell under the admitted mount. The response binds the
action, complete request and deadline digests. Renewal, reboot, late responses,
changed packages and foreign configurations fail closed.

The controller forces a separate intent before each mutation. It submits each
install or seal at most once. Lost replies permit only queries of original claims
and verified ready inventories, under the same deadline. An empty but consumed
cell, incomplete import or partial local bootstrap stays uncertain or fails; none
is permission to retry the mutation. A completed seal is rechecked against the
actual local authority inventory before its original identity is returned.

[The source adapter](../../../scripts/v51/guest_bootstrap_source.py) likewise
starts one preparation command and, after a lost reply, queries that command's
original store. The source and local public bootstrap JVMs share the original
600-second owned preparation deadline; no reconnect starts a new budget. The
existing 90-second per-process ceiling is also preserved. Service stop, failed
attempt charging, immutable upload/read-back and exact-ID cleanup continue through
the existing runner, including when bootstrap prevents every service launch.

## Qualification and evidence boundaries

The adapter is explicitly `qualification-shared-source-paths`. Source parts are
read from retained local paths outside the mounted guest cell. Their binary cloud
transport is **not implemented**. Install/seal/query control does travel over
real pinned loopback SSH through the complete-package receiver. Provider and block
observations remain fixtures. Native SSH/IAP, provider mutations and paid admission
remain disabled.

The new optional [owned gate](../../../scripts/v51/guest_owned_qualification.py)
uses a separate producer and three receiver mount views at the same sealed path.
It preserves native UIDs because the receiver authenticates ancestor ownership.
CI explicitly permits a private sudo mount namespace, which drops to the original
user before the command. This changes no host mount and writes no block device;
network and PIDs remain shared. It is filesystem-layout qualification, not host
security isolation or cloud performance evidence.

The gate discards every completed install/seal response and requires exactly one
mutation plus two queries (precheck and recovery) for each. It then starts/stops
three idle services and retains original bootstrap, cleanup and accounting
receipts. `publicBootstrapVerified=true` is separate from
`engineWorkloadExecuted=false`: source preparation/public bootstrap JVMs run, but
no timed workload JVM or measured cell does. `paidCloud=false` and
`fullRemoteQualification=false` remain mandatory.

Closed controller retention adds 15 bootstrap JSON files, each at most 256 KiB:
plan, source metadata, group receipt, six intents and six operation records.
Five extra readiness boundaries per member add 15 service JSON files, bringing
the optional service inventory to 46 plus the 15 bootstrap records. Unknown files
and symlinks are rejected. The full qualification artifact separately retains the
producer/receiver backing directories, partial claims and local authority bytes.
Private SSH keys remain outside the artifact tree.

The foundation lane reuses its existing exact-source build/package and adds one
720-second qualification guard plus `v51-owned-bootstrap-${sha}` retention for
seven days at compression level 1. Required jobs, job dependencies, workload
windows, 5400-second attempt ceiling and 1080-second cleanup grace are unchanged.

```bash
python3 -m unittest scripts.v51.test_guest_owned_bootstrap scripts.v51.test_guest_bootstrap
# Linux, pinned toolchain and a complete package from this exact checkout:
python3 -m scripts.v51.guest_owned_qualification target/v51-owned-bootstrap \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" \
  --bootstrap --allow-sudo-namespace
```

Portable tests explicitly model Linux boot/process identity, package contents and
controller/provider state. They exercise real package/import checks, consumed
claims, lost replies, disagreement, deadlines and cleanup, but do not qualify
actual SSH, mount namespaces or Java bootstrap on macOS. Fresh Linux evidence is
required before acceptance; historical runs are not relabelled as this candidate.

Next implement native bounded source transfer and connect complete owned workload
windows, faults and independent physical history/backup/restore validation. The
[cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md),
[local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md), frozen workload,
[guest deadline contract](PHASE_6_GUEST_DEADLINES.md) and existing root/package
admission contracts continue to govern that work. Trusted preflight and separate
V5.1 workflows remain later prerequisites for separately confirmed paid execution.
