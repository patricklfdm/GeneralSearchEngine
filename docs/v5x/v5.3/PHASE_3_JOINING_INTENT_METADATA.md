# INTENT metadata before joint publication

Phase 3 remains **OPEN**. This component provides a read-only native transport
entry for the exact sealed learner to retrieve a matching certified INTENT
before its joint checkpoint is published. It does not yet force a learner's
applied end, produce its checkpoint acknowledgement or finish joining.

## Why the ordering matters

In a 3-to-4 ADD with only two old members available, the original 2/3 majority
can certify INTENT. Its checkpoint ends in the joint view, which needs an old
majority and a new 3/4 majority. Requiring the learner to fetch an already
published JOINT capsule before acknowledging that checkpoint would therefore
make the two operations wait for each other. The same issue applies to minimal
quorums in replacement profiles when the selected old quorum includes the
departing member.

The original complete-source joining/placement/native handoff remains useful
after publication. A separate prepublication route must first let the learner
authenticate and force the matching old-history-plus-INTENT applied end. This
increment implements only the source's original metadata leg of that route.

## Actual source ownership and restricted transfer

`MembershipGrantJournal.JoiningIntent` has a private constructor. It requires
this owner's exact `nativeApplied` result and `PendingPublication`, complete
original certificate, original selector/selection/promise, unchanged SEALED
generation and an unfenced ballot. The descriptor must match the full active
ADD/REPLACE request, prepared revision, sealed typed receipt, joining identity
and unchanged application image. Bare SEALED state, ACCEPT alone, conditional
history and a caller-constructed projection cannot create this capability.

`MembershipJoiningIntentExport` routes through the existing activation endpoint
and transfer service. The derived lookup alias binds root, full request,
permanent learner identity and the current published SEALED cut. A different
request, identity, revision/cut, correlation ballot or view refuses. The envelope
still uses the old governing context; it does not pretend that JOINT is already
published.

The contact-only client has a separate `JOINING_INTENT` read mode, pinned to the
exact hinted peer/cut and metadata alias. The existing ROOT, prefix and progress
modes keep their original allowed references. None creates a listener or permits
promotion into a voter transport; the new mode cannot request a complete prefix
under its metadata trace.

One bounded private JSON body carries the actual original ENTRY, ACCEPT, PROOF,
CERTIFICATE, payload and projected CATALOG/CHECKPOINT, plus exact parent/target
anchors and identities. Original owner checks bracket construction and every
read. The existing CHUNK/SOURCE_OFFER/TRANSFER_COMMIT exchange retains its exact
duplicate handling, chunk bounds, original deadline and final-commit replay.
No public record kind, wire kind, POM, workflow or frozen measurement changes.

The export borrows the existing six-prefix-export registry solely for owner,
generation and deadline lifetime. It does not expose any prefix, image or
generation bytes. Its metadata is charged to CONTROL before construction, with
existing per-reservation and total queue limits; constructor failure and close
release acquired reservations. Generation replacement, fencing or expiry
invalidates reads. No additional physical source/generation is allocated.

## Authority that is still required

Metadata receipt is not a voting observation, stored-history capability,
completed source acquisition, joining admission or CHECKPOINT_ACK. In
particular, the existing replicated-retention requirement for a complete
learner source is unchanged. This narrowly scoped metadata read cannot be used
as another prefix alias to bypass it.

The receiver-side path still needs to retain independently authenticated complete
old history, match the actual typed receipt/image and force original INTENT and
the new-side applied end before acknowledging. Its durable lifetime, recovery,
source retention and eventual handoff must be connected before the coordinator
can publish JOINT and continue to joint FINAL and a fresh stable barrier.
There is no fallback that accepts the old majority as the new majority.

## Qualification scope

The targeted native regression constructs a real bootstrapped cluster and typed
learner, closes one old voter before selection, uses only the other two for the
actual INTENT certificate, and reads the original metadata over TCP. It also
requires checkpoint completion with only those two original acknowledgements
to refuse. Durable replica and learner files must remain identical across the
metadata read. Routing fixtures cover all five joining profiles without claiming
native transition qualification for those fixtures.

The [retained component receipt](phase3-evidence/joining-intent-metadata.json)
records exact source snapshots, tests and any
development failures. Complete original-first physical replay, all-profile
minimal-quorum joint publication, fresh-process interruptions and public typed
service are still in [deferred acceptance](PHASE_3_DEFERRED_ACCEPTANCE.md).
