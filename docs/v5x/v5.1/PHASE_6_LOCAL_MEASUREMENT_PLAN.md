# V5.1 Phase 6A local measurement contract

**Status:** accepted with the [Phase 6 entry](PHASE_6_ENTRY_PLAN.md) through PR #215.
Implementation begins with the [rich model foundation](PHASE_6_MODEL_FOUNDATION.md).
Values below are the implementation specification for a reduced local preset, not
observed performance or a cloud preset. Changing them requires a reviewed plan revision.

## Identities and execution layers

The [machine-readable plan](phase6-plan.json) materializes these 6A identities.
The full performance evidence schema remains reserved until runtime qualification:

- Plan: `gse-v51-phase6-plan-v1`; preset: `v5.1-phase6-local-smoke-v1`.
- Measurement evidence: `gse-v51-performance-evidence-v1`.
- Local provenance: `local-public-runtime-only`; no credentials/provider operations.
- Candidate authority/wire: admitted automatic `gse-replicated (1,2)` /
  `gse-replication/1.2`. Published V5.0 stays configured `(1,1)` / `1.1`.

These names do not extend the existing fake planner's schema by implication.
Separate local/fake/remote/cloud validators must check actual process/resource
provenance; a changed execution label cannot upgrade a receipt.

Compile external consumer adapters independently against candidate JARs, published
V5.0 core/replication and published V4.4 core. The exact pins in
[published-controls.json](published-controls.json) remain unchanged. Use isolated
classpaths/directories/JVMs, record loaded classes' code sources and artifact hashes,
and reject a candidate or workspace class shadowing a published control. Shared
workload source may use the common core API; mode-specific bootstrap/routing lives
in its adapter. Do not mix V5.1 automatic declarations into the V4.4/V5.0 classpath.

## Healthy workload, frozen local values

| Input | Local value |
| --- | --- |
| Corpus | 64 documents, integer IDs 1–64, revision 0, seed 17; immutable source backup loaded in four batches of 16 |
| Corpus digest | `1c0ce897a4074c9d8429067ba6a5d6e2d050027502c95fc17add23438a998cb8`; ascending IDs, four-byte big-endian document length followed by encoded document |
| Document tuple | `(id, "Java "+id, category, price, "java search memory revision "+revision)`; category is `news` iff `(id+revision+17)%3==0`, otherwise `guide`; price is `(id*17+revision+17)%1000` |
| Codec | Five UTF-8 fields separated by LF, no trailing LF; four-byte big-endian integer key. Shared semantic codec/schema and `performance-store` identity as in the V5.0 model. |
| Index definitions | Prefix title, equality category, range price, text body with `gse-simple-v1`; preserve source ordering and compare actual index definitions/order |
| Query | `category=guide AND body contains java`, insertion order; hash canonical ordered result IDs, not an unordered set |
| GET | ID `1 + cycle % 64`; hash the same canonical display value as the published control |
| Healthy cycle | `ADD, UPDATE, REMOVE, ADD_ALL, UPDATE_ALL, REMOVE_ALL, INDEX_DROP(category), INDEX_CREATE(category), GET, QUERY` |
| Keys and revisions | Temporary key `100000 + cycle*100 + i`; UPDATE key `1 + (cycle+i)%64`; GET as above. Bulk size four; revision `cycle+1`. Cycle numbers 0–8 never reset between windows. |
| Warmup | One complete cycle (10 calls), retained in correctness history but excluded from measured statistics |
| Measured windows | `baseline-a, instrumented-a, instrumented-b, baseline-b` (ABBA), two complete cycles / 20 calls each |
| Arrival model | One caller, completion-paced closed loop; await every operation before the next. Record actual rate. No offered fixed-rate or saturation claim. |
| Shared application | `semantic-schema`, `semantic-codec/1`, FORCE_SCAN, snapshot queue 31 / max batch 16 / wait 1234567 ns; max documents 1024, max bulk 16, key 1024 bytes, document 4096 bytes |
| Shared application storage | 32 MiB checkpoint WAL, 128 MiB retained application bytes, 4 MiB derived state; preserve published durable/backup `(1,2)` formats |
| Resolved replication bounds | Frame 1 MiB; entries per append 16; in-flight per peer 4; pending clients 4; retries 2; request 1200 ms; backoff 25 ms; snapshot chunks 4096 bytes; retained and staging 64 MiB each |
| Automatic policy | Heartbeat 1200 ms, election 3600–6000 ms, operation 9600 ms on **all three voters**. Do not use the Phase 5 node-3 delayed-election fixture. |
| Each JVM | Java 21, `-Xms64m -Xmx512m -XX:+UseG1GC -XX:ActiveProcessorCount=2`; capture exact vendor/build, flags and host limits. Local results with different exact toolchains are separate identities. |

