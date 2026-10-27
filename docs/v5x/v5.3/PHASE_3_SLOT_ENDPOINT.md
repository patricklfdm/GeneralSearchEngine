# Phase 3 — continuous native slot receiver

The private `MembershipSlotEndpoint` combines incoming ACCEPT, PROOF, APPLY,
future retention and PUBLISH under one installed native selection. It keeps the
same socket handler and original deadline through all phases. A single transfer
registry owns the actual source sessions across the application/publication
handoff. There is no fallback to a different registry after a failed trace.

Only the actual owner's completed typed application can create the publication
scope. Checkpoint acknowledgements are still fetched from their original owners;
application ACK does not publish the selector. Original governing future-target
recording remains a prerequisite on the sender. After the receiver publishes,
exact PUBLISH duplicates may acknowledge that completed cut, while stale voting
controls are refused. A higher verified ballot fences both paths.

Different concurrent controls are refused before a second mutation task is
admitted; identical controls share the underlying bounded completion. Reverse
source transfers do not wait on the control writer. Close cancels child work,
releases transfer ownership and drains active control callers without holding
the journal monitor. All reservations use the existing resource limits.

`MembershipSlotDelivery` sends only the proposer's actual native ACCEPT/PROOF/APPLY
with at most three identical I/O/deadline attempts, one original deadline and an
actual socket-write fence. A correlated response is never counted as an original
vote observation. Invalid responses are not retried.

Checkpoint collection starts one bounded batch sufficient for both old and new
majorities, contacting the original owners concurrently and consuming their
receipts in identity order. A failed I/O/deadline owner is omitted and the next
eligible owner may be contacted. Protocol errors and higher ballots remain fatal.
The writer reserves completed-receipt storage for the current statement plus
at most six renewed ancestors and six original owners per statement, using the
catalog's maximum CHECKPOINT_ACK frame size. This reservation outlives individual
pulls until publication finishes. Tasks, transfers and buffers use the existing
resource limits; cancellation
closes outstanding pulls and joins their workers. The dispatcher relies on each
child's durable checks and retains its own deadline/close boundary; it does not
cache or bypass storage identity validation.

The original sequential four-voter DATA diagnostic reached publication validation
14.962 seconds after first send and durable completion at 17.846 seconds, without
a delivered ACK. A subsequent parallel-collection diagnostic delivered the ACK at
12.899 seconds under the same five-second request and three-attempt bounds. These
are individual local observations, not an SLA. Earlier failed matrices and the
diagnostic compile error remain retained at `target/v53-slot-endpoint`.

The [local receipt](phase3-evidence/slot-endpoint.json) records 22 passing Java
tests before the final receipt-buffer reservation correction, followed by three
current-source checks of capacity refusal, concurrent DATA publication and active
close/cancellation. All 674 Python tests pass. Six stable slot TCP histories,
three existing remote-publication histories and eight halt/SIGKILL restart cases
provide 17 original histories. All 17 histories and 181 exact mutations pass independent original-first
physical/network replay and archive relocation with Python assertions disabled.
Earlier failures remain retained; this qualifies the named component only. The local sender and original activation remain
explicitly driven. Automatic election/discovery ownership, next-slot maintenance,
redispatch after coordinator restart, learner/joint completion, maximum combined
resource headroom and full Phase 3 qualification remain open. No public API,
wire/storage format, frozen measurement parameter, cloud workflow or release pin
is changed by this integration.
