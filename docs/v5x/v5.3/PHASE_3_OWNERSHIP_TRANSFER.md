# Exclusive custody transfer prerequisites

Subsequent [file-custody qualification](PHASE_3_FILE_CUSTODY.md) reproduced a
separate lock-loss bug in inspection/force paths and corrects it by borrowing
the registered descriptor. The results below qualify transfer itself, not all
reads performed by earlier learner paths.

Phase 3 remains **OPEN**. These private primitives support the next learner-to-
voter ownership transaction. They do not implement that transaction, produce a
joined-voter admission, move the staged generation into the live replica, or
open a voter journal. The [dormant stage](PHASE_3_LEARNER_VOTER_STAGE.md) is still
nonvoting.

`MembershipOwnership.transfer()` moves one wrapper's exclusive custody to a new
wrapper over the same `FileChannel`, `FileLock`, path and inode. It does not open,
close or unlock a descriptor and never unregisters the path or inode in between.
Before transfer, require the original registered live channel/lock, an empty
single regular file and the same original inode at the original path. Replaced,
aliased, nonempty, closed or already transferred owners are refused.

All subsequent channel/lock access and transfer through the old wrapper refuse.
Closing an old wrapper is harmless to the successor. Only closing the current
owner releases the actual channel and process registry entries. Concurrent
transfer/transfer and transfer/close use the same registry monitor, so only one
successor can exist, or close wins before any successor is created.

This does not revoke a raw channel reference borrowed earlier by an internal
caller. The actual handoff coordinator must quiesce old writers and force its
original protocol decision before transferring custody. Transferring a lock
alone is not authorization to vote, mutate the replica inventory or delete old
storage. A crash releases the OS lock; cold semantic recovery must still use
the original durable handoff plan and admission records.

`MembershipResources.transferStorage()` transfers an explicit group of actual
storage leases within the same pool. Validate the whole group, target names,
foreign/released handles, occupied or duplicate targets and pending generation
claims before changing any ownership. Build successor handles and the replacement
registry first, then swap ownership under the resource monitor. Metadata,
staging, protected headroom, category counts and byte extents remain unchanged.
This works at the existing full category limits without acquiring a duplicate
slot. The caller must retain the same physical files and separately transfer
their real ownership.

The old lease handles can no longer grow or transfer their reservations; closing
them cannot uncharge a successor. Labels can be swapped within the same group,
but category or extent cannot change. CONTROL/WAITER resources and an unresolved
learner-to-generation claim cannot enter this storage transaction. Completion
headroom and the shared staging limit still apply after transfer.

Focused tests use actual independent JVM lock probes, concurrent transfer and
close, descriptor identity, old-handle close, replacement/alias refusal and one
SIGKILL of a child that owns a transferred lock. This process test qualifies only
OS lock release/reacquisition, not membership crash recovery. Resource tests fill
all storage categories, preserve accounting through transfer and stale closes,
and reject whole groups before partial change. These tests do not establish that
a native joining member has been admitted or can vote.

The integration sequence remains required:

1. Force the exact source/receipt/path-bound handoff decision under the original
   prepared learner and staged-generation owners.
2. Quiesce old users, transfer original ownership and storage reservations, and
   revoke old learner-facing capabilities without an unlock/accounting gap.
3. Install and recover the exact staged files at the original replica, with a
   joined-voter admission distinct from initial-member bootstrap.
4. Retire covered nonvoting predecessors only after their durable replacement is
   proved, then open the original-history voter journal with rotation capacity.
5. Qualify native minimum-quorum INTENT delivery, joint FINAL/fresh barrier,
   independent original-first replay and the complete Phase 3 process matrix.

Long acceptance remains queued in [the deferred plan](PHASE_3_DEFERRED_ACCEPTANCE.md).
No runtime entry, public format, resource ceiling or measurement parameter changes
are made by these primitives.

The [component receipt](phase3-evidence/ownership-transfer.json) retains the three
executed snapshots. The first ten ownership tests pass; the final production
bytes pass 23 ownership/resource tests and 12 allocator/real learner-stage
regressions (35 distinct cases, no failures or skips). The lightweight contract
test also passes. All public byte fixtures, format catalogs and resource ceilings
remain unchanged. Full learner takeover, native joining votes and Phase 3 closure
are explicitly unqualified by this receipt.
