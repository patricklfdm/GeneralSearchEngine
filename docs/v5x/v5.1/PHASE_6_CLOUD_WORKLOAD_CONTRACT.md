# V5.1 Phase 6B cloud workload contract

**Status:** original contract accepted through PR #222, master
`33aa89bf8a6b4b0587fa6a127e481d73671a60ec`, exact-master CI `35937300754`.
The original calibration and measurement identities remain unchanged. During 6C2B
implementation the user explicitly approved the two document-size exceptions below.
This amendment requires protected acceptance of the new source and plan. It supplies
no paid admission.

Original canonical JSON SHA-256:
`bee0b38ae20611a0d36259e554c5d03b1e1ebd87fc71ab648b3848681854754a`.
Amended canonical JSON SHA-256:
`f0e964ba12fea8702a40082d4a01a85d6d3eb1bf7fe3fecf8778c899af44bea7`.
The [amendment record](phase6-cloud-workload-amendment.json) binds both hashes and
the unchanged [historical calibration](phase6-cloud-calibration.json).
Removing exactly the two added cell fields reconstructs the original pinned plan;
a regression checks that no other frozen value changed.

### Approved fault-document amendment

The two-field codec stores a four-byte integer key before the UTF-8 value. The
already specified 4096-byte and 20000-byte values therefore need these exact limits:

| Fault cell | Value bytes | Encoded document limit |
| --- | ---: | ---: |
| interrupted-transfer | 4096 | 4100 |
| minority-capacity | 20000 | 20004 |

Only these two cells override `application.maxEncodedDocumentBytes=4096`. Both
bounds apply consistently to all three voters within that cell; only node 3 in
minority-capacity retains the separately frozen 128-KiB replication budget. Rich
schedules, public call counts, other application/replication bounds, timers and
cost/time allocations are unchanged. The historical calibration is not relabelled
as execution of this amendment. Current arithmetic and real fault qualification
bind the new hash; exact-source CI also reruns the unchanged rich tapes.

## Calibration and workload scope

The independent replay of master CI `35920225478` supplies actual local measurements
for the same 64-document corpus, seed 17, indexes, codec, public methods and JVM
settings. The complete cloud rich tapes are independently decoded/projected, and
a synthetic 512-slot image checks encoding size. No full cloud schedule was executed
in this batch. Fixed arrivals, simultaneous rich callers, remote timing and the
complete fault schedules must be exercised locally by the 6C remote adapter before
paid preparation.

The corpus is deliberately unchanged from 6A: a small protocol/per-operation
measurement, not large-dataset search scaling. The automatic mode's slowest observed
20-call window completed at 7.838 calls/second, and maximum observed API latency was
194.736 ms. The proposed one-call/second load leaves a 5.135 ratio between spacing
and that observed maximum. Four such durations also fit a four-second burst period
with the same ratio. This is a trace-backed starting-load choice, not a prediction
of independent cloud disks/network or a guarantee against a future slower sample.

## Identities, placement and resources

Each experiment, failure-drill and canonical repetition creates one fresh topology
of three concurrent `n2-standard-8` Standard VMs in `us-west4-a`. Each has a 50-GiB
boot and 100-GiB data `pd-balanced` disk, with verified ext4 data mounts. Peak is
24 vCPU / 450 GiB; no extra control VM. Controls run sequentially using those hosts.
There are no external IPs; guest control uses IAP, replication private VPC addresses.

The image selection is exact `ubuntu-os-cloud/ubuntu-2404-noble-amd64-v20260918`,
ID `763874002631433611`, from the historical V5.0 read-only availability record.
That record is not current readiness. 6C must check exact ID, READY state,
architecture and deprecation, plus quota/IAM/network/filesystem/retention/cleanup.
Unavailability blocks preparation; do not silently follow an image family.

Guest Java is Eclipse Adoptium `21.0.12+8-LTS`. Preserve
`-Xms64m -Xmx512m -XX:+UseG1GC -XX:ActiveProcessorCount=2`, matching local calibration.
The physical VM has eight vCPU; JVM activity is deliberately capped at two for this
measurement identity. 6C pins build toolchain, complete bundled jlink runtime,
consumer/observer code and candidate/control artifact hashes before any prepare.
The immutable V4.4 and V5.0 control pins remain unchanged.

