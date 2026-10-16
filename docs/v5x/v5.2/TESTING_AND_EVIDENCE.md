# V5.2 testing and independent evidence

**Status:** accepted evidence design, revision 0.1. No V5.2 model, runtime or
measurement has been executed by this document batch. Governing
[contract](PHASE_0_CONTRACT.md), [API](API_FORMAT_AND_COMPATIBILITY.md) and
[lifecycle](READ_AUTHORITY_AND_LIFECYCLE.md) supply the expected behavior.

Accepted in PR #335; see the [acceptance record](PHASE_0_CHECKLIST.md) and
[current Phase 1 implementation](PHASE_1_FOUNDATION.md). Statements about unexecuted
work below describe the original Phase 0 delivery; runtime qualification remains pending.

## Evidence families

These nine families map to the concrete schedules below. A family is not one test
count or one CI job. Unit/model/public/physical evidence is recorded separately.

| ID | Required evidence | Schedules |
| --- | --- | --- |
| E01 | Old API binary/default behavior and complete new public surface, with published V5.1 replication and V4.4 search controls | S01–S03, S22 |
| E02 | Exact proven and published prefix behind every result; accepted/unpublished state excluded | S04–S07 |
| E03 | Minimum progress, confirmed-write ordering, zero/positive wait and no silent fallback | S08–S12 |
| E04 | Token identity/format/lifetime through restart, compaction, backup and new group | S13–S16 |
| E05 | Promise/capture, partition and install races preserve policy-specific authority | S17–S21 |
| E06 | Bounded waiters, cancellation, close, callback completion and reentrancy | S23–S30 |
| E07 | Scoped views, absent explicit paging, and unchanged original cursor behavior | S22, S29 |
| E08 | Independent parsing and deliberate evidence corruption reject invalid success, without counting invalid originals | N01–N16 |
| E09 | Frozen offered-load/read-wait/write-recovery measurements with counts, failures and resource reporting | M01–M04 |

## Source, processes and oracle

Every receipt binds exact source/tree state, artifact/control SHA-256, schema/codec,
manifest/history, process incarnation, node, seed/configuration, run/attempt and
complete raw-file inventory. A merge source and a branch source are different.
Reuse source-bound shared builds and existing sharded aggregate validation; do not
substitute a rerun's successful step for a failed attempt in an allegedly continuous
history. All failed runs remain retained and classified.

Use external public consumers compiled against packaged JARs, not implementation
packages, for application calls. Test hooks may pause at capture, promise,
publication and release; they cannot manufacture a token/result or serve reads
through `inspectLocal`. Process cases run three independent JVMs with real durable
directories, supported bootstrap/start and actual halt/controller SIGKILL where
specified. Preserve pre-reopen files and observed process exit causes.

The independent checker decodes physical genesis/manifest, entries, ACCEPT/proofs,
forces, ACKs and publication order through existing V5.1 rules; its V5.2 extension
does not call the production token parser or capture decision. Replay the application
prefix against the V4.4 search truth, including imported base, NO_OP separation,
atomic bulks and index lifecycle. The logical model supplies policy outcomes; it
cannot replace physical checks. The token's own checksum cannot prove publication.

For every successful read retain invocation, options/input token bytes, admission,
wait events, capture, callback invocation/release and response, with decoded actual
policy/index/sequence/result and node/process identity. Bind capture to the exact
application generation and the decoded proven prefix. Strong additionally requires
its own fresh barrier, valid epoch at capture and real-time ordering. Local reads
need the prefix but no fresh barrier. Same-clock monotonic intervals measure waits;
cross-host ordering uses message/response edges, never timestamp subtraction.

Record allocation/release events and current/high-water counts for permits,
waiters, timers, live views and application engines. Pin release must be observed,
not inferred from a completed/cancelled Future. Source/attempt/inventory checks run
before semantic replay; independently downloaded evidence must retain location
mapping rather than assume original absolute paths.

## Concrete correctness schedules

