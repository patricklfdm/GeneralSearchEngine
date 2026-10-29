# Forced learner installation custody

Phase 3 remains **OPEN**. `MembershipLearnerCustody` now consumes an actual live
[dormant voter stage](PHASE_3_LEARNER_VOTER_STAGE.md), forces an original ownership
decision, transfers the real learner's locks and storage reservations, and
revokes the old learner object graph. This is the installation owner's custody;
it does not move voter payloads into the live replica, open a voter journal,
create joined-voter admission, retire old files or permit a joint vote.

## Original decision before revocation

The only entry is the private `Ready` capability. Revalidate its matching forced
INTENT, actual typed receipt, staged local fence and original source. Traverse
the actual learner store, operation, typed owner, successor/slot/seed, retained
receives, INTENT and stage. Collect their real handles by identity, including
still-counted predecessors; do not reconstruct reservations from names or take
an arbitrary resource pool. Refuse unknown storage, CONTROL/WAITER reservations
and unresolved generation claims before creating a decision directory.

The bounded canonical decision is at
`.gse-v53-learner-custody-<plan digest>/custody.json`, with private schema
`gse-v53-learner-custody/1.3`. It binds the original plan, exact receipt and source,
its own directory identity, and the nine fixed original roots: replica,
operation, initial typed, successor, successor typed, slots, slot typed, INTENT
and voter stage. Record both present and absent roots. Existing roots must belong
to the actual owner graph; preserve ordered original directory/file identities,
lengths and hashes. Inventory paths are string values in a sorted entry list,
not arbitrary JSON field names; the strict canonical codec remains unchanged.
A copied or changed member cannot enter a new original seal.
Hashes are streamed, with bounded file count/depth and no extra application copy.
Transient lease names are not durable proof; cold recovery may conservatively
reserve the same physical files under different process-local names.

The directory, complete decision and parent are forced before any old handle is
revoked. Every cut rechecks original files, actual reservations and locks; after
the decision file exists, its current original inode/prefix is also checked.
A last-boundary decision mutation must refuse before transfer. No decision can
be repaired from an incomplete prefix. A complete original may be re-forced
under freshly reopened typed/INTENT/stage owners.

The decision is at most 256 KiB, reserved in the existing staged GENERATION
metadata allowance before creating it. Together with the two 64 KiB stage
companions this reserves 384 KiB, plus the actual dormant payload metadata.
The public GENERATION count/size, seven-image bound, MISC/completion headroom and
all other resource ceilings are unchanged. The decision creates no third GEN.

## Live ownership transfer

Transfer the complete actual storage group atomically, preserving category,
bytes and counts. Transfer each original empty authority lock with
`MembershipOwnership.transfer`, and each nonempty receiving-file lock with the
registered descriptor-custody transfer. Both retain the same channel and kernel
lock. The nonempty transfer also revokes old borrowed views. The registry never
opens or closes a second descriptor during transfer.

Close the old learner graph only after the new owner holds every transferred
handle. Old lease/lock closes are harmless, including repeated delayed closes
of the typed owner, INTENT, stage and store. New-owner checks require the exact
original decision, all original files, live lock handles and unchanged complete
resource accounting. Close releases child locks before root ownership, then the
new leases; no files are deleted. Partial in-memory transfer failure exposes no
voter and closes both sides while retaining the original decision and files for
explicit recovery. The caller must quiesce the learner's controller before this
transaction; this private component is not a concurrent public operation API.

## Recovery and qualification boundary

No replica layout has changed at this boundary. Cold recovery reopens the actual
original learner/typed/INTENT/stage owners, validates the complete original
custody decision, re-forces it and repeats only the handle transfer. It never
fetches a replacement history, recreates missing authority or treats a torn
JSON file as an accepted handoff. The forced INTENT already prevents a new
preparation, refresh, CANCEL or replacement decision from using this learner.

Focused tests exercise initial, promoted and the first selected slot's cold typed owners, kernel locks
through independent JVM probes, unchanged usage after stale closes, unknown
storage/in-flight rejection, interrupted transfer and unchanged original cold
recovery, and torn/corrupt decision refusal. Historical checkpoint quorums remain
conditional fixtures; injected exceptions are not process-death qualification.
The [component receipt](phase3-evidence/learner-custody.json) identifies executed
snapshots and results. Complete initial/promoted/alternating and all-profile native
histories remain in [the deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

The retained development attempts include the initial inventory-encoding failure:
all five custody cases stopped before reaching their intended transfer because
relative paths were used as canonical JSON object keys. A separate added resource
test initially requested zero-byte SOURCE/CONTROL reservations and was corrected
to obey the existing contract. Both failures remain in the component archive;
neither counts as successful qualification. The codec and resource limits were
not relaxed to make those tests pass.

The broader matrix then exposed an inspection-side failure in the cold-slot
test: the shared content-snapshot helper opened/closed the replica lock through
`Files.readAllBytes`, releasing its POSIX lock before custody transfer. A separate
small test reproduced this on the original helper. Snapshot hashing now streams
through owned-descriptor views and keeps the helper's existing content-only
semantics for aliases. An intermediate helper refused hard-linked negative
specimens; the final helper hashes those through an isolated child JVM so their
inspection cannot release the parent's locks. Production admission still refuses
hard links. This changes test observation, not admission policy.
The affected cold-slot case and descriptor/resource tests are rerun on that
correction; the original failed matrix remains recorded as failed. Its unaffected
passing cases and the corrected focused run use identical production classes.

Next, consume this installation owner in the original-path staged-payload move
transaction and its cold recovery. Preserve the original ROOT/NODE/replica.lock
inodes and all predecessor charges until covered retirement. Native joined
admission, old-majority INTENT delivery before joint checkpointing, joint FINAL,
fresh barrier and independent full-history replay remain required. A complete
published-source custody transfer does not solve the minimum-quorum joining
boundary or close Phase 3.