Each cell uses fresh group IDs and directories on the same owned topology; close
all prior voter processes before the next group starts. Rich cells import the
unchanged verified V4.4 source backup; fault cells use a fresh empty group with the
existing two-field public-history model. No authority copying, same-group disk
replacement, follower application read or operator-selected automatic leader.
All three voters use the same 1200 / 3600–6000 / 9600 ms automatic policy.

Healthy mode order is V4.4 local, V5.0 configured, V5.1 automatic. The V4.4 host and
V5.0 configured leader rotate node 1/2/3 across canonical repetitions 1/2/3; experiment
uses node 1. The actual automatic leader is recorded. Do not force its election for
matched placement. Comparisons retain placement and consistency differences.

## Complete healthy and concurrent tapes

The independent generator is
[`cloud_workload_contract.py`](../../../scripts/v51/cloud_workload_contract.py).
Documents and source digest match 6A. Revisions cycle as `1 + cycle % 9`, so all
emitted documents use the existing independent decoder's supported domain. The
healthy global cycle starts at zero and continues across warmup/ABBA windows.

| Program, one fresh group | Arrival / concurrency | Counts | Final sequence / documents |
| --- | --- | --- | --- |
| Canonical healthy, each of three modes | One call/second; one caller; 20 warmup calls, then four 60-second ABBA windows | 260 calls = 208 mutations + 52 reads; 240 measured, 24 samples/operation | 212 / 64; peak 68 |
| Experiment healthy, each mode | Same spacing; 10 warmup calls, four 20-second windows | 90 calls = 72 mutations + 18 reads | 76 / 64; peak 68 |
| Read-heavy, automatic only | Thirty four-caller bursts, one burst every four seconds, 120 seconds | 120 calls = 30 UPDATE + 90 GET/QUERY; 75% reads | 34 / 64 |
| Sustained, automatic only | Forty-five four-caller bursts, one burst every four seconds, 180 seconds | 180 calls = 108 mutations + 72 reads | 112 / 64; peak 68 |

Healthy ten-call cycle: ADD, UPDATE, REMOVE, ADD_ALL, UPDATE_ALL, REMOVE_ALL,
INDEX_DROP, INDEX_CREATE, GET, QUERY. Temporary key is `100000 + cycle*100 + offset`;
UPDATE keys are `1 + (cycle+offset)%64`. Bulks contain four documents. A failed
index operation ends the case; no reset or continuation after hidden failure.

Read-heavy lane 0 updates key `1 + burst%64`; lanes 1 and 2 issue GET and QUERY;
lane 3 alternates GET and QUERY. GET uses that same key, so the physical read-cut
oracle must resolve the actual concurrent prefix, not assume the generator's order.
Sustained lanes 0–3 each repeat ADD, UPDATE, GET, QUERY, REMOVE nine times on their
own key `200000 + lane*10000 + cycle`. Lanes have disjoint mutation keys, and all
added documents are removed by the final burst. QUERY still observes global state.

The generated interleaving proves payload validity/counts and a reference final
state. It is not exhaustive linearizability for the rich concurrent workload.
6C must decode actual chosen mutations and bind each GET/QUERY to its captured
prefix/NO_OP; it must not pass rich tapes to the two-field bounded history checker.

## Scheduler, clocks and outcomes

Schedule in one issuing guest's monotonic clock. A healthy window contains arrivals
at offsets 0 through 59 seconds (experiment 0 through 19). Concurrent bursts are
at offsets 0, 4, ... seconds; dispatch the four intended callers within 10 ms.
Require actual overlapping API intervals in both concurrent cells. Four calls per
burst are intentional; missed earlier arrivals never create a catch-up burst.