Use a fixed three-voter manifest, two distinct groups/histories, deterministic
integer document keys and values, and a published imported base in at least one
case. Define a known committed cut `k`, its next accepted entry `k+1` and a distinct
later committed publication. Inject delays using event barriers, not lucky sleeps.
Each table row is mandatory; enumerated variants within a row all run. This is 30
schedule definitions, not a claim that 30 runtime executions have passed.

| Case | Schedule and required result |
| --- | --- |
| S01 | Run published V1–V5.1 consumers against candidate artifacts; exercise all inherited automatic read/mutation/maintenance signatures. Old automatic follower get still rejects; configured semantics remain unchanged |
| S02 | Third-party implementation compiled before the new method loads unchanged and returns default UnsupportedOperationException on explicit read; stopped GSE handles reject before any codec/path/thread/network side effect |
| S03 | Exercise all seven view methods under all three policies, including absent document, ranking/highlight/explanation and multi-query one-cut callback. Returned policy/token/sequence match the decoded cut |
| S04 | Isolate a follower at k, commit a later write on the majority, then stale-read follower. Return exactly its older committed prefix; never claim latest |
| S05 | Deliver/force ACCEPT(k+1) without proof, then stale/minimum read. Old prefix only; minimum k+1 cannot succeed |
| S06 | Force valid proof(k+1), pause before publication, then stale/minimum reads. Neither may label old documents k+1; after publication a new minimum read succeeds |
| S07 | Imported genesis index zero with nonzero application sequence, then control-only NO_OP. Verify index/sequence distinction and no fabricated write |
| S08 | Confirm bulk write, then explicit strong token issuance, then lagging follower minimum read. Hold publication, observe wait, release and verify whole bulk history coverage |
| S09 | Bounds below/equal/above local publication with wait=0: success/success/PROGRESS_NOT_REACHED; none starts a new replication operation |
| S10 | Same bounds with positive wait: already satisfied returns without progress wait, future cut waits; absent progress yields DEADLINE_EXCEEDED with no callback |
| S11 | Token-producing read overlaps an unconfirmed write, and a later update/delete supersedes a confirmed write. Checker rejects invented confirmed-write coverage and accepts legitimate later state |
| S12 | Publication immediately before registration, immediately after registration, and exactly at deadline. No lost wakeup; capture at deadline fails; late wakeup never changes terminal result |
| S13 | Wrong group, wrong history and wrong manifest at the same numeric index each reject INCOMPATIBLE_HISTORY before a wait/pin; include same sequence/different log index |
| S14 | Retained-disk halt and SIGKILL/restart, then new leader, using a previously returned token. Same compatible lower bound succeeds once published; no epoch/node binding |
| S15 | Token below checkpoint/compaction floor, plus verified snapshot catch-up; read succeeds at a newer cut without old-log lookup. Token does not retain old files |
| S16 | Verified backup/new-group import preserves application sequence but changes identity. Old token rejects; fresh token succeeds. Disk loss cannot be repaired by presenting a token |
| S17 | Isolated old leader: fresh strong fails without quorum; explicit stale may read its valid old cut. Local minimum succeeds only if already covered |
| S18 | Higher promise before/after strong capture: reject before, allow overlap completion after valid capture. Never change to stale policy |
| S19 | Higher promise and CANDIDATE/RECOVERING transitions before local capture: apply exact state gate; after capture preserve the valid cut. No status-only permission |
| S20 | Pause snapshot reconstruction/install before publication, then issue local reads. Reject non-readable state; new call after verified publication uses new identity/cut pair atomically |
| S21 | Concurrent writes and index create/drop around multi-method callback, then queued replacement. Callback sees one generation; old engine is not closed until release |
| S22 | Compile-negative explicit page call; old leader first/next page behavior, NO_OP cursor continuity, changed materialization and wrong-node/process cursor rejection; nested old page call from new view rejects reentrancy |
| S23 | P=4 gives R=3. Register three behind waiters, reject the fourth explicit read; use remaining public slot and normal protocol progress to publish their target. All three complete and all counters return to baseline |
| S24 | P=1 gives R=0; explicit read rejects capacity while the old API remains admissible. P=65 and default P=10000 both cap explicit requests at 64; no boundary overflow |
| S25 | Cancel while queued, while waiting, immediately before capture, after capture and during completion callback. Exactly one release; no callback if cancellation wins before capture; no late success |
| S26 | Close while waiting and while callback is paused. Waiting calls fail CLOSED; active view remains valid until release; incomplete close retains authority ownership and a later close completes |
| S27 | Callback throws, result is null, callback blocks, and completion handler blocks. Preserve original error/null, bound active work and permits, and do not advertise a total-duration timeout guarantee |
| S28 | Oldest waiter unsatisfied, younger ready; publication/read queues continuously nonempty. Ready work and protocol application tasks follow bounded alternating dispatch; timers are not blocked by waiters |
| S29 | Store wrapper in result/closure and invoke after callback, or invoke from another thread during callback: VIEW_NOT_ACTIVE. Same-handle query/mutation/backup/checkpoint/start/close inside active context rejects; pure metadata/status works |
| S30 | Corrupt required authority before new capture; storage failure, unsupported token version, malformed bytes, max signed-long index and maximum wait. Fail with prescribed reason, no allocation proportional to index, no fallback |

