# Phase 3B — runtime-scoped transfer service

Status: locally qualified. The complete
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open.

## Actual storage dispatch

`MembershipTransferService` owns incoming read-only source sessions for one runtime
view/ballot lifetime. A requester provides the original content reference; the
journal resolves its type from retained PROMISE/BASIS/SELECTED records, a complete
active vote, or the verified current packet. An original BASIS opens its complete
source export; other supported records open only that exact record. No caller
registers a replacement source or supplies record bytes to this dispatcher.
The BASIS ballot must equal the exchange ballot. Other original records may have
older ballots; the receiving protocol still validates their exact expected meaning.
A historical BASIS without its retained source cannot open a complete source.

Every request is bound to the frozen root/view/ballot, permanent sender/recipient
identities and trace. A new trace requires sequence one and an empty initial
CHUNK REQUEST. The existing offer/chunk/commit protocol owns content ordering,
transfer IDs, exact duplicate replies, framing and shared buffer limits. Transfer
completion is not an installation or voting ACK, and serving another voter's
retained record does not claim that this server performed that voter's force.

## Lifetime, capacity and concurrency

The registry, each trace/tombstone, source exports and cached replies use shared
resource reservations. Per-peer simultaneous calls obey the caller's in-flight
bound. Independent peers progress without holding a global monitor during source
I/O. A failed trace retains a bounded tombstone until this runtime scope closes;
it cannot reopen against a newer source. A refused capacity admission allocates no
trace. Successful sessions retain the last reply/export until scope closure or
expiry, permitting an exact retry after a lost final reply.

All traces inherit the original start and deadline. Requests and replies check
time and the runtime fencing guard; delayed work cannot extend the budget. The
runtime's periodic loop must poll expiry and close this service on campaign
replacement, fencing or owner shutdown. There is no separate background reaper.
Close is performed outside the journal monitor, marks the scope closed before
releasing sessions, and prevents an already admitted request from creating a new
export. An outstanding caller still drains through its normal finally path.

## Evidence and limits

The real TCP case uses public bootstrap at sizes 3/4/5. Two different peers
concurrently obtain a full original source and a separate original PROMISE through
one service, without preregistered sessions. The independent reader reconstructs
the original bootstrap, grants, unchanged final storage, exact exported/received
files and both complete wire transcripts. It also checks the source-bound test's
observed before/after-close counts; those counts alone are not physical proof of
resource reclamation. Java assertions check actual shared reservation release.

Additional qualification covers duplicate requests, poisoned traces, missing
records, foreign identities/context, concurrency and shared capacity exhaustion,
original deadlines, fencing, close during an admitted request, lost responses,
all seven record kinds and published records after pending-vote retirement.
The seven-kind fixture uses private initial provisioning; the TCP and published
record cases use public offline bootstrap. Neither fixture substitutes for a
complete network activation or joint membership transition.

This supplies the transfer handler, not the complete runtime's authority/ballot
owner loop. Full activation dispatch, authenticated force-observation provenance,
newer-prefix discovery/adoption, source rotation, abandoned receiving-scratch
recovery, learner/joint transitions, voting/publication and distributed process
qualification remain open. Public automatic membership stays disabled. No wire
or persisted format, POM, workflow, retry count, legacy runtime or V5.2 runner is
changed.

The [local receipt](phase3-evidence/transfer-service.json) binds **63 Java tests
across nine suites**, including twelve service cases, and **551 Python tests** in
normal and optimized modes. The three-size TCP evidence contains 45 complete-source
exchanges and nine separate-record exchanges; independent original-first replay,
15 exact negative mutations and optimized/portable replay pass. Existing source,
record, export and activation evidence from this build also passes replay.

An initial 60-test execution passed. Three additional service cases and actual
lifecycle-count serialization were then qualified in a twelve-test execution;
the other 51 tests retain their initial results against identical production
JARs. Repeated cases are counted once. Both original executions and source/build
indices remain retained. These checks establish local component behavior, not
full distributed activation, maximum-envelope performance or protected acceptance.
