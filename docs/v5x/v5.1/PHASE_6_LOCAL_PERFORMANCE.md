# V5.1 Phase 6A local runtime measurements

**Status:** implementation candidate; protected exact-source full CI and review
are required before accepting 6A. The rich model foundation was accepted through
PR #216 at `bcac615aeef93dadcab6636162a86ce2156e5515`, full master CI `35841378072`.
The [frozen local contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md) and
[plan](phase6-plan.json) remain unchanged. No cloud configuration, admission,
sequence, budget or paid execution is supplied by this local gate.

## Executed schedule

`verify-v51-phase6-performance.sh` compiles separate external adapters and runs:

1. Checksum-pinned published V4.4 local durable engine.
2. Checksum-pinned published V5.0 configured replication, three concurrent JVMs.
3. Candidate V5.1 automatic replication, three concurrent JVMs with the same
   1200 / 3600–6000 / 9600 ms policy on every voter.
4. A separate fresh automatic group with the bounded two-field concurrent history,
   one real idle-leader SIGKILL and same-authority voter restart/rejoin.

Healthy modes run sequentially with exactly 90 calls each: 10 warmup and four
20-call ABBA windows. No operation retry, corpus reset or hidden currentSequence()
read is used. There are 72 mutations, 18 GET/query reads and final application
sequence 76. Automatic mode's one final backup uses one explicitly counted auxiliary
read barrier. The observed healthy automatic prefix has 92 slots, while configured
V5.0 has 73; these indices are deliberately not treated as equal application progress.
All three voters must durably reach the final cut before normal shutdown.

The unchanged V4.4 source backup seeds both replicated groups. Both replicated
exports are restored through a separate published V4.4 process and compared with
independently decoded ordered documents/indexes. The local V4.4 final checkpoint is
checked directly: its known post-index-recreation backup ordering limitation remains
recorded in the [foundation review](PHASE_6_MODEL_FOUNDATION.md).

Small failover retains every attempt within the frozen maximum of 18 application
calls. The original 24-operation / 100000-state exhaustive two-field checker and
physical checker both run. The killed PID must own the preceding successful read;
a survivor must publish in a higher epoch. An immutable archive precedes reopening,
and the restarted process must preserve admission files and rejoin through the
post-fault captured durable cut. Only the contract's classified availability outcomes
permit the next fresh-key progress pair. Integrity/capacity/unknown errors fail.

## Measurements and observation boundary

All JVMs use Java 21 and the four frozen heap/GC/processor flags. Evidence records
exact vendor/build, loaded JAR paths/hashes, compiler commands, source/class
inventories, PID/start ticks, process intervals, host/cgroup limits and clock resolution.
Published controls cannot load candidate/workspace engine classes. The bundle retains
all five JARs and each independently compiled adapter directory.

API intervals use the issuing JVM's monotonic clock and observe the original public
future's completion, or synchronous read result. Controller dispatch/result latency
is reported separately. Warmup remains in correctness checks but contributes no
measured percentile. Each measured operation has eight samples; nearest-rank
p50/p95/p99, ABBA per-operation costs, attempted/completed rate, successful read/write
counts and mutation document touches are recomputed from raw calls. No throughput
or latency threshold asserts that the candidate is faster.

Essential force, wire, publication and read-cut observations remain enabled in A
and B. B additionally retains force durations and reports protocol executor submission
→ actual request-write intervals on the same JVM. That queue interval includes
serialization, connection and reservation overhead; it is not pure executor wait.
Direct basis/rejoin requests have a different ID domain and are not paired with
protocol executor submissions. Detection uses the candidate-local last election timer
arm → campaign start; promise quorum and activation are separate milestones. Failed
campaigns remain in the trace. Controller fault request/confirmed exit bracket the
injection uncertainty; first successful post-fault write/read and client outage use
that same controller clock. None of these smoke values is a failover SLA.