Before Phase 4 acceptance, S14, S18, S20, S25 and S26 each have public separate-process
coverage in addition to deterministic tests. For capture/release crash cuts use both
in-process abrupt halt and controller SIGKILL. A lost response remains a lost response;
do not infer client success from an on-disk prefix. At least one complete multi-query
and catch-up path uses genuine search/codec callbacks, not an all-status workload.

## Independent model and negative qualification

The Phase 1 finite model explores three voters, two identity tuples, log positions
0–3, application sequences 0–2, epochs 1–3, at most three admitted reads and one
active view per node. Include promise, acceptance, proof, publication, callback,
cancel, close and abstract deadline transitions. Deduplicate states by the complete
authority/ownership state, not only role/index. Explore every enabled schedule to
depth 12 from declared initial states. Record explored states/transitions, terminal
outcomes and excluded bounds; hitting a tool resource cap is INCOMPLETE, not PASS.
No production protocol/token parser is imported into this model.

Check eight invariants: committed-prefix-only result; identity-before-index;
minimum respected; strong barrier/epoch ordering; one callback cut; terminal result
never resurrected; unique bounded ownership/release; no wait-owned publication
resource. Liveness tests use an explicit fair schedule and finite callback execution;
safety does not assume these eventually complete. Model reachability is not a
proof for unbounded histories or all JVM schedules.

| Negative | Deliberate mutation that must be rejected |
| --- | --- |
| N01 | Wrong group with equal index |
| N02 | Wrong history with equal sequence |
| N03 | Altered manifest digest with recomputed token checksum |
| N04 | Result token index ahead of actual captured publication |
| N05 | Accepted-only entry forged as readable authority |
| N06 | Proof present but publication missing/reordered |
| N07 | Returned documents/ranking/explanation from a different cut |
| N08 | Strong success with missing barrier or promise already changed at capture |
| N09 | AT_LEAST_INDEX timeout replaced with successful stale response |
| N10 | Callback success after pre-capture cancellation/deadline |
| N11 | Forged write-response-before-token-invocation ordering |
| N12 | Escaped view declared valid or released pin reused |
| N13 | Removed permit/timer/pin allocation or release masks resource excess |
| N14 | Borrowed source/build/attempt/process identity from a different run |
| N15 | Missing/altered inventory file or copied authority with no valid relocation mapping |
| N16 | Unsupported token version/reserved bits/trailing bytes accepted after checksum recomputation |

Validate the unchanged original before applying negatives. Every negative retains
mutation identity and exact rejection category; an unrelated parser failure is not
evidence that its intended semantic check works. Run negatives after packaging and
relocation too. Missing traces, exceeded decoder budgets and incomplete bundles fail
qualification rather than count as successful rejections. An independent byte fixture
set additionally covers null/length, UUID ordering, negative index and checksum damage.

## Measurement contract and later freeze

