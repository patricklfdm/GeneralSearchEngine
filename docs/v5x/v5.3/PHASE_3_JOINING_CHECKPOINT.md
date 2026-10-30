# Original joining checkpoint serving and publication

Phase 3 remains **OPEN**. The forced pending learner end now has a bounded
read-only listener for its exact `CHECKPOINT_ACK`. This connects the existing
checkpoint pull/collection path to the actual joining owner. The learner still
has no election vote, native selector or public serving role.

## Original force ownership

Only the live `MembershipLearnerDisposition` can create the private checkpoint
capability. It validates and forces the retained pending source and ACK before
opening the listener. Callers cannot provide an acknowledgement or observation
set to create this capability. One pending owner may have one listener; failure
to force the ACK never opens a port.

The immutable plan and complete source are semantically validated at capability
creation. Reads check the actual typed head, original source paths/inodes and
byte digests, metadata inventory and exact ACK bytes. They do not decode the
entire unchanged historical certificate chain for each chunk. This preserves
original byte checks without making small control requests replay all history.

The listener uses the existing trusted private network identity boundary. It
accepts only reserved old-view voters and CHUNK/TRANSFER_COMMIT frames for this
one exact ACK. It does not export an application image, prefix, generation or
arbitrary record, and does not accept PREPARE/ACCEPT/PROOF/PUBLISH commands.

## Transfer scope and revocation

Existing `MembershipSourceSession` implements offers, chunks, correlation and
exact retries. A fresh trace may use another valid old-view campaign ballot to
read the same already forced end. That read creates no promise, new vote or new
ACK. Each trace fixes its ballot; changing it mid-transfer is rejected. The
root/view, permanent reader identity and digest remain bound throughout.

All buffers and trace markers use the same CONTROL pool; the one listener owns
at most six live exports and a bounded trace registry. Completed sessions release
export buffers and keep only a charged exact final reply. Failed traces cannot
resample data. The original scope deadline never renews on retry. The existing
receiver supplies finite retries for transient transport errors; no new retry
loop or timing limit is introduced.

Every response, including a cached completion, checks the original capability
again immediately before the transport writes it. Parent close revokes first,
then drains workers outside the owner monitor, before releasing retained source
reservations. Store close also closes this child. If draining fails, the pending
owner preserves its reservations for an explicit close retry; a closing listener
cannot be replaced until its workers and leases are released.

## Integration and qualification

The component uses actual typed preparation, local durable files and TCP. Its
old voting history is a conditional fixture. Tests cover identical lost-reply
retries, changed originals, expiration, malformed references and identities,
later valid campaign reads, per-trace ballot binding, six-export/shared CONTROL
capacity, failed force, and parent close at the actual response-write boundary.
Existing pending/CANCEL/INTENT recovery regressions remain required.

The separate native history begins with actual bootstrap and only two of three
old voters available. It retains SEALED history before native INTENT, forces the
joining end, and asks the unchanged native publication path to collect the new
ACK through this listener. Future-retention quorum recording remains in place.
This execution passed: both surviving old voters actually pulled the learner
ACK and published JOINT. The [component receipt](phase3-evidence/joining-checkpoint.json)
binds the source, original evidence and all 11 passing tests (seven endpoint
cases, three existing persistence regressions, one native publication history).
The initial nine-case run and its two failures are retained too: repeated full
history decoding exceeded the unchanged request timeout, and one malformed-ballot
test used the wrong field. Both were corrected before qualification. No success
is inferred from conditional tests or an in-memory checkpoint.

After JOINT publication, the new learner still owns a pending SEALED source and
INTENT end. Explicit bounded conversion to full published-JOINT custody and
native installation remains necessary. Coordinator scheduling, alternate-leader
continuation, joint FINAL/fresh barrier, all-profile original physical/history
replay and process-death qualification remain open. This is not Phase 3 closure.
