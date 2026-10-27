# Phase 3 — native remote publication

This batch connects a live future-retention quorum to the actual remote PUBLISH
operation. It does not enable public membership or close a whole 3B–3E gate.
The original native application and votes are explicitly driven in the retained
histories; autonomous scheduling and native incoming vote/application controls
remain required.

## Authority and ownership

The sender's `Recorded` value constructs only its own certificate/recipient
PUBLISH. It rechecks the native pending application, exact SELECTED, original
ballot, retained local future proof and original deadline. The TCP write boundary
performs the check again after connection/queueing. A caller cannot supply an
arbitrary dispatch callback or substitute a different payload. Three identical
I/O/deadline attempts are allowed; they do not reset the original budget. Closing
cancels an outstanding exchange and late completions cannot produce a successful
return. The durable future proof remains after any indeterminate send.

`MembershipPublicationEndpoint` is scoped to one actual completed native
application. It pulls exact original checkpoint ACKs from their permanent owners,
counts separate old/new majorities, then uses the native selector publication
transaction. Expected ACK bytes are lookup hints only. Supplemental renewed
checkpoint paths use the same collection rule, but first-BARRIER evidence does
not qualify maximal ancestry or every joint profile. A received higher ballot
fences the receiver and its correlated rejection is propagated to the sender.

Reverse source transfers remain available while the one bounded writer waits.
Duplicate PUBLISH calls share that writer and recheck actual published bytes
before responding. [A06](PHASE_3_CONTRACT_AMENDMENTS.md#a06--exact-remote-publication-acknowledgement)
adds a distinct PUBLISH_ACK binding certificate, selection, complete published
anchor and actual local generation. The ACK follows selector force and covered
application/retention cleanup. A higher ballot after force suppresses it without
undoing the published cut. Publication ACKs do not authorize peer-possibility
narrowing; that still requires a complete verified copy.

## Qualification and limits

The source-bound [receipt](phase3-evidence/remote-publication.json) records the
native tests and original-first independent physical/network replay. Stable
3/4/5-voter histories actually publish only the intended remote receiver while
the sender retains the pending future. The 3-voter case deliberately loses its
first publication acknowledgement; ordinary per-request timeouts may also require
identical retries in the larger groups. The reader checks actual sends and
received responses separately from server response-write attempts, which alone
cannot establish delivery. A further exact duplicate changes no stored files.

Negative native cases cover ballot/close between queue and write, missing actual
checkpoint majority, higher ballot after publication force, higher checkpoint
rejection, wrong certificate and expired scope. The independent reader derives
all original votes, applied ends, each original future proof, checkpoint bytes,
published generation and ledger promotion before comparing outputs. Exact
mutations include missing original certificate/ACK, quorum delivery, send ordering,
checkpoint receipt ordering, selector/ACK bytes, retry identity and force evidence.
Original validation precedes every negative replay.

The earlier catalog initialization and test-report serialization failures remain
retained. The receipt distinguishes earlier source snapshots, added observability,
and the final rejection-fencing correction. There is no measurement retry or
relabeling of failed evidence as an accepted original.

This receiver scope does not yet reconstruct a duplicate-publication service from
an already-published restarted owner. Autonomous owner replacement/reconciliation,
real incoming ACCEPT/PROOF/application controls, learner ADD/REPLACE, all seven
joint profiles, final new-view service barriers and maximum completion headroom
remain open. Existing storage crash qualification is not claimed as new incoming
publication process-kill evidence. Full Phase 3 acceptance and protected CI remain
open; this batch changes no V5.2 runner, cloud workflow, POM or paid execution.