There are at most four callers and zero queued arrivals. If a lane is still busy
or dispatch is over 250 ms late, retain a NOT_DISPATCHED arrival and fail the healthy
cell. All attempted results remain visible. No silent queue, adaptive rate, mutation
retry or discarded warmup failure. Warmup does not pad measured counts. A healthy
call must succeed inside its existing API deadline; pending/cancelled/indeterminate
calls fail that cell. Capacity failure is only expected in the explicit capacity
cell. Unexpected integrity/storage errors always fail.

A window lasts its full scheduled duration. Boundary/control/drain time is separate,
recorded and charged to the cell's finite overhead. Drain is at most ten seconds;
startup, boundary control, drain and close together must fit the stated cell ceiling.
Healthy mode has 40 seconds outside its 260-second scheduled workload; read-heavy
and sustained each have 60 seconds. Unused time never extends another ceiling.
Report guest API latency and controller dispatch/receipt latency separately; no
cross-process nanoTime subtraction. Percentiles use nearest rank and raw counts.

ABBA A retains correctness and required resource samples; B adds force/queue timing.
Acceptance requires 100% scheduled successful completion under the same offered
load/deadlines and all evidence/resource checks. Report per-operation B/A without
inventing a speedup target. This is an offered-load completion criterion, not an
unbounded throughput or general p99 SLA.

## Fault schedules and independent evidence

Each fault cell starts a fresh two-field group. Common seed is three successful
ADD_ALL calls with two 64-byte-value documents each (tags 10, 20, 30), followed by
a strong read. Each later bulk uses fresh keys. Allow at most four progress pairs
(new two-document ADD_ALL, then fresh strong read), followed by at most four final
read attempts; the whole cell, including seed/target/refusals/maintenance calls,
is capped at 24 public operations. Never fill the cap with retries of an uncertain
mutation. Predeclare IDs and attempted branches; record all selected branches and
responses, including killed-process disconnects. Exhausted attempts fail.

| Cell | Seconds | Required schedule and facts |
| --- | ---: | --- |
| leader-loss | 120 | SIGKILL the ready leader identified by the seed read's active ballot; surviving majority progresses; restart the same retained voter and verify rejoin. |
| isolated-old-leader | 120 | Bidirectionally partition the seed leader for 15 seconds. Minority read/write reject; majority commits. Heal; verify higher-promise fencing and final prefix. |
| asymmetric-requests | 120 | Drop old-leader outgoing protocol requests for 15 seconds while retaining reverse traffic. Record actual drops/received messages, majority progress and heal. |
| asymmetric-responses | 120 | Deliver old-leader requests but drop their returning responses for 15 seconds. Record actual peer replies, conservative client outcome, majority progress and heal. |
| slow-follower | 180 | Delay one follower's ACCEPT/PROOF force by 1500 ms for 15 seconds; remaining quorum progresses. Release delay, measure lag and verify recovered prefix. |
| interrupted-transfer | 180 | Add two 4096-byte-value documents while one follower is isolated. Heal and pause its real transfer after the first durable 4096-byte chunk/progress record; SIGKILL recipient, restart unchanged partial authority, and verify transfer completion. Never manufacture a partial file. |
| entry-chosen | 120 | Hold leader at ACCEPT_ACK_RECEIVED before proof; SIGKILL. Reconstruct the chosen value from actual forced quorum, preserve the disconnected/uncertain caller, activate a survivor. |
| proof-quorum | 120 | Hold leader at PROOF_ACK_RECEIVED before publication/client reply; SIGKILL. Recover the proven prefix; never fabricate a successful response. |
| group-restart | 120 | Stop all three voters after the seed read. Restart the same retained directories with new process identities; elect and read the acknowledged state. |
| maintenance | 240 | Pin a captured read; partition its leader while the other majority commits. Heal/rejoin while pinned, release the unchanged old view, then checkpoint, V4-compatible backup, close and separately restore. Retain generation/pin and release evidence. |
| no-quorum | 120 | Isolate all three for 15 seconds. Fresh write/read refuse conservatively. Heal, then require fresh durable write and quorum-backed read. |
| minority-capacity | 180 | Node 3 has a sealed 128-KiB retained bound; others 64 MiB. Establish a healthy leader using the bounded PREPARE-direction fault, then remove it. Catch node 3 up to seeds, isolate it, commit two bulks of two 20000-byte-value documents (tags 40/60) on the healthy pair, retain exportable cut, heal. Require real resource rejection, refuse node-3 write/read, retain healthy service after node-3 restart and subsequent leader restart. Do not enlarge the sealed budget or repair authority. |

