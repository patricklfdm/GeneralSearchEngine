# Original pending/full-INTENT pair recovery

Phase 3 remains **OPEN**. `resumePublished` explicitly reopens the original
pending/full-INTENT pair under the actual typed learner. It never discovers a
replacement source or reconstructs an ACK from arguments. A live original pair,
CANCEL state or placement transaction refuses this entry.

## Before the first recovery write

Read the bounded original plans and capture their complete file identities.
Independently verify both source histories, original typed receipt, exact
pending INTENT/checkpoint and ACK, the complete original retained marker, and
the child's original directory/inode/hash link to that parent. The original
pending source must already be in its retained location. The child can still
be in its exact original receiving directory after an interrupted move.

Reserve pending metadata as SOURCE plus its JOURNAL/images, and child metadata
as the single LEARNER plus its images. Reserve the entire pair before any force
or rename; capacity refusal releases all partial reservations. The second
GENERATION slot stays free. The existing bounds and private plan formats remain
unchanged. No forced source capability is issued during this preflight.

The pending and full histories can contain identical image digests in separate
physical files. Their recovered image reservation names must be distinct. Both
copies stay charged under the existing seven-image allowance; content equality
does not merge their ownership or reduce the accounting.

Re-force the pending plan and every source member/parent, then its original ACK
and marker/parent. Only then finish the full INTENT plan and original source
move/forces. Both owners are rechecked around each exposed force boundary.
Return only after both complete. Any failure revokes the reconstructed pair and
preserves all files. Closing the returned handle releases both sides.

## Qualification boundary

Focused qualification uses real original typed owners, TCP-acquired histories,
files and force with conditional old-voter histories. It covers JOINT/COMPLETED
reopen, interrupted full-source moves/plans, corruption of either side, copied
marker inode and altered link, capacity refusal in SOURCE/LEARNER/JOURNAL,
repeated failure during recovery and existing standalone recovery paths.
Results and original failures are retained in the
[component receipt](phase3-evidence/pending-pair-recovery.json).

Here cold reopen means closing and reconstructing the original owners from disk
inside one JVM. Independent process death, maximum profiles/resources and original
physical/history replay remain deferred. At this component's original source, linked custody and placement remained
blocked. The subsequent [linked custody component](PHASE_3_PENDING_JOINED_CUSTODY.md)
connects those owners through native installation. Autonomous continuation,
all-profile qualification and Phase 3 closure remain open.