There are **90 calls per healthy mode: 72 mutations and 18 reads**. Initial imported
application sequence is 4; final sequence is 76 if every call succeeds. The main
corpus ends with 64 documents; peak is 68 while a temporary bulk exists. A failed
index operation stops the case; do not continue the cycle and manufacture a later
"index already exists" failure or silently reset the workload.

Both replicated modes publicly import separate targets from the unchanged, verified
V4.4 backup. V5.0 uses its documented configured activation; V5.1 starts three peers
and observes automatic activation. Run V4.4, V5.0 and V5.1 sequentially. Compare the
same 90-operation program, final state, index truth and application sequence. The
replication slot counts intentionally differ: V5.1 adds **18 read NO_OPs** as well
as activation/recovery NO_OPs; V5.0 does not add automatic strong-read barriers.
Status/metric queries are not substituted for either GET or QUERY. In the current
public automatic implementation, `currentSequence()` is itself a strong read and
`backup()` also acquires a fresh barrier. Do not copy a before/after `currentSequence()`
wrapper around every measured call: it would add 180 unintended barriers. Use raw
capture evidence for truth and diagnostics only for labelled status observations.

## Small concurrent failover history

Use a separate fresh **empty** automatic group and the existing two-field `Doc`
consumer/model, not the healthy rich corpus. This preserves the supported model of
[public_history.py](../../../scripts/v51/public_history.py). Freeze this schedule:

1. Successfully add one uniquely tagged two-document bulk and read it (two calls).
2. Submit one four-call wave `addAll, read, addAll, read` before collecting all four
   results; use disjoint fresh keys. Require all four to succeed in this healthy wave.
3. With those calls completed, SIGKILL the currently observed ready leader. Capture
   exact PID, request/exit interval and immutable pre-reopen archive. Bind that PID
   to the preceding successful read barrier/active ballot and require a higher-epoch
   activation on a survivor; a cached role hint alone cannot qualify leader loss. This is an idle
   leader-loss measurement, not an entry/proof-quorum crash-cut experiment.
4. Route to the surviving processes using public role hints, never manual promotion.
   At most four progress pairs each submit a **fresh** two-document bulk followed by
   a strong read. Retain every attempt. Stop progress pairs when both calls succeed;
   require the successful read to preserve all earlier acknowledged operations.
5. Restart the old voter from that same retained authority, require its new process
   identity and verified rejoin through the post-fault durable cut, then complete a
   final strong read within at most four read attempts. No new group or repaired copy.

Maximum application history: `2 + 4 + 2*4 + 4 = 18` calls, within the unchanged
24-operation / 100000-state checker limit. Retain all invocation/response intervals,
uncertain outcomes and intermediate reads. Independent physical and full-history
checks must agree; resource/process/archive checks still apply. No whole-case retry
or dropped attempt may turn a failed fixed schedule into PASS.

Only classified availability refusals may lead to another progress pair/read:
NOT_LEADER, NOT_READY, QUORUM_UNAVAILABLE, STALE_EPOCH or DEADLINE_EXCEEDED with the
existing conservative read/write outcome combinations. An uncertain write is never
replayed; every pair has new operation IDs and keys. Missing responses must remain
explicit, not be guessed as NOT_SUBMITTED. Integrity, storage, explicit capacity,
CLOSED or unknown errors fail. An exhausted attempt/time bound fails the case.

