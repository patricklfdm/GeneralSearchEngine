# V5.1 Phase 5 entry: combined faults and repeated recovery

**Status:** user entered `test/v5.1-phase5-hardening` after Phase 4 acceptance.
This batch defines and implements the first bounded hardening gate. Phase 5 as a
whole remains open; Phase 6/cloud/release are separate decisions.

## Accepted starting point

Phase 4 A–P: PR #208, master `b0d586f32b01f59aadfa940d7f778a8a2b5ea078`,
[exact-master CI 35802660895](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35802660895).
All 13 jobs succeeded, including the full public matrix, new heartbeat/disk-loss
gate and Required. The [final Phase 4 review](PHASE_4_FINAL_COVERAGE.md) preserves
all E01–E12 layer boundaries; it does not claim exhaustive arbitrary schedules.

## Batch A schedule, fixed before execution

Three scenarios, three consecutive rounds each, on the **same three admitted
voter directories and same GroupId**. No fresh bootstrap between rounds, manual
activation, restored authority, or replay of an uncertain mutation is permitted.

| Scenario | Combined fault and required recovery |
| --- | --- |
| `partition-accept-kill` | Pause a real ACCEPT_ACK after response read on the leader; isolate it; the surviving majority must recover the chosen pending value and complete a new read/write while the old request is held. SIGKILL the old process, archive its retained authority, heal, restart it and regain service. Repeat three times. |
| `partition-proof-kill` | Repeat the same partition/failover/crash sequence with COMMIT_PROOF_ACK held before delivery. Every chosen value and acknowledged prefix must survive all three rounds. |
| `whole-group-restart` | After service, close both followers, require read/write refusal from the sole survivor, then close it. Archive all three authorities before reopening any voter, restart all JVMs with new process generations, and recover read/write service. Repeat three times with rotated start order. |

Fixtures keep the already admitted backpressure profile: four pending public calls,
1200 ms request deadline, 9600 ms operation deadline, 4096-byte chunks; node-3 votes
and recovers but its sealed election timer is 600000–601200 ms. The other two use
3600–6000 ms election timers. The test injects schedule events, not a production
leader-selection mechanism. Pauses are bounded at 60 seconds, recovery reads have
the existing four-attempt bound, and no write is silently retried.

The whole history is bounded at 48 attempted operations / 100000 search states;
the independent linearizability search fails if inconclusive. All physical chosen
prefix, per-call barrier and application-byte checks still apply. Actual process
starts bind generations 1–4; each node's generations must be contiguous and each
restart follow the recorded termination and immutable pre-reopen archive.

Resource samples must fit the admitted mailbox/client/application bounds and show
zero pending client work, timers and ordered work after each recovered round.
Transport reservations are checked per PID. Gracefully closed processes must
balance every reservation. SIGKILL may end with bounded live reservations, which
are explicitly classified as destroyed with that exact dead process; they cannot
be credited as releases in a later process. This is finite recovery evidence, not
an endurance benchmark or proof about OS-level exhaustion.

## Remaining batches and exit

- A: the combined partition/acknowledgement/crash and complete retained restart
  matrix above; independent archive/process/outcome/accounting negatives and CI.
- B: separately freeze broader deterministic combinations, including corrupted
  authority with recovery/pressure and cancellation/close across a recovery cut.
  Preserve failed schedules rather than retrying an entire case into a PASS.
- C: reconcile hardening coverage and resource accounting, run the complete relevant
  local/CI gates, record protected Phase 5 acceptance and then propose Phase 6 entry.

These later combinations are planning scope, not completed evidence. No API,
authority-format, membership, follower-read or paid-cloud behavior changes are
included. If a concrete production fault is found, retain its failing trace and
make the smallest regression-backed correction within this contract.
