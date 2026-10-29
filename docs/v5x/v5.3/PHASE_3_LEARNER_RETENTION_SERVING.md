# Native learner source serving with quorum retention

[A32](PHASE_3_CONTRACT_AMENDMENTS.md) connects the existing activation endpoint to
[quorum recording](PHASE_3_LEARNER_RETENTION_QUORUM.md). An explicitly enabled
retained-mode owner serves the actual learner only after the current installed
proposer records the exact endpoint on a majority. Phase 3 remains **OPEN**.

## Serving and lifetime

The original request, permanent identity, correlation, source cut and reserved
alias are validated before the local force. Prefix, ancestry and generation traces share
one 64 KiB-accounted recording within the source service's original deadline.
Concurrent requests share the result; a failed quorum remains failed for that
service lifetime. Three identical transport attempts per peer are inherited from
A31. No fresh trace resets that budget or retries a different logical operation.

Only the recording's exact owner/resource pool/reader can use it. Creation,
references and bytes revalidate the original selected endpoint and ballot under
the journal lock. Completed-session cache replies are also checked. A higher
observed ballot, changed source, deadline or close prevents further replies;
already-returned frames remain protected by the durable obligation.

Closing first cancels the quorum, then drains transfer sessions. Waiting network
calls hold neither the journal nor the registry lock. The retained control lease
is released after the recording task exits; cancellation cannot make its still
live memory disappear from accounting. Source aliases for ordinary voters cannot
be used by a retained-mode nonvoting learner to bypass recording. ROOT discovery
continues to expose only the original metadata.

## Focused qualification

`V53LearnerRetentionServingTest` constructs actual native BARRIER, RESERVE and
PREPARE histories. The network scenario uses the real activation endpoints,
TCP transports and learner source client. Node 2 loses its first forced ACK and
node 3 is unavailable; the subsequent complete prefix/generation acquisition
must reuse one recording, preserve one ledger revision, and exactly match every
original generation file. No local voter or live materialization is created.

Other cases test foreign owners/readers/resource pools, unguarded export refusal,
expiry and close of a live capability, final completion-cache refusal after a
higher ballot, invalid correlation/ordinary aliases before recording, and
cancelling two requests that share a pending quorum. Legacy source and transfer
service regressions cover compatibility with the earlier explicit fixture mode.

Execution results and exact source/archive hashes are recorded in the
[source-bound receipt](phase3-evidence/learner-retention-serving.json). This is
focused component qualification, not an independent whole-history proof or the
full hosted matrix.

The same batch also executed the original continuous READY/CANCEL/reopen case
with enabled owners in 377.4 seconds, before adding the final start-of-recording
cut guard. Its separate source snapshot and diagnostic retain exact endpoints
0, 1, 3, 4 and 5. The old independent reducer refuses the new owner ledger at
`admitted exact before-network: node-1`; that is a reader implementation gap, not
a qualified evidence negative. Current-source focused tests exercise the final
guard separately. No historical receipt is rewritten to claim newer coverage.

The subsequent [independent replay batch](PHASE_3_LEARNER_RETENTION_REPLAY.md)
now derives those original bytes and validates the retained READY/CANCEL/reopen
history and 31 exact evidence negatives. The previous receipt and reader-gap
observation remain unchanged; this is a new source-bound reader qualification.

Remaining work: authentic forced-head confirmation and narrowing, current-source
and all-profile READY/CANCEL/reopen qualification, locally forced matching INTENT,
all five joining profiles, original-first independent replay and evidence
negatives, halt/SIGKILL, maximum combined resources and autonomous scheduling.
The immutable full histories belong in the [deferred hosted matrix](PHASE_3_DEFERRED_ACCEPTANCE.md).

Final-source execution passed all three focused serving tests with no skips.
The separately identified earlier runtime passed 17 compatibility tests and the
native cancellation case; all three snapshots total 25 Java test executions
(including repeated cases). Five lightweight Python checks and the documentation
contract passed, including 1,344 local links. The 7,317,018-byte archive retains
original physical histories, exact tested sources, reports and the still-failing
whole-history reader diagnostic; its digest is in the receipt.