The first post-fault durable write/read metrics refer to the earliest qualifying
successful calls, even if a later pair is needed for complete progress. All attempt
and routing time remains in controller-observed recovery/outage. This smoke schedule
is a diagnostic bounded progress test, not a production failover SLA.

## Time, slot and evidence ceilings

| Local stage | Maximum seconds |
| --- | ---: |
| Artifact checks, source backup and bootstrap preparation | 90 |
| Published V4.4 healthy control | 150 |
| Published V5.0 healthy control | 150 |
| Candidate automatic healthy | 150 |
| Small automatic failover history, including its bootstrap/rejoin | 180 |
| Quiesce, backup/restore comparison, collect and independently validate | 120 |
| Final owned-process cleanup reserve | 60 |
| **Whole local gate** | **900** |

Each healthy mode reserves at most 30 seconds for startup/warmup and four 30-second
measurement windows. Windows complete their fixed call count rather than waiting
out a fixed duration. Unused time does not enlarge another ceiling. Include shutdown
of each earlier mode before starting the next in that mode's allocation; the last
60 seconds remain available on failure. The controller bounds commands and cleanup;
Java force or application callbacks are not assumed forcibly interruptible.

For each automatic group, admit at most eight auxiliary strong barriers (including
any extra read, `currentSequence()` or backup capture) and 64 activation/recovery
NO_OPs outside its primary schedule. Healthy bound:
`90 + 8 + 64 = 162`, below a **192-slot** ceiling. Failover bound:
`18 + 8 + 64 = 90`, below the same ceiling. These are maxima, not instructions to
issue extra reads. Every probe/barrier must be accounted for. Use offline retained-state inspection
and published-V4.4 restore to validate rich final state instead of calling a large
multi-query report on the automatic runtime. The small-history fixture uses
status/retained proof for rejoin so its application history stays at 18.
Re-proposals of the same value use additional acceptance records without inventing
new logical slots; account for their bytes and ballot identities separately.

The 192-slot admission ceiling is far below the generic million-anchor limit; it
is not permission to ignore a smaller byte bound. Before execution, the generated
codec/operation plan must fit 256-byte documents, 2048-byte application payloads and
16-KiB encoded ENTRY/ACCEPT/PROOF records. Failed admission retains diagnostics.
6A must check actual bootstrap/snapshot/basis/frame encodings, JSON/base64 expansion,
re-proposal records, both generations, staging, pins and duplicate force observations.
A sum of logical payload bytes alone does not establish retained-memory/disk bounds.

Local evidence limits: **1 GiB expanded bundle, 1 GiB compressed input, 4000 files,
64 MiB logical member, 4 MiB command response and 512 MiB total traces/samples**.
Require safe paths, no symlinks/duplicates, bounded extraction and full member hashes.
Use complete bounded parts where necessary; never truncate raw authority/history or
accept a summary after collection overflow. Retain a classified failure manifest
and available diagnostics if complete evidence cannot be collected. No valid performance
receipt may be issued. These limits do not increase the production storage limits.

Sample resources at mode/window/fault boundaries and every second while running:
heap/GC, sampled RSS/CPU, threads, public permits, queues, transport reservations,
retained/staging/pinned bytes and disk/network I/O where measurable. Report unsupported
counters explicitly; a required missing sample fails qualification. Sampled RSS is not
a hard peak. Correctness observations remain enabled in every ABBA window; B adds
force/queue timing detail. Compare per-operation costs and counts, not a claim of
zero instrumentation in A. No one-second sleeps are added to pad short windows.

## Measurement schema and independent validation

Every attempted call records run/mode/cell/window, node/process generation, opId,
operation/keys/payload digest, controller invocation/result interval, worker-local
API start/end, result or structured reason/outcome, and references to immutable raw
evidence. Capture full retained state and source inventories before offline validation.