The pinned read can overlap a majority write but must retain its original captured
view. A later read needs its own fresh barrier. The two crash-cut cells remain
separate from idle leader loss. Resource capacity must be established by actual
reservation/transfer rejection and raw bytes, not by a request that merely failed
for another reason. The intentionally larger resource/transfer documents use the
two-field fault codec, not the rich document decoder's 256-byte domain.

First post-fault write/read and retained rejoin each have a 60-second upper bound,
clipped to the original cell deadline. These nested ceilings do not extend the
whole cell or promise two separate additional sixty-second reservations. Capture
fault request/confirmed-exit uncertainty and retain all campaign/routing time.
Only the already accepted conservative availability outcome combinations permit
another fresh progress pair/read; storage/integrity/capacity/CLOSED/unknown errors
fail, except the specifically witnessed minority resource refusal. Final acceptance
requires independent complete two-field history and physical vote/proof/publication,
read-cut, process, fault, archive/rejoin and resource validation. A worker PASS line
or cached leader status is insufficient.

E mapping: healthy/read-heavy/sustained E01/E09/E10/E11; leader-loss/group-restart
E01/E05/E08/E10; isolation/asymmetry E02/E03/E06/E09; slow/transfer E07/E11;
chosen/proof crashes E04/E05/E06; maintenance E07/E09/E10; no-quorum E03/E10/E11;
minority-capacity E10/E11. E12 and deterministic/internal edge cases remain required
exact-source local gates. No physical disk-loss/same-group-replacement claim is added.

## Presets and complete time allocation

- **Experiment:** healthy in all three modes at its reduced 90-call tape, then
  leader-loss, maintenance and no-quorum: four cells. Keep the canonical cell ceilings;
  shortened measurement time does not increase another cell's limit.
- **Failure-drill:** the twelve fault cells above, in table order.
- **Canonical:** healthy, read-heavy, sustained, followed by all twelve fault cells
  in table order. Primary workload-call arithmetic: `3*260 + 120 + 180 + 12*24 = 1368`.
  Fault branch outcomes may use fewer than their maxima; all attempted calls remain.
  Separately account for at most eight auxiliary strong barriers in each of the
  fifteen automatic groups (120 total); auxiliary calls in a fault history also
  consume its 24-operation cap. Setup/control calls never pad measured counts.

| Canonical allocation | Seconds |
| --- | ---: |
| Provisioning, guest identity, source and fresh-cell bootstrap preparation | 600 |
| Three healthy modes, 300 seconds each | 900 |
| Read-heavy | 180 |
| Sustained | 240 |
| Twelve fault cells | 1740 |
| Separately recorded control/SSH/transition overhead | 540 |
| Validation and complete evidence retention | 600 |
| Owned-resource cleanup and exact-ID absence checks | 600 |
| **Topology lease total** | **5400** |

The at-most-1080-second operation grace is cleanup/accepted-provider-operation
reconciliation, not extra measurement time. The runner must debit each interval
once to an explicit category, include all cell startup/drain/close intervals, expose
wall-clock totals and fail on either category or lease overflow. 6C must execute
slow-control/collection/credential-renewal negatives to verify this accounting.
The 540-second control allocation covers work outside cells. In-cell IAP/control
delay stays inside that cell's wall-clock ceiling; do not subtract it to rescue an
overrun. No nominal window consumes its entire cell ceiling without control room.

## Byte, slot and evidence budgets

Application and common replication bounds inherit the admitted 6A values exactly:
1024 live documents, bulk 16, application retained 128 MiB, replication retained
and staging 64 MiB each, frame 1 MiB, four in-flight requests per peer, four pending
public calls, two retries, 4096-byte chunks. The explicit minority retained bound and the two approved per-cell encoded-document limits differ.
Logical slots are capped at 512 per group, including at most eight auxiliary read
barriers and 64 activation/recovery NO_OP slots. Largest normal schedule:
`260 + 8 + 64 = 332`, below 512. Re-proposals still consume bytes/force observations;
a logical-slot cap does not exempt their storage or evidence cost.

