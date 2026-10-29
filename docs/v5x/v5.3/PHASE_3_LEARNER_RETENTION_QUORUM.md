# Native learner retention recording

[A31](PHASE_3_CONTRACT_AMENDMENTS.md) adds dedicated intent/ACK messages for the
nonvoting source obligation. This follows
[frozen capture and selected merge](PHASE_3_LEARNER_RETENTION_SELECTION.md).
Phase 3 remains **OPEN**. A returned recording is not yet consumed by the source
export path; export in the new mode stays disabled.

## Recording boundary

The proposer builds the request from its installed native SELECTED, complete
original ADD/REPLACE request and exact current endpoint. Every receiver checks
its own installed round, original stable configuration, joining identity and
endpoint. A pending slot, unfinished maintenance, different request, foreign
storage identity or changed endpoint refuses. This component covers an already
installed pre-joint target; it does not infer an unpublished application or admit
a learner into the voting set.

Under the existing exclusive journal owner, recording conservatively adds the
endpoint to the two-point ledger. Identical retries preserve the same revision.
The ACK follows candidate force, active replacement and parent force, then another
round/fence check. A higher observed ballot after the force suppresses the ACK
while preserving the obligation. Quorum recording includes the proposer and
distinct current voters; a lost ACK repeats only the same frame, at most three
attempts inside the original deadline. Malformed replies fail immediately;
unavailable peers are exhausted and the round fails once a quorum is impossible.

The temporary recording rechecks its original owner, ballot, selected endpoint,
ledger and deadline. Closing cancels even an exchange future returned after close.
No returned set of ACKs becomes durable authority by itself. The local ledgers,
frozen source objects and selected merge remain the durable recovery path.

## Focused validation

`V53LearnerRetentionQuorumTest` builds actual three-voter BARRIER/RESERVE/PREPARE
histories and uses the real TCP endpoint. One scenario loses node 2's ACK after
the ledger force while node 3 is unavailable: a repeated identical request must
return the same revision and establish exactly the node 1/node 2 recording.
Native reopen must retain that ledger, and source export must still refuse.

Separate scenarios cover exhausted three-attempt retries, malformed logical
intent ACKs, the original deadline, a future returned after close, duplicate
receiver requests, invalid root/selection/request/identity/endpoint/proposer,
foreign resource pools, higher-ballot fencing between force and ACK, and
revocation of an existing recording after the local owner observes a higher ballot.
The [source-bound receipt](phase3-evidence/learner-retention-quorum.json) identifies
the actual reports, preserved failed attempt and original raw histories.

All 52 pre-A31 frames, command fixtures and the V5.2 read token remain byte-exact;
the two new kinds bring the syntax inventory to 54. Java-produced frames are
independently checked by Python, separate from protocol authority qualification.

The first local execution was prevented by the sandbox's prohibition on creating
TCP sockets, before bootstrap or protocol execution. Its logs remain retained.
The same source snapshot is tested with local loopback access; no external
network, GitHub job or cloud experiment is involved. That execution passed the
protocol assertions but failed while serializing the request report: node names
are not permitted JSON object keys in the canonical encoder. The corrected test
uses explicit `node`/`digests` rows and adds the local-recording fence assertion.
Production code remains byte-identical across those attempts; the final receipt
must use the corrected execution, not the earlier partial result.

The corrected execution passed all eight Java tests (three native quorum tests
and five format tests), with no skipped tests. Eleven Python tests and independent
validation of all 54 Java-produced frames passed. Source binding checks 1,681
code/build inputs; all three attempts have identical 892 production class files.
The 4,791,616-byte archive retains both failures, successful reports, original
physical histories, network traces and the exact test-source correction.

Remaining work includes consuming the exact live recording under the export
owner lock, authentic forced learner-head confirmation/narrowing, cancellation
and INTENT integration, all five joining profiles, halt/SIGKILL at recording/ACK
cuts, original-first physical and wire replay with evidence negatives, maximum
combined resources and autonomous scheduling. Whole histories stay indivisible
in the [deferred hosted matrix](PHASE_3_DEFERRED_ACCEPTANCE.md).