Boundary and one-second samples include heap/GC, RSS high-water observations, CPU,
threads, process I/O, application retained bytes and public status. Candidate-only
read-only probes also capture bounded queues/permits, transport reservations,
source/basis pins, seed staging and authority/transfer disk bytes. Control-owned
containers are inspected on their owning thread; this diagnostic query introduces
no application call, network request or read barrier. Samples include both retained
generations on disk. They are observations, not unsampled peak guarantees; transient
stack-local allocations are represented by JVM heap observations. Published V5.0
private queue details, separate public admission timing and per-process network I/O
are explicitly unsupported. Linux namespace network counters are not presented as
per-process measurements.

Production changes are limited to package-private observation seams: before-force,
election timer/campaign/promise-quorum and outbound queue events. The default runtime
has no added protocol observer. External test sources inject observation hooks only;
there is no private promotion, synthetic force or authority mutation in an adapter.
The existing before-force crash test includes the new cut. Public declarations,
wire/storage formats, authority decisions and cloud paths remain unchanged.

## Independent evidence and failure handling

[performance_physical.py](../../../scripts/v51/performance_physical.py) reconstructs
rich chosen values from actual exact-ballot force observations, validates transferred
frozen bases/selection, local force before ACK, remote proof ACK before publication,
publication before successful response, fresh post-invocation read barriers and exact
captured answers. It checks all three final retained prefixes and settled transport
reservations. The configured control uses its independent 1.1 parser and actual
entry/proof force, ACK and publication order; it is not relabelled automatic evidence.

[performance_evidence.py](../../../scripts/v51/performance_evidence.py) binds original
worker results to controller exchanges, toolchain/artifacts, concurrent process
lifetimes, fixed program/windows, counters and stage budgets. It never accepts a
cached PASS summary in place of these inputs. The rich sequential check does not
claim exhaustive concurrent rich-workload linearizability; exhaustive history checking
applies to the separate supported two-field schedule.

Thirty actual-evidence negatives cover missing calls/failures, changed answers,
replayed IDs/timing, missing force/ACK/basis/voters/publication, a reused barrier,
changed capture, a resealed wrong snapshot, leaked reservations/close permits,
missing periodic/window samples, wrong artifacts/toolchains/process intervals,
forged kill/archive/rejoin, and altered small concurrent histories. Deterministic
unit tests additionally cover percentile/count arithmetic, zero duration, truncated
JSON, safe archive paths/types, duplicate/missing members and every size ceiling.
The accepted foundation's rich decoder/projection adversaries remain required.

The controller owns its child processes and records stage failures and raw logs.
Preparation is 90 seconds, each healthy mode 150, failover 180, validation 120 and
cleanup 60, within a 900-second whole gate. Startup/warmup and each window also retain
their 30-second ceilings. An outer GNU timeout kills the process group if the bounded
controller cannot finish. There are no whole-case retries. Cleanup/retention failure
cannot produce a successful gate.

[performance_bundle.py](../../../scripts/v51/performance_bundle.py) enforces the
1 GiB expanded/compressed, 4000-file, 64 MiB member and 512 MiB trace/sample bounds.
It checks complete member hashes, rejects links/traversal/duplicates and performs
bounded extraction. Raw authorities remain bound to their original admitted absolute
paths. The extraction check establishes portable byte integrity; it does not admit a
copied authority as live storage or claim relocation-aware semantic replay.

## Commands and CI

```bash
scripts/verify-v51-phase6-performance.sh             # Build first
scripts/verify-v51-phase6-performance.sh --skip-build # Current packaged artifacts
python3 -m unittest scripts.v51.test_performance_runtime
```

The existing `v51-foundation` job runs the gate and always uploads
`target/v51-performance` under `v51-performance-${{ github.sha }}` for fourteen days.
The seventeen required jobs, docs-only behavior and all previous commands remain.
The original adapter/model check still runs inside the foundation gate.

## Local validation record

The first complete gate passed at `target/v51-performance/run.Y3RF4S/evidence` in
59.876 seconds before final packaging, with 270 healthy calls, nine small-history
calls, 25 real-evidence negatives and a 24.34 MB compressed bundle. Additional
resource/configured-causality negatives extend the final gate to thirty. In that
first complete observation, automatic voter sampled RSS maxima were 139–157 MB;
first post-SIGKILL durable write/read were 4.002/4.140 seconds after confirmed exit.
These are local Ubuntu `21.0.12+8-1-22.04-Ubuntu` observations, not Temurin/cloud results.

