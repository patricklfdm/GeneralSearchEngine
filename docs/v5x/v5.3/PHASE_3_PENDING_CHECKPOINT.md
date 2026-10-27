# Phase 3B — native pending checkpoint receipt delivery

The retained-record service previously searched forced votes and published
capsules, but not the native applied end awaiting publication. A receiver could
therefore have forced its application ACK while the publisher could not retrieve
it. The original-source regression fails with `original forced record unavailable`.

## Native ownership and lifetime

`MembershipGrantJournal` now also resolves CHECKPOINT and CHECKPOINT_ACK records
from its own completed native application, including its retained renewal records.
The lookup compares the exact requested digest/kind, then checks the live
`PendingPublication` capability against the owner, promise, selection, certificate,
selector, original parent and complete on-disk application end.

Reopening files alone does not recreate the capability: native certificate
application must re-establish it. Copied ACKs, a foreign voter and incomplete or
stale application state cannot substitute for that owner. Each borrow read
rechecks retention, so higher-ballot fencing revokes a pending export. Close and
the original deadline retain their existing bounded release behavior. Existing
published-history lookups remain distinct and unchanged.

The change adds no wire/storage format, resource ceiling or public API. It uses
the existing record-transfer protocol and original-owner checkpoint receipt
validation. Returned remote observations come from that real transfer, never
from reconstructing a witness digest alone.

## Qualification

The [source-bound receipt](phase3-evidence/pending-checkpoint.json) records exact
snapshots, tests, original failure and raw archives under
`target/v53-pending-checkpoint/`.

The final immutable build passes 29 Java tests: three new native export tests,
ten existing record-transfer tests and sixteen existing checkpoint-transfer
tests. Every current native source/resource/test file matches that snapshot.
The new original-first reader regression passes normally and with Python `-O`;
three related future-quorum reader regressions also pass.

The native TCP history starts with actual public bootstrap, election, phased
BARRIER votes and application by all three voters. Node 1 fetches nodes 2 and 3's
original ACK bytes, then uses the actual received observations to publish index 1.
Both remote nodes remain at published index 0. The test explicitly drives this
sequence; it is not the future-retention dispatch loop or an autonomous election.

Independent replay derives every original bootstrap/vote/application record,
checks all six TCP exchanges and their permanent owners, requires native force
before receipt delivery and delivery before selector publication, and derives
the exact final files. Ten mutations cover original certificates, owner ACKs,
wire data/correlation/commit, local and remote force order, delivery order,
publication files and result scope. The original must pass first. Archived,
relocated optimized replay must reproduce the same outcomes.

Additional Java regressions check pending statement/ACK bytes, rejection of a
different owner's ACK, expiry, reopen without native application, actual
reapplication, higher-ballot fencing and released control leases. Existing record
and checkpoint transfer suites preserve their own original qualification scope;
renewed pending-parent maximum headroom is not inferred from the first-BARRIER
history. No new durable-write transaction or power-loss qualification is claimed.

## Remaining integration

The runtime must still connect incoming vote/application controls and real remote
publication, consume the future-recording prerequisite at actual sends, and
schedule reconciliation/election/maintenance autonomously. Learners, all seven
joint profiles, maximal completion headroom and the full 3B–3E closure audit remain
required. This component does not enable the public membership runtime or change
V5.2, CI, cloud execution or release behavior.
