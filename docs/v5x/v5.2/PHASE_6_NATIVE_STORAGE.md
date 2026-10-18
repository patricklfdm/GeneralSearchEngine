# V5.2 Phase 6BC native data volumes and installed Placement

This stage connects the [native guest scope](PHASE_6_NATIVE_GUESTS.md) to data
volume preparation, the existing immutable Python installation protocol and
whole-history `Placement`. It does not execute a cloud history or create a
qualified member PASS.

## Original authority and root entry

`Guests.prepare_storage(output)` consumes one storage preparation under its
original native `Session`. It requires the original admitted checkout, Java/input
proof and package bytes, ACTIVE ownership, numeric VM/boot/data disk IDs and the
observed guest boot/UID/GID. A replacement guest scope under the same Session may
use prepared storage only after repeating the original identity checks.

The controller sends fixed, compressed source over pinned SSH. The root receiver
imports only its transmitted guest identity helper and the standard library;
it never imports installed guest modules or accepts a shell command or output
path from a request. Before operations it checks actual root credentials, NSS
and sudo's original invoking account, boot UUID and bounded fixed metadata fields.
Provider identity and ownership are checked on both sides of each exchange.

The receiver reads the fixed data/boot device aliases, `lsblk`, `findmnt` and
read-only `wipefs`. It requires a separate whole writable data disk of the exact
admitted size, the admitted boot size and root filesystem ancestry ending at that
boot disk. Existing filesystems, signatures, child partitions, mounts/swap,
symlinks, changed aliases or unsafe target directories reject before formatting.
V5.1's fixed 100-GiB assumptions are not used to authorize V5.2 devices.

The exclusive root-owned initialization claim, original clock grant and original
process identity are fsynced before inspection or writes. A second complete blank
observation must equal the first. Only the derived fixed mkdir/mkfs/mount/chown/
chmod plan is allowed; `mkfs.ext4` has no force flag. Root context and both aliases
are rechecked before every write, and intent is retained before dispatch.
The resulting ext4 UUID, device, major/minor, sole mount, rw/nodev/nosuid options
and private owner/mode are independently replayed and checked again from current
observations. A startup status alone cannot establish readiness.

## Lost responses, failure and time

Initialization is submitted once. A lost response permits queries of the same
durable claim and original grant. A live matching PID/start-time permits waiting;
a missing/partial claim, dead process without a terminal result, failed operation
or three consecutive transient query failures stops promptly. No branch reformats
or repairs an uncertain initialization. The original owner still performs fenced
cleanup of its exact resources. Failure diagnostics retain closed error types and
bounded original replies, without raw SSH stderr or credentials.

Guest and controller monotonic clocks remain separate. A nonce-bound guest clock
sample defines the original initialization grant, at most 300 seconds and within
the current lease plus grace. Lost replies cannot renew that grant. Later read-only
mount checks receive separate bounded grants, while their responses must still
arrive before the original controller deadline. These are individual privileged
operation/exchange bounds, not a hard cap on a cloud stage or the experiment.
The existing soft total time and cost policy is unchanged.

## Immutable installation and whole-history parents

The Python capsule is composed from the original checkout and installed with the
existing one-submission protocol. A lost installation reply can only verify that
installation. Host boot/UID and original installation identity remain bound; mount
identity is checked again afterwards. The final storage receipt must be retained
before the scope becomes ready. A failed final receipt write cannot grant a
Placement or skip cleanup.

`Storage.placement(guests, name)` accepts only a complete history declared in the
original member selection and consumes it before remote control actions. It
rechecks each original mount and immutable installation. A fixed unprivileged
receiver creates an exclusive history parent on that mount, checking actual
account, boot, device, ancestor ownership and private mode. Its original claim
cannot be recreated after an interrupted write. Lost responses permit only a
query, and repeated Placement requests for the history reject.

The returned existing `remote_bound_receivers.Placement` combines those parents
and installation receipts with current private topology/host domains. Its source
binding includes Java from the original admitted input proof; the resource claim
alone does not contain that Java binding. No history is measured by storage setup.
The retained status is `STORAGE_READY_NOT_QUALIFIED`, with
`engineWorkloadExecuted=false` and `fullRemoteQualification=false`.

## Local validation and limits

`test_cloud_volume` uses an independent block-device model and real exclusive
claims, immutable records and fsync. It covers blank-device/size constraints,
topology/identity drift, partial claims, failed writes, clock binding, bounded
decoding and unprivileged history parents. `test_cloud_storage` runs the actual
native admission/owner/resource/IAP/storage factory with external I/O modeled,
including lost preparation and installation replies, failed intermediate nodes,
changed installations, late queries and final receipt failure.

`cloud_volume_qualification` uses the existing private mount namespace and chroot
helper. System binds are recursively read-only; no host block device is exposed.
Actual root/NSS/sudo/boot checks, root directory ownership, immutable file writes
and process death run in that filesystem. Only metadata and block observations/
writes are modeled. Eight cases cover success, lost format result, metadata drift,
unsafe or symlink ancestors, changed original claim, expired grant and a killed
initialization process. The receipt records effective UID, transmitted source/model
hashes and explicitly denies real device or cloud execution.

The existing measurement gate includes both new test modules and this isolated
qualification. Original failures and exact local source/log hashes are retained
in `target/v52-native-volumes/`. A sandbox UID mismatch rejected the history-parent
test; the same code passed under the real current UID without weakening ownership.
No Java workload or whole cohort was rerun for this storage-only change.

Final local validation passed 123 targeted storage/installation/host/IAP tests
(29 new) in 702.957 seconds, all eight isolated-root cases, and 69 CI/provenance
regressions in 46.108 seconds. The executed source index checks 1,749 files;
documentation/static checks also pass. The complete current Python inventory is
977 unique cases across 77 modules; collecting that inventory is not execution
of the full suite. Full corrected-source protected CI is still required.

Remaining work is original input staging and owned complete member execution,
independent physical/history/resource replay, immutable qualified retention,
five-member set replay and protected Runner/operator configuration. Python
installation does not install Java: original-version, hash-pinned guest Java
delivery/verification must also precede a history; the base image cannot be
assumed to provide it. The Python
gate has outgrown its original 20-minute job budget locally. The foundation gate
also discovers all V5.2 Python tests, duplicating much of the measurement gate.
Split independent tests into required CI lanes before pushing, preserve the
standalone local gate behavior, and retain every test, tier rule, artifact and
exact-source provenance contract. Local timing is not a hosted CI
measurement, and earlier hosted workload evidence is not rebound to this source.
