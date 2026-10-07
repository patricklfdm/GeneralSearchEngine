# V5.1 native guest volume and package preparation

**Status:** accepted through PR #291 at master
`70b452348832d6c2803870ae1b3ec74409e43ece`,
[exact-master CI 37411762406](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37411762406)
attempt 2, all 36 jobs successful. The rerun does not diagnose attempt 1.
The preceding
[resource/IAP entry](PHASE_6_RUNNER_RESOURCE_ENTRY.md) is accepted through PR #290,
master `5cf4bf10efb2df7b084ffee7f297877c7a494dee`,
[exact-master CI 37400113526](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37400113526)
attempt 2, all 36 jobs successful. That result does not diagnose attempt 1 or
establish actual Compute/IAP permissions.

## Entry and authority

`cloud_runner_guest_setup.prepare_native` joins fresh request admission, resource
creation, pinned IAP identity, data-volume setup and original CI package transfer
in one invocation. It has no injected transport, account, target, command, clock
or backend argument. There is no CLI or workflow caller for this entry yet.

The [native experiment timing amendment](PHASE_6_PREPARATION_BUDGET.md) gives the
complete chain one 1800-second preparation deadline, including archive verification,
credential exchange and all three guests. Plan/preflight freshness still gates
the first lease mutation. Admitted preparation does not expire with the approval
window. The 5400-second lease and 1080-second grace are unchanged.
The [guest deadline propagation correction](PHASE_6_PREPARATION_BUDGET.md#guest-deadline-propagation-correction)
passed PR #297 / exact-master CI `37552754929`, attempt 1 (36 jobs):
native volume/package/session receivers select that same
1800-second profile, including installed-package and source/bootstrap checks.
Ordinary helper/package paths remain limited to 600 seconds. The original clock
and consumed deadline cannot be renewed, including after a lost response.
Admitted run `37555787624` completed all three volume/package/session stages;
source preparation then failed at a separate directory/configuration boundary.
The [source-producer correction](PHASE_6_SOURCE_PRODUCER.md#native-source-preparation-correction)
preserves the same clocks and strict persistent-service roots.
Before and after each native connection, the controller verifies the retained
lease generation/content, reserved ledger, provider numeric VM/disk identities,
attachments and pinned host key. It uses the same admitted Runner credential;
an unexpired token may be reused only if it covers the original command deadline.
Temporary token files and isolated gcloud configuration stay outside evidence.

Native requests and volume/package receipts have distinct schemas. The existing
offline root, volume and package entry guards stay closed to native requests.
Shared private algorithms do not grant authority on their own. Guest receipts
describe native receiver operations without claiming paid execution; the outer
Runner receipt records the actual native/offline domain.

## One-shot volume setup

The controller sends its own compressed, closed module set through pinned SSH to
`sudo -n -u root -g root -- /usr/bin/python3 -I`. It does not import a helper from
an unverified archive or user-writable staging directory. The trusted receiver
requires root real/effective UID/GID, the exact non-root invoking account, and
metadata matching the numeric instance ID and attempt SSH access. Project SSH
keys remain blocked and OS Login disabled for this approved access profile.

Only `clock`, `prepare`, `query` and `check` are accepted. The fixed claim parent
is `/var/lib/gse-v51-native-volume`, owned by root with mode 0700 and protected
ancestors. An exclusive claim and durable request/deadline precede observation
and every write. A changed deadline, request or boot identity cannot resume it.

The existing independent Linux observations check the boot ancestry, data-device
alias, whole writable 100 GiB disk, blank signatures, absent partitions/mounts,
unchanged device mapping and safe target before formatting. Writes remain the
fixed mkdir, `mkfs.ext4` without force, mount with `nodev,nosuid`, chown and chmod
sequence. Each command has a forced intent. Readiness rechecks UUID, device,
major/minor, ownership and mount options against the original receipt.

A lost SSH reply causes queries of the original claim only. An interrupted
format/mount is FAILED or UNCERTAIN; it never authorizes reformatting. The
boot-bound guest deadline is mapped once from the remaining controller budget
after the clock round trip and cannot be renewed by reconnection.

## Package transfer

The controller rereads the admitted original `package.zip`, verifies its original
SHA-256, extracts the bounded tar, and independently checks archive, manifest,
build and workload hashes. It does not select an unbound sidecar tar. Only these
authenticated bytes reach the three guests.

The native package descriptor binds the volume request, startup digest, mount
UUID/device/owner and full source/build/package identity. Each receiver call runs
unprivileged, checks exact account/metadata, then observes the data mount through
filesystem stat, `findmnt` and `lsblk` before and after the transfer operation.
The fixed destination is `/mnt/gse-v51`; a missing or replaced mount fails before
writing package data. It is not a fallback directory on the boot disk.

The existing 1 MiB part and 256 MiB archive bounds, exclusive part/install claims,
part hashes, whole-archive hash and source-controlled safe unpacker are reused.
Mutations are submitted once; lost replies query their retained receipts. Partial
parts and interrupted installation are not resumed. Native actions are limited
to clock/begin/part/query/finish: service, source, producer and bootstrap execution
remain unavailable through this receiver.

## Preparation connection reuse

The [second paid-run review](PHASE_6_NATIVE_RUNNER_ENTRY.md#second-native-run-and-preparation-connections--2026-10-06)
records the preparation deadline failure and local correction. Native preparation
now scopes one foreground SSH master to each admitted numeric VM ID, including
subsequent initial session/source preparation. Every existing command retains its
individual input/output bounds and full identity/mount/content checks. Private
credentials cover the original deadline and are isolated from ambient gcloud
configuration. Target, client key or host pin drift rejects reuse.

A broken connection never replays its command. Missing control sockets cannot
fall back to a fresh network submission; protocol receipt queries may establish
a new pinned master under the same deadline. Scope exit kills/reaps every master
and its IAP proxy and removes private files before cleanup or measurement. The
closed retained inventory adds only `iap-preparation.json` with numeric identities,
connection/command counts and timing; it contains no private credentials.

## Result and next integration

`GUEST_PACKAGES_READY` is PARTIAL. The lease/reservation remain active, and
`engineWorkloadExecuted` and `fullRemoteQualification` remain false. Node request,
startup, package, readiness and connection records are retained alongside the
existing safe failure phase/type and resource-ID/intent diagnostics.

Successful preparation does not complete or refund the ledger. Active manual/scheduled cleanup remains WAITING;
eligible independent expiry cleanup removes only the retained identities and
preserves failed charges. The [owner failure continuation](PHASE_6_OWNER_FAILURE_CLEANUP.md)
now has a local immediate-cleanup and immutable-retention candidate. The same
batch adds [native owned experiment integration](PHASE_6_NATIVE_OWNED_EXPERIMENT.md)
through a separate fixed entry; protected CI and paid workflow review remain open. Actual image/IAP/disk/package behavior still
needs an approved user-triggered cloud experiment. Phase 6 remains open.

## Validation scope

The new tests exercise real claim/deadline, disk parser and transfer algorithms
against modeled OS/provider boundaries. Coverage includes three complete guest
installations, lost format replies, torn claims, changed boot/deadline, boot/used
disks, alias/UUID drift, metadata/account mismatch, changed original archives,
corrupt parts and failed node-two installation. The latter is replayed through
fresh-process active and expired cleanup, retaining the synthetic USD 5 charge.
Trusted receiver source also loads in an isolated Python process without repository
imports. These checks do not execute `sudo`, open host block devices or use GCP.

The suite is included in Python storage and the existing focused storage gate;
no new CI job or Maven build is added. Retained local logs and validation index
are under `target/v51-native-guest-setup/`. Its protected acceptance is recorded
above; the subsequent owner-failure candidate requires its own protected CI.
