# Read-only distributed learner-head queries

This is the next component after [local forced-head observation](PHASE_3_LEARNER_HEAD_OBSERVATION.md).
Phase 3 remains **OPEN**. Receiving an ACK does not yet discharge any durable
source obligation or complete automatic learner enrollment.

`MembershipLearnerHeadEndpoint` installs a real listener only from the sealed
prepared/current head of an actual typed owner. Its only handler is
`LEARNER_HEAD_QUERY`; PREPARE, voting, source transfer and self/nonvoter requests
are refused. The listener retains only the original at-most-five voter identities
needed for authorization, not another full operation catalog. It uses the existing
transport's bounded buffers, private-address checks and permanent peer mapping.
Those checks assume authentic exclusive peers on the trusted private network;
they do not provide TLS authentication against a malicious network member.

The query carries the complete original ADD/REPLACE request. Its envelope binds
the root, original stable view, permanent voter and learner identities, fresh
trace, sequence 1 and the learner's correlation ballot. The ballot is never
allocated/observed as an election. The ACK contains the request hash and exact
forced endpoint (cut, catalog and application). Source status, a downloaded
receipt and a caller-created endpoint cannot instantiate the listener. Original
typed ownership and cancellation checks run while handling and immediately
before response writing. Closing stops future responses and drains transport
outside the handler monitor before releasing the observation lease.

`MembershipLearnerHeadProbe` obtains its full request from the actual native
retention ledger, under its exclusive journal owner and exact resource pool. It
does not offer another endpoint; it must work with two unresolved endpoints
already present. The probe reserves 128 KiB CONTROL before retaining query,
reply and binding metadata. The learner observation uses the existing 32 KiB
CONTROL reservation; transport buffers remain separately accounted.

The same query frame may be sent at most `min(3, maxRetryAttempts)` times. Only
transport IO and per-attempt deadline failures retry. Original expiration,
closure, protocol/capacity failures and malformed responses stop the exchange.
Every attempt shares the same absolute original deadline. No client mutation,
membership operation or measurement is retried. Submission/waits do not hold
the journal monitor. Close cancels the pending future; if submission is still
executing, its metadata remains accounted until that task exits.

On receipt, normal envelope/correlation checks are followed by exact request
hash and independent current source ancestry checks. A source behind the claimed
head cannot accept it by merely trusting a larger index. The live result
rechecks its owner, retained original operation, ancestry and deadline. A
terminal publication such as CANCEL invalidates that reservation. No durable
ledger entry point consumes this result yet, so observing progress cannot
accidentally erase an older selected source's uncertainty.

The [source-bound component receipt](phase3-evidence/learner-head-protocol.json)
records focused qualification and all failed development attempts. The native
case uses actual BARRIER/RESERVE/PREPARE, quorum-retained source endpoints,
TCP acquisition and typed selection, then loses a real server ACK and checks
the retry. It preserves the source files and `[2,3]` ledger throughout querying.
Negative cases cover identities/request/trace, ancestry, permanent and exhausted
transport failures, original expiration and concurrent close. A final actual
CANCEL invalidates the previously received result. The separate typed fixture
checks that revoked ownership and voting requests cannot produce an ACK.

This is not a full independent physical/history replay or a process-death gate.
The existing [deferred acceptance requirements](PHASE_3_DEFERRED_ACCEPTANCE.md)
still apply. Next, persist sufficient discharge authority through PROMISE and
SELECTED, prove that a stale `[2]` source plus confirmed `[3,4]` can be reconciled
without dropping an unconfirmed endpoint, and connect repeated refresh and the
matching locally forced INTENT. Do not weaken the two-endpoint bound or the
conservative merge to make that case pass.

Rollback removes the new listener/probe entry points. No durable file format or
existing message has changed; the new unpublished wire IDs must not be reused
with a different meaning. Existing conservative ledgers remain valid.
