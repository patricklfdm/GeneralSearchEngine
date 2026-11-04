# Transport connection identity for overlapping identical attempts

Status: **native TCP component and independent replay PASS; joining-history
integration OPEN**. This addresses the observation mechanism needed by the
[required-four network gap](PHASE_3_REQUIRED_FOUR_PHYSICAL.md). It does not repair
or upgrade the old trace: that original still lacks attempt identity and remains
unqualified by the complete network gate.

## Runtime observation contract

`MembershipTransport.Events` now has compatible overloads carrying a local
`Connection`: a fresh UUID and the actual local/remote socket addresses and ports.
One immutable connection value accompanies request write, response read and caller
failure; the accepted socket has its own value for request read, response offer
and receiver failure. The caller failure retains that value after the socket has
closed. The two sides correlate through the exact reversed TCP endpoint pair,
not equal UUIDs. Both local IDs must remain distinct and stable within their own
invocations.

The token is never transmitted, persisted as protocol authority, used to dedupe
operations, or used to select a quorum. Wire frames, peer authentication
assumptions, original/per-request deadlines, retries, queue/resource bounds and
handler results are unchanged. It is bounded per in-flight invocation; no global
attempt history or map is retained in production. The existing three-argument
observer and failure callbacks remain valid through default forwarding. A
preflight refusal still does not invent an attempted write or connection event.
Observer failures retain the existing error/suppression behavior.

`V53ConnectionTrace` collects these observations only in the dedicated component
fixture. It binds each retained response frame to the receiver's original
connection value and keeps actual event order across both sides. Existing
joining collectors continue to emit their original trace format until their
whole reader pipeline is extended; silently dropping the new fields to make
an old gate pass would lose the distinction this work is establishing.

## Actual socket histories

`V53TransportConnectionTest` bootstraps three real original owners and runs two
bounded loopback TCP histories. Each holds the first handler until its caller
has actually timed out, then starts an identical request on another socket.

- **late-handler:** the retry completes successfully before the first handler
  throws its declared I/O fault. The old inbound terminal belongs to the first
  invocation even though a later request with the same hash already succeeded.
- **late-response:** the second handler remains blocked while the first offers
  its response and the observer injects the declared I/O loss. The retry then
  returns identical response bytes. Only the second response is delivered.

Latches fix these interleavings; no repeated run is used to wait for a lucky
schedule. Each case retains one caller DEADLINE, one receiver IO, two sends/two
reads and one delivered reply. Both owners drain their sockets/leases, and all
three original owner inventories remain unchanged. The cases are transport
components, not membership execution or resource-maximal qualification.

## Independent reader

`scripts.v53.connection_transcript` checks exact observation schemas and bounds,
canonical local IDs, stable owner/scope/request metadata, literal endpoint
identity, reversed socket pairs, and each invocation's complete ordered
boundaries. It consumes every original response frame and delivery exactly once.
It rejects simultaneous reuse of one TCP endpoint tuple, ambiguous pairings,
missing terminals, metadata changes, duplicate responses, and post-read failures
that would otherwise be silently classified as success. A fully ended tuple may
be reused by a later invocation with new local IDs.

This first entry admits original literal IP endpoints; it does not resolve live
DNS and treat that as retained route authority. Receiver response offers with
no delivery remain failed-attempt observations, never votes or successful replies.
The reader does not infer failure completion from a later matching response.

`scripts.v53.transport_connection_evidence` independently reconstructs the public
bootstrap and unchanged final storage, then checks both exact overlap schedules
and their narrow receipt. It first validates the original and then rejects eight
copy-only mutations with exact reasons: socket mutation, crossed delivery, a late
terminal moved to the retry, missing caller/server terminals, a duplicated
terminal, a missing original response and a false membership-completion claim.
An unrelated rejection cannot count. The original inventory must stay unchanged.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53TransportConnectionTest,V53TransportAttemptTest,V53MembershipTransportTest,V53JoiningTraceTest' test
python3 -m scripts.v53.transport_connection_evidence "$ORIGINAL" --qualify
```

The [retained index](phase3-evidence/connection-attempts.json) records the actual
results: 22 Java test executions with no failures/skips, the two fresh socket
histories, eight exact negatives, and 76 Python tests (17 new). The unchanged
legacy attempt reader also passes the newly produced six-case evidence and all
thirteen existing negatives. Initial Python fixture errors are retained; the
fixture was corrected to use its actual scoped recipient, not node 2's port.
No test threshold or production timeout was changed to make those fixtures pass.

## Remaining integration

1. Thread connection metadata through the old-owner and joining-owner collectors,
   including failure/decorator callbacks and response inventories.
2. Compose that evidence with the complete joining transcript, phase ACK,
   transfer/export and control readers. Preserve legacy strict rejection for
   traces without adequate identity; do not borrow an ACK across attempts.
3. Execute a fresh required-four native history on the integrated source and
   retain independent physical/network/resource validation. The earlier runtime
   `25d80cb3` remains historical evidence for its stated slices only.

Combined resources, frozen coverage and final-source hosted cohorts also remain
open. No Phase 3 completion, public READY, hosted subset or final-source admission
is granted here. The planned twelve subsets / 544 histories are unchanged.
Rollback removes these optional observer overloads and their component collector,
reader and tests together; the legacy trace interface and protocol remain intact.