Synthetic full-slot analysis encoded ENTRY/ACCEPT/PROOF peaks of 482/632/274 bytes,
a 136680-byte snapshot, a 182404-byte IMAGE, and 243208 bytes after image base64.
The IMAGE is below one-quarter staging admission (16 MiB). This is encoding analysis,
not proof of actual two-generation retention, compaction, transport metadata or peak
heap. Full-size bootstrap/basis/wire/transfer/re-proposal/pin/retention qualification
remains a hard 6C gate, using the same plan before a cloud prepare is enabled.
The [actual 512-slot component candidate](PHASE_6_FULL_SIZE.md) now supplements
this historical encoding analysis; its separate scope and remaining public-runtime
integration are recorded explicitly. It does not change this frozen plan.

A member retains at most 8 GiB expanded / 2 GiB compressed, 6 GiB traces/samples,
16000 files, 32-MiB members, 4-MiB command responses, 128-MiB trace output per node
per cell. Use complete 8-MiB parts, at most 256 compressed parts; the 2-GiB limit
must still hold even when input is poorly compressible. Keep full member hashes,
source/toolchain identities and original attempts. Transfer large parts as bounded
binary streams; command responses carry bounded metadata, not an oversized base64
part. Unsafe paths, duplicates, missing
parts or overflow fail; never truncate authority/history into a PASS summary.
Sample resources every second and at every boundary; report sampled RSS rather
than asserting an OS hard peak. Required missing heap/RSS/queues/retained/staging/pin
observations fail. Unsupported process network counters stay explicitly unsupported.

Retain successful and failed evidence for thirty days. Fresh pricing must cover up
to ten GiB compressed successful-member storage plus failed attempts and temporary
objects. The USD 100 aggregate envelope remains a proposal pending current-price,
remaining-budget and exact-request confirmation. Five full leases plus grace reserve
27 VM-hours and 4050 GiB-hours of disks; these are cost units, not dollar prices.

## Sequence, admission and 6C handoff

Choose and lock experiment → failure-drill → canonical 1/2/3 or canonical 1/2/3 →
experiment → failure-drill on the first member. All five require the same admitted
source, artifact, workload, environment and toolchain identities. Keep every failed
attempt and cost; a retry gets a new attempt ID and remaining-budget admission.
A failed canonical member requires a fresh comparable canonical set. No simultaneous
topologies or automatic paid dispatch from push/PR/schedule.

6C implements and qualifies the exact remote command receipt/scheduler/cell path,
including partial provisioning, dropped SSH responses, interrupted upload,
cancellation, credential renewal and deletion negatives. A lost command response
never permits replay of a potentially accepted mutation. Query an exact durable
command receipt or fail with retained uncertainty. Evidence retention failure cannot
suppress cleanup; unresolved resources block another allocation.

Before any paid prepare/run: protected acceptance of this contract, exact-source
local/remote full qualification, fresh read-only image/IAM/quota/storage readiness,
recent successful scheduled **or safe manual** cleanup for that exact source, a
complete priced request, and explicit user confirmation. The cleanup freshness
limit remains two hours and preparation receipt age 900 seconds; runtime lease is
separate. Manual cleanup changes reconciliation timing, never expiry/grace/ownership.
User controls cloud dispatch and commit/push/PR/merge.

Reproduce this batch's checks:

```bash
python3 -m scripts.v51.cloud_workload_contract
python3 -m unittest scripts.v51.test_cloud_workload_contract scripts.v51.test_performance_artifacts
python3 -m scripts.v51.cloud_calibration \
  --local-evidence target/v51-phase6-cloud-contract/master-performance/run.uMX9h3/evidence \
  --output target/v51-phase6-cloud-contract/calibration-replay.json
```

The final command independently validates actual downloaded evidence before deriving
calibration. It requires a fresh output path and does not create cloud resources.
