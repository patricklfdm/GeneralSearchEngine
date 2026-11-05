# Phase 3 recovery requires completed disposition release

This extends [failed listener drain](PHASE_3_PENDING_LISTENER_DRAIN.md) to
same-store replacement and linked recovery admission. The
[development evidence index](phase3-evidence/recovery-release-guard.json) binds
the original failures and corrected-source checks. Phase 3 remains OPEN.

## Observed boundary

`MembershipLearnerDisposition.closed()` means immediate revocation. A close
from a listener's own callback cancels I/O, then reports incomplete drain; the
original retained storage remains owned for an external close retry. Previously,
the store's replacement and linked-recovery guards accepted that revocation
flag as sufficient to replace the owner.

Two real TCP regressions reproduce this for checkpoint and head listeners. The
linked-recovery entry passes the original-owner guard, then fails later with
`resource ownership/count` while attempting to reserve the existing pending
journal. These observations demonstrate an early admission defect; they do not
show successful duplicate ownership, overwritten evidence or data corruption.
The existing capacity check still rejected both attempts.

## Release boundary

Immediate serving revocation remains separate from completed release. The new
internal `released()` predicate becomes true only after successful listener
drain and child cleanup. Store attachment of CANCEL, INTENT and pending INTENT,
linked INTENT replacement and linked recovery require this predicate for the old
owner. Checks that require a live parent or prohibit further serving continue
to use immediate revocation.

After listeners drain outside the disposition monitor, child cleanup and its
completion flag are serialized under that monitor. Cleanup completion is no
longer published before child close calls return. A failed attempt does not set
the completion flag. This does not qualify arbitrary filesystem-close failures
inside every descendant owner.

The unchanged new regressions require repeated linked-recovery calls to reject
at the original-owner guard while the callback remains held, with unchanged
files and resource usage. After external drain completes, the guard permits
recovery, the actual pending original can be resumed, and the newly live owner
again excludes concurrent recovery. Passing the guard alone never supplies the
absent linked INTENT authority.

Existing callback/interrupted-drain and reentrant store-close tests cover the
surrounding lifecycle. Normal CANCEL/INTENT reopen and linked-pair cold recovery
exercise successful release paths. Where complete original resource journals
are emitted, the existing retained-owner reader and its twelve exact negatives
are replayed without changing their acceptance criteria.

No disk format, wire format, durable voting, capacity or timeout changes.
These are conditional-history lifecycle checks. Full native ownership and
resource composition, other export/task lifetimes, combined maxima and
final-source hosted qualification remain pending. Earlier source-bound results
are retained as historical evidence, not relabeled for this runtime.
