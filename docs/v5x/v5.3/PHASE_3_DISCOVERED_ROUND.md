# Discovered native round entry

Phase 3 remains **OPEN**. `MembershipRoundDriver.startDiscovered()` now owns a
read-only discovery/adoption pass before its existing activation, carried recovery
and fresh BARRIER. The ordinary `start()` remains available for callers which
already own the governing cut. Neither entry is a public factory or election timer.

## Discovery and authority

`MembershipPrefixRecovery` captures the actual original local cut and root fence,
then visits each other identity in that cut's permanent directory once, in node
order. It does not learn identities from STATUS, combine hints, rank advertised
ballots, or trust `ready`. Existing exchanges retain at most three identical
transport attempts; only exhausted IO/deadline failures may advance to another
known identity. Malformed responses, explicit rejections, capacity failures and
local fencing stop the pass. An equal-index conflicting cut is refused.

A higher cut in the same authority remains the activation selector's ancestry
responsibility. A higher cut advertising a different authority causes complete
packet/image acquisition and a separate original manifest/ancestry acquisition.
The retained-copy verifier authenticates the exact original source before the
existing journal adoption transaction checks the local ancestry, retained tail,
resource obligations and membership-certificate fence. The discovery hint alone
cannot write a promise, install a generation or count as a vote.

Only the first complete verified newer authority is adopted in this invocation.
No fallback catches a durable adoption failure. The subsequent round checks local
eligibility before forcing a fresh grant: a newly removed identity cannot proceed
to PREPARE or READY. A surviving identity must still complete selected installation,
carried recovery and a fresh current-ballot BARRIER. Discovery itself is not a
quorum health check and does not promise that the later campaign will succeed.

## Lifetime and accounting

Discovery, every source attempt, adoption and the subsequent round inherit the
same original start and budget. The original cut/fence is rechecked before work;
the durable transaction runs under the journal monitor. Both receiving owners
remain live through that transaction. No old scope or stored selection restores
readiness after failure, close or expiry.

The owner reserves 256 KiB of existing CONTROL capacity for its bounded directory
and bookkeeping. Existing per-request/source/image accounting remains in force.
There is at most one packet receiver and one ancestry receiver. A guarded OUTGOING
scratch scope is opened only when acquisition is needed and drained before normal
activation reuses the same path. An unchanged-view scan writes no scratch or grant.

Close cancels pending reads and waits for the owning runner. It does not interrupt
an admitted adoption force. Cleanup failure retains child and parent ownership for
explicit cleanup retry; it cannot be converted into READY. No wire/storage format,
resource limit, production timeout, POM, workflow or V5.2 experiment is changed.

## Qualification boundary

Focused checks cover unchanged discovery, exact finite transport retries, fatal
responses, unverified hints, fencing/deadline, cancellation, and actual local
adoption through original transfer bytes. The latter uses explicitly conditional
historical force fixtures; it is not distributed transition evidence. A separate
native TCP history exercises discovery before activation and two stable slots.
The [source-bound receipt](phase3-evidence/discovered-round.json) records:

- The first snapshot's native two-slot method passed in 105.914 seconds with
  unchanged default request/retry/round bounds. Two new test assertions failed:
  the expiry assertion expected the wrong exception class, and the request-kind
  assertion confused an offer response with its CHUNK request. Their original
  failed reports remain retained; neither failure is claimed as runtime success.
- The corrected final snapshot passed eight recovery checks and the existing
  busy-round/close regression: nine tests, no failures or skips. Together with
  the unchanged native method, ten focused Java checks pass in separate executions.
- Fourteen Python checks pass. Explicit `--discovery` replay validates both
  original pre-grant responses, 39 subsequent transfers and both slots. All 39
  exact evidence negatives pass (31 native/discovery and eight round negatives).

The old native reader rejected pre-grant STATUS as using the wrong ballot. The
new opt-in reader derives its fence and cut from the physically replayed original
files, requires the exact two known peers and response delivery before allocator
write, and keeps every later frame bound to the selected ballot. The unchanged
default entry still rejects this extended trace. No workload rerun or original
trace editing was used to qualify the reader extension.

```bash
python3 -m scripts.v53.round_driver_evidence RAW_DIRECTORY --discovery --qualify
```

Still required: the complete heterogeneous native transition from an obsolete
surviving owner through fresh service, removed-owner integration, source rotation
during real transfer, original-first replay of those histories, process-death cuts,
automatic election scheduling and all seven profiles. Keep each complete history
on one runner; independent histories may be deferred to the hosted campaign.

Rollback removes the private discovery entry and `MembershipPrefixRecovery`.
Existing adoption recovery and ordinary round entry remain necessary for any
already forced original history. This component does not migrate persisted bytes.
