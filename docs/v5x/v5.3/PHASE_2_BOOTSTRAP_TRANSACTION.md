# Phase 2 — private all-voter bootstrap transaction

Status: private transaction locally qualified; **Phase 2 remains OPEN**. This transaction
consumes the [original retained plan](PHASE_2_BOOTSTRAP_PLAN.md). Public bootstrap,
random-history planning, typed/source rechecks and complete-store seal admission
are not enabled by this component.

## Decisions and original authority

The coordinator holds `operation.lock`, verifies the original plan and image, and
owns each target's existing or newly created `replica.lock`. Targets comprise all
3, 4 or 5 initial voters. Their core materialization paths remain absent. The
transaction writes the frozen `BOOTSTRAP` kind's four exact decisions:

1. **PREPARING** permits only original planned payload prefixes and directories.
   Every payload and directory is forced before the target's preparation marker.
2. **PREPARED** requires every target's complete original payload and preparation.
   Missing or different authority is refused, including when the next decision
   is only partially written. A target with even a partial preparation marker
   already requires its complete original payload; it is not reconstructed.
3. **COMMITTING** follows the caller's final typed/source recheck. It authorizes
   publishing the exact global receipt through a forced candidate and atomic rename.
4. **COMMITTED** follows the forced receipt and its parent directory. Only then
   may individual local seals be published through their own forced candidates.

A full original plan binds decisions, all per-target inventories, preparations,
receipt and seals. The relative target names in `BOOTSTRAP` are calculated from
the common absolute ancestor of the bound paths; they are never resolved against
cwd. The full absolute descriptors remain in the original plan. Private GSBP 1.3
kinds 2, 3 and 4 represent preparation, receipt and local seal metadata. They do
not add a kind to either frozen GSER/GSRP catalog.

Recovery can finish an exact decision prefix only after verifying that decision's
prerequisites. It never truncates conflicting bytes, changes the history, repairs
an active receipt/seal from a candidate, or recursively deletes a target. Existing
directories, payloads and visible decisions are re-forced before continuing. A
redundant exact candidate is deleted only after forcing the active file and parent.
Read-only result inspection performs no repair and requires all complete initial
payloads and local seals; it is not yet the future public post-runtime result reader.

## Ownership and reservation

The original parent filesystem bindings are checked at admission and before each
new decision. Between guarded writes, original parent device/inode and real paths,
all directory/member identities, lengths, hashes, exact inventory and lock validity
are checked. An in-process replacement with byte-identical data still fails. Lock
files are checked as empty single-link regular files without opening another
channel while held; force uses the original owner channel. A V5.3-only process
registry rejects overlapping path/inode owners before opening a second channel.
This also protects the existing allocator and plan owner: a failed duplicate open
must not close another descriptor for the same POSIX process lock. Close releases
the registration only after its original channel is closed. Legacy admission
helpers and formats are unchanged.

Admission reserves the complete transaction byte envelope before writing a decision:
original plan plus possible duplicate plan, coordinator image, every voter payload,
all four decisions, preparations, receipt plus candidate and all seals plus their
candidates. Existing byte/count/depth bounds reject unknown or oversized trees.
This covers the retained transaction. The public planner must additionally account
for projection/typed-validation scratch and integrate the complete local resource
owner; these are not waived by this calculation.

## Qualification scope and remaining work

[Source/build/raw evidence](phase2-evidence/bootstrap-transaction.json) records
84 passing Java tests, including eight transaction tests, four new ownership tests
and seed/plan/application/allocator/grant/declaration/legacy regressions. The Java
producer covers EMPTY and actual verified backups at all 3/4/5 sizes,
strict partial/complete authority distinctions, caller recheck failure, immutable
reopen, conflicting/missing files, ownership and exact candidate publication. A
separate JVM attempts to acquire every coordinator/replica lock after all forces.
The retained **84-case** interruption matrix and independent original-first Python
replay check file prefixes, every decision/receipt/seal and force order, including
a second interruption during recovery. Fourteen exact-reason negatives, portable
replay and normal/optimized Python agree. These injections are not process-death or
power-loss evidence.

The regression first reproduced an external process acquiring the coordinator
lock after a rejected in-process duplicate open. The corrected registry blocks
that acquisition, including allocator/plan ownership, another Java thread, moved
inodes and repeated close/reopen.

Public planning/apply/resume/result, typed revalidation on the real entry, complete
storage opening and seal accounting, and fresh-process crash qualification remain
required. The separate transferred-context/lifetime and full Phase 2 physical
closure obligations also remain open.

The [fresh-process gate](PHASE_2_BOOTSTRAP_PROCESS.md) separately qualifies the
original transaction through repeated halt/SIGKILL; its narrower three-voter EMPTY
scope does not enable public admission or remove the remaining integration gates.
