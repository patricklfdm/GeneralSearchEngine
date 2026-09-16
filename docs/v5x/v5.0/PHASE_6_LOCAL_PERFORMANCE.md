# V5.0 Phase 6A local performance and evidence

- **Status:** Accepted through PR #157 and exact-master CI `35043760510`
- **Branch:** `feat/v5.0-phase6a-local-performance`
- **Starting master:** `3eb0dc1067b3001c04768190a2844be69c137da3`
- **Predecessor:** [Entry plan, PR #156](https://github.com/patricklfdm/GeneralSearchEngine/pull/156), [master CI 35039318340](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35039318340)
- **Plan:** [phase6-plan.json](phase6-plan.json)
- **Gate:** [verify-v50-phase6-performance.sh](../../../scripts/verify-v50-phase6-performance.sh)
- **Runtime contract:** [Public admission Step C](PUBLIC_ADMISSION_RUNTIME.md)

## Delivered boundary

The gate compiles the application consumer against the production core and
replication JARs, then compiles the observer separately. All application and lifecycle
calls use public APIs. The observer installs existing test hooks for entry/proof
force, quorum/publication events and encoded transport attempts. No production code,
public API, storage format or default changes are required.

The published `4.4.0` control is compiled separately with only its checksum-pinned
core JAR. It runs the same workload and shared application configuration before the
candidate processes start, and restores the candidate's exported backup after they
exit. The loaded code source, classpath, JAR hashes and complete semantic report
are retained. The control digest remains
`0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`.

The candidate owns three separate JVMs on loopback. PID, Linux process start ticks,
boot ID, command exchanges and parent-monotonic lifecycle times bind the concurrent
healthy windows to those processes. Followers are queried for diagnostics; their
application state is inspected independently from quiescent retained files.

## Frozen local workload

| Input | Local smoke value |
| --- | --- |
| Preset | `v5.0-phase6-local-smoke-v1` |
| Corpus | 64 documents; seed 17; four initial atomic batches of 16 |
| Corpus identity | SHA-256 of ordered length-prefixed encoded documents, recorded in the plan |
| Schema/codec | `AdmissionSemanticModel.Doc`, `semantic-codec/1`, four indexes; integer keys and newline-delimited documents |
| Query | `category=guide AND body contains java`, insertion order |
| Cycle | ADD, UPDATE, REMOVE, ADD_ALL, UPDATE_ALL, REMOVE_ALL, INDEX_DROP, INDEX_CREATE, GET, QUERY |
| Bulk calls | Four documents per measured bulk request |
| Scheduling | One closed-loop client; one warmup cycle, then two cycles per window |
| Windows | baseline-a, instrumented-a, instrumented-b, baseline-b (ABBA) |
| Application sequence | Bootstrap base 4; warmup + measured writes advance to 76 |
| Log bounds | Activation NO_OP + 72 application entries = committed index 73; one failed no-quorum tail at index 74 |
| JVM | Java 21, G1, 64 MiB initial / 256 MiB maximum heap, two active processors |
| Time ceilings | 30 seconds per window; 120 seconds reserved for measurement, 90 for control/setup, 30 for cleanup; 240 total |
| Storage bounds | 64 MiB replica log and staging limits; 128 MiB materialization retention; encoded document bound 4096 bytes |

Each cycle inserts/removes temporary IDs and updates existing IDs. The final state
contains the original 64 IDs in insertion order. The Python model independently
derives every mutation payload digest, read-answer digest, sequence and final encoded
document. The corpus and operation ceilings keep this run far below the runtime's
one-million-anchor snapshot limit. Initial load belongs to the source backup and
does not create replica-log application entries.

Warmup produces 10 calls and eight mutations. The measured windows contain 80 calls,
including 64 durable mutations. Afterward, the gate explicitly catches up both
followers, checkpoints each node, exports a backup, stops both followers and attempts
one more write. `QUORUM_UNAVAILABLE` is counted separately as indeterminate, with zero
durable successes. Committed reads remain equal to the control, and independent
inspection confirms the unproven tail does not change the committed prefix.

## Measurement definitions

All durations use a JVM-local monotonic clock. Parent-monotonic times establish
process overlap and command ordering; the verifier never subtracts clocks from
different processes. Every successful mutation in an instrumented leader window
must contain entry force, entry quorum, proof force, proof quorum, publication and
the success barrier before its Future returns.

The gate retains raw operation samples and calculates nearest-rank p50/p95/p99,
attempted/admitted/completed/durable-success counts, rejected/time-out/indeterminate
counts, elapsed window time and request rate. Bulk request counts and documents
touched are separate. Warmup and the no-quorum cell are excluded from healthy rates.

The ABBA summary records the observed ratio of instrumented to baseline elapsed
time. Both control and candidate retain all four windows. The control has no replica
hooks, so its same-named windows also expose ordering/warmup variation. Two samples
per operation/window cannot support a tail-latency or causal overhead claim; no
performance threshold is asserted by this smoke.

Resource samples record heap, RSS, process-lifetime peak RSS, GC, process CPU, Linux
process I/O counters, local storage bytes, pending clients and observed peer indexes
at command/window boundaries. These are observations, not continuous queue or disk
peaks. Transport counters count encoded message attempts, including possible retries;
they do not claim actual bytes delivered by the network. Hook data is bounded in
memory and never written to disk from a measured hook.

## Runtime evidence contract

This introduces `gse-v50-performance-evidence-v1` and
`gse-v50-performance-member-v1`. The historical Phase 1 schema and fixtures are
unchanged. The accepted execution value for these local validators is exactly
`local-public-runtime-only`; fake, GCP and canonical labels are rejected.

| Retained path | Contract and independent checks |
| --- | --- |
| `plan.json` | Exact bytes of the reviewed plan; schema, preset, seed, schedule, JVM and resource ceilings checked before execution |
| `metadata.json`, `source-inputs.zip` | Source HEAD and dirty flag; hashes and retained source/build/probe/workflow inputs; JDK, compiler, Maven, kernel, filesystem/mount data and local boot identity |
| `artifacts/*.jar`, `processes/*` | Core, replication and pinned published control JARs; separate compile commands; stdout/stderr and owned process receipts |
| `members/node-{1,2,3}.json` | Member schema, node/PID/start ticks, loaded code source, flags, lifecycle, every request/response, telemetry and clean reaped exit |
| `control.json`, `restore.json` | Separate V4 workload and exported-backup restore receipts, bound to process output and loaded control artifact |
| `node-{1,2,3}/**`, `operation/**`, `source/**`, `export/**` | Retained authority, bootstrap receipt, immutable source and completed export; independent 1.1 proof/ancestry, configuration and snapshot inspection |
| `measurements.json` | Derived statistics, overhead observation and separate fault outcome; verifier recomputes them from raw samples |
| `set.json` | Schema, execution, protocol, preset, plan digest, exactly three members, run times and complete relative file inventory with byte lengths/SHA-256 |

`set.json` does not hash itself. No other file may be omitted from the inventory.
The validator rejects symlinks, duplicate JSON keys, excess nesting, nonfinite
numbers, missing members, unreviewed plans and oversized bundles. Limits are 16 MiB
per file, 128 MiB total, 2000 files, 4 MiB per worker response, 4096 observations of
each kind per window and 8 MiB of encoded attempts per member/window. The source
archive has an independently bounded expanded size and is read without extraction.

The [independent verifier](../../../scripts/v50/performance_evidence.py) checks
each member before the set: process identity/exit, isolated classpaths, command
schedule, resource observations, row count/order/timing, sequence/read semantics,
quorum/publication observations, source genesis, selected snapshot payload ancestry,
committed-prefix equality, V4 round-trip equality and recomputed statistics. It
checks hashes again afterward to prove read-only inspection. These receipts support
review of an owned local run; they are not external process attestations.

The [negative-fixture gate](../../../scripts/v50/test_performance_evidence.py)
copies actual runtime evidence, changes it, recomputes the outer checksums and then
requires rejection. Cases include fake/cloud relabeling, missing samples, invented
success sequences/read answers, impossible timing, serial voters, reused PIDs,
false cleanup, missing force/proof observations, mixed artifacts, wrong control,
forged aggregates, missing members, changed plans/source backup and corrupt authority. One case
rewrites a snapshot's payload digest and reseals its snapshot, generation and selector
checksums; checksum consistency still cannot substitute for valid history.

## Execution and retention

```bash
scripts/verify-v50-phase6-performance.sh
# Or reuse a reactor build from the same unchanged source:
scripts/verify-v50-phase6-performance.sh --skip-build

# Standalone, read-only revalidation of a retained bundle:
python3 -m scripts.v50.performance_evidence /path/to/evidence \
  --plan docs/v5x/v5.0/phase6-plan.json
```

`GSE_V50_CONTROL_JAR` may select an already downloaded control; its digest must match.
The gate writes fresh `target/v50-performance/run.*/` directories and retains failure
stdout/stderr and cleanup receipts. Work stops before the cleanup reserve; a shell
watchdog and signal handling bound cancellation. Cleanup addresses only owned child
process handles. Required CI runs the gate after Step C and uploads the directory
with `always()` for 14 days. Python unit negatives also run in the no-GCP job.

Local development evidence records a dirty source inventory rather than claiming
the work ran on the starting master alone. After merge, exact-master CI supplies
the clean source receipt. The test sources, workers and instrumentation are excluded
from all production JARs and checked by the verifier and release artifact gate.

## Remaining Phase 6 gates

6A establishes the reduced local probe and evidence contract. Its plan carries the
inherited cloud resource ceilings, with cloud execution explicitly disabled.
[6B](PHASE_6_CLOUD_RUNNER.md) now supplies the accepted runner, preflight machinery,
guest/storage identities and reduced cloud evidence provenance. The separate
[full cloud workload plan](PHASE_6_CLOUD_WORKLOAD_PLAN.md) was accepted in PR #159;
[workload/evidence implementation](PHASE_6_CLOUD_WORKLOAD.md) was accepted in PR #160.
[Runner preset qualification](PHASE_6_RUNNER_PRESETS.md) and remote integration
still require acceptance before 6C measurements. Cloud presets
must allocate the complete cell matrix and measurement budgets from the accepted
[entry plan](PHASE_6_ENTRY_PLAN.md); a local reduced schedule cannot satisfy them.

Restart/fencing, slow/unavailable followers, interrupted snapshot transfer, disk
replacement and cancellation remain correctness-covered by Step C and Phases 1–5.
This smoke does not turn those results into performance measurements. Their cloud
measurement cells and sustained high-frequency resource sampling remain open.
No experiment, failure-drill, canonical repetition or baseline registration is
claimed by this PR.

## Regression correction

The consolidated regression run exposed an existing slow-follower test assumption:
a held APPEND response was treated as freezing the follower application. The retained
trace showed the follower advancing from index 9 to 12 while the healthy leader
reached 19. Outgoing FIFO timeout allows later valid commit proofs to arrive; this
is legal progress. The Phase 5 harness now records the observation, requires all
ten healthy-quorum writes, and bounds follower progress by the acknowledged prefix.
It retains the real-hold transcript check and independent post-recovery comparison.
Three focused tests reject regression, unacknowledged progress and loss of quorum.

## Local validation

The final local gate completed in 10.12 seconds and reported 80 measured requests,
64 durable measured mutations, sequence 76, committed index 73 and one separately
classified no-quorum indeterminate result. All 20 resealed negatives were rejected.
The local receipt names starting HEAD `3eb0dc1067b3001c04768190a2844be69c137da3`
with `sourceDirty=true` and retains the exact candidate inputs.

| Check | Result |
| --- | --- |
| Reactor `clean -Prelease -Dgpg.skip=true verify` | PASS; 705 tests reported, four existing skips, zero failures/errors |
| Release contents | PASS; all nine JARs; core and replication SHA-256 unchanged from Step C |
| V5 Python tests | PASS; 98 tests |
| CI classifier | PASS; 14 tests; JSON plan selects full CI |
| Public admission A/B/C | PASS; Step C includes 21 public runtime cases |
| Phase 1–5 gates | PASS; final Phase 5 run includes all 16 cases after the assertion correction above |
| Phase 6A | PASS; pinned V4 control, concurrent JVMs, independent state/measurement checks and 20 negative cases |
| Documentation/shell | PASS; Phase 0 contract, local links, fences, shell syntax and whitespace |

Cloud profiles remain pending. Clean exact-master CI is now accepted below. The local run makes no
throughput/p99 target or cloud-readiness claim.

## Acceptance

- [x] Entry plan PR #156 and exact-master documentation CI verified.
- [x] Public consumer and independently compiled pinned V4 control execute locally.
- [x] Final three-JVM smoke, independent member/set validation and 20 resealed negative cases pass.
- [x] Consolidated reactor/release and existing V5 regression gates pass.
- [x] Protected 6A PR and exact-master CI accepted.
- [x] 6B real runner/preflight accepted through PR #158 and exact-master CI `35051728286`.
- [x] Full cloud workload plan accepted through PR #159.
- [ ] Executable cloud workload/evidence and runner presets accepted.

## Protected acceptance

[PR #157](https://github.com/patricklfdm/GeneralSearchEngine/pull/157) merged at
`7754b696fea7e6fb18c79dd632ab055f5f1da546`.
[PR CI 35042495172](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35042495172)
and [exact-master CI 35043760510](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35043760510)
passed all six jobs. Master logs confirm public A/B/C, Phase 1–5 and 6A executed.
The 6A receipt reports `sourceDirty=false`, sequence 76, committed index 73,
80 measured requests, 64 durable writes, one no-quorum indeterminate call and
20 rejected semantic negatives. [6B cloud runner and preflight](PHASE_6_CLOUD_RUNNER.md)
has since been accepted through PR #158 and the
[full cloud workload plan](PHASE_6_CLOUD_WORKLOAD_PLAN.md) through PR #159.
[Workload/evidence implementation](PHASE_6_CLOUD_WORKLOAD.md) was accepted in PR #160
with exact-master CI `35058372449`. The current candidate is
[runner preset qualification](PHASE_6_RUNNER_PRESETS.md).
