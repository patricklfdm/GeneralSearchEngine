# Bounded outgoing heartbeat samples

This receipt describes the original stable, READY-only sampler. The later
[recovery-heartbeat increment](PHASE_3_RECOVERY_HEARTBEAT.md) adds checked
installed-campaign recovery and exact joint majorities, with at most five remote
peers. The explicit API and the historical reader below still require READY;
their original results are not complete recovery qualification.

Phase 3 remains **OPEN**. `MembershipRoundDriver.heartbeat()` now samples the
current stable voters concurrently, after the existing fresh-barrier readiness
guard. It is an internal single-call component; automatic timer/campaign
ownership and public service are still separate work.

## Lifetime and authority

A sample captures the original root, view, permanent identities, proposer ballot
and local cut. It reserves a bounded request/reply pair for every peer before
fanout. A partial reservation or encoding failure releases the reservations
without sending. The construction reservation covers the private header bound
even if the caller frame cap is smaller. At most four peers and three attempts per peer are admitted;
transient transport IO/deadline failures retry the same immutable frame under the
same sample deadline. Capacity, close and protocol failures do not start another
attempt. A healthy alternative can complete the contact majority while an
unavailable peer is cancelled. Exhaustion fails the enclosing round.

The sample deadline is the smaller of the enclosing round's remaining original
lifetime and the existing per-request timeout times its finite attempt count.
Neither a new sample nor a retry renews that round. Close cancels pending futures
and wakes the waiter. Idle polling checks cancellation and the observed ballot
without taking the journal writer monitor or scanning storage. Consuming a reply,
sending/retrying and returning still perform the full readiness/owned-file checks.
The idle check is a cancellation hint and cannot authorize work.

An authenticated, exactly correlated higher-ballot rejection is observed before
it enters the reply queue. A different peer's queued ACK cannot hide that fence.
A reply delivered by the link after local completion still validates its original
context before observing a higher ballot; a foreign root or recycled identity
cannot fence this owner. Cancelled or undelivered bytes are not observations.

`Contact` is diagnostic. Its majority may include a current voter outside the
fixed selected source set and its cuts are untrusted progress hints. It creates
no grant, copied floor, vote, read lease, new selected set or readiness. Subsequent
slots still perform their own original ACCEPT/PROOF and retention/publication
protocol. Learners, removed members and another view are not contact voters.

## Original evidence

The [receipt](phase3-evidence/heartbeat-round.json) retains source inventories,
executions, failed attempts and original native histories. Component tests use an
actual installed selection with an explicit guard; only the native integration
establishes real fresh-barrier readiness and subsequent DATA publication.

The native history is public bootstrap, original activation, BARRIER 1, one
heartbeat sample and DATA 2 on the same owner. Before/after heartbeat inventories
are exactly the independently reconstructed cut-1 files for all three nodes.
The reader reuses the complete two-slot physical/network and round-lifecycle
validators. Its temporary projection omits only the separately validated heartbeat
snapshots/events/frames; retained originals remain unchanged. Every omitted send,
response, delivery, diagnostic majority and hint is checked against the original
identities, ballot, cut and readiness boundary.

The unselected third voter can observe the heartbeat ballot without installing
the selected state. Its later retention request then rejects at the installation
check instead of the earlier fence check. The specialized diagnostic check binds
this case to a retained heartbeat response, the unchanged physical node, no more
than two request hashes and three identical diagnostics per hash. Failed request
bodies are not retained by this fixture, so their diagnostic hashes/reasons are
not voting evidence or proof of the failed payload. The older readers retain
their original rejection policy by default.

Thirteen negative variants cover altered underlying publication, heartbeat
storage changes, missing original snapshots, ordering, correlation/cut forgery,
retry overflow, invented contact/hints, missing delivery and hidden writes or
failures. Original validation must pass before any negative is counted.

The first native execution completed the operations but its test-side event
encoding used node IDs as JSON keys, which the canonical encoder forbids. The
corrected evidence encodes ordered `{node, cut}` rows. Its failed original remains
retained; it cannot qualify a complete history. A later review moved reservation
before frame encoding and added bounded idle cancellation. The receipt separates
those source snapshots and their validation results.

Final-source validation passes all 15 outgoing Java tests, the complete native
original replay and all 13 exact negative variants. Thirty-five focused Python
tests pass, including the unchanged older-reader rejection policy. The earlier
inbound nine-test regression also passed during this batch. The idle cancellation
regression fails against the earlier implementation and passes after correction.
The last session interruption is retained as unqualified; no process remained
alive before the unchanged Java inputs were validated in a fresh snapshot.

Replay one complete original with:

```bash
python3 -m scripts.v53.heartbeat_round_evidence /path/to/original/run --qualify
```

This does not qualify autonomous elections, continuous restart/rejoin, all stable
sizes/membership transitions, process-death cuts, or a failover SLA. Those remain
Phase 3 gates. No frozen format, timing limit, POM, workflow or cloud execution is
changed. Rollback removes the private outgoing helper, its round ownership route,
and this qualification extension; the earlier inbound heartbeat component and
retained originals remain available.
