# Phase 3B — bounded private transport component

Status: **LOCALLY QUALIFIED**, 2026-10-25. The enclosing
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open. This component does not
enable public membership service or close the complete transport/source batch.

`MembershipTransport` sends the frozen protocol 1.3 frames over actual private
TCP connections. Its peer directory comes from a verified complete capsule. It
retains immutable full identities for historical discovery without granting those
identities a vote. A directory update must preserve all earlier reservations and
the same root/local identity; resolved private endpoints cannot alias each other.
Addresses are resolved once on admission. Receiving a frame checks its root,
complete sender/recipient identities and the sender's allowed network address.

This is the protocol's existing trusted-private-network/exclusive-identity model,
not TLS or Byzantine authentication. A transport response remains untrusted
protocol input. Voting eligibility, higher-ballot handling, source verification,
durable force and application readiness remain the owner's responsibility.

## Retry, lifetime and capacity

- One `exchange` call makes exactly one connection/request attempt. The protocol's
  `MembershipExchange`/activation controller owns the three-attempt limit and exact
  original request. There is no second transport retry loop.
- The transport uses the earlier of the original deadline and the caller's
  per-request timeout, measured before worker dispatch. It checks the deadline
  during nonblocking connect/read/write and before returning an observed reply.
  Event/handler work cannot produce a successful reply after that deadline.
- Each peer has separate inbound/outbound caller-bounded permits. Inbound and
  outbound virtual tasks permit reverse source requests without a fixed worker
  pool deadlock. The shared control-frame accounting bounds total buffers/owners;
  incomplete inbound connections also have a finite global limit and timeout.
- A receiver reserves a header slot, validates kind/version/length and the stricter
  caller frame bound, then increases that same reservation before body allocation.
  Failed growth leaves its existing ownership intact for cleanup. The frozen
  8 MiB frame, 256 control-owner and 64 MiB queue ceilings remain unchanged.
- Cancellation keeps reservations until its running worker unwinds. A completing
  sender releases bytes and its peer permit before executing user continuations.
  Close shuts sockets and interrupts workers; external close has separately
  bounded acceptor and worker waits using the caller timeout. Close from a
  worker/callback initiates shutdown without waiting
  for itself. Handlers must cooperate with shutdown; an uncooperative handler
  causes explicit close failure rather than a fabricated successful drain.
- Request/reply root, view, ballot, trace, sequence and inverted full identities
  must match. An exact protocol REJECT is delivered to its owner for handling;
  malformed/foreign frames, thrown handlers and capacity failures manufacture no
  voting ACK. Transport failure categories do not authorize client-operation retry.

## Qualification boundary

`V53MembershipWireTest` checks all 21 frozen frame kinds, header-only rejection,
correlation and atomic reservation growth. `V53MembershipTransportTest` starts
real sockets over public offline-bootstrap identities at stable sizes 3/4/5 and
exercises stalled/reverse requests, explicit lost-reply attempts, original
deadlines, cancellation, callback close, inbound/outbound bounds and wrong replies.

The full-mesh component retains 38 ordered STATUS exchanges, original admitted
bootstrap bytes and unchanged final disk snapshots. The independent Python
reader reconstructs that bootstrap, requires every ordered pair, checks exact
status/correlation bytes and verifies unchanged storage. Original evidence must
pass before ten targeted negative mutations can count as successful rejections.
The raw transcript's socket provenance comes from the Java test and retained
source/build/JUnit; a transcript alone is not proof of a network execution.

Still required in 3B: source/record/application delivery with real staging lifetime,
historical authority discovery and adoption, failed-source rotation, and integrated
network/process activation evidence. Learner/joint transitions, automatic FINAL,
public READY and complete S/N qualifications are later checklist obligations.

The [local receipt](phase3-evidence/transport.json) retains exact source/build
hashes, 54 Java tests in ten suites, the original network bytes, normal/optimized
and portable independent replay, and the earlier compile failure. The compile
failure was a test recorder referring to a private context field; it was corrected
to use the original bootstrap ROOT record. Subsequent tests did not relax any
production validation or frozen format. The earlier 15-test network pass lacks
the later final-disk recorder and remains a separate preliminary observation.