Relevant regressions passed: 50 Java store/protocol/public-runtime/checkpoint tests;
310 V5.1 Python tests; the published-control model gate; and the public concurrent
qualification gate (six interruption cases plus rich semantic parity). The final gate passed at `target/v51-performance/run.6RIbK8/evidence` in 56.955
seconds before final packaging: all three modes, the nine-call SIGKILL history and
all thirty real-evidence negatives passed. Nineteen CI topology/classification tests,
47 unique artifact names, all 115 workflow shell blocks and changed-document links
were checked. Full protected CI for this source remains outstanding.

Development failures remain under `target/v51-performance-runtime-{first,second,third,fourth}`
and the associated logs. They exposed observer shutdown ordering, actual transport
permit ceilings, canonical diagnostic-map keys and queue-statistic context/domain
binding. Their FAIL receipts were not rewritten as passing runs. The standalone
failover diagnostic and complete passing schedules have separate directories.

Next: review exact-source protected full CI before accepting 6A, then separately
freeze 6B cloud workloads/rates/timings/collection inputs. Local results do not
reuse or reset any V5.0 cloud ledger, cleanup admission or prior paid approval.

## PR #217 resource-oracle compatibility correction

[CI 35849128807](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35849128807)
passed the new three-mode performance gate (75 seconds) but failed the existing
internal `promise-count` resource check. The Phase 6 observer added
`PROMISE_BEFORE_FORCE`; the resource oracle still expected only AFTER_FORCE and
BEFORE_ACK for the permitted identical-promise retry after capacity rejection.
This was a deterministic observation-contract mismatch, not a timing failure.

The retained CI archive has identical before/after authority inventories, 10,000
promises and unchanged epoch 29,996. The actual delta is exactly one BEFORE_FORCE,
one AFTER_FORCE and one BEFORE_ACK. The corrected oracle requires all three once
for both promise-count and retained-byte retries. It still rejects missing/duplicate
force observations, all additional writes/deletes and any force event in rejection
cases that have no retry. The authority/archive/reopen checks remain intact.
Production code, limits, timeouts and workloads are unchanged by this correction.

Regression coverage adds missing/duplicate force/ACK, unrelated force/write/cleanup
and nonretry refusal cases. All 26 resource-oracle tests and all 313 V5.1 Python
tests pass. The retained failed CI input is independently rechecked; its original
failed receipt remains unmodified. Logs are `target/pr217-resource-fix.log` and
`target/pr217-resource-python.log`.

The full local resource gate is **not passing**: at `target/v51-resources/run.osjTv8`,
all six internal cases and public `snapshot-staging` pass, but public
`retained-bytes` fails the unchanged 40-second majority activation deadline after
the original leader restarts. Its raw traces show repeated selection of exhausted
node 3, incomplete healthy-peer basis transfers and no activated healthy majority
before the deadline. The traces do not establish the precise transfer failure cause.
This is separate from the deterministic counter mismatch; this patch does not
claim to fix it or accept Phase 6A.

One targeted diagnostic run, using temporary external consumers with additional
read-only last-exchange/last-recovery status fields, passes at
`target/pr217-resource-diagnostic/run/retained-bytes`. It selects healthy node 2
at node 1's next campaign and completes the post-restart read. No production
code, workload, budget or deadline changed between these runs. This diagnostic
pass does not replace the failed full gate or establish stable recovery. Keep the
original failure and treat minority-capacity recovery as an open follow-up; exact
protected CI on the corrected source remains required.


## Post-merge recovery follow-up

PR #217 merged at `e3efda820beef9efcd6f6f06e8af71006c3b85ce`;
[exact-master CI 35889987294](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35889987294)
passed all nineteen jobs, including resources and local performance. The prior
local failure remains evidence of an intermittent recovery path. The
[resource recovery correction](PHASE_4_RESOURCE_LIMITS.md#recovery-scheduling-after-the-phase-6a-resource-rerun)
adds a bounded alternate-peer opportunity after failed activation, with deterministic
regressions. It changes the candidate runtime artifact, so the original performance
hashes and PR #217 CI do not qualify that new artifact. Full 6A acceptance and the
separate 6B cloud-parameter freeze await correction validation and protected CI.
