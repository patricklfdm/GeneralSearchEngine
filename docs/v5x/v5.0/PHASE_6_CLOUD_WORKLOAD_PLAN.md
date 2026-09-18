# V5.0 Phase 6 cloud workload plan

- **Status:** Plan accepted through PR #159; workload/evidence and runner preset qualification accepted; remote workload adapter candidate
- **Branch:** `docs/v5.0-phase6-cloud-workload-plan`
- **Starting master:** `72137865f39535e8f41052b455bbfdd0e01be163`
- **Predecessor:** [PR #158](https://github.com/patricklfdm/GeneralSearchEngine/pull/158), [exact-master CI 35051728286](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35051728286)
- **Authority:** [Phase 6 entry plan](PHASE_6_ENTRY_PLAN.md), [6A local probe](PHASE_6_LOCAL_PERFORMANCE.md), [6B runner](PHASE_6_CLOUD_RUNNER.md)

## Delivery boundary

PR #158 accepts the owned runner, preflight, fake failures and local volume-layout
probe. Its sole executable profile remains `admission-probe`. This accepted plan freezes
the separate full cloud workload before implementation and 6C. It supplies no cloud
measurement, paid-readiness receipt or registered baseline.

The existing [6A plan](phase6-plan.json), [6B plan](phase6-runner-plan.json), schemas
and limits stay authoritative for their existing profiles. In particular, changing
a profile string cannot enable these workloads. Follow-up implementation must add a
separate closed cloud plan, probe, independent validator and runner integration.
Acceptance of this document closes design review only; implementation and exact-source
CI must pass before preparing a paid request. Resource or workload changes require
another reviewed plan and a new comparable evidence set.

## Workload and measurement contract

Use the existing independent [document model](../../../scripts/v50/performance_model.py)
and [Java codec](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/PerformanceWorkload.java).
The cloud implementation parameterizes their current local-only bounds explicitly.

| Input | Frozen cloud value |
| --- | --- |
| Corpus | IDs 1–4096, revision 0, seed 17; load 256 batches of 16 before public bootstrap |
| Corpus identity | SHA-256 `fbd977b2037c930f2bb7ae380cc61fbfb67f6157cee4609f5386cb869e7d8a92`; concatenate each encoded document preceded by its four-byte big-endian length, IDs ascending |
| Codec | Five UTF-8 fields separated by newline, no trailing newline; initial corpus 217153 encoded bytes, maximum initial document 54 bytes; keys four-byte big-endian integers |
| Indexes | `prefix:title`, `equality:category`, `range:price`, `text:body:gse-simple-v1`; preserve insertion/index order |
| Application | `semantic-schema`, `semantic-codec/1`, `performance-store`, `FORCE_SCAN`; snapshot queue 31, batch 16, wait 1234567 ns |
| Healthy cycle | `ADD, UPDATE, REMOVE, ADD_ALL, UPDATE_ALL, REMOVE_ALL, INDEX_DROP(category), INDEX_CREATE(category), GET, QUERY`; bulk size 16; eight mutations per ten calls |
| Healthy keys | Existing model: temporary ID `100000 + cycle * 100 + i`; update/get ID `1 + (cycle + i) % 4096`; revision `cycle + 1`; cycle never resets between windows |
| Query | `category=guide AND body contains java`, insertion order; independent full-result digest plus bounded paginated state evidence |
| Warmup | 20 seconds, 20 complete healthy cycles, 200 calls and 160 mutations, excluded from measurements |
| Healthy arrival schedule | One client, one call every 100 ms, no overlapping calls; cycle starts every second |
| Sustained arrival schedule | Four client lanes; global 20 calls/s, round-robin lanes; each lane repeats three UPDATEs then one QUERY, updating its own key 1–4 with a monotonically increasing lane revision |
| Fault background | At most one UPDATE/s on key 5, revisions from a separate increasing counter; paused during proof cuts, replacement, checkpoint, backup and close barriers |
| JVM, each voter/control | Java `21.0.12+8`; `-Xms256m -Xmx2g -XX:+UseG1GC -XX:ActiveProcessorCount=8` |
| Sampling | Process/host resources every second, plus cell boundaries; per-call latency/outcome and committed sequence; instrumented windows add force/proof/publication observations |

The healthy schedule is paced, not a saturation benchmark. Record scheduled arrival,
actual start, Future completion and scheduler delay with the issuing process's
monotonic clock. A pending call at the next slot records a missed slot; do not build
an unbounded client queue or catch up with a burst. Healthy/control/sustained cells
require all scheduled calls and no unexpected rejection, missed slot or timeout.
A run that cannot sustain this offered load fails this preset; it cannot shorten the
window or lower the rate after the fact. Report the offered rate alongside results.

The four healthy windows are `baseline-a, instrumented-a, instrumented-b, baseline-b`
(ABBA). Baseline retains essential outcome/latency/resource evidence; instrumented
adds internal timing events. Compare per-operation service latency, scheduler delay
and CPU overhead, not the ratio of equal fixed wall-clock windows. There is no
predeclared V5 throughput or p99 improvement target. Small fault-cell sample counts
must be visible and cannot support general tail-latency claims.

Concurrent sustained QUERY results are checked against the recorded publication cut,
not controller arrival order. A public read does not atomically return its sequence:
the probe must record its public-read execution cut with test-only instrumentation,
or reject an ambiguous sample. The offline model replays independently decoded entries
and proofs; it must not trust a worker-supplied expected digest. Report attempted,
admitted, completed, durable-success, rejected, timed-out and indeterminate counts
separately; bulk request counts and affected document counts are separate.

The independently compiled published V4.4 control remains
`io.github.patricklfdm:general-search-engine:4.4.0`, SHA-256
`0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`.
Run the same corpus, warmup and healthy/sustained schedule on the leader VM with all
candidate JVMs stopped. In failure-drill, use four 30-second healthy control windows.
After candidate shutdown, that control also restores the exported backup and verifies
ordered semantics. Shared settings match; V4 has no replication/quorum fault latency
counterpart. Control and candidate use separate authority directories. Their startup,
restoration and timings count toward the same topology deadline and cost.

## Ordered cells and time budgets

These are elapsed measurement windows, including the cell's fault, recovery and
settling time. Early completion leaves an observed quiet interval until the window
ends. A deadline failure ends the topology and retains failure evidence. Setup,
warmup, control and final collection are separately budgeted below. No hidden fresh
bootstrap or unreported extra topology is allowed between cells.

| Order | Experiment cell | Seconds |
| ---: | --- | ---: |
| 1 | Healthy ABBA, 30 seconds per window | 120 |
| 2 | One follower unavailable, then healed | 30 |
| 3 | One slow follower, then healed | 30 |
| 4 | Incremental catch-up | 30 |
| 5 | Snapshot transfer, interrupt and retry | 45 |
| 6 | Restart and stale-incarnation fencing | 60 |
| 7 | Writer-ordered backup, cancellation/close and restart | 120 |
| 8 | No write quorum and committed leader reads; final shutdown | 15 |
| | **Total** | **450** |

| Order | Failure-drill cell | Seconds |
| ---: | --- | ---: |
| 1 | Leader kill after entry quorum, before proof | 100 |
| 2 | Leader kill after proof quorum, before client success | 100 |
| 3 | Interrupted snapshot installation and recovery | 120 |
| 4 | Follower disk loss and replacement | 150 |
| 5 | Configured-leader disk loss and reconstruction | 210 |
| 6 | Stale incarnation rejected after fencing | 70 |
| 7 | Backup cancellation, close and restart | 120 |
| 8 | Local checkpoint capacity rejection preserves sources | 90 |
| | **Total** | **960** |

| Order | Canonical cell (each of three serial fresh topologies) | Seconds |
| ---: | --- | ---: |
| 1 | Healthy ABBA, 120 seconds per window | 480 |
| 2 | Sustained four-client sampling | 300 |
| 3 | One follower unavailable, then healed | 60 |
| 4 | One slow follower, then healed | 60 |
| 5 | Incremental catch-up | 90 |
| 6 | Snapshot transfer, interrupt and retry | 180 |
| 7 | Restart and stale-incarnation fencing | 120 |
| 8 | Follower disk loss and replacement | 180 |
| 9 | Configured-leader disk loss and reconstruction | 180 |
| 10 | Checkpoint/backup, cancellation/close and restart | 120 |
| 11 | No write quorum and committed leader reads; final shutdown | 30 |
| | **Total** | **1800** |

Experiment qualifies the basic cloud path; failure-drill supplies the two proof cuts
and deliberate capacity failure. Canonical repeats its complete matrix three times;
the aggregate set requires the admitted experiment and failure-drill too. A failed
canonical repetition fails the set; a successful retry cannot replace it in place.

The [2026-09-18 execution-order amendment](PHASE_6_RUNNER_PRESETS.md#execution-order-amendment--2026-09-18)
permits either experiment → failure-drill → canonical 1/2/3 or canonical 1/2/3 →
experiment → failure-drill. The first member locks the order. Every member must
still pass on the same source/artifacts, and the full five-member set is required.
This changes sequencing policy, not the frozen workload JSON or measurements.

| Per-topology reservation, seconds | Experiment | Failure-drill | Canonical |
| --- | ---: | ---: | ---: |
| Provision, distribute, mount, bootstrap, start | 900 | 900 | 900 |
| Control, including warmup and final V4 restore | 180 | 300 | 900 |
| Candidate warmup and pre-measurement checks | 60 | 60 | 120 |
| Measurement cells | 450 | 960 | 1800 |
| Quiesce, collect, independently validate, retain | 600 | 900 | 1380 |
| Cleanup reserve | 300 | 300 | 300 |
| **Planned maximum elapsed time** | **2490** | **3420** | **5400** |

Each reservation is a ceiling; unused time does not extend a measurement cell.
The provider watchdog and paid cost reservation still cover 5400 seconds per topology.
If the pre-cloud local/fake qualification cannot fit these budgets, stop and review
an amended plan before paid admission.

### Remote recovery window amendment (2026-09-17)

[Experiment 35284962814](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35284962814)
passed healthy, unavailable, slow, incremental and snapshot. Restart completed in
30.685196299 seconds, returned the leader to READY at epoch 3 (previously 2), and
rejected the retained epoch-2 request with STALE_EPOCH. The former 15-second window
therefore rejected a functionally completed recovery. Controller receipts account
for 9.19 seconds stopping/reaping three JVMs, 18.79 seconds opening three new worker
streams and checking their identities, 0.288 seconds activating, and approximately
2.41 seconds checking stale-message rejection. Startup/identity intervals include
SSH/IAP setup and guest JVM work; the evidence does not isolate pure SSH latency.

The experiment restart window becomes 60 seconds. Experiment and failure-drill
maintenance become 120 seconds, matching canonical: maintenance performs two
restart rounds in addition to backup publication, kill, cancellation and close.
Its previous 15/60-second windows did not allow two instances of the observed
restart path. No maintenance completion is claimed for this failed experiment;
that scenario was not reached. The table values above supersede the original
300/900-second profile totals with 450/960 seconds.

All recovery orchestration remains charged to its elapsed fault cell. Overruns
still fail, early completion waits out the full window, and the independent
validator enforces the same limits. Healthy/sustained calls, rates and windows,
canonical cells, cleanup reserves, VM/disk bounds and the 5400-second watchdog are
unchanged. Existing USD 4.48 per-attempt allocations already price that watchdog
and 1080 seconds of disk cleanup overhang; this change needs no larger allocation.

The amended full-workload plan SHA-256 is
`93fe1627fad6a39e073ffcd0cb6a87b3bfcab20fa62a3211b383121f6a28b944`.
It replaces the budget-amendment digest `64732d1b192351dbe91f81b05314555c7c734eb06a5d6c7b87f1d2208a3a83d5`.
This is a prospective plan change: the prior experiment remains failed and its
USD 4.48 reservation remains in the ledger (USD 26.56 cumulative, USD 73.44 below
the approved USD 100 ceiling). All thirteen owned resources had confirmed absence
and evidence retention was VERIFIED. After protected review/merge and exact-source
CI, prepare a new sequence and review its current preflight before manual execution.

Local validation: 246 Python tests and the Foundation gate passed. The virtual
controller regression fails the former plan with the observed 30.685-second
restart and a simulated 75-second maintenance, passes the amended schedules, and
still rejects elapsed work beyond the new limits. Independent timing tests reject
shortened and overrun fault windows. The remote adapter gate passed 21 Python tests,
all fourteen local JVM cells and fifteen provenance negatives using the existing
built Java runtime. These are local checks; the amended cloud sequence has not run.

### Remote control accounting clarification

The user approved separate control accounting on 2026-09-16 during remote adapter
implementation. Healthy ABBA and sustained sampling retain every frozen call,
interval and nominal measurement second. SSH round trips, window transitions and
inter-cell preparation are recorded separately and charged, together with actual
candidate warmup, to the existing 60/60/120-second candidate preparation reservation.
Unused measurement time cannot fund that overhead. Fault cells retain their elapsed
windows. Controller timestamps are used only within the controller clock; JVM
sample durations and schedule checks remain within their issuing JVM.

The independent validator recomputes nominal measurement time from call counts and
intervals, measures the additional controller elapsed time and rejects an exhausted
preparation reservation. The existing fixed-rate scheduler's one-second bounded
completion allowance remains a rejection ceiling, and its elapsed overhead is
included in control accounting. This clarification changes neither the workload
JSON/hash nor the topology, cleanup or cost ceilings.

## Fault mechanics and authority checks

All application operations use public APIs and sealed `(1,1)` startup. Test barriers,
owned-process signals and run-scoped network controls may coordinate faults; private
initializers, private application calls and private floor advancement are excluded.
Every cell records command/PID/incarnation identities, the injection/acknowledgement,
quorum membership, observed progress, recovery result and unchanged source hashes.

| Cell | Injection and required observation |
| --- | --- |
| Unavailable follower | Isolate node-3's replication traffic for the first 10 seconds; node-1/node-2 continue bounded writes. Heal and publicly catch up before the cell ends. |
| Slow follower | Add 250 ms to node-3 APPEND acknowledgements for the first 10 seconds with a bounded test transport queue. Record actual delay, retries and lag; do not assume holding an ACK freezes follower publication. The healthy quorum continues. |
| Incremental | Isolate node-3 for the first 10 seconds while the leader writes; no checkpoint before this cell. Heal and require committed batch transfer with independently equal history/application. |
| Snapshot | Isolate node-3, commit ten background updates, then take a public leader-local checkpoint. Its snapshot index exceeds the follower's committed index, making the public catch-up path choose a snapshot. Drop the first snapshot-chunk ACK, retain the partial-transfer evidence, heal and retry through public catch-up. Require verified installation and source preservation. |
| Entry/proof cuts | One dedicated write, no background operations. Kill the owned leader at the named real barrier; record a missing client success as indeterminate. Entry quorum alone supplies no invented commitment; proof-quorum recovery must preserve the proven write. Restart/fence/reconcile from retained authority before proceeding. |
| Restart/fencing | Stop/restart the configured leader, explicitly activate a strictly higher epoch; send a retained old-incarnation request and require rejection. No election or follower application read is introduced. |
| Follower disk loss | Retain a bounded pre-loss copy, stop the owned worker, unmount/delete its owned data disk and verify absence before creating its replacement. Use public replacement/bootstrap admission; it remains non-voting until verified recovery. |
| Leader disk loss | Retain the pre-loss copy and replace its disk as above. One available survivor must fail configured-leader reconstruction; both valid survivors are required. Record the same configured leader identity and public reconstruction/fencing. |
| Maintenance | Writer-ordered backup with a known preceding successful write; validate its committed cut and pinned-V4 restoration. At a second backup's publication barrier, cancel/close the owning operation/process, restart and prove an already published backup survives. Do not report cancellation as rollback of a completed write. |
| Capacity | With a resolved cut and no interleaved catch-up, attempt at most three local checkpoints at distinct committed cuts. Two retained generation slots and an unadvanced local recovery floor must yield `CAPACITY_EXCEEDED` before protected sources are overwritten. Stop this cell on the first expected rejection and inspect the last valid sources; unexpected storage failure is not a pass. |
| No quorum | Isolate both followers for the final write/read phase. Attempt one write and classify its actual failure/indeterminate outcome; read the last committed leader state. Retain any unresolved tail, then stop for offline inspection; this cell is last to avoid hiding reconciliation work. |

A local checkpoint does not advance the recovery floor. Public catch-up can establish
peer recovery floors through its own verified protocol; record that distinction.
The snapshot predicate depends on snapshot index, not on assumed deletion of old
logs. Before each checkpoint, record selected generation and floor. Normal cells
must not hit generation capacity unexpectedly. The deliberate capacity cell has no
interleaved peer maintenance and runs last in failure-drill. Local qualification must
prove the entire ordered sequence works with the two-slot generation rules.

Disk replacement extends the current runner's fixed inventory: each new disk needs a
fresh name, create request ID, intent, returned ID, mount/seal receipt and cleanup
record in the same lease. Do not reuse a stale disk/PID receipt. At most three VMs
exist; obsolete data disks are deleted before replacement creation, preserving the
450-GiB peak. Pre-loss evidence copies remain diagnostic and cannot secretly serve
as a reconstruction source in a simulated disk-loss case.

## Bounds and admission arithmetic

The following numbers are proposed cloud inputs, not edits to executable 6A/6B plans.
GiB/MiB mean binary units. Initial V4 load creates base sequence 256 outside the
replication log; all subsequent application entries, activation NO_OPs and unresolved
tails count toward the replication cap, including warmup and recovery.

```json
{
  "preset": "v5.0-replicated-single-shard-v1",
  "execution": "disabled-until-implementation-and-paid-admission",
  "corpusDocuments": 4096,
  "maximumClientCalls": 60000,
  "maximumLogIndex": 32768,
  "maximumFaultCalls": 12000,
  "maximumRecoveryEntries": 1024,
  "maximumEncodedDocumentBytes": 256,
  "maximumEncodedApplicationPayloadBytes": 2048,
  "maximumEncodedEntryBytes": 2560,
  "maximumEncodedProofBytes": 2048,
  "maximumSnapshotImageBytes": 16777216,
  "application": {
    "maxDocuments": 8192,
    "maxBulkElements": 16,
    "maxEncodedKeyBytes": 1024,
    "maxEncodedDocumentBytes": 4096,
    "checkpointWalBytes": 33554432,
    "maxRetainedBytes": 134217728,
    "maxDerivedStateBytes": 16777216
  },
  "replicationBounds": {
    "maxFrameBytes": 1048576,
    "maxEntriesPerAppend": 16,
    "maxInFlightPerPeer": 4,
    "maxPendingClientOperations": 16,
    "maxRetryAttempts": 2,
    "requestTimeoutMillis": 1500,
    "retryBackoffMillis": 10,
    "snapshotChunkBytes": 4096,
    "maxRetainedLogBytes": 268435456,
    "maxSnapshotStagingBytes": 67108864
  },
  "evidenceBounds": {
    "maxBundleBytes": 4294967296,
    "maxJsonMemberBytes": 16777216,
    "maxBinaryMemberBytes": 33554432,
    "maxFiles": 2000,
    "maxResponseBytes": 4194304,
    "maxSamplesAndTracesBytes": 536870912
  }
}
```

Canonical steady work is 4800 healthy calls (3840 mutations) plus 6000 sustained
calls (4500 mutations), with 200 warmup calls (160 mutations). Even reserving all
12000 fault calls as mutations and 1024 recovery/activation entries gives at most
21524 entries, leaving 11244 below the log cap. The 60000-call envelope also bounds
queries, commands and duplicate client attempts; transport retries do not mint new
logical entries. Exact generated operations must independently pass all byte/count
limits before execution; limits are not permission to fill the entire disk.

At the log cap, 2560-byte entries plus 2048-byte proofs total 144 MiB before journal
framing. Two 16-MiB images and a 16-MiB journal/metadata reserve total 192 MiB, below
the 256-MiB retained-log bound. The 64-MiB staging limit is separate. Ancestry is
bounded by 32768 anchors, below the runtime's 1000000-anchor ceiling. These byte
calculations do not prove a Java heap bound: local qualification must measure the
4096-document workload, independent validation, both generations and transfer peak
with the exact 2-GiB heap. Record GC, heap, sampled RSS, CPU, queues, force timings,
network bytes and all authority/staging disk bytes. Sampled RSS is not a hard peak
measurement. Resource exhaustion or a missing sample fails acceptance.

The cloud evidence schema needs a separately reviewed increase from the existing
128-MiB evidence bundle to at most 4 GiB uncompressed per topology. Keep the offline
artifact bundle at 128 MiB and command responses at 4 MiB. Split state/trace/image
members with ordered part hashes and complete reassembly checks; never truncate a
report or accept only an aggregate digest. Bound nested/uncompressed archive bytes,
member count, paths and each member before extraction/allocation.

Reserve five authority copies (three final voters and two pre-loss disks), each up
to 320 MiB replication plus 128 MiB application data: 2240 MiB. Add 128 MiB control,
256 MiB source/published backups, 512 MiB samples/traces, 128 MiB artifact inventory
and 128 MiB manifests/diagnostics: 3392 MiB, leaving 704 MiB below 4 GiB. Allocation
is a cap, not permission to discard a protected source: if actual retained sources,
framing, backup or evidence exceed it, stop and retain a classified failure before
admitting another topology. Keep only bounded wire traces for fault windows; preserve
raw per-operation measurements and streaming independent state evidence for all cells.

## Resource, cost and admission gates

Inherit three Standard `n2-standard-8` VMs, `us-west4-a`, 24 vCPU, private replication
endpoints, three 50-GiB boot disks and three 100-GiB `pd-balanced` ext4 data disks.
The pinned image remains `ubuntu-2404-noble-amd64-v20260906`, ID
`6257327608773510097`; catalog/quota observations in the runner report are historical.
A changed image/JDK/build input requires a reviewed exact plan and new receipts.

The complete experiment + failure-drill + three canonical sequence is limited to
USD 100 under the [approved budget amendment](PHASE_6_BUDGET_AMENDMENT.md), including control, evidence, cleanup, failed attempts and any optional paid
admission probe. Pricing every topology at the 5400-second ceiling reserves 22.5
VM-hours and 3375 GiB-hours of provisioned disks before cleanup overhang. Reserve
at least 1080 seconds of disk overhang per topology (another 675 GiB-hours across
five); provider/scheduler outages can exceed that allowance and remain unresolved
cleanup failures. Evidence allowance is up to 20 GiB for the five bundles, plus
Actions copies, metadata, failed attempts and retention/transfer duration.

Before approval, attach current VM/disk/storage/transfer price sources and the
calculation `VM-hours * VM-rate + disk-hours * disk-rate + evidence/transfer +
cleanup/failed-attempt reserve`. This document supplies ceilings, not a current-price
quote. Optional admission probes and retries consume the same append-only USD 100
ledger; failed reservations are not automatically refunded. If the priced complete
sequence does not fit, stop before mutation and review scope/budget explicitly.

Retain the runner's 900-second receipt expiry, exact protected-master full CI,
service-account/WIF/firewall/quota checks, successful actually executed scheduled
cleanup for that source within two hours, reviewed request digest, GCS generation
conditions, provider watchdog and 300-second cleanup reserve. The global lease
blocks the next topology until evidence retention and owned-resource deletion are
verified. Adding workload presets must not weaken these gates. IAM setup, cleanup
enablement and an exact paid confirmation remain separate later actions.

## Implementation order and acceptance

| Next PR | Deliverable | Required gate |
| --- | --- | --- |
| Cloud workload and evidence | Materialize this plan as a separate JSON contract; parameterized public worker, deterministic schedule, streaming independent model/validators, bounded evidence extension | Reduced named local preset plus full-size corpus/byte arithmetic checks, ordered fault/public-operation sequence, concurrent read-cut verification and resealed semantic negatives; no cloud credentials |
| Runner preset qualification | Add explicit experiment/failure-drill/canonical plan/fake selection, closed elapsed allocations, replacement resource generations and shared ledger sequencing; full offline bundle with volume paths | Same runner decisions through fake adapter, serial-set/cost negatives, partial replacement/lost create ACK/cancellation/cleanup failures, real local three-JVM workload and full CI |
| Remote runner preset integration | Connect remote signals/network faults, public replacement, timed cloud cells, bounded collection and independent cloud/member/set provenance | Real adapter contracts, collection overflow/failure and resealed cloud-provenance negatives; exact-source full CI before paid preparation |
| 6C staged execution | Fresh read-only admission, current-price complete-sequence review and explicit paid confirmation; execute all five topologies serially in either admitted order | Independently valid member/topology/set evidence and cleanup after every topology |
| 6D registration | Review every retained result and exact measured source/artifacts; separate append-only baseline PR | Register `v5.0.0-replicated-cloud` only after complete accepted evidence |

The cloud schema must reject missing/short cells, incomplete/duplicated parts, altered
seed/rate/corpus, wrong public/control artifacts, false proof-quorum success,
ambiguous concurrent reads, suppressed rejections, fabricated force samples, stale
resource generations, overlapping replacement disks above the cap, mixed canonical
sources, forged cleanup and selective reruns, even after outer hashes are recomputed.
Local reduced receipts, fake cloud receipts and real cloud receipts remain distinct.

The named local qualification uses completion-paced v2 arrivals with a 20-second
window ceiling. It waits for each lane's prior operation and keeps the nominal,
deferred and actual dispatch timestamps, all operation samples and bounded concurrency.
Its 200/100-ms intervals are minimum dispatch gaps. This avoids treating hosted-CI
jitter as a cloud offered-load result. The cloud fixed-rate workload, durations,
resource reservations and no-missed-slot requirement above are unchanged. Full cloud
profiles abort at the first missed slot and retain its diagnostic record.

- [x] Runner PR #158 and exact-master CI accepted, including executed 6A/6B gates.
- [x] Corpus, operation mix, rates, ordered cells, durations and resource/evidence budgets proposed.
- [x] This documentation plan accepted through PR #159 and exact-master documentation CI `35053778177`.
- [x] Cloud workload/evidence implementation accepted in PR #160 with exact-master full CI `35058372449` and 22 independent negative fixtures.
- [ ] Runner preset integration accepted with local/fake and exact-source full CI.
- [ ] Fresh admission, cloud setup and exact paid confirmation complete.
- [ ] Experiment, failure-drill and three canonical repetitions independently accepted.
- [ ] Baseline registration accepted; only then may Phase 7 begin.

## Validation scope

This change is Markdown-only. Validate the Phase 0 contract, existing CI-classifier
tests, local links/anchors, fences, corpus digest, duration/count/byte arithmetic and
whitespace. Existing runtime plans, workflow and production artifacts are unchanged;
Java/process/build gates belong to the subsequent implementation PRs.

Local validation passed: Phase 0 contract, 14 existing CI-classifier tests, 209 local
links (one anchor), fences and whitespace across all ten changed Markdown paths.
Independent Python checks reproduced the corpus digest and table totals, exhausted
6000 healthy cycles (maximum generated document 61 bytes, bulk payload 1169 bytes),
and checked entry, disk/evidence and cost-unit arithmetic. Both executable plan files
are byte-identical to accepted HEAD. The changed paths select `run_full_ci=false`;
protected acceptance completed below.


## Protected acceptance

[PR #159](https://github.com/patricklfdm/GeneralSearchEngine/pull/159) merged at
`29f3d8458d93023c5d4d86b6a22692b4e95d14f8`.
[PR CI 35053755868](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35053755868)
and [exact-master CI 35053778177](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35053778177)
passed Change scope and Required, with all four full-build jobs correctly skipped.
[Cloud workload and evidence](PHASE_6_CLOUD_WORKLOAD.md) were accepted in PR #160
with exact-master full CI `35058372449`. The current candidate is
[runner preset qualification](PHASE_6_RUNNER_PRESETS.md).
Remote integration and paid admission remain later gates.
