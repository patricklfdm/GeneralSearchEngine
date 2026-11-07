# Bounded automatic service owner

Phase 3 remains **OPEN**. A private automatic owner now connects the native round's
election wait, discovery and fresh-barrier activation to a serial heartbeat and
command loop. It owns one original bounded lifetime. The subsequent
[typed-loss continuation](PHASE_3_AUTOMATIC_CAMPAIGNS.md) can open another bounded
round without renewing that lifetime. The native node lifetime below additionally
owns storage, endpoint and transport. Complete competing-candidate/process/profile
qualification and public runtime integration remain separate work.

## Execution and limits

`MembershipRoundDriver.automaticOwner` requires an unused round. Its adapter
passes the owner's original start into the existing election/discovery path.
Only the native round's fresh barrier completes startup. Diagnostic READY is not
a lease: each queued readiness request invokes the full native guard again.
Idle checks use the lock-free current-view/ballot fence; protocol work retains
its existing physical original-byte checks.

One control thread runs all outbound work. A due heartbeat precedes queued
commands. Sampling completion starts the next interval, avoiding bursts of
missed ticks after slow storage or scheduling. Requests and heartbeats share the
original enclosing budget; neither a successful pulse nor a client wait renews
it. The original owner could delay a pulse for a whole active operation.
[Cooperative active-write progress](PHASE_3_ACTIVE_WRITE_HEARTBEAT.md) now services
due samples at unlocked work/wait boundaries inside that invocation. An individual
synchronous storage operation can still delay progress; no failover or latency SLA
is claimed. Complete competition and profile qualification remain required.

The mailbox counts both queued and executing calls against the configured
pending-call bound and the existing global 64-waiter limit. Its fixed 64 KiB
owner reservation accounts for bounded control metadata. Each immutable payload
is reserved before copying, including an input at the existing 8 MiB frame
ceiling; execution's own reservations remain additional. Failure to reserve
returns the waiter immediately. Invalid commands are rejected before admission.

Client admission additionally leaves two free shared waiter slots for the
original local publication's activation caller and nested slot handler. The
count and reservation occur atomically under the resource monitor. With no
other waiters, at most 62 automatic calls (including the executing call) are
admitted; existing protocol waiters or a smaller configured pending-call bound
reduce that number. Both internal handlers still acquire and release ordinary
charged leases under the unchanged global limit of 64. Admission does not
reserve fictitious protocol work, bypass accounting or increase capacity.

### Client backlog completion regression

An original native three-voter run admitted 64 automatic calls, completed the
remote DATA work, then failed at local PUBLISH because its own client backlog
occupied every waiter. The original resource trace records 64 automatic waiters
at that publication request and no matching successful local response. An
earlier diagnostic exhausted its original lifetime after a 90–150 second
election wait; that retained failure alone does not establish waiter starvation.
The isolated regression uses a supported 15–25 second election window while
retaining the 30 second RPC bound and original 180 second lifetime.

`V53AutomaticWaiterCompletionTest` holds one admitted DATA call before dispatch,
fills the remaining client queue, and then runs the actual native protocol.
Success requires the same DATA publication to complete, every queued readiness
call to drain, the owner to remain READY and an observed overlap of 62 original
client leases with its two request-bound publication handler leases. No client
mutation is retried. Two additional control-loop regressions check atomic
refusal, pre-existing protocol occupancy and full-backlog close/release.

This protects completion against the owner's own client backlog. Concurrent
external control requests can still consume the remaining capacity; byte
exhaustion and adverse protocol floods are separate bounds. These focused
regressions do not qualify the full resource envelope or the final-source
cohort. The [development receipt](phase3-evidence/automatic-waiter-completion.json)
retains the failed originals and the validation actually completed.

The corrected-source checks passed 48 Java tests and 19 Python contract tests.
The isolated native test failed on the original runtime at 77.35 seconds and
passed after correction at 77.80 seconds. Independent accounting replay of all
three owner traces passed, including empty final ownership. The leader trace
ties the 62+2 overlap to the same original local PUBLISH request and successful
response. This is a component regression and accounting replay, not the full
physical/history admission of that new source.

