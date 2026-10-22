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

### Slow read checks and closed receiver diagnostics

Runs `39729635598/1` and `39755195425/1` failed before/during a read-only
mount check. The latter stopped at `java-volume-before` on node 1 with
`REMOTE_EXIT`, before any history, after all three initial mount receipts passed.
Cleanup deleted all 13 resources and released the lease. The retained receiver
error did not identify the underlying rejection; neither an exact timeout cause
nor a WSL crash is established for that run.

The controller now records SSH response arrival before either provider
postcheck. Guest expiry is the nonce-bound remote sample plus the remaining
controller time at that arrival. The remote sample predates arrival, so this
conversion remains conservative; the postcheck no longer consumes the guest
budget a second time. Initialization still has its original 300-second grant,
one submission and queries of that same grant.

Each standalone mount check has one 300-second window and at most three read
attempts. A transient connection loss or explicit remote clock/deadline rejection
may obtain a new sample for a new read, within that same original window and
current lease plus grace. Renewal cannot extend the check's original deadline.
Clock sampling retains its existing maximum of three read exchanges. Late
success is rejected. No format, initialization, install or workload is replayed.
Identity, metadata, owner/mode, filesystem, source, malformed-response and unknown
remote failures remain terminal.

The fixed volume/history receiver still exits nonzero on rejection. It emits a
small `gse-v52-volume-rejection-v1` response containing only a closed code, action
and hash of the complete request envelope. The controller accepts this diagnostic
only from a failed remote exchange with the exact action/envelope binding and
closed schema. Raw stderr, command text and exception text are not retained.
Unknown or damaged failure envelopes remain terminal `REMOTE_EXIT`.

Per-attempt elapsed/remaining milliseconds and closed codes are retained in
separate `node-N-check-NNNN.json` diagnostic records. The final failure summary
projects the current check's bounded attempt list. These records do not replace
mount receipts or grant qualification. Diagnostic write failure cannot mask the
original outcome or skip owner cleanup.

Local regressions simulate slow connections, delayed provider postchecks, remote
expiry, three-attempt exhaustion, terminal drift, lease clipping, stale/unknown
failure envelopes and safe public summaries. Three timing/retry regressions fail
on the original controller. Real local subprocess and isolated namespace tests
cover receiver output and root/file boundaries; cloud network timing still
requires a new original run after merge.

## Control reads during lease renewal

Each scoped control-object read holds the API's existing reentrant lock from
metadata lookup through generation-pinned body validation. The original owner's
heartbeat cannot replace the policy's observed generation between those two
requests. Nested policy reads reuse that same lock; the read path never acquires
the owner's lifecycle lock. The lock order remains owner, then API.

Lock waiting consumes the existing 30-second control-read deadline. Expiry or
failed lock acquisition sends no request; every acquired lock is released on
success or failure. This is an individual exchange boundary, not a stage budget.
External replacement/deletion still rejects the pinned read, and ownership,
lease expiry, exact resource IDs and cleanup fencing remain mandatory. There is
no new HTTP or workload retry.

`test_cloud_control_reads` deterministically starts the real offline scoped
owner's renewal after metadata arrives. The original implementation rejects the
subsequent body even though the lease remains ACTIVE and the allocation is
unchanged. The corrected read completes at the original generation before the
heartbeat proceeds. Separate tests cover lock deadline/exhaustion, reentrant
policy reads, changed claims, external 404/412 responses, malformed metadata,
truncated bodies, absent/expired leases and safe diagnostic projection. These
are local concurrency and boundary tests, not hosted workload qualification.

## Immutable installation and whole-history parents

Python installation has one 300-second exchange grant covering IAP/SSH connection,
capsule upload and durable writes, matching the existing Java installation grant.
Recovery queries use that same absolute deadline; they cannot renew it or submit
installation again. Later standalone Python verification has a 60-second exchange
bound. Per-write progress limits and terminal identity/integrity rejection remain
in force. These are individual operation limits, not stage or experiment budgets.
Python and Java upload/late-response expiry raises transport uncertainty; malformed
receipts remain terminal validation failures. Buffered late success is rejected.

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