Phase 0 selects goals and initial numeric workload parameters below. Before any
measured run, Phase 6 must commit the full machine plan: exact corpus/query bytes,
seed, control/JAR identities, environment, resource limits, fault schedule, evidence
schema/decoder budgets and pass/fail rules. That freeze may refine these initial
parameters in a reviewed plan before execution; it must not tune acceptance to
already observed candidate results. No measurement is authorized by this document.

| Cell | Initial plan and required report |
| --- | --- |
| M01 | Healthy, 3 repetitions of each policy: 60 s warmup + 120 s measurement, 64 documents, deterministic get/filter/ranked/highlight/explain mix of 20% each, 10 offered reads/s and 1 mutation/s; each run uses a fresh declared fixture history |
| M02 | Minimum-progress lag: 30 public reads at each lower-bound relation (below/equal/above), with deterministic publication gates; positive waits 1000 and 5000 ms plus zero-wait variants. Report wait versus queue/callback time and all outcomes |
| M03 | Saturation: P=4 and P=65, submit R behind reads then one excess read and release progress; report accepted/rejected/in-flight counts, permit peaks, publication and write progress, retained bytes, and post-run cleanup |
| M04 | One leader SIGKILL/retained restart and one follower snapshot catch-up with carried tokens; separately report detection, activation, first write, first strong read and first successful minimum read |

M01 compares candidate default/explicit strong behavior with the published V5.1
strong control under the same offered workload. V4.4 supplies result truth, not a
fake replica consistency control. Stale/minimum numbers are labelled by policy and
target node; stale throughput cannot be described as equal-consistency speedup.
Freeze node targeting and interleaving in the machine plan, and keep the mutation
stream/history and all dependent reads together during a cell. Do not split a
continuous experiment, lease/source/history or recovery schedule into independent
fragments and call their sum one qualifying run.

Report offered/completed calls, rejections, cancelled/timed-out calls and all latency
samples (including queue/wait/callback components), plus allocation and write/recovery
impact. No speedup or latency SLA is a Phase 0 exit condition. Correctness, no silent
fallback, finite resource accounting and complete evidence are mandatory. A timing
failure remains recorded; rerun success does not establish its root cause.

Future cloud qualification reuses existing ownership, credential renewal, cleanup,
retention and retry infrastructure. Freeze a V5.2 suite with experiment, failure-drill
and three canonical repetitions, fresh exact-source/admission/control bindings and
one qualifying sequence. The V5.1 image-continuation exception does not carry over.
Paid runs remain manually authorized/triggered. Existing soft operational time/cost
policy is not changed here; API read deadlines are semantic outcomes and stay finite.

## CI and retention

Phase 1 adds a V5.2 foundation suite using the established registry/planner and
shared build contracts. Unknown non-doc V5.2 paths select full, never integration by
default. Preserve Required, all existing suites, exact-master/attempt cloud consumers,
artifact uniqueness and original failures. Reuse already implemented rich sharding,
Python/cloud partitioning and portable negative replay. Split only independent
histories and make the aggregate authoritative; an incomplete shard is not PASS.

Preserve existing nine-JAR/three-POM release qualification, six predecessor consumer
modules, exact-source evidence validation and 90-day release-evidence retention.
Add the V5.2 consumer in its own qualification phase; do not rewrite historic
fixtures or hashes. Small receipts remain local and raw evidence follows the existing
archive policy, with checksummed links to its retained location. CI evidence retention
must support review of failed attempts as well as the final accepted source.

## Persistent voter lifecycle qualification

The optional [Phase 6AE gate](PHASE_6_PERSISTENT_VOTERS.md) executes three independent
local voter services, loses one original update response and queries it over a new
stream without resubmission. Original/relocated physical/query and message-edge
checks remain mandatory. It does not replace the complete measured cohort or
qualify SSH routing across three hosts.

## Persistent SSH voter transport

The optional [Phase 6AF gate](PHASE_6_SSH_VOTERS.md) qualifies three pinned SSH
streams, a lost update response and observation-only reconnect against the same
original history. Both portable replays require route and sequence evidence.
Service launch and file delivery remain local; this does not admit cloud hosts.

