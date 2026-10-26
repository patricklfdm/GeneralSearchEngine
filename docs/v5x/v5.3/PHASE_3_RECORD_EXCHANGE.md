# Phase 3B — original referenced record exchange

Status: locally qualified. This extends the
[complete source exchange](PHASE_3_SOURCE_EXCHANGE.md) to records referenced by
PREPARE and later voting frames. The complete [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md)
remains open; this is not an enabled automatic membership runtime.

## Actual retained bytes

The journal exports one exact content hash and typed record from its retained
PROMISE/BASIS/SELECTED journal, complete active vote, or verified current packet.
Supported record kinds are PROMISE, BASIS, SELECTED, ENTRY, ACCEPT, PROOF and
CERTIFICATE. Candidate files, caller-provided bodies, absent digests and a different
kind cannot be substituted. A current packet can retain a record originally
produced by another voter: serving its bytes is not a claim that this sender
performed that other voter's force. Receipt/context validation remains mandatory.

A record export reserves shared CONTROL capacity before copying bytes. It checks
the live exclusive owner, physical file identities, original bytes, retained
reference and unchanged view before every reply. It uses the original start and
budget, releases on expiry/close/owner failure, and cannot be revived by moving
the clock backwards. A later grant does not replace a retained older record.

Unlike a full source borrow, this small record borrow does not pin a source's
packet/images or prevent journal compaction/retirement. If the original record is
no longer retained, the next access revokes the borrow. The immutable cached reply
also passes this check before replay; old bytes are never silently refreshed.

## Shared transfer and receiver ownership

`MembershipTransferExport` supplies only verified content references, context,
identity, exchange ballot and bounded reads. Both complete-source and single-record
exports use the existing `MembershipSourceSession` offer/data/commit state machine.
It retains exact correlation, single-use transfer IDs, sequence and extent checks,
Base64/frame limits, one last-response cache and original deadlines. There is no
new persisted or wire format and no second retry implementation.

`MembershipSourcePull.fetchRecord` fetches the actual hash and exact typed body,
checks its root and invokes the required protocol validator **before** transfer
commit. The validator must check the expected phase, ballot, parent and references;
carried original records can retain an earlier ballot than the current exchange.
This method never constructs an `Owned` receipt or voting/install ACK. Returned
bytes are borrowed until the pull closes; their CONTROL reservation remains live
through that lifetime. Failed validation or cancelled delivery releases the buffer.

The same original fencing guard and at-most-three identical attempts apply (with
any stricter caller retry limit preserved). Explicit REJECT, malformed/contextual
failure, capacity, closed transport, cancellation and the original deadline do not
retry. The protocol owner must process higher promises and force its own authority
before answering its voting frame.

## Qualification boundary

The network case uses actual public bootstrap at sizes 3/4/5. A receiver handles a
PREPARE by pulling the proposer's original PROMISE over a reverse TCP exchange,
validating the original, then forcing its own grant and returning the exact BASIS
reference. The independent reader reconstructs the original bootstrap, captured
proposer state, receiver state and every offer/data/commit/prepare byte. It also
checks the source-bound execution's validation/force/return ordering.

The seven-kind test uses actual retained local journal/vote files; its initial
provisioning is a private fixture, not public cluster admission. The published
record test uses public bootstrap and actual publication before pending-vote
retirement. Neither is relabelled as a complete network election. These tests
qualify content service, not remote force authenticity by possession alone.

Remaining Phase 3 work includes production session registration and dispatch,
complete activation network integration, root-bound newer-prefix discovery and
adoption, source rotation, abandoned-scratch recovery, learner/joint transitions,
automatic voting/publication and full deterministic/network/process qualification.

The [local receipt](phase3-evidence/record-exchange.json) binds **51 focused Java
tests across eight suites**, including ten record-exchange cases, and **548 Python
tests** in normal and optimized modes. The three-size TCP trace contains 15
record transfer exchanges and three PREPARE exchanges; its original-first reader,
13 exact negatives and optimized/relocated replay pass. Existing source-delivery,
source-export and activation evidence also passes independent negative replay.

A new regression failed on the earlier implementation because it could not find a
published record after its pending vote was retired. The corrected lookup checks
the actual verified current packet as well as journal/active-vote storage. The
failed log, original build/input index and successful final-source run remain
separate. Initial reactor-path and compilation errors are retained too. These
local functional tests do not establish full distributed activation, a performance
bound, protected CI or cloud qualification.