The private result handle permits blocking waits and completion inspection,
without caller completion/cancellation or executable callbacks on the control
thread. A wait timeout does not cancel or retry an admitted mutation. Errors
from protocol execution reject the remaining queue and stop this owner. A lost
or failed response may still describe a published mutation; no automatic client
replay or public outcome classification is introduced here.

Close wakes idle work and delegates native cancellation/drain to the round,
preserving discovery's special cancellation handling. Queued inputs can be
released immediately. Executing input and owner reservations remain held until
the worker drains; a cleanup failure or close wait expiry retains ownership for
an explicit later cleanup attempt. The owner does not close the caller's journal,
listener or transport, nor mutate original files merely because a timer expires.

## Validation scope

This section records the original automatic-owner batch; later service and
campaign qualification is linked above. Native node lifetime qualification is
recorded separately below, against its own source snapshot.

The [receipt](phase3-evidence/automatic-owner.json) binds all fourteen tests to
one final-source execution. Earlier twelve-test and two-boundary-test runs remain
retained. Review then moved the first heartbeat's timing anchor before the startup
completion notification, preventing a waking caller/scheduler from postponing it.
All fourteen checks were rerun against that final source.

- Scripted sessions exercise ordering, copied inputs, pending/global capacity,
  heartbeat priority without catch-up bursts, original deadline, higher-fence
  failure, no mutation replay, client wait timeout, close, cleanup failure,
  full-size body accounting and ownership retained after a drain timeout. These
  fixtures qualify the control loop; their response bytes are not native votes
  or proof of a successful membership history.
- The actual round/owner adapter runs a public-bootstrap three-node TCP fixture
  and closes during WAITING. Independent original-file replay confirms unchanged
  authority bytes, the exact normal reopen force sequence and no requests or new
  grants; all six existing negative mutations pass.

The earlier native election-entry and outgoing-heartbeat histories remain bound
to their original sources. They do not substitute for this owner driving an
entire service/restart/transition history. That whole-history qualification,
failure-driven fresh campaigns, all profiles and the Phase 3 process matrix stay
pending. No public API, persisted format, workflow, frozen limit or paid-cloud
execution changes. Rollback removes the private owner/adapter; explicit bounded
round entry, submissions and heartbeat samples remain available.

## Native node lifetime

`MembershipNodeOwner` is a private closeable owner for the original journal,
activation endpoint, TCP transport and automatic service. Construct it before
calling `open`: even a partial open then leaves the caller an exact cleanup
handle. The journal validates original root and local identity; configured seeds
must equal the original directory identities. Scratch paths remain disjoint from
authority and materialization. The resource pool uses the configured staging
limit; existing frame, queue and metadata bounds remain additional constraints.

Opening alone does not campaign or restore READY. After all children are owned,
`start` enters the existing election/discovery/barrier path. Closing first stops
admission, then drains the opener and all work owners before releasing journal
ownership. Worker callbacks can request cancellation but cannot prove their own
termination. The automatic owner now joins its actual thread; the node also
checks transport termination, channels and in-flight counters. A failed drain
retains the journal and exact child for a later external close attempt. A failed
writer cannot be replaced inside that same object. Explicit close followed by a
fresh object must reopen the original disk and acquire a new barrier before work.

The [node lifetime receipt](phase3-evidence/node-lifetime.json) binds:

- Nine lifecycle tests: exclusive cold open; bind failure; close before open;
  seed identity mismatch; cancellation during opening; undrained transport;
  callback close; close during WAITING; actual injected grant-write failure.
  The last case verifies the original storage lock remains held until drain,
  then a fresh object opens without READY or queued command replay.
- Four transport drain regressions and all fourteen automatic-owner tests.
  Their native WAITING-close original history again passes six evidence negatives.