## Phase 6AG SSH service lifecycle

[The local lifecycle gate](PHASE_6_VOTER_LIFECYCLE.md) connects remote service
configuration, one original launch, terminal observation and bounded evidence
download to the unchanged untimed history and original/relocated replay. Local
artifact/seed staging remains; this is not three-host or paid-cloud qualification.
Run `scripts/verify-v52-phase6-voter-lifecycle.sh --skip-build` with existing
current Java packages and local OpenSSH prerequisites.

## Phase 6AH receiver delivery

[The receiver-delivery gate](PHASE_6_RECEIVER_DELIVERY.md) uploads one immutable
JAR/helper/seed capsule to each receiver, observes one detached bootstrap, and
continues through the prior SSH voter lifecycle and portable physical replay.
Run `scripts/verify-v52-phase6-receiver-delivery.sh --skip-build`. This remains
loopback qualification with a shared Python checkout, not cloud acceptance.

## Phase 6AI remote partition and snapshot recovery

[The remote partition gate](PHASE_6_REMOTE_PARTITION.md) runs the complete frozen
M04 follower-snapshot/carried-token history over SSH-delivered receiver inputs and
persistent services. Original cut/heal receipts and three-receiver ACK barriers
join the existing portable physical/query/resource replay. Run
`scripts/verify-v52-phase6-remote-partition.sh --skip-build`. This is single-host
loopback fault qualification; independent hosts remain open. The second M04
crash/restart history is qualified separately below.

## Phase 6AK formal SSH histories

`scripts/verify-v52-phase6-remote-formal.sh --skip-build` executes the unchanged
M02 above/1000, both M03 capacities, candidate explicit-strong M01 r1 and published
V5.1 legacy-strong M01 r1 through delivered SSH services. Each history must pass
complete original/relocated replay, all frozen negatives, exact business counts
and owner cleanup. No window is shortened and no original call is retried.
The [stage record](PHASE_6_REMOTE_FORMAL.md) retains the initial M03 recovery failure,
the deterministic runtime correction and the new acceptance status. This remains
single-host qualification; the full three-host/cloud suite is still pending.

## Phase 6AL independent Python inputs

`python3 -m scripts.v52.remote_python_qualification target/v52-remote-python/new-run`
packages the actual guest dependency closure, installs it through a standalone
bounded receiver and validates real isolated imports without a Git checkout.
The [stage record](PHASE_6_REMOTE_PYTHON.md) describes the source/inventory/ownership
checks and thirteen regressions. This gate starts no workload or cloud resource;
the real SSH launcher still needs integration with the installed identity.

## Phase 6AJ remote retained restart

[The remote restart gate](PHASE_6_REMOTE_RESTART.md) executes the complete frozen
M04 leader SIGKILL/retained-reopen history through the SSH service owner. It binds
the original crash, pre-reopen bytes, two service generations and lost-reply
queries to the existing portable physical/query/resource replay. Run
`scripts/verify-v52-phase6-remote-restart.sh --skip-build`. This remains single-host
qualification with shared Python sources; it is not cloud member acceptance.

## Installed Python runtime over SSH

See [Phase 6AM](PHASE_6_REMOTE_PYTHON_RUNTIME.md) for the source-bound capsule,
isolated children, full smoke receipt and retained failures. Run
`scripts/verify-v52-phase6-remote-python.sh --skip-build` after the reactor artifacts
are available. This is local loopback qualification, not three-host acceptance.

## Complete histories over installed helpers

[Phase 6AN](PHASE_6_INSTALLED_HISTORIES.md) connects the same source-pinned capsule
to the existing formal and M04 controllers. Run
`scripts/verify-v52-phase6-installed-histories.sh --skip-build` for the four complete
representative histories. An explicitly selected subset retains its exact names;
it cannot stand in for the default matrix, all 33 histories or three-host cloud
acceptance. Failed matrices are never resumed by splicing successful fragments.
