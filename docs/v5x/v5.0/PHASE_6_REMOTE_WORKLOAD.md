# V5.0 remote workload execution and evidence

- **Status:** Adapter accepted through [PR #163](https://github.com/patricklfdm/GeneralSearchEngine/pull/163). Paid experiments passed healthy measurement but failed during follower catch-up. The latest [run 35241694135](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35241694135) exercised the controller retries and exposed repeated application replay in the READY handshake; the runtime correction is documented below. Complete paid 6C evidence remains pending.
- **Branch:** `feat/v5.0-phase6-remote-workload`
- **Starting master:** `a885bc7789a332525d3c375635ce35ce7bc15dec`
- **Predecessor:** [PR #161](https://github.com/patricklfdm/GeneralSearchEngine/pull/161), [correction #162](https://github.com/patricklfdm/GeneralSearchEngine/pull/162), [exact-master CI 35069706211](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35069706211)
- **Contract:** [Frozen workload](PHASE_6_CLOUD_WORKLOAD_PLAN.md), [runner qualification](PHASE_6_RUNNER_PRESETS.md)

## Runtime path

[cloud_remote_probe.py](../../../scripts/v50/cloud_remote_probe.py) implements the
full workload through persistent private guest streams and the existing owned
resource Runner. The guest uses independently compiled public consumers, the exact
production JARs, pinned V4.4 control and pinned Java runtime. The separate
`gse-v50-remote-workload-bundle-v1` also carries the exact Python guest/inspection
inputs. The old admission bundle and local-only workload bundle retain their own
schemas and entry boundaries.

Each node's JVM restart receives a fresh generation, stream directory and process
receipt. PID, Linux start ticks, VM ID and boot ID identify a process. A proof cut
checks the actual barrier marker and this identity before sending SIGKILL. Killing
the controller SSH process alone cannot count as guest cleanup. Collected stop
receipts preserve deliberate kills and normal exits separately.

Warmup and ABBA/sustained windows use the frozen profile's call counts and arrival
rates. Failure-drill measures its fault matrix; its published V4 control still runs
the specified four thirty-second healthy windows. Unavailable, slow, incremental
and snapshot cells issue ten bounded background updates with at least one second
between dispatches. Snapshot selection follows a public checkpoint ahead of the
isolated follower; the first chunk acknowledgement is deliberately lost. Restart
replays a retained old-incarnation request and requires `STALE_EPOCH`.

Catch-up can outlive one bounded peer RPC while the follower is still installing
the durable batch. The controller retries public `catchUp` for `QUORUM_UNAVAILABLE`
or `CAPACITY_EXCEEDED` only while the leader reports `READY` and write quorum
available. It retains the existing 20-attempt/50-ms-backoff bound and limits each
response wait by the remaining cell and run deadlines. Conflict, fencing,
integrity, storage and closed-state failures remain terminal. A failed cell now
records `FAIL` and its diagnostic; each command response remains in the member
receipt. Neither the 1500-ms RPC bound nor any frozen workload allocation changes.

The follower's READY handshake reuses an already published application at the
verified committed boundary. Startup and recovery installation already rebuild
that application; retrying READY must not repeat the full replay. The handshake
still validates voter status, intact committed history, index and digest. A stale
application or unresolved private prepared operation still requires reconstruction.

Both replacements use the existing delete/read-back/create lifecycle. The old
authority copy is diagnostic only. The fresh disk mounts on the designated survivor
for public replacement admission, then moves to its configured voter. Data and
materialization remain on that disk. Configured-leader reconstruction must first
reject one survivor and then succeed with both. Maintenance retains the published
backup across a kill at its real publication barrier and a separate cancellation/
close. Capacity checks compare the exact protected authority bytes before and after
the first expected rejection.

The adapter qualification exposed a production replacement defect: comparing the
complete original materialization path binding also compared the destroyed disk's
filesystem identity. Replacement now retains the absolute materialization path and
all format/identity/codec/bounds policy while binding the new disk in the new plan.
Apply/resume still reject any further physical identity change after planning.
The [format clarification](PUBLIC_ADMISSION_FORMAT_1_1.md) and both independent
oracles use that rule. Regression tests retain the old parent inode to make disk
replacement deterministic; deleting/recreating a local directory can reuse it.

## Independent evidence and bounds

Each guest packs only its own node/generation namespace. Transfers use a bounded
manifest, ordered parts of at most 32 MiB, checksums and exclusive extraction.
The complete retained workload stays within 4 GiB/2000 files. The Runner uploads
the packed workload plus lifecycle/admission receipts with conditional GCS writes
and read-back, including incomplete runs. Collection failure still permits resource
deletion; incomplete retention keeps the lease.

[cloud_remote_evidence.py](../../../scripts/v50/cloud_remote_evidence.py) checks
VM shape, private endpoints, watchdog, mounts, exact artifacts, process generations,
physical replacement identities and absent-resource cleanup receipts. It invokes
the independent committed-history/payload/force/read/restore verifier with the
specific frozen cloud profile. Remote clocks are never compared between hosts.
Equal numeric PIDs on different VM/boot namespaces are valid. Local/fake evidence
cannot satisfy cloud provenance or the five-topology set validator.

Set validation requires experiment, failure-drill and canonical repetitions 1–3,
the same source and production artifacts, distinct ownership nonces, serial
lifetimes, retained approval/budget receipts and verified cleanup for every member.
A failed member remains a failed set. Baseline registration remains a separate 6D PR.

## Budget interpretation and admission

The user-approved [control accounting clarification](PHASE_6_CLOUD_WORKLOAD_PLAN.md#remote-control-accounting-clarification)
keeps measurement rates, call counts and durations fixed. Window/SSH preparation
overhead uses the existing candidate preparation reservation and is independently
recomputed from controller receipts. Fixed elapsed fault windows and all topology/
cleanup/cost ceilings remain in force. Preset descriptor v2 makes the required paid
admission explicit; it does not modify either frozen plan JSON.

The protected workflow can prepare a full profile with a shared 32-character hex
sequence ID and repetition ordinal. `run` uses the exact prepared request, clean
source, matching bundle schema, fresh preflight, explicit cost confirmation and an
executed successful remote-adapter gate on that source. Expired cleanup understands
both admission and full-profile leases. It still cannot allocate resources.

This implementation performs no cloud provisioning or paid experiment. Fresh
workflow service-account preflight, WIF/cleanup setup and complete-sequence cost
confirmation remain prerequisites after protected PR and exact-master acceptance.

## Local qualification

```bash
python3.11 -m unittest scripts.v50.test_cloud_remote
scripts/verify-v50-phase6-remote-workload.sh --skip-build
```

The gate runs the actual guest command protocol with three owned local JVMs and
fake resource IDs/attachments. It executes all fourteen reduced workload cells,
including fresh local directories with distinct parent inodes standing in for
destroyed disks. Retired fake directories stay outside the guest namespace until
cleanup, preventing accidental inode reuse. Its label is
`local-remote-workload-only`; it proves neither IAP/SSH connectivity nor GCP physical
disk operations. Cloud durations are checked with deterministic budget fixtures;
the local gate does not spend 300/900/1800 seconds pretending to be a cloud run.

The local lane also delays one follower's durable catch-up batch response beyond
the RPC timeout. It requires an actual public `QUORUM_UNAVAILABLE` followed by
successful public catch-up and a `READY` follower at the verified applied/commit
index. The extra fault is selected only by the local qualification controller;
the paid fault schedule is unchanged. The receipt is
`runner/catchup-timeout-regression.json`. This regression reproduces the previous
controller failure before the retry correction.

### First workload catch-up failure

[Run 35200890419](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35200890419)
used source `f524ac177e9017fdd1ba0a3e5ceb592c77ee4d9c`. All four healthy windows
passed. The unavailable cell isolated node-3 for ten background updates, leaving
its committed index at 1121 while the leader reached 1131. After healing, the
public catch-up call returned `QUORUM_UNAVAILABLE` after approximately 1.59 seconds;
the leader remained `READY` with write quorum. Subsequent node-3 samples show the
batch reached committed/applied index 1131 and application sequence 1386, but the
controller had already aborted instead of completing the public READY handshake.
The timeout is therefore not evidence that the whole write quorum was lost.

The original failure remains rejected evidence. All 13 owned cloud resources
were verified absent, retention passed, and the lease was released. The failed
sequence and its USD 5.60 reservation remain in the ledgers; see the
[current budget boundary](PHASE_6_CLOUD_SETUP.md#workload-catch-up-timeout-and-budget-boundary).

Correction validation passed 242 Python tests (19 remote-adapter tests), all 14
local remote workload cells and all 15 provenance negatives. The injected timeout
reproduced the original abort before the fix; afterward two public timeout
responses were followed by successful catch-up and follower READY at index 67.
These are local qualification results, not a successful paid cloud rerun.

### Repeated READY replay after controller retries

[Run 35241694135](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35241694135)
used source `95c954f5326edde231dab47bb0ea0c676ea1f7fc`, including the retry correction
from PR #168. Healthy measurement passed. The unavailable cell produced nine
completed `QUORUM_UNAVAILABLE` catch-up responses and a tenth indeterminate request
before its 30-second deadline. From the second completed response onward the
leader observed node-3 at committed/applied index 1131; node-3 telemetry repeatedly
remained `CATCHING_UP`. The leader retained write quorum.

The runtime unconditionally rebuilt the entire application in every `ready`
request, even though batch installation had already published that same history.
Repeated activation and READY requests therefore repeated expensive replay rather
than finishing with the existing materialization. The single delayed-batch local
regression from PR #168 did not cover this persistent replay cost.

`V50ReadyTest` counts real document decoding across node catch-up calls. Before
the runtime fix, all three restart/incremental/snapshot cases failed because READY
decoded the published history again. The correction reuses that application only
when its applied index matches the validated committed boundary and no prepared
operation remains. Regression cases also exercise repeated catch-up, a subsequent
write with the recovered follower as the only available peer, and reconstruction
of missing published state or an unresolved private operation. The workload rates,
RPC timeout and cell deadlines remain unchanged.

Local correction validation passed `./mvnw -o -f reactor/pom.xml package`:
549 core tests (4 skipped), 165 replication tests including five new READY cases,
and five processor tests. The remote adapter gate passed all 19 Python tests,
14 workload cells and 15 provenance negatives. Its delayed-batch receipt contains
two public `QUORUM_UNAVAILABLE` responses followed by successful catch-up and
follower READY at index 67. The Phase 4 recovery and Phase 5 hardening gates also
passed with the rebuilt runtime. These results qualify the local implementation;
complete paid cloud evidence remains pending.

The READY regression also accounts for transport admission after isolation:
completion through the healthy quorum does not drain requests queued for the
unavailable follower. Its incremental case holds a proof response on the leader's
sender thread until the queue fills and catch-up returns `CAPACITY_EXCEEDED`, then
releases the response and retries admission within one ten-second test deadline.
Only that capacity classification is retried; RPC timeouts and recovery failures
still fail the test. The zero-replay assertions remain in force after admission.
This removes the scheduler-dependent assumption exposed by the PR CI run.
Validation passed 44 targeted READY/recovery/network/pressure tests and three
additional consecutive runs of all five READY cases, each forcing backpressure.

This run remains failed evidence. All 13 resources were verified absent,
retention passed, and the live lease read-back was absent. Sequence
`57ef85cf9c994afabe8d65fc3323fc74` cannot be reused. The budget ledger retains its
USD 4.48 reservation; cumulative reservations were USD 22.08 and the remaining
allocation under the original USD 40 ceiling was USD 17.92. The later
[approved USD 100 amendment](PHASE_6_BUDGET_AMENDMENT.md) preserves those reservations.
A new paid sequence requires a new complete cost
review and admission; this runtime correction does not authorize execution.

- [x] Predecessor exact-master full CI verified.
- [x] Local guest/runtime, policy, provenance and negative receipts recorded below.
- [x] This implementation accepted through protected PR #163 and exact-master CI `35079404376`, with all six jobs successful and the remote adapter gate executed.
- [ ] Fresh paid admission and staged 6C cloud execution accepted.
- [ ] Independent set review and 6D baseline registration accepted.

Next: [6C configuration and readiness](PHASE_6_CLOUD_SETUP.md), followed by fresh
paid admission. The local receipts below remain historical candidate evidence.

### Candidate validation receipts

The candidate was checked on source
`a885bc7789a332525d3c375635ce35ce7bc15dec`, with `sourceDirty=true` because these
changes await commit. `./mvnw -o -f reactor/pom.xml clean package` passed:
549 core tests (4 skipped), 160 replication tests and 5 processor tests, with no
failures/errors. This includes deterministic new-disk acceptance, stale planned-disk
rejection and unchanged materialization path/policy checks. V5 Python discovery
passed 178 tests; CI change classification passed 14 tests. The 14 remote tests
include virtual-clock execution of all three full cloud schedules. Public-admission
foundation, Phase 0 contract, workflow YAML, shell syntax and diff checks passed.

The fresh remote bundle is
`target/v50-remote-workload/run.9rYsFw/artifacts`. Its first runtime attempt retained
an `entry-cut` recovery failure: snapshot chunk replies exceeded the frozen request
deadline and activation returned `QUORUM_UNAVAILABLE`. The failure remains in
`qualification`; no timeout, rate or measurement limit was relaxed. A separate
execution of the identical bundle in `qualification-recheck` passed all 14 cells,
including both replacements with distinct parent inodes. This establishes a passing
local qualification while retaining the observed intermittent timeout for review;
it does not establish cloud reliability.

The independent result is 72 measured calls, 56 durable measured mutations,
committed index 92 and application sequence 340. Cleanup passed, retention was
verified and the lease was released. All 15 resealed provenance negatives rejected,
including presenting local evidence as a real cloud member. The artifacts remain
labelled `local-remote-workload-only`.

Production core SHA-256 remains
`ac25695c3a446b2ea07e312164b6277f612610eeec2d33dc91f94a2316b0769f`.
The replacement correction changes replication SHA-256 to
`56ab507f884cec665b83c93dec9a8f4ecfe2a6416df724e1cc93cd5cdfb09d83`.
Both frozen plan JSON files and the published V4.4 control pin remain unchanged.

The existing full local workload gate also passed in
`target/v50-cloud-workload/run.CQhyNs`: 48 policy tests, all 14 runtime cells and
38 independent semantic negatives. The public offline authority gate passed 106
case receipts covering its
bootstrap/cleanup/replacement crash boundaries and all three published V4 source
formats with semantic round trips. These checks use the corrected production JAR.
The original 6B runner gate passed in `target/v50-cloud-local/run.AxVTlS`, including
its fake failure matrix and the volume-layout public-runtime/published-control probe.
