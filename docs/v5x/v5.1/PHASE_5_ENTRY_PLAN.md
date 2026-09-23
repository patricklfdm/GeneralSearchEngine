# V5.1 Phase 5 entry: combined faults and repeated recovery

**Status:** Batch A accepted at master
`04d12316bd6971ac477cfcb08c5073b2252ecf2a` (exact-master CI `35818964327`,
all 19 jobs passed). The original schedule below remains the Batch A record.
[Batch B combined lifecycle](PHASE_5_COMBINED_LIFECYCLE.md) is accepted through
PR #213 at `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`, exact-master CI `35826641489`.
The [Batch C review](PHASE_5_ACCEPTANCE.md) and full Phase 5 were accepted through
PR #214 at `15c8c68011e37370dfcd31ee855f91247c3771d8`, docs-only CI `35830149418`.
The [checklist](PHASE_5_CHECKLIST.md) records completion; the separate
[Phase 6 entry](PHASE_6_ENTRY_PLAN.md) is now a candidate.

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
- B: the [combined lifecycle schedule](PHASE_5_COMBINED_LIFECYCLE.md), including corrupted
  authority with recovery/pressure and cancellation/close across a recovery cut.
  Preserve failed schedules rather than retrying an entire case into a PASS.
- C: reconcile hardening coverage and resource accounting, run the complete relevant
  local/CI gates, record protected Phase 5 acceptance and then propose Phase 6 entry.

The linked Batch A/B records retain their original local evidence separately from
protected acceptance. Batch C's [review](PHASE_5_ACCEPTANCE.md) is accepted through
PR #214. No API,
authority-format, membership, follower-read or paid-cloud behavior changes are
included. If a concrete production fault is found, retain its failing trace and
make the smallest regression-backed correction within this contract.
