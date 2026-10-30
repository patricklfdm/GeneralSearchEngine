# Joining preparation hint over the existing transfer channel

Phase 3 remains **OPEN**. The old-side preparation coordinator now registers its
result on the actual old proposer's activation endpoint. The joining endpoint's
`initializeFrom(proposer)` fetches this routing hint over the existing bounded
CHUNK/SOURCE_OFFER/TRANSFER_COMMIT path before its managed source acquisition,
durable initialization and voting handoff. The whole native test no longer passes
the in-memory hint directly to the joining initializer.

The publication is ephemeral read-only data. `MembershipJoiningPreparation`
binds the actual old proposer and resource pool, current JOINT cut, exact joining
identity, original local BASIS and ballot, original preparation guard/deadline,
and absence of a selected round. It holds at most one endpoint registration. A
higher fence, changed source/cut, selection, close or original deadline prevents
new reads; the endpoint's existing expiry loop retires an expired publication.
Closing preparation revokes its registration before abandoning the campaign.
The native composed test keeps that preparation scope alive through acquisition
and initialization, instead of closing it immediately after obtaining the hint.

The derived lookup alias binds root/cut/joining identity. The at-most-16-KiB
canonical `gse-v53-joining-preparation-hint/1.3` payload contains root, cut digest,
joining identity, ballot and a canonically ordered node/BASIS list. This is a
new ephemeral metadata payload carried by existing transfer frames, not a new
frozen wire record, persisted ledger, grant, receipt, majority proof or public
API. Duplicated nodes, foreign roots/cuts/identities, wrong proposer, malformed
membership, noncanonical ordering and oversized payloads are refused.

A hint only limits routing. It does not prove that a majority forced anything.
The joining owner still retrieves each advertised original and verifies its
exact BASIS bytes, one ballot and conservative retention union under its actual
unused original-owner capability. Conditional fixtures and hints alone cannot
initialize a new voter. Missing publication fails without allocating a ballot,
selecting a different source or manufacturing fallback data. Unavailable
transport retains the existing identical-request retry rule; explicit refusal
is not silently retried as a new campaign.

The publisher and reader retain their own original local deadlines. No monotonic
clock value or renewed lifetime is imported from the remote hint. Close cancels
a pending hint read through the same initialization task that owns later source
reads and admitted force work. Publication and each active export reserve 32 KiB
of existing CONTROL capacity. The joining task conservatively reserves 64 KiB
for encoded/decoded routing data until its admitted work exits, including when
close races with force completion. Existing global, source and transfer bounds
remain unchanged. Completed-transfer exact reply caches retain their ordinary
read-only replay semantics; such a cached reply cannot revive a publication or
establish a vote/initialization capability.

Focused validation exercises actual encoded frames through the production
activation endpoint and transfer service using original conditional disk
fixtures. Tests cover lost offer/data/commit replies, no publication, independent
publisher expiry, higher fencing, revocation, exact owner/single registration,
canonical decoding, local BASIS mismatch, failed-admission accounting and
expiry without lifetime renewal. These component tests are not a native TCP or
process-history claim. The broad run passed **59 tests in 243.541 seconds**, including thirteen existing
activation-endpoint cases and sixteen transfer-service cases. After adding the
receiver routing reservation and independent publisher clock, the final-source
run passed **17 directly affected tests in 21.522 seconds**; all main/test sources
compiled. The earlier 16-test run passed, and the initial negative-test wildcard
compilation failure is retained separately. No run has failures or skips hidden
by aggregation. Documentation contract and its regression check passed.
Original attempts and immutable snapshots are indexed in
`phase3-evidence/joining-hint-handoff.json`.

The existing complete native entry is compiled and now uses actual TCP hint
retrieval followed by exact-source initialization, actual new-voter FINAL,
fresh BARRIER and retaining cold reopen. It remains **unexecuted in this batch**
and indivisible in the [hosted queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Automatic
proposer discovery/election scheduling, full learner/joining orchestration,
all-profile native/process histories, combined maximum-resource validation and
independent original-first replay still prevent Phase 3 closure.

No workflow, POM, paid cloud, V5.2 experiment or repository setting is changed.
