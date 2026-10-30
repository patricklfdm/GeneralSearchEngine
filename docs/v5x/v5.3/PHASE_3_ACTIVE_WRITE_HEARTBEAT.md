# Heartbeats during a native stable write

Phase 3 remains **OPEN**. The [competing-campaign producer](PHASE_3_COMPETING_CAMPAIGNS.md)
exposed a serialized DATA keeping the automatic owner away from its ordinary
heartbeat loop. Cooperative progress now services a due heartbeat within that
same original write invocation. It adds neither another writer nor mutation
replay. Component and complete-history evidence are distinct.

## Ownership and scheduling

`MembershipRoundDriver` arms a private interval only after an automatic round
has completed its fresh BARRIER and entered READY. Both ordinary heartbeats and
cooperative samples record their completion time. A slow sample starts one new
interval rather than issuing a burst of missed ticks. No sample overlaps another.
The original round lifetime and every request/retry bound remain unchanged.

The native slot coordinator checks for due work at validated phase boundaries,
during local generation maintenance, and while waiting for selected peer work,
future-retention recording and remote publication. Waiting uses bounded polls;
an empty poll is not a retry, a new exchange, or permission to extend the deadline.
Peer workers never issue their own heartbeat sample. A progress callback holding
the actual journal monitor cannot start network work; the next unlocked boundary
can service it. Maintenance retains its existing full guard after progress.

A sample uses the existing heartbeat implementation and complete `current()`
validation. It still requires the exact installed selection, stable authority,
ballot and original current cut; a majority response grants no read/leadership
lease. During remote publication a peer can already advertise the new cut while
the coordinator still owns the old cut. The coordinator only advertises its
actual original cut and only advances after local publication completes.

No pulse is enabled during initial recovery, carried-entry replay, fresh BARRIER
construction, SEAL or a configuration handoff. A newly completed fresh barrier
rearms it. Close and fencing retain the existing cancellation/drain paths; a
failed pending publication now cancels its exact future before forgetting the
handle, including a failure raised by cooperative progress. There is no public
API, wire/record format, POM, workflow or configured limit change.

## Evidence and limits

The final adapter-based execution passes **13** checks: five scheduling cases,
four native active-write cases (held ACCEPT, higher heartbeat rejection, explicit
close, held remote publication), and four existing slot cancellation/fencing/ACK
regressions. The unchanged production bytes also pass all **16** existing heartbeat
checks and four selected future-retention checks, including progress without a
fabricated ACK, the original deadline, submission/close races and unrelated replies.
These are **33 distinct passing component checks**, not a complete reactor run.

The earlier expanded execution is retained as **29 tests / one failure**. That
new higher-ballot test incorrectly used the raw round instead of the actual
automatic Session adapter and expected the adapter's exception type. The corrected
four-case suite exercises the actual adapter; the assertion was not relaxed.
The initial six-test snapshot and original implementation comparison retain their
own source hashes and outcomes in the [receipt](phase3-evidence/active-write-heartbeat.json).

The new default-bound three-owner history remains **FAIL**. Node 3 completed its
fresh BARRIER at cut 1 and its one original DATA at cut 2, with heartbeat requests
actually written between the DATA slot's beginning and completion. It then failed
the producer's all-owners-healthy assertion: node 2 had stopped after pre-grant
original-copy acquisition remained unavailable. Close completed without a recorded
error. All 2,493 events, 232 responses, original files and failure diagnostics are
retained; this is not a qualified competition result or independent physical/history
replay. The remaining follower/startup availability path needs investigation without
raising retry counts, fabricating retained copies or replaying the client DATA.

Cooperative scheduling cannot preempt an individual synchronous file operation
or arbitrary callback. It provides progress at unlocked work/wait boundaries,
not a failover SLA under unbounded storage delays. Long measurements and remaining
all-profile/process qualification can run later as independent whole histories
on hosted runners; one continuous original history cannot be split or retried
into success.

Rollback removes the cooperative interval/slot integration together with its
regressions. Keep the earlier failed competition histories and both versions of
their original sources. No persisted-state migration is needed.
