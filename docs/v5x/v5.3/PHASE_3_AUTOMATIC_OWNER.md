# Bounded automatic service owner

Phase 3 remains **OPEN**. A private automatic owner now connects the native round's
election wait, discovery and fresh-barrier activation to a serial heartbeat and
command loop. It owns one original bounded lifetime. An error ends that lifetime;
starting another campaign after failure, continuous campaign progress and public
runtime integration remain separate work.

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
it. A long active operation can delay a pulse. No failover or latency SLA is
claimed, and active-campaign progress integration remains necessary.

The mailbox counts both queued and executing calls against the configured
pending-call bound and the existing global 64-waiter limit. Its fixed 64 KiB
owner reservation accounts for bounded control metadata. Each immutable payload
is reserved before copying, including an input at the existing 8 MiB frame
ceiling; execution's own reservations remain additional. Failure to reserve
returns the waiter immediately. Invalid commands are rejected before admission.

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
