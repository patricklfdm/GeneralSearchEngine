# Bounded pending INTENT reception

Phase 3 remains **OPEN**. The [native export](PHASE_3_JOINING_INTENT_METADATA.md)
now has a bounded receiver, connected to the existing live learner progress
owner. This step reads and compares original bytes; it does not force an applied
end, authorize a vote, or finish the minimum-quorum joining protocol.

## Source and owner lifetime

`MembershipLearnerProgress.joiningMetadata()` requires its completed complete
SEALED prefix/generation transfer and the same live typed learner head. It uses
the original peer, receipt, resource pool and original progress deadline. It opens
only the dedicated contact client; there is no new listener or voter identity.
The parent owns and closes the extra contact/pull, including constructor failure.
Each access checks the original progress transfer and typed head; an unavailable
current head or a closed parent cannot continue receiving or expose a live result.

This complete SEALED source must be acquired while its actual retention permit
is available, before certification blocks ordinary source maintenance. Metadata
alone cannot replace that source or silently open another physical generation.
The coordinator still needs the corresponding acquisition/INTENT scheduling and
durable joining transaction.

## Exact structural validation

`MembershipJoiningIntentMetadata` checks the canonical private envelope, exact
field/record inventory, full request, permanent source/learner identities, exact
parent anchor and forced typed receipt value. It checks the original ENTRY,
ACCEPT, PROOF and CERTIFICATE linkage and both old-side phased quorum shapes.
The entry must be the next INTENT over this SEALED cut with the exact sealed
payload. Its CATALOG changes only the matching phase and joint cut; the expected
CHECKPOINT and target anchor must match exactly, including the unchanged image
and sequence. No additional application image is allocated for this comparison.

These are structural comparisons with already supplied historical inputs. A
serialized witness hash is not an actual force observation. The decoder cannot
construct `Owned`, stored-certificate provenance, an applied-end acknowledgement,
new voter admission or public readiness. Retained diagnostic bytes remain values;
they do not become authority when their supplying owner is closed.

## Bounded transfer and failures

`MembershipJoiningIntentPull` keeps one trace and ordered sequence. It validates
the RECORD offer, reserves three times its declared body against the existing
CONTROL cap before allocation, then checks each chunk and the whole digest. The
maximum body derives from that existing per-reservation limit. Semantic decoding
must pass before TRANSFER_COMMIT, and its exact reply must pass before success.
The body remains charged while the pull is open; close or failure releases it.
There is no new public resource or wire limit.

Only transport IO/DEADLINE failures retry, with at most the existing retry bound
capped at three attempts. Each retry keeps identical request bytes and the
original overall deadline. REJECT, malformed content/correlation, expired time,
capacity rejection and revoked parent fail immediately. Close cancels an
outstanding future; a late result cannot restore a closed exchange.

## Qualification

Short conditional byte/link tests cover all five ADD/REPLACE profiles, 18 altered
metadata forms, lost offer/chunk/final replies, permanent failures and exhaustion,
eight malformed reply forms, shared capacity, parent revocation and cancellation.
A separate test uses a real typed learner, complete SEALED source transfer and
TCP contact to check owner integration and unchanged durable files. That test's
voting history and metadata certificate are explicit conditional fixtures; it is
not native certificate creation or a force-before-ACK qualification.

The [component receipt](phase3-evidence/joining-intent-receiver.json) records the
actual runs and retained development failure. The preceding native export test
remains separate evidence; it is not claimed as a rerun of this receiver source.
Full native receiver authentication, durable force/recovery, minimal-quorum
publication, all-profile physical replay and process cuts remain deferred.