| Measurement | Boundary / interpretation |
| --- | --- |
| API latency | Same issuing JVM's start immediately before the public call to its synchronous result or original Future completion, including local queue and barrier wait |
| Controller latency | Same controller clock around dispatch/result receipt; includes transport/routing overhead, reported separately from API latency |
| Force/queue timings | Same owner process around the actual force/reservation event; bind entry/proof/ballot identity and causal order, not adjacent timestamps from another JVM |
| Detection | Candidate-local last qualifying progress observation to local campaign start; retain any interval unavailable because the owner was killed |
| Election/activation | Local campaign start → complete frozen promise quorum → fresh activation NO_OP publication; report failed campaigns separately |
| First durable write / strong read | Controller fault request and confirmed exit bracket to earliest qualifying post-fault success; expose injection uncertainty and never subtract guest nanoTime from controller time |
| Client outage | Controller last pre-fault qualifying success to first post-fault success, separately for reads/writes; includes the probe's sampling gap |
| Throughput and percentiles | Attempted/completed rates and per-operation nearest-rank p50/p95/p99 with raw sample count; eight measured samples per operation in healthy local mode are diagnostic only |

Record monotonic clock resolution. Nonnegative zero-duration samples are retained
when the clock cannot resolve an event; reversed intervals or invented timestamps
fail. Independent causal order comes from event/operation identities, not a forced
positive timestamp difference.

Outcomes partition attempts into SUCCESS, NOT_SUBMITTED, INDETERMINATE, PENDING,
CANCELLED, NOT_APPLICABLE or VALIDATION_FAILURE as applicable. Timed-out is an
additional reason/observation, not a double-counted exclusive outcome. Separate
write durable successes, read successes, admission observations and touched-document
counts. A read timeout is not a zero-effect mutation; a Future cancelled after a
chosen write is not rollback. No guessed admitted count from absence of an error.

The healthy rich workload needs an independent operation decoder/state model. Decode
actual durable entries, accepted ballots, chosen quorums and publication cuts rather
than interpreting the old configured-leader anchor list as automatic truth. GET/query
answers are checked against the exact read capture and its fresh NO_OP/barrier; do
not bracket `currentSequence()` and guess the cut or silently resample the read.
V4.4/V5.0 control answers use their own documented semantics and isolated histories.
Comparisons use application state/sequence, not equality of log indices across modes.

The small failover history additionally runs the unchanged bounded checker over the
complete two-field history. A rich-workload PASS cannot be called exhaustive
linearizability. Extend physical/model validators with fixtures before allowing any
abbreviated performance trace; essential force, chosen prefix, read-cut, process and
archive facts remain independently reconstructible in every window.

Required negative families, including mutations with recomputed outer checksums:

- Wrong candidate/control artifact, wrong authority mode, mixed source/toolchain or
  serial stand-ins for concurrent voter processes.
- Changed seed/corpus/operation/window order, missing call or hidden failed outcome;
  malformed timing, cross-clock subtraction, wrong percentile/count arithmetic.
- Missing durable vote/proof, duplicate quorum voter, lost acknowledged value,
  fabricated NOT_SUBMITTED effect, changed uncertain/cancelled outcome or split bulk.
- Missing/reused read barrier, wrong capture cut/result ordering, NO_OP incorrectly
  advancing application sequence, or a control read relabelled as an automatic read.
- Forged process generation/kill/archive/rejoin, stale/copy-admitted authority,
  leaked reservations, missing required samples, exceeded slot/byte/window ceiling.
- Unsafe archive path, duplicated/missing part, expanded-size overflow and incomplete
  retention disguised by a PASS summary.

## 6A exit and later calibration

Materialize the plan/schema under V5.1, implement both local automatic groups and
both published controls, exercise the independent negatives and integrate a bounded
`verify-v51-phase6-performance.sh` gate with failure uploads. That filename is a
planned deliverable, not an existing command. Report exact JDK/source/artifact hashes,
all failed schedules and observed duration/resource peaks; keep test assets out of
production JARs. Preserve existing V5.0 plans and public regression gates.

After local qualification, 6B separately freezes full cloud corpus/rates, fixed-rate
scheduler behavior, concurrent/read-heavy windows, fault budgets, collection parts,
current build/image inputs and acceptance criteria. The 900-second **local gate** is
not a 900-second cloud failure-drill ceiling. Never inherit the V5.0 window arithmetic
or its published read semantics by renaming the preset.