- One complete three-node TCP history with node 1 close/open on the same disk:
  BARRIER 1, DATA 2, fresh BARRIER 3, DATA 4. The actual second selection uses
  node 3 in place of node 2. The physical reader independently reconstructs
  both selected original sources, the unused node 2 capture, installation,
  retention merges, application images and all sixteen snapshot groups. It also
  verifies object lifetimes, original reopen forces and fresh READY ordering.

The earlier cold-reopen result remains `PARTIAL`: its 487 wire exchanges lack
original send bytes for silent requests. The subsequent fully instrumented
history below supplies network qualification without rewriting that result.
Same-process cold reopen is not SIGKILL. Each explicit
service object has a 180-second fixture lifetime; production timings and resource
limits are unchanged. Preserve the whole bootstrap-to-close history on one
runner. No public API, workflow, POM, frozen-format or paid-cloud change.

Rollback removes the private node wrapper and its tests/reader. The existing
explicit journal/endpoint/transport owners remain available; no persisted-format
migration or data rollback is necessary.

## Complete network replay

The subsequent [node process gate](PHASE_3_NODE_PROCESS.md) extends this exact
physical/network replay to distinct leader JVMs after halt and SIGKILL. Its
completed-DATA crash point and original process observations are separately
qualified; they do not change the same-process scope of the history below.
The later [in-flight process gate](PHASE_3_NODE_INFLIGHT.md) separately requires
exact retained DATA reacceptance and a fresh readiness barrier after actual
ACCEPT/PROOF parent-force death.

The [network receipt](phase3-evidence/node-network.json) binds a new whole native
history to the same runtime source plus two fixture observations: complete raw
bytes before request writes, and a boundary after authenticated request reads.
The source, bootstrap, storage and evidence from the earlier 487-exchange run
remain intact. This is a distinct execution, not additional evidence fabricated
for the earlier run.

The new history again changes its selected remote voter from node 2 to node 3
after close/open. Independent physical replay runs first. Network replay then
binds all 515 request writes to original identities, object lifetimes and phases;
all 488 responses require prior actual receipts, and observed client deliveries
require corresponding prior responses. Both selections, all four slots, source
bytes, application transfer, maintenance, original ACCEPT/PROOF observations,
checkpoint ACKs and future-retention quorums are checked before publication.

| Whole-history phase | Response exchanges | Source traces |
| --- | ---: | ---: |
| First activation | 28 | 4 |
| BARRIER 1 | 81 | 16 |
| DATA 2 | 96 | 19 |
| Cold reopen and second activation | 88 | 10 |
| BARRIER 3 | 86 | 18 |
| DATA 4 | 109 | 21 |

Of 88 source traces, 87 complete. The unused node 2 basis pull stops after its
original data and before commit. The reader checks exactly that prefix and never
completes it or counts it toward SELECTED. Node 3's installation includes the
original application image absent from its lower bootstrap cut. Its future ledger
has a different revision from node 1's; each ACK must match its own independently
reduced physical frame, rather than a revision inferred from the slot number.

The remaining 27 writes are nine groups of three silent attempts: four unused
future-retention requests and five checkpoint lookups against the unselected
owner. Their original envelopes and checkpoint references are reconstructed;
none supplies a vote, ACK or delivery. An unrelated, additional or unbounded
silent request fails validation. The retained bytes establish these failed
attempts, not a particular socket error or scheduler root cause.

All 48 physical/network negatives pass, including missing original writes or
receipts, excess attempts, cross-phase and old-lifetime writes, changed unused
source bytes, missing application data and fabricated checkpoint references.
Nineteen focused Python tests pass. The shared slot reader also replays the
earlier 388-exchange automatic reactivation history and all 47 of its negatives;
that historical result remains bound to its original runtime source.

The new one-history result is `PASS` with `fullWireReplay=true`. Phase 3 remains
**OPEN**: actual halt/SIGKILL, competing automatic candidates and complete
transition/profile qualification are still required. No runtime Java, POM,
workflow, protocol format, time/resource limit or paid-cloud behavior changed in
this network-replay batch.
