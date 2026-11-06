# Required-four voting, slot and activation ownership

The complete required-four resource entry now requires the existing voting,
slot and activation CONTROL/WAITER readers on the same whole original. These
readers were previously restricted to stable histories. The historical
89-negative diagnostic did not independently qualify their request and caller
lifetimes across membership transitions.

This is supplementary component work. All five Phase 3 gaps remain OPEN, and
the catalogue remains 566 histories / 260 groups / 500 archives / 544 jobs.
A successful-history resource reader does not qualify simultaneous maximum
bytes or interrupted handlers.

## Original observations and authority

The private slot driver's existing event interface has two default no-op hooks.
The joining fixture records the exact local PUBLISH request before entering the
real endpoint and the actual PUBLISH_ACK after return and original publication
checks. Both observations enter the same ordered event/resource-boundary stream
as network calls. Observer exceptions cannot produce driver success; failure
after publication preserves the actual durable cut. The hooks add no heartbeat,
retry, election or publication.

The producer explicitly enables `v53.resource.slot.control`. Missing request or
response observations cannot be reconstructed from allocation labels, later
round-completion events or a producer PASS receipt. Earlier originals lacking
them continue to fail strict replay.

After complete physical replay, expected ACKs are derived per slot from its
original SELECTED, CERTIFICATE and each proof voter's published generation.
Root, original view/ballot, permanent identity, complete published anchor and
generation digest remain bound. The final selection or a bare slot number cannot
stand in for earlier stable/joint authority or publication bytes.

Voting replay binds ACCEPT/PROOF/APPLY writers and callers to exact incoming
bytes and durable boundaries. Slot replay binds outbound delivery, nested
voting waiters, real local calls and all publication transactions. Activation
replay binds request/cache extents, mandatory callers and the original
publication boundary behind fast replies.

## Complete entry and compatibility

`gse-v53-required-four-resources-v2` requires nine exact negative families:
15 accounting, 19 handoff, 13 file, 12 network-close, 12 joining-close,
18 export-allocation, 16 voting-control, 22 slot-control and 20 activation-control:
**147 total**. All original readers pass before any mutations count. Each control
negative driver's original replay must also equal the complete original's
corresponding result. Inventories remain unchanged.

The old v1/89-case diagnostic retains its original reader hash and historical
scope; it cannot satisfy the new gate. The existing manual-only hosted entry
carries the new capture flag and gate. No workflow was dispatched, no history
was split, and no frozen S/N count or resource limit changed.

## Validation and pending execution

The unchanged full `feeb7241` original passes voting replay with 138 reservations
(69 writers / 69 waiters). Original publication derivation finds 34 publications.
It still lacks local PUBLISH observations, so slot/activation composition fails.
This diagnostic does not change its original admission.

Two Java regressions cover exact local bytes through a real two-slot TCP driver
and exceptions before/after local publication. Small native evidence and
independent replay qualify the observation path, not the whole required-four
history. See [the validation index](phase3-evidence/membership-control-resources.json).

Final validation passes both Java regressions, 152 focused Python tests and 96
tests with Python assertions disabled. The final two-slot original passes full
native physical/publication/resource replay followed by all 58 voting/slot/
activation negatives. The earlier sandbox socket refusal and missing stable
quorum observation remain recorded separately. Document contracts and the
unchanged five-gap qualification plan also pass.

The next complete execution must retain one immutable source/build/reader
through bootstrap, learner, INTENT, joint voting, FINAL, new-view continuation,
maintenance and close, then pass all 147 negatives. That long final-source
execution remains pending for the hosted batch. Existing exact-attempt,
relocation and original-first admission constraints still apply.
