# Phase 2A — private ballot allocation and directory ownership

Scope: internal filesystem component; **public runtime and bootstrap disabled**.
The input is a deliberately small pre-provisioned test authority, not a complete
replica/application backup. No quorum or authenticated peer observation is claimed.

Local batch result: **2A complete**, Phase 2 remains open. The
[retained summary](phase2-evidence/allocator.json) binds parent `5ab987b` and exact
local implementation/JAR bytes. Final reporting and this summary follow that
source binding; this is not a clean-HEAD or protected-CI result.

## Existing authority, never recreated from arguments

`MembershipBallotAllocator` requires an existing empty `replica.lock`, original
`root.gsr` (16 KiB), `genesis.gsr` (64 KiB), `node.gsr` (4 KiB), and
`allocator.gsr` (4 KiB). Only `allocator.pending.gsr` (4 KiB) may additionally exist.
Every file must be regular and single-linked. Unknown files, symlink paths,
unsupported filesystems and unavailable inode identities fail closed. The existing
`AdmissionPaths` helper is reused without modification.

Open takes the exclusive lock without creating it, binds directory/lock inodes and
the parent filesystem identity, checks original ROOT/GENESIS consistency and frozen
limits, and matches the caller's root and full local identity against NODE. Every
mutation rechecks these bindings and exact immutable/current bytes. This assumes
cooperative exclusive ownership, not protection from a malicious same-user process
replacing files between checks. Complete voter membership/role is a later concern.

Missing counter, root or lock cannot reset the allocator to zero. Foreign identity,
legacy frames and changed/corrupt authority are retained and rejected. Fixtures
create these records only in the test worker, including a synthetic genesis
application digest; that is not public empty or backup provisioning acceptance.

## Reservation and interruption

The next counter is `max(local, observed) + 1`. Check before incrementing, with
largest allocatable value `2^63-2`; exhaustion refuses as
`CAPACITY_EXCEEDED / NOT_SUBMITTED` without changing bytes.

The sequence is: create bounded pending file, write complete canonical ALLOCATOR,
force file, atomically replace current, force directory, then return. No fallback
to a non-atomic move is allowed. Any exception within the write path poisons the
handle; it must close and reopen before another reservation.

| Retained state after interruption | Open/restart behavior |
| --- | --- |
| No pending file | Validate and re-force current plus directory; allocate strictly above its counter |
| Complete pending counter greater than current | Force and atomically promote it, force directory, burn that counter even without a prior return |
| Empty, torn, corrupt, foreign or stale pending | Retain original bytes and refuse open |
| Rename visible before prior directory force | Re-force the visible current file and directory before exposing the counter |

The blocked empty/torn-pending case deliberately has no automatic repair in 2A.
Later complete-store recovery must provide the exact recovery/repair decision; the
component cannot infer that uncertain authority is disposable. Counter gaps are
legal. Promoting an unreturned complete reservation prevents accidental reuse.

## Focused qualification

Ten Java tests cover sizes 3/4/5, observed-bound jumps, locks, missing/foreign/linked
authority, owner inode replacement, all seven reservation boundaries, three
interrupted-recovery boundaries, exhaustion and exact force/return order.

`allocator_qualification` launches fresh JVMs for **48 cases**: per initial size,
clean reopen, concurrent owner contention, seven `Runtime.halt` cuts and seven
external SIGKILL cuts. SIGKILL waits for an explicit cut handshake; contention runs
while a separate JVM still holds the lock. Original bytes and every process's
stdout/stderr/exit code remain retained, including failed qualification attempts.

An independent Python frame reader checks counters, identity, unchanged authority,
crash boundaries, refusal reasons and force-before-return observations. It first
validates all original cases, then requires ten mutations to reject for their
specific reason. Relocated copies replay without depending on original paths.
Synthetic Python reader tests do not count as real process executions.

These force callbacks occur immediately after actual channel/directory force
calls. Halt/SIGKILL leaves the OS page cache alive: the qualification does **not**
test physical power loss, prove an fsync implementation or establish distributed
protocol acceptance. Repeated interruption during recovery is currently covered
by deterministic Java I/O exceptions, separately from the process crash matrix.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_allocator_evidence scripts.test_ci_v51_bundle
python3 -m scripts.v53.allocator_qualification \
  "target/v53-phase2-allocator/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

The output must be new. Thirty-second subprocess/handshake guards detect a broken
local test; they do not change any cloud or workload budget. Shared current-version
build bundles require the executed allocator suite and worker class, preserving
all existing prerequisites. No workflow is added or reduced.

Actual validation: 62 focused Java tests (including ten new allocator tests),
23 focused Python/build-bundle tests and seven optimized-Python tests passed.
The complete 48-case qualification launched 186 independent JVMs and passed in
29.836 seconds; all ten reason-specific negatives and relocated replay passed.
Raw logs, physical snapshots and the hash inventory are retained under
`target/v53-phase2-allocator/qualified/`. Full GSE regression, public membership,
power-loss testing and hosted/cloud acceptance were not run for this private batch.
