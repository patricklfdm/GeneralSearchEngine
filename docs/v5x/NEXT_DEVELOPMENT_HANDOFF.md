# Next-development documentation handoff

Current milestone: [V5.1 publication](v5.1/RELEASE_CHECKLIST.md) is complete;
V5.2 Phases 1–5 are locally verified and the complete hosted M01–M04 cohort passed;
pre-cloud adapter integration and complete remote qualification are next.
Full protected acceptance remains pending.
Phase 6 closed through PR #320, master `5c88a2b908347fa3e411e2018876657a21fa0912`,
exact-master CI `38457745089` attempt 1 (46 successful jobs). Phase 7A merged through
PR #321 at `9c03356ab343fc5aafcefbbfcc0e33382d19eef0` with the operator's one-time
PR/master CI skip; that source has local validation, not hosted CI acceptance.
Phase 7B was accepted in PR #322 at `516fe1efb54ef0787f38209108f322f258f71696`,
exact-master CI `38482900297` attempt 1 (all 46 jobs). Signed tag `v5.1.0` and
Release `38488481320` published that commit. The independent post-publication
check passes twelve signatures/checksums, twelve canonical hashes and all six
fresh remote consumer modules (22 tests, V1 compile-only). Stable is **5.1.0**.
The Phase 7A skip did not carry forward to final-candidate or release validation.

<a id="next-batch-v52-phase-0"></a>

<a id="current-batch-v52-phase-1"></a>

## Current batch: V5.2 Phase 6 remote integration

The [hosted acceptance record](v5.2/PHASE_6_HOSTED_ACCEPTANCE.md) binds successful
run `38888573888`, attempt 1: 28 histories, 27,373 reads, 2,745 updates and 878
negative rejections. All 21 original artifacts are archived. The measurement
fixes and recovered pre-cloud stages now share the development worktree.
[Stable command slots and one owned real history](v5.2/PHASE_6_REMOTE_OWNED_HISTORY.md)
connect the existing receiver and command foundations. The integrated local gate
passed both five-mode entries, six receiver bootstraps, four command subprocess
cases and the one-submission real history; all 292 V5.2 Python tests passed.
[Whole-history receiver execution](v5.2/PHASE_6_REMOTE_HISTORIES.md) now connects
the unchanged M01–M04 controllers, per-receiver paths and owned recovery lifecycle.
Five complete representative histories passed original/relocated replay and all
158 negative rejections, preserving 1,845 original read and 196 update outcomes.
The existing five smoke modes and default detached entry also passed; all 305
V5.2 Python tests and 21 CI tests passed. These remain local receiver checks.
[Pinned SSH command transport](v5.2/PHASE_6_SSH_HISTORY.md) adds a fixed guest
entry, durable detached launch ownership and boot/user/directory identity checks.
Its real loopback SSH qualification passed nine control cases and one original
11-read/3-update history with 48 physical evidence negatives. All 322 V5.2 Python
tests and 21 CI suite tests passed. This is separate from three-host cloud acceptance.
[Persistent per-voter services](v5.2/PHASE_6_PERSISTENT_VOTERS.md) now separate
three local JVM owners from the controller and add bounded persistent streams,
original-result reattachment and process-local clock/message evidence. Three services
and three JVMs passed one 11-read/3-update smoke, 548 message edges and 48 original/
relocated physical/query negatives; 344 V5.2 Python tests and 21 CI tests passed.
This remains an untimed local lifecycle backend.
[Per-voter SSH streams](v5.2/PHASE_6_SSH_VOTERS.md) now connect the original
controller to each existing service with pinned persistent channels and exact
resume cursors. Its real loopback gate passed eleven reads, three updates and
48 original/relocated negatives with all service/JVM/SSH processes stopped.
That stage retained local process launch and collection.
[SSH service lifecycle and evidence export](v5.2/PHASE_6_VOTER_LIFECYCLE.md)
now adds fixed remote preparation/start/query/stop ownership and bounded stopped
archive download, with one consumed launch and original-result reattachment.
Artifact/seed staging and public bootstrap still remain local; independent-host
qualification and formal fault lifecycle remain open. Its final real SSH gate
passed eleven reads, three updates, 48 original/relocated physical/query negatives
and 14 lifecycle negatives in 61.792 seconds. All 385 V5.2 Python tests and 21
CI suite tests pass; source and evidence hashes remain bound to that local receipt.
[Receiver capsule delivery and bootstrap](v5.2/PHASE_6_RECEIVER_DELIVERY.md)
now connects bounded pinned SSH uploads and one detached public bootstrap per
receiver to that service lifecycle. Receiver inputs are transferred; the Python
checkout is still shared on one host. Its real gate passed in 109.172 seconds:
three one-submission bootstraps, eleven reads, three updates, 48 physical/query
negatives, 14 lifecycle negatives and 14 delivery negatives. All 406 V5.2 Python
tests and 21 CI suite tests pass; its receipt retains the actual source binding.
Cross-host transport/identity, complete owned members, protected full CI and fresh
cloud admission remain open. The milestones below
retain their original validation scope and source; earlier pending statements
describe those historical stages, not the current hosted cohort result.

[SSH partition and snapshot recovery](v5.2/PHASE_6_REMOTE_PARTITION.md) adds the
complete frozen M04 follower snapshot/carried-token history to the delivered
receiver/service backend. Original remote cut/heal claims, all-receiver ACK barriers
and separately recorded failure cleanup supplement the unchanged physical/query
replay. This remains single-host qualification; SIGKILL/retained restart and
independent hosts are not enabled by its exact-profile admission.
The final gate passed in 106.028 seconds with four original reads, four updates,
six original receiver transitions and 76 negative rejections. All 430 V5.2 Python,
31 affected V5.1 fault and 21 CI suite tests pass. Serial-control timing failure
and the historical six-frame completeness failure remain retained; parallel
preconnected control and explicit selected-quorum M04 coverage were qualified.

[SSH retained leader restart](v5.2/PHASE_6_REMOTE_RESTART.md) completes the second
M04 service profile. One guest-owned SIGKILL, forced pre-reopen authority copy and
exact dead-predecessor admission permit one explicit generation-2 reopen. Lost
terminal/launch replies query original receipts without repeating kill or launch.
The real gate passed in 104.727 seconds, with four original reads, four updates,
four stopped services/JVMs and 68 original/relocated negative rejections. All 442
initial V5.2 Python and 21 CI suite tests passed. A further partition regression
retained a snapshot failure after a 2.459-second heal barrier. Prepared persistent
control now removes repeated process/import/source setup from each transition;
the corrected complete history passed in 100.497 seconds with 0.418/0.423-second
cut/heal barriers and all 76 negatives. The final Python suite passes 448 tests.
The final shared SSH implementation also passed a fresh complete restart history
in 102.110 seconds, with all 68 negatives and all original owners stopped.
[Formal SSH histories](v5.2/PHASE_6_REMOTE_FORMAL.md) add exact M01–M03 admission,
parameter delivery and large stopped exports with the existing bundle bounds.
The first real gate passed M02 and exposed a stale snapshot transfer occupying
one M03 follower after an install rejection. A deterministic regression reproduces
that failure; failed exchanges now abort their own transfer while preserving the
original failure and accepted/proven authority. Rebuilt five-history qualification
is pending. Independent hosts/clocks, complete owned members and protected
CI/provider admission remain.

[Independent Python source packaging](v5.2/PHASE_6_REMOTE_PYTHON.md) supplies the
next deployment foundation: a static guest dependency closure, bounded standalone
installer, exact source/file hashes and isolated imports without a Git checkout.
Its actual source-bound gate passes with 159 files and 84 loaded modules;
all 476 V5.2 Python tests and 21 CI suite tests pass.
[Installed Python runtime over SSH](v5.2/PHASE_6_REMOTE_PYTHON_RUNTIME.md) now
replaces that shared path for the complete smoke history. Three independently
installed capsules, explicit source pins and isolated children pass original and
relocated replay, 48 ordinary negatives, 18 Python-source negatives and all
28 delivery/lifecycle negatives. The whole gate passes in 159.016 seconds;
all 498 V5.2 Python tests pass. Its separate source snapshot preserves the still
running formal gate's worktree and retains its own immutable source identity.
[Complete histories over installed helpers](v5.2/PHASE_6_INSTALLED_HISTORIES.md)
now selects all 33 exact frozen histories through their original controllers,
including second-generation restart and prepared fault channels. Its representative
four-history local gate passes in 577.630 seconds: 24 original reads, 15 updates,
338 negative rejections and all 13 service/JVM owners stopped. All 508 V5.2 Python
tests pass on the final development worktree. The actual run retains its separate
source snapshot and is not relabelled as protected acceptance. Independent-host
identity, clock/routing qualification, owned members and cloud admission remain open.

[Bound host and process domains](v5.2/PHASE_6_HOST_PROCESS_DOMAINS.md) now distinguish
equal cross-host PIDs and retained PID reuse through explicit resource/boot/start
identities. Independent clock offsets preserve message/local-order checks, and
installed Python paths are scoped to the expected host. These component checks
and retained physical replay do not enable private-host execution; provider/lease
ownership, live routing, whole owned members and cloud admission remain next.

The previously running five-history formal SSH gate also completed: all five
original/relocated replays pass in 3,950.755 seconds, with 3,704 reads, 372 updates,
158 negative rejections and all 15 service/JVM pairs stopped. Its original
`5d183ca` source plus recorded checkout hash remain bound to that evidence.

Phase 0 PR #335 is accepted at master `9e1aeb282135802ff8886c4585351ce42a7908b0`.
Exact-master CI `38710485375` attempt 1 passed docs scope (2 successful meta jobs,
36 skipped suite placeholders). See the [acceptance checklist](v5.2/PHASE_0_CHECKLIST.md).

The [Phase 1 foundation](v5.2/PHASE_1_FOUNDATION.md) implements six public types,
one disabled default read method, independent token/model/evidence checks and an
external V5.2 consumer, at `5.2.0-SNAPSHOT`. Full protected PR/master qualification
is pending. The [schedule map](v5.2/PHASE_1_SCHEDULE_MAP.md) preserves S01–S30 for
later runtime work; synthetic evidence does not complete those schedules.

The operator authorized [locally verified sequential commits](v5.2/LOCAL_DEVELOPMENT_SEQUENCE.md)
without intermediate pushes. The [Phase 2 capture/waiter kernel](v5.2/PHASE_2_CAPTURE_KERNEL.md)
passes deterministic ownership and real runtime tests. [Phase 3 public reads](v5.2/PHASE_3_PUBLIC_READS.md)
implements all three policies and verified follower publication. The external
three-process gate now passes with actual published V4.4 query replay, portable
physical evidence and eleven rejection checks. Phase 4 completes the broader
fault/lifecycle/resource schedules; the healthy gate does not close that matrix.
Local 4B now passes six carried-token/partition/publication fault cases. Local 4C1
passes eleven original-Future cancellation and cooperative-close process cases,
including halt/SIGKILL and independent ownership accounting. Local 4C2 passes
seven higher-promise/snapshot-install process cases. Phase 4D0 wires all existing
V5.2 gates into four required shared-build lanes. Phase 4D1 adds three-policy
physical application/query lifecycle qualification, including update/delete and
index create/drop. Phase 4D2 qualifies public token identity/format rejections and
maximum-index/wait ownership. Phase 4D3 links an actual public backup to a new
group with preserved application sequence and rejected old tokens. Phase 4D4
qualifies old tokens after actual two-source retirement and follower snapshot
installation. Phase 4D5 qualifies three public capacity configurations and reserved
writer progress with independently replayed ownership counters. Phase 4D6 confirms
P=1 rejects all explicit policies while legacy reads/writes retain their slot.
Phase 4D7 adds public cursor lifecycle tests and reruns seven consumer modules,
published default/API checks and negative compilation. Phase 4D8 adds real public
corrupt-startup and fatal-I/O before/after-capture tests. Phase 4D9 adds nine
public accepted-only, isolated-leader, higher-promise and candidate/snapshot
state-transition tests. Phase 4D10 completes 28 targeted physical negatives across
N01–N16, including portable replay and an independently checked confirmation
edge. Phase 4D11 completes the [schedule mapping](v5.2/PHASE_4_SCHEDULE_RESULTS.md),
the confirmed-bulk/lagging-follower public read case, sustained worker fairness
and final local reactor/consumer/API validation. The complete reactor passes
997 tests (four existing skips); seven consumers pass 25 tests. Individual process
receipts retain their original source/build bindings; they are not relabelled as
one run on the final source. Phase 5 combined hardening and Phase 6 preparation
follow under the local commit authorization.
[Phase 5 hardening](v5.2/PHASE_5_HARDENING.md) now passes both combined
partition/restart crash modes and sixteen continuous bounded-pressure rounds,
with 122 public reads and complete portable physical/query validation. Freeze
M01–M04 before measurements; no paid cloud execution is authorized here.
The [Phase 6A program/query foundation](v5.2/PHASE_6_MEASUREMENT_PROGRAM.md) fixes
the offered requests and checks all 138 query descriptors against published V4.4
at five actual application states. This is untimed; complete execution freeze,
replicated measurements and portable measurement evidence remain open.
The [Phase 6B trace foundation](v5.2/PHASE_6_MEASUREMENT_TRACE.md) now verifies
lossless bounded encoding, real SIGKILL append recovery, published V5.1 compatibility
and relocation. Existing observer encoding is unchanged by default. The measurement
execution harness and physical/query replay are still required before timed runs.
The [Phase 6C advancing query replay](v5.2/PHASE_6_MEASUREMENT_REPLAY.md) checks
690 queries against each actual core using one ordered update replay, with
independent application-state hashes. All 71 V5.2 Python tests pass; physical
measurement-cut binding and the actual replicated offered-load harness are next.
The [Phase 6D public measurement consumers](v5.2/PHASE_6_MEASUREMENT_CONSUMERS.md)
now pass five short three-JVM histories (55 reads/15 updates), actual published
query truth and portable physical replay. The final checker rejects 43 mutations
per location. These are untimed integration histories; full offered-load windows,
allocation sampling, M02–M04 execution and the complete measurement freeze remain
pending. No paid execution or push has occurred.
Stop before cloud entry for combined push/PR/master acceptance. Push/PR/tag
operations remain operator-owned; paid runs remain manual.
The V5.1 published baseline and historical CI failures stay retained.

The [Phase 6E offered driver and sampler](v5.2/PHASE_6_MEASUREMENT_LOAD.md)
now retain original due times, every outcome and process-wide resource observations.
Five short integration histories pass physical/query replay before and after
relocation. Full-size evidence packaging, M02–M04 schedules and the complete
execution freeze remain open; no formal measured window has run.

The [Phase 6F package/replay qualification](v5.2/PHASE_6_MEASUREMENT_PACKAGING.md)
adds a separate bounded large-history archive and original-path authority replay.
The short driver now confirms its actual read/write targets have published the
prepared updates; retained failures explain both that correction and the old V5.1
follower boundary. Full measured validation and M02–M04 execution remain pending.

The [Phase 6G projector and streaming negatives](v5.2/PHASE_6_MEASUREMENT_PROJECTION.md)
now preserve rejected/uncertain update semantics and distinguish offered ordinals
from chosen application sequences. The old strict query format remains intact;
new selected-update replay passes actual V4.4/candidate queries. Ten retained
original/relocated inputs preserve all 124 existing rejection results without
materializing whole traces. Full measured-history admission remains open.

The [Phase 6H consumer ledger](v5.2/PHASE_6_MEASUREMENT_HISTORY.md) binds every
received/invoked/completed call and reconstructs explicit-read permit transitions.
Transient rejection outcomes remain failures, distinct from successful query cuts;
fatal or incomplete histories reject. The short smoke still requires all calls to
succeed. Formal workload coverage, fault schedules and execution freeze remain open.

The [Phase 6I durable publication profile](v5.2/PHASE_6_MEASUREMENT_PUBLICATION.md)
now retains forced generation bytes and reconstructs received snapshot images before
qualifying follower publication. Fresh five-mode and large-package replay passes;
earlier control timing and checker-compatibility failures remain retained. The
complete measured-window path and M02–M04 schedules are next; no formal M01 ran.

The [Phase 6J window ledger](v5.2/PHASE_6_MEASUREMENT_WINDOWS.md) now validates
the full 1,980-call offered program and retains rejected/late calls in statistics.
Successful cut validation is shared with the short gate; all ten old results and
190 negatives remain identical. Resource-window binding, full execution and fault
schedules still precede the complete machine freeze and formal measurements.

The [Phase 6K asynchronous boundaries](v5.2/PHASE_6_MEASUREMENT_RESOURCE_WINDOWS.md)
now bind resource observations to original controller marker tasks and actual
process-local warmup/measured boundaries. Five short histories retain all 45 marker
calls and 30 resource-window reports, with portable physical/query validation and
200 negatives. Full M01 execution, M02–M04 schedules and the machine freeze remain
open; the short three-second gate is not a formal measured history.

The [Phase 6L M01 controller](v5.2/PHASE_6_M01_CONTROLLER.md) now connects the
full 1,980-call clock, initial-target preparation, asynchronous markers, common
drain and unconditional process cleanup. Virtual-clock coverage includes all 15
members and partial failures. Controller completion remains OBSERVED, with full
physical M01 admission and M02–M04 schedules required before the execution freeze.

The [Phase 6M member validator](v5.2/PHASE_6_M01_EVIDENCE.md) connects complete
offered windows to physical/query/ownership/resource checks and selected-update
replay. Its streaming aggregate admission runs before physical reconstruction.
Full-size member and portable negative qualification still await the machine
freeze; unchanged short histories only validate shared components.

The [Phase 6N portable set wrapper](v5.2/PHASE_6_M01_SET.md) now requires all 15
fresh M01 histories with one source/build/JVM/run/attempt, exact compiled controls,
and independent original/relocated member replay. It preserves all failures and
never substitutes a PASS receipt for raw evidence. Fixture validation is complete;
actual full-size execution still waits for M02–M04 and the machine freeze.

The [Phase 6O wait/capacity configuration](v5.2/PHASE_6_WAIT_CAPACITY_PARAMETERS.md)
separates M02's zero/1s/5s waits and M03's P=4/P=65 fixture from unchanged M01
defaults. Java startup and replay bind the declared values; zero-wait progress
rejection requires its explicit profile. Relation/saturation schedules, M04 and
the machine freeze are still required before any formal measurement.

The [Phase 6P minimum controllers](v5.2/PHASE_6_MINIMUM_CONTROLLERS.md) now execute
all nine M02 and both M03 schedules using original futures, cumulative admission
gates and reserved writer capacity. Fresh development histories pass the shared
physical/lifecycle checks. Scenario-specific admission, M04 and the complete
machine freeze still precede formal measurements; these observations are not a
formal M02/M03 acceptance set.

The [Phase 6Q independent minimum validator](v5.2/PHASE_6_MINIMUM_EVIDENCE.md)
connects complete M02/M03 histories to physical/query/lifetime/resource replay and
reconstructs each live gate from raw events. Portable replay preserves original
bindings and exact negative results. M04, complete machine freeze and fresh formal
measurement histories remain required before cloud preparation.

## Accepted V5.1 cloud evidence

Accepted [five-member baseline](v5.1/PHASE_6_NATIVE_SET_ACCEPTANCE.md):
All five paid members are complete: canonical-1 `38280933954`, canonical-2
`38300809738`, canonical-3 `38346492463`, experiment `38363263163` and failure-drill
`38372566659`. The final drill passed twelve cells, 103 calls and 129 evidence
negatives; all thirteen resources were cleaned and the lease released.

The first two members retain source `f46f9a4ea624df2b42902efd0b633c30933ae2f2` /
sequence `eb7859da90c94c468215f2867638b0bf`. The remaining three retain source
`7100b61e752647c52246cc86f2887fefa00821ea` / sequence
`c4d557b802ec49cd843081326608becb`. Only the explicitly authorized
[image continuation](v5.1/PHASE_6_IMAGE_CONTINUATION.md) permits this mapping.
Both measured sources passed all 46 jobs in their recorded exact CI attempts.

The completion audit is PASS with five members, USD 250 cumulative reservations,
no PENDING attempt and no active lease. Historical failures and charges remain.
PR #320 accepted full raw archive replay and baseline registration. No additional
paid experiment is needed for consumer/documentation/release-tooling preparation.
Subsequent batches retain normal source/sequence rules; cloud dispatch remains manual.

## Historical implementation milestones

PR #311's native experiment `37970604996` remains accepted on its earlier source.
The owner-authorized accounting restart of 2026-10-09 preserved the original
USD 110 ledger and verified USD 0 / 200 before the new attempt. This correction
adds no reset or refund. Historical failures, failed-attempt accounting and the
complete five-member acceptance requirement remain in force, with only the
explicit image-continuation exception above.

[Complete owned canonical qualification](v5.1/PHASE_6_OWNED_CANONICAL_AGGREGATE.md)
is accepted through PR #310 / master `07e0745de7498c9f45ad9fc9209d7afbc550e4c8`,
CI `37887342685` attempt 2. All three repetitions passed fifteen cells and 1080
rich calls with independent replay and modeled cleanup. Original failed attempts
remain retained; no timing root cause is claimed. The twelve-cell drill was
accepted through PR #308 / CI `37837221623`. The accepted PR #311 integration
connects all five native members through request, guest session, controller,
independent replay and cleanup. Paid full-preset acceptance remains pending;
diagnostic-only stays the default.

CI `37869232192` completed all fifteen cells and the independent replay in each
repetition, but failed the 600-second validation/retention ceiling and then used
the expired deadline for service shutdown. The correction collects original
evidence once, closes services before one bounded replay, and preserves cleanup
time after validation expiry. The original failed runs do not constitute complete
acceptance; PR #310 subsequently completed the corrected-source qualification.

Follow-up CI `37876817676` passed 42 jobs but failed all complete repetitions:
one exhausted validation time and two exceeded a fault observer's mistaken
32-MiB whole-trace bound. The operator authorized additional headroom. The
complete offline coordinator now has a 2400-second validation/retention ceiling
inside the unchanged 5400-second lease, with 120 seconds reserved for retention
and the existing 600-second cleanup reserve. Stopped fault traces are losslessly
segmented under the existing 32-MiB member / 128-MiB per-node limits. The
[canonical record](v5.1/PHASE_6_OWNED_CANONICAL_AGGREGATE.md#follow-up-hosted-headroom-and-fault-trace-segmentation)
documents the original failures and subsequent protected acceptance. The current native integration still requires corrected-source protected acceptance.

**Status:** local documentation integration and review record, 2026-09-19.
The V5.1-V5.4 refinements and V6 preview remain PROPOSED. Integration does not
constitute protected acceptance of a protocol or authorization to implement it.

**Reviewed source:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

**Latest native milestone:** PR #304, source
`500a41f30a5149703b81c4c2d01da75cd3baf1ed`, protected CI `37718123364`, native run
`37723402614`: first complete four-cell experiment accepted, including independent
archive replay, retention and cleanup. Start with the
[acceptance record](v5.1/PHASE_6_NATIVE_EXPERIMENT_ACCEPTANCE.md) and
[remaining preset implementation plan](v5.1/PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).
Full Phase 6 and final same-source five-member qualification remain open.

The owned network and complete failure-drill lanes passed corrected-source master
CI `37837221623`. The accepted complete canonical gate preserves three 260-call
healthy modes, 120 read-heavy calls and 180 sustained calls, and independently
replays all twelve faults. The current integration binds full-preset budgets, remaining-sequence prices and ledger
constraints, with matching Action member/order choices and native guest/validator paths. Offline
qualification cannot close a paid preset or the formal five-member cloud set.

**Subsequent design handoff:** after planning PR #183, the user started V5.1 Phase 0
on source `09d2bf247f004eb134eb81c59ee88005affafe92`. The
[contract candidate](v5.1/PHASE_0_CONTRACT.md) now supplies all six design outputs;
its [checklist](v5.1/PHASE_0_CHECKLIST.md) records current review/acceptance state.
The integration record below retains the original boundary and validation history.

**Current implementation handoff:** full V5.1 Phase 4 is accepted through PR #208 at
`b0d586f32b01f59aadfa940d7f778a8a2b5ea078` (exact-master CI `35802660895`, all 13 jobs passed).
The [final Phase 4 review](v5.1/PHASE_4_FINAL_COVERAGE.md) preserves the E01–E12
public/internal evidence boundaries. [Phase 5A combined recovery](v5.1/PHASE_5_COMBINED_RECOVERY.md)
is accepted at master `04d12316bd6971ac477cfcb08c5073b2252ecf2a` (exact-master CI
`35818964327`, all 19 jobs passed). [Phase 5B combined lifecycle](v5.1/PHASE_5_COMBINED_LIFECYCLE.md)
is accepted through PR #213 at `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`, exact-master
CI `35826641489` (all 19 jobs and 23 V5.1 verification steps passed).
[Full Phase 5](v5.1/PHASE_5_ACCEPTANCE.md) is accepted through PR #214 at
`15c8c68011e37370dfcd31ee855f91247c3771d8`, docs-only master CI `35830149418`.
Its review retains the 23 public/eight internal cases on the unchanged fully tested runtime.
The [Phase 6 entry](v5.1/PHASE_6_ENTRY_PLAN.md) and
[local measurement contract](v5.1/PHASE_6_LOCAL_MEASUREMENT_PLAN.md) are accepted through
PR #215, master `243434f6e1dc94422b57997b33eabb3cc1e8f64d`, docs CI `35831892351`.
The current [rich model foundation](v5.1/PHASE_6_MODEL_FOUNDATION.md) implements the
closed local plan, independent rich prefix decoder and actual published V4.4 parity.
It is accepted through PR #216, master `bcac615aeef93dadcab6636162a86ce2156e5515`, exact-master full CI `35841378072`.
The [local runtime candidate](v5.1/PHASE_6_LOCAL_PERFORMANCE.md) adds the three-mode
measurement gate and bounded automatic SIGKILL/rejoin history. PR #217 merged at
`e3efda820beef9efcd6f6f06e8af71006c3b85ce`, exact-master full CI `35889987294`
(all nineteen jobs passed). The separately retained local resource-recovery failure
has a [scheduling correction candidate](v5.1/PHASE_4_RESOURCE_LIMITS.md#recovery-scheduling-after-the-phase-6a-resource-rerun).
PR #218 merged that correction at `84990b3fa6d5007b90427c95f376473c8db48bd9`.
Its PR CI `35894824934` passed; master CI `35896844608` failed the earlier public
bounds gate on a [single-permit driver race](v5.1/PHASE_4_PUBLIC_BOUNDS.md#post-pr-218-correction-observe-released-admission),
so the resource step was skipped. PR #219 then passed exact-master CI `35920225478`
at `54e203eeca6c087b7ba03954d546c7682e8338f2`, all nineteen jobs and 24 V5.1 steps.
The [6A review](v5.1/PHASE_6_LOCAL_ACCEPTANCE.md) independently replays that raw
performance evidence and corrects portable evidence inspection without changing
live authority admission. The [6B cloud contract](v5.1/PHASE_6_CLOUD_WORKLOAD_CONTRACT.md)
is a closed candidate with local calibration, synthetic full-slot encoding and
fifteen canonical cells. PR #220 merged at `717bed8f578019c71ffe3d739deaf067ec0fa8d2`;
master CI `35927462738` failed an inherited
[Phase 5A recovery-write assumption](v5.1/PHASE_5_COMBINED_RECOVERY.md#post-pr-220-correction-a-recovered-read-does-not-lease-leadership).
PR #221 merged that correction at `af68d8473f9998628e49189a2d8be658b8bfe116`.
Master CI `35932225694` exposed a separate
[proof-sample boundary and inherited retry fixture](v5.1/PHASE_5_COMBINED_RECOVERY.md#post-pr-221-correction-confirm-proof-before-recording-a-drained-round).
PR #222 accepted both corrections at `33aa89bf8a6b4b0587fa6a127e481d73671a60ec`;
exact-master CI `35937300754` passed all nineteen jobs and 24 V5.1 verification steps.
6A/6B are accepted under the [checklist](v5.1/PHASE_6_CHECKLIST.md).
The [6C1 remote control foundation](v5.1/PHASE_6_REMOTE_FOUNDATION.md) now implements
persistent command claims, fixed arrivals, time accounting and binary collection,
with control-only local qualification. PR #223 accepted it at
`833da4947266b4edfbee2a0e6fe10055ed3be00c`, exact-master CI `35942555519`
(nineteen jobs and 25 V5.1 verification steps passed). PR #224 accepted
[6C2A rich workloads](v5.1/PHASE_6_REMOTE_RICH.md), exact-master CI `35961961431`
(twenty jobs, 26 V5.1 gates). PR #225 accepted the
[6C2B fault workloads](v5.1/PHASE_6_REMOTE_FAULTS.md) and the two approved document-size
exceptions: master `22328ed4dc358e0adc7fde1399528295ebf8d2a3`, exact-master CI
`35989431966` (all 21 jobs). PR #227 closed [rich CI sharding](../CI_V51_RICH_SHARDS.md)
on master `2db90846606547325c2f35a466813c622cc1ffac`, CI `36064320654` (all 26 jobs).
The [512-slot component gate](v5.1/PHASE_6_FULL_SIZE.md) was accepted through
PR #228 at `3c3d9d19c8aa1d24aa88f971c983235bd186033d`, exact-master CI `36072038218`.
The [public runtime integration](v5.1/PHASE_6_FULL_SIZE_RUNTIME.md) was accepted
through PR #229 at `57622552e02addfae991642786e1a87a0633fb43`, exact-master CI
`36094121631` (all 27 jobs), closing full-size 6C2 under unchanged deadlines.
[6C3A cloud control](v5.1/PHASE_6_CLOUD_CONTROL.md) is accepted through PR #230,
master `2db3ebb645907eaa8b02fa849302c35accb03ff4`, exact-master CI `36105310891`.
Its first PR attempt's Maven transport and burst timing failures remain recorded;
the successful rerun does not establish a timing root cause. The [6C3B guest/provider gate](v5.1/PHASE_6_CLOUD_PROVIDER.md) is accepted through
PR #231, master `5b101a6e73a83ef9091ea369997f4d01e6ca4c26`, CI `36113872308`.
The [6C3C1 guest slice](v5.1/PHASE_6_GUEST_SERVICE.md) is accepted through PR #232,
master `2183dafa618238f0b824fc0a3b3d42624ce24782`, exact-master CI `36124423253`
(all 27 jobs). Its initial rich timing failure remains recorded; the rerun does not
establish a timing cause. The [6C3C2 bootstrap slice](v5.1/PHASE_6_GUEST_BOOTSTRAP.md)
is accepted through PR #233, master `d27da43086406384ab41cab6704541015aa0a1bf`,
CI `36149275698` (27 jobs). The [6C3C3 owned startup slice](v5.1/PHASE_6_GUEST_STARTUP.md)
is accepted through PR #234, master `79344fca6b447a3e77205be36d3d16e597d4bc23`,
exact-master CI `36185893530`, attempt 2 (all 27 jobs). Its first concurrent
measurement's 63.021587 ms burst spread remains a retained failure; no timing
cause is established by the successful rerun.
The [6C3C4 helper delivery slice](v5.1/PHASE_6_GUEST_DELIVERY.md) is accepted through
PR #235, master `d40d7d8be1320a3e989ab551536715f4e47795be`, exact-master CI
`36206334728` attempt 1 (all 27 jobs). It adds a closed, digest-authenticated helper
payload, consumed installation claims and real loopback OpenSSH receipt queries.
The [6C3C5 deadline slice](v5.1/PHASE_6_GUEST_DEADLINES.md) is accepted through
PR #236, master `3cf47ac19a71c24fdc1e10689c646c8bbceb0a53`, exact-master CI
`36212673545` attempt 2 (all 27 jobs). Its initial HTTP 403 and healthy warmup
lane-occupancy failure remain recorded; the rerun does not establish a timing cause.
The [6C3C6 root-admission slice](v5.1/PHASE_6_ROOT_ADMISSION.md) is accepted through
PR #237, master `de3264cb41e594e10e641748d1cdd75fe7c3a8ad`, exact-master CI
`36281785824` attempt 1 (all 27 jobs). The original upload failure is retained.
[6C3C7 package/services](v5.1/PHASE_6_PACKAGE_DELIVERY.md) is accepted through
PR #238, master `ef7562bc60a0a15ab4202367c5e286fe6250cbdb`, exact-master CI
`36302498537` attempt 2 (all 27 jobs). The initial rich healthy failure remains
recorded; its successful rerun does not establish a timing cause. The
[6C3C8 owned services](v5.1/PHASE_6_OWNED_SERVICES.md) is accepted through
PR #239, master `1feeb2f1941367ef29cbb1cdabd3cead6715ebb8`, exact-master CI
`36370271323` attempt 2 (all 27 jobs). Attempt 1's automatic-healthy lane-busy
failure remains recorded; the rerun does not establish its cause. The
[6C3C9 guest evidence](v5.1/PHASE_6_GUEST_EVIDENCE.md) is accepted through PR #240,
master `0ef49cb8f5f6c793b9fe03db4b4069dd04e059ac`, exact-master CI `36378226619`
attempt 1 (all 27 jobs). It independently validates the existing guest warmups;
complete owned workload execution remains open.
The [6C3C10 owned bootstrap](v5.1/PHASE_6_OWNED_BOOTSTRAP.md) is accepted
through PR #241, master `87e0cdda3f38dbadce149e54eb1cc45f0f634e28`, exact-master CI
`36388477710` attempt 1 (all 27 jobs). The original non-private mount-backing
failure remains recorded. The [6C3C11 source transfer](v5.1/PHASE_6_SOURCE_TRANSFER.md) is accepted
through PR #242, master `41bee83b675bdd903d335fc9f1e0cc62cb350429`, exact-master CI
`36395914043` attempt 1 (all 27 jobs). The
[6C3C12 source producer](v5.1/PHASE_6_SOURCE_PRODUCER.md) is accepted through PR #243, master
`eb56fa6d2565770bd8aac7f76e484834f563a0f3`, exact-master CI `36407418156`
attempt 1 (all 27 jobs). Its original hardening and warmup timing failures remain
recorded; the successful run does not establish a timing cause. The
[6C3C13 owned healthy tape](v5.1/PHASE_6_OWNED_WORKLOAD.md) is accepted through
PR #244, master `71ca5d9e52139815a5bd4dfddf330c4d0d9fe800`, exact-master CI
`36462747697` attempt 1 (all 27 jobs). The original large-part collection failure
and diagnostic replay remain recorded. The [6C3C14 physical evidence](v5.1/PHASE_6_OWNED_PHYSICAL_EVIDENCE.md)
is accepted through PR #245, master `d07fe8a5ca27e28ebf1b20c157337ed0f078ea5e`,
exact-master CI `36486236193` attempt 1 (all 27 jobs). It qualifies each stopped
voter's own authority and joint force/publication/read replay for the 90-call tape.
The [6C3C15 backup/restore](v5.1/PHASE_6_OWNED_BACKUP.md) is accepted through
PR #246, master `2846bbc2758f2336e0ed73dbc45001dfe83d8f6a`, exact-master CI
`36498232963` attempt 1 (all 27 jobs), including the owned Linux backup/restore gate.
The [6C3C16 configured healthy control](v5.1/PHASE_6_OWNED_CONFIGURED.md) is accepted
through PR #247, master `dfae45670330ffe2a3974982bcc020c534861309`, exact-master CI
`36505526404` attempt 1 (all 27 jobs), including the configured Linux workload gate.
The [6C3C17 published V4.4 healthy control](v5.1/PHASE_6_OWNED_V44.md) is accepted
through PR #248, master `b6c055df306e9e8dbb155924fa4a834fe751e786`, exact-master CI
`36514227052` attempt 2 (all 27 jobs). Attempt 1's V5.0 prerequisite-build failure
remains recorded; retry success does not establish its cause.
The [6C3C18 configured physical/backup evidence](v5.1/PHASE_6_OWNED_CONFIGURED_EVIDENCE.md)
was accepted through PR #249, master `7273f00ce8f291797c2d74cd9d830b4f993aaceb`,
exact-master CI `36523283002` attempt 2 (all 27 jobs). Attempt 1's automatic-healthy
rich shard failure remains recorded; retry success does not establish its cause.
The [6C3C19 three-mode owned healthy integration](v5.1/PHASE_6_OWNED_THREE_MODE.md)
was accepted through PR #250, master `2f8da1d96a1080a4c8f29d89d71b984e10722b58`,
exact-master CI `36534342886` attempt 2 (all 27 jobs). Attempt 1's healthy lane
occupancy and concurrent burst-spread failures remain retained; a successful
rerun does not establish their scheduling cause.
The [6C3C20 owned experiment fault qualification](v5.1/PHASE_6_OWNED_EXPERIMENT_FAULTS.md)
adds separate fresh two-field leader-loss and no-quorum groups using the same
owned lifecycle, authenticated services and independent physical/history replay.
It was accepted through PR #251, master `49845530b0dd42db5b721219e92d36d8ced005a2`,
exact-master CI `36551903980` attempt 1 (all 27 jobs).
The 6C3C21 owned maintenance and complete four-cell experiment was accepted
through PR #252, master `471a36eea31f6e7cd5cbbdf4cd963f352fb29059`, exact-master
CI `36566870122` attempt 1 (all 29 jobs). Its three CI lanes completed in 8m11s,
9m37s and 17m02s. The 6C3C22 source/provider preflight passed corrected master
`0b22b671d39074fe019571dd90178b648a91cb38` (PR #254), CI `36635538287` attempt 1
(all 29 jobs), and live read-only preflight `36643330675` (all seven checks).
The observer and subnet configuration were separately authorized and read back;
organization/folder effective IAM remains unverified. The 6C3C23 disabled identity
proposal/audits were accepted through PR #255, master
`41b567b7cb96d36157a4434b02268b746492edfd`, exact-master CI `36648030423` (29 jobs).
That acceptance covered the proposal; later authorized staging is recorded below.
The 6C3C24 retained cleanup reconstruction was
accepted through PR #256, master `2ea9dbbfbf2821afc859663c87925a0e1d93322c`,
exact-master CI `36655860450` attempt 1 (29 jobs). The 6C3C25 native record formats
and closed cleanup HTTP policy were accepted through PR #257, master
`133b05e5cc02560877a74902911b21efacf2ba4c`, exact-master CI `36664035569` attempt 2
(29 jobs). Attempt 1's automatic-healthy warmup `LANE_BUSY` remains recorded;
retry success does not establish its latency cause. The 6C3C26 bound cleanup entries were accepted through corrected-source PR #259,
master `a25ecba2121526e4cef4d41ee1a90f1e1f64259e`, exact-master CI `36679824140`
attempt 1 (29 jobs). PR #258's inherited timeout-oracle failure remains recorded.
The 6C3C27 credential integration is accepted through PR #261, master
`27d6f7fa23377dbf305a1ac719ac5f8a6e97df9c`, CI `36695145198` attempt 1 (29 jobs).
The [disabled identity staging](v5.1/PHASE_6_CLEANUP_ACTIVATION_REVIEW.md) was
subsequently authorized and completed: 45 commands and 33 independent reads;
all three accounts/pools/providers remain disabled. The scoped cleanup network
entry (6C3C28) and deployment review (6C3C29) are also accepted; their exact CI
records remain in the [Phase 6 checklist](v5.1/PHASE_6_CHECKLIST.md).
The [6C3C30 state review](v5.1/PHASE_6_CLEANUP_STATE_REVIEW.md) and runtime
outbound-admission correction are accepted through PR #266/#267, master
`9243bc31dc3727a132b50740430426b3512fc5c8`, CI `36785256345` attempt 1 (29 jobs).
The original failed run remains retained. Fresh read-only ancestor inspection
still cannot read the organization allow/deny policies. The operator subsequently
authorized the [bounded IAM review amendment](v5.1/PHASE_6_CLEANUP_STATE_REVIEW.md#iam-admission-scope-amendment--2026-09-30):
ancestor reads are optional and retained as unassessed; explicit role/trust review,
actual-identity required/forbidden permission checks and real cleanup qualification
remain mandatory. Do not request organization privileges or migrate the project
merely to read ancestor policies. The amendment merged at
`e1adb7c7ea028124d104f5ccb05eb7a6d2686431`: PR CI `36791659694` passed, but
master CI `36793951268` attempt 1 failed on the existing selection driver's
[retained-restart coordination race](v5.1/PHASE_4_PUBLIC_SELECTION.md#retained-restart-coordination-correction--2026-09-30)
and a separate rich healthy warmup `LANE_BUSY`. PR #269 accepted the selection
correction and amendment at master `c209383a510ae785244003b8778e5e193cdaf255`,
CI `36804323832` attempt 1, all 29 jobs. That success does not prove the warmup
delay's cause. The [6C3C31 permission precheck](v5.1/PHASE_6_IDENTITY_PERMISSIONS.md)
binds observer/runner/manual/scheduled identities to diagnostic project/bucket
queries, with offline qualification and observer/proposed-cleanup integration.
Its first PR CI `36808406642` exposed a
[subsequent checkpoint restart defect](v5.1/PHASE_2_RECOVERY.md#subsequent-checkpoint-restart-correction-candidate).
The same PR resumes exact local checkpoint bytes in either inactive slot,
preserving floor-authorized retirement; deterministic regressions and retained-data
replay cover the correction. PR #270 accepted both changes at master
`13393b528bccd47a2d091ad43f3a1530f0aa6c8b`, CI `36830413171` attempt 1 (29 jobs).
PR #271 accepted credential diagnostics at master
`a65c66e41c7f89f90265b8ce51a9a17acdae1416`, CI `36903623343` attempt 2 (29 jobs).
PR #272 accepted the runtime path correction at master
`e763601ef7cc018d901e9b70f77ce8afb2fa0b7d`, CI `36934779388` attempt 2 (29 jobs).
Preflight `36937960812` passed descriptor checks but failed credential exchange.
The repository OIDC API confirms immutable subjects while the validator expected
the legacy format. The [immutable subject correction](v5.1/PHASE_6_IDENTITY_PERMISSIONS.md#immutable-oidc-subject-compatibility)
binds the exact names, numeric IDs and environment, with no legacy fallback or
cloud setting change. PR #273 accepted it at master
`4cb0280356280aa23d9f6b353d26e69916067e52`, CI `36943901305` attempt 1 (29 jobs).
Observer preflight `36945892944` attempt 1 passed all eight checks on that source,
including actual credential exchange and project/bucket permission queries.
The operator then [authorized manual cleanup deployment and post-merge enablement](v5.1/PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md#authorized-manual-deployment--2026-10-01).
PR #274 accepted the exact manual workflow at master
`b0a0173584d499a06abce870f8f0f2e46202c7b9`, CI `36951936364` attempt 2 (29 jobs).
All three authorized manual enable requests completed, each independently read
back; complete manual-state review passed all 17 groups / 33 observations.
Manual run `36957603644` attempt 1 passed actual credential/permission checks and
independent `STATE_MATCH / NO_LEASE`, with unchanged zero-cost ledger. The runner
and schedule stay disabled. Do not repeat enablement or seek the same approval.
PR #275 accepted the [single-disk cleanup preparation](v5.1/PHASE_6_CLEANUP_FIXTURE.md)
and USD 200 ceiling at master `35befc9adf41bf90520099721354632ff429bebf`,
CI `36963053297` attempt 2 (29 jobs). PR #276 accepted the
[fixture/probe driver](v5.1/PHASE_6_CLEANUP_FIXTURE_DRIVER.md) at master
`c23a8f654daab5a4cad4d645c761f82e7a21aa92`, CI `36972787971` attempt 1 (29 jobs).
The user approved the exact first fixture after regional price review; one data
disk was created and USD 1 reserved. Manual probe run `36976479227` failed at
overwrite-denied with 412; empty-input run `36977401162` then passed independent
active-state `STATE_MATCH / ACTIVE_OR_GRACE`. Neither qualifies object denials or
actual deletion. Original failed evidence remains retained.

The [generation-bound probe correction](v5.1/PHASE_6_CLEANUP_FIXTURE_DRIVER.md#first-live-attempt-and-412-correction--2026-10-02)
was accepted through PR #277 at master `f299b61a2e724ffb45c27a2c9150965d09626655`,
CI `36986377529` attempt 1 (29 jobs): positive retained generations for existing expendable
canaries, still only 403 qualifies denial, and v2 request approval prevents
reinterpreting the original zero-generation scope. The user requested preparing
the branch/PR while keeping master unchanged through the first disk's cleanup.
That hold was satisfied: expired run `36985944368` passed independent absence,
terminal ledger and provider deletion-audit review. Grace run `36984397533` was
WAITING, but a separate post-grace snapshot was not retained before deletion.
The separately approved v2 request `f1a49e0c223c4a0d99621cb1f861899a9af809100b6796049c022b5713ba3d81`
then passed all eight object probes and independent `OBJECT_SCOPE_MATCH` / active
`STATE_MATCH` in run `36989911551`. Grace `36998281162` returned WAITING;
expired `36999734150` passed independent absence/terminal-ledger and deletion-audit
review. A separate post-grace snapshot was not captured before deletion.
Never repeat a consumed probe, recreate canaries or reset failed charges.

The [complete-topology cleanup batch](v5.1/PHASE_6_CLEANUP_TOPOLOGY.md) was accepted
through PR #278, master `3e7e564972be01eb5894977cdc3c05e362bda0c0`, exact-master
CI `37000588745` attempt 1 (29 jobs). The user subsequently approved its first
USD 5 allocation. Preparation stopped after four firewalls, six disks and one VM:
GCP returned `maxRunDuration` with explicit `nanos: 0`, rejected by exact dictionary
comparison. PR #279 accepted the duration correction at
`9542f4910da439f31356da30b121ee8ced1af6ba`, exact-master CI `37059101337` (29 jobs).
Manual cleanup `37062489423` exposed a separate numeric-ID `targetLink` decoder
failure: VM deletion was accepted but not awaited, and boot disk deletion was
refused while attached. Follow-up `37063862494` passed independent absence,
lease-release and deletion-audit review; all eleven resources are gone. The ledger
retains USD 7 and the original FAIL completion. PR #280 accepted the deletion-operation
correction and asynchronous dependency regressions at master
`e9c85c4631ce75b82fdeec3777361ddbbfe846c0`, CI `37075056038` attempt 1 (29 jobs).
The user then approved a fresh USD 5 topology allocation: all thirteen resources
were prepared and independently matched. Manual run `37078761266` passed active
WAITING and independent STATE_MATCH, with USD 12 cumulatively retained.
Grace run `37084997701` independently matched unchanged WAITING state before
eligibility. Expired run `37086891033` independently matched PASS and all thirteen
original resource IDs absent, lease released and USD 12 retained. Provider audits
matched 26 start/end rows to the manual service account, with VM deletion before
disk deletion. All four cleanup-only attempts retain terminal FAIL; none ran an
engine workload. Evidence remains under `target/v51-topology-v2-review/`.

PR #281 accepted the [scheduled cleanup entry](v5.1/PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md#scheduled-deployment-candidate--2026-10-02)
at master `471ffd25787bcd872b1b4d71aed2ea620193eecf`, exact-master CI `37087985200`
attempt 1 (29 jobs). The separately authorized provider/pool/account enablement
completed; all 33 observations / 17 groups passed. Manual and schedule are enabled,
runner is disabled, and lease/ledger bytes and generations stayed unchanged.
Evidence: `target/v51-schedule-activation-review/`. Do not repeat enablement.

**Current operator direction:** manual cleanup is primary; actual schedule runs
are optional and must not delay development. Preserve the schedule; the user will
report a run for later qualification. The [native preflight amendment](v5.1/PHASE_6_CLOUD_PREFLIGHT.md#manual-first-native-preflight-amendment--2026-10-02)
fixes fake-format parsing of the live ledger and the old USD 100 display, and
collects exact-source recent manual PASS evidence without querying schedule.
PR #282 accepted it at master `aefaa51753c4294759981fc5feb3b2f132eae04e`,
CI `37095187875` attempt 1 (29 jobs). Manual `37105503864` attempt 1 passed
NO_LEASE; preflight `37105539166` attempt 1 passed all nine checks. Original raw
evidence and the nested cleanup artifact independently replayed; no freshness
extension is implied. The ledger still retains USD 12 / 200, no pending attempt
and no lease.

The [Runner permission entry](v5.1/PHASE_6_RUNNER_PREFLIGHT.md) is accepted through
PR #283, master `11a26936096d421fdb14f5b148ecb33ae3d731d1`, CI `37141295482`
attempt 1 (29 jobs). Separately approved Runner enablement passed 33 observations /
17 groups; only its provider/pool/account enabled bits changed. Same-source manual
`37252211351` passed NO_LEASE and preflight `37252295233` passed all nine observer
checks and actual Runner PRECHECK_PASS. Raw artifacts independently replayed;
original expiry `1791165298` is not renewed. Ledger remains USD 12 / 200 with no
pending reservation or lease at that observation. The [native storage
protocol](v5.1/PHASE_6_RUNNER_STORAGE.md) is accepted through PR #284, master
`69fb188b204feab01ffb6d2fdc37e02ab682c36c`, exact-master CI `37261105426` (29 jobs).
The current [exact-request storage entry](v5.1/PHASE_6_RUNNER_STORAGE_ENTRY.md)
adds operator canary preparation, optional Runner probes and independent raw
evidence/state review. It reserves USD 1 separately for each stage, retains failed
charges and releases the preparation lease before the unchanged same-run observer.
PR #285 / exact-master CI `37269773248` accepted the entry. Authorized preparation
retained USD 13 / 200. Native run `37274475579` failed on the CLI class identity
check before storage transaction requests; independent readback found unchanged
prepared state, no lease and no pending reservation. PR #286 / CI `37280773489`
attempt 1 accepted the CLI correction and Python CI partition (36 jobs) at
`b0bc7b4b9e63a40a1d812138d86cb40e7e298e92`. The [live review](v5.1/PHASE_6_RUNNER_STORAGE_LIVE_REVIEW.md)
records two separately authorized successful storage runs `37285400939` and
`37290067974`: eight probes each, original artifact provenance and independent
state. USD 17 / 200 remains reserved; no lease/pending attempt at observation.
The second run's provider audit covers seven of eight probes; outside-write's
original HTTP 403 and unchanged canary are retained without a matching audit row.
Temporary Storage audit configuration was restored. Do not spend another run
solely to fill that gap or require one audit row per HTTP call as a new gate.
The [Runner frozen-image read](v5.1/PHASE_6_RUNNER_RESOURCE_ENTRY.md) is accepted:
PR #287, master `530fe8573ebf25b2ac489175f33b6abc3794da3f`, CI `37341517723`
(all 36 jobs); manual `37375168508` NO_LEASE and Runner `37375846878`
project/bucket/image PRECHECK_PASS, independently replayed at original times.
The [ordinary resource lifecycle](v5.1/PHASE_6_EXPERIMENT_RESOURCES.md) adds shared
once-only creation and fresh-process expired cleanup qualification, accepted
through PR #288 at `d1f7b798897b83c51be6d3de53912860005b9f6d`, exact-master CI
`37383808101` attempt 2 (36 jobs). The rerun does not diagnose its earlier failure.
The [Runner request inspection](v5.1/PHASE_6_RUNNER_ADMISSION.md) adds
original artifact, price, exact approval, precheck, ledger and bound credential
checks in a read-only native constructor, with an offline resource/cleanup chain.
It is accepted through PR #289, master `e442e734564cd0cd34b47a29f0ab27401ab9a535`,
CI `37392515334` attempt 1 (36 jobs). The local
[native resource/IAP candidate](v5.1/PHASE_6_RUNNER_RESOURCE_ENTRY.md#native-resource-and-iap-candidate)
adds fresh original-input rechecks before lease CAS, thirteen once-only inserts,
Runner-credential isolation, pinned-host/provider/guest identity probes and ten
fresh-process interruption/expiry-cleanup cases. PR #290 accepted it at master
`5cf4bf10efb2df7b084ffee7f297877c7a494dee`, CI `37400113526` attempt 2 (36 jobs);
the rerun does not diagnose the original failure. The local
[native guest preparation](v5.1/PHASE_6_NATIVE_GUEST_SETUP.md) adds one-shot root
volume setup and unprivileged exact-package transfer. PR #291 accepted it at master
`70b452348832d6c2803870ae1b3ec74409e43ece`, CI `37411762406` attempt 2 (36 jobs).
That successful rerun does not establish attempt 1's cause. The local
[owner failure continuation](v5.1/PHASE_6_OWNER_FAILURE_CLEANUP.md) now connects
immediate exact-ID cleanup, immutable original diagnostics and append-only FAIL
completion under the original lease.
The same batch adds the [native owned experiment integration](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md):
original-lease service sessions, shared source/bootstrap, all four experiment cells,
independent physical/history validation, immutable retention and exact-ID cleanup.
PR #292 accepted both at master `20f977e8b5fed5bc5f54f53218c27d7971c2b3d4`,
exact-master CI `37424341468` attempt 1 (all 36 jobs).
The [manual entry](v5.1/PHASE_6_NATIVE_RUNNER_ENTRY.md) adds explicit
prepare/run workflow selections, public original-artifact handoff, exact plan
confirmation, private environment-key handling and detailed result summaries.
PR #293 accepted it at master `dc71dc003bc1d541a065f7d65bd6840da8ec5f06`,
CI `37434593823` attempt 1 (36 jobs). The secret was configured and unpaid prepare
`37438942134` passed; approved run `37439476170` failed on host-key HTTP 404 before
any workload, with incomplete immediate cleanup. The
[bounded readiness/delete-wait correction](v5.1/PHASE_6_NATIVE_RUNNER_ENTRY.md#first-native-run-and-bounded-readiness-correction--2026-10-06)
passed PR #294 and original resources were independently confirmed absent.
PR #295 accepted preparation connection reuse at master
`46e2d15cf2e5bf6fe468571101f4e8f753ddfe29`, CI `37524630590` (36 jobs).
Its admitted run `37531128228` consumed 494 seconds before guest setup and
exhausted the 600-second ceiling before any workload. Owner cleanup and independent
readback confirmed all thirteen resources absent, no lease and USD 47 / 200 retained.
The [preparation timing amendment](v5.1/PHASE_6_PREPARATION_BUDGET.md) passed
PR #296 at master `5254455d04bc832c5fb4ae4f2b8735a724a089e7`, CI `37540790465`
attempt 2 (36 jobs): 1800 seconds for this four-cell experiment, with the original
900-second admission window, 5400-second lease and 1080-second grace. Its admitted
run `37546477964` stopped before workload after 249.500 seconds. Retained-request
reproduction exposes a 600-second guest validator rejecting about 1550 seconds
remaining; the original clock reply and detailed exception were not retained.
Owner recovery and independent exact-ID reads confirmed all thirteen resources
absent, no lease and USD 57 / 200 retained.
The [guest deadline propagation correction](v5.1/PHASE_6_PREPARATION_BUDGET.md#guest-deadline-propagation-correction)
passed PR #297 at master `cdfb5af108c16c7bc01df98b74182a00db6396ee`,
CI `37552754929` attempt 1 (36 jobs). Admitted run `37555787624` completed all
three volume/package/session stages, then failed at source creation with
`native session exact configuration`; preparation used 1027.482 seconds, not the
1800-second ceiling. Recovery passed in 339.570 seconds; independent exact-ID
reads confirmed thirteen resources absent, no lease and USD 67 / 200 retained.
The [source-producer correction](v5.1/PHASE_6_SOURCE_PRODUCER.md#native-source-preparation-correction)
passed PR #298 at master `58a2376c0687810ee8e294737ccf6f7c98cc6fc3`,
CI `37565010319` attempt 1 (36 jobs). Run `37569971625` successfully generated
and downloaded the seed, then failed before workload with `guest root`: the
controller supplied a relative producer export path. Preparation used 529.357
seconds; recovery passed in 263.530 seconds. Independent reads confirmed all
thirteen resources absent, no active lease and USD 77 / 200 retained.
The [controller path correction and chain review](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md#controller-path-correction-and-chain-review)
passed PR #299 at `45b49095643aef6a5bb171e0f61158f3f7f22a27`, CI `37575940225`
(all 36 jobs). Run `37580265449` passed the published bootstraps but exhausted
1800 seconds before workload (0/4); owner recovery and independent absence checks
passed. The [preparation round-trip reduction](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md#preparation-round-trip-reduction)
passed PR #300 at `a91101f7a88a0a592ecaf98da8e889d9b3a1ef48`, CI `37590718799`
(36 jobs). Run `37595059219` installed all packages but exhausted preparation
querying node 2's unestablished session after an initial SSH/remote exchange failure.
All four formal cells remain unexecuted; recovery and independent absence checks
passed, USD 10 / 200 retained. The
[bounded session recovery](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md#bounded-native-session-recovery)
passed PR #301 at master `f22930f3c7b53fa94a250093199fbdbebc56b68f`, CI
`37613099633` (36 jobs). Run `37619934689` completed preparation in 1113.778
seconds with all three sessions succeeding on the first exchange, then failed
before the first healthy command reached its guest: the new owner API rejected
an exact-ID resource read using uninitialized cleanup reconciliation state.
No formal cell completed (0/4); retained evidence, thirteen-resource cleanup and
lease release passed. The local
[runtime identity handoff correction](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md#runtime-identity-handoff-correction)
separates exact retained-ID reads from cleanup operation resolution, shares each
command's deadline with its real guards, reduces duplicate identity reads and
retains safe runtime failure codes. Real promotion/guard regressions now cover the
lifecycle rather than substituting a mock recheck.
PR #302 merged the handoff correction at `47d6d2874258b2554b6397b6a691d531f1575dc3`.
Run `37689820061` completed preparation and V4.4 healthy, then exhausted V5.0
final-observation and retention budgets; cleanup confirmed thirteen resources
absent, but incomplete retention kept the lease. The
[first-run headroom correction](v5.1/PHASE_6_NATIVE_EXPERIMENT_HEADROOM.md) widens all
native stage/lease and nested control clocks, reuses short-lived pinned runtime
connections, retains bounded query-only recovery and adds 30-second heartbeats.
It passed PR #303 at master `366e379455ad7628a81160db604e09b09ffe9e0e`, CI
`37703102993`. Native run `37706121942` executed all four cells within budget,
but healthy shutdown closed leader node 1 first. The surviving quorum forced
NO_OP 93, leaving final cuts 92/93/93; independent healthy replay rejected this.
Cleanup of all thirteen resources, retention and lease release passed. Diagnostic
replay of the three original fault cells passed 22 negatives without qualifying
the failed aggregate. The current [shutdown correction](v5.1/PHASE_6_NATIVE_EXPERIMENT_HEADROOM.md#healthy-shutdown-correction)
closes followers before the observed issuer while preserving strict oracles,
original stop identities, failures and shared deadlines. PR #304 accepted this
correction with protected CI `37718123364`. Run `37723402614`, prepared by
`37722737290`, passed all four cells and 42 evidence negatives; retention and all
thirteen-resource cleanup/lease release passed. Original archive replay agrees.
Next extend the [native full presets](v5.1/PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).
The experiment-only v2 timing and USD 200 ceiling remain unchanged; this run's
USD 20 reservation brought the restarted ledger to USD 70. This is reserved cost,
not a bill or a new budget reset.
Default dispatch stays read-only; standalone native preparation stays PARTIAL.
Preserve the offline/native domain boundary.
The resource plan maps reuse, remaining implementation and exact-request approval;
it does not require another topology-only paid allocation by default. Preserve
historical receipts and original expiry; no need to wait for schedule.
Do not resume failed preparation or automatically remove failed charges.
The user approved the [USD 200 cumulative ceiling](v5.1/PHASE_6_CLOUD_CONTROL.md#approved-cumulative-ceiling-amendment--2026-10-01);
the single-disk proposal stays USD 1. On 2026-10-07 the user explicitly authorized
a [budget restart](v5.1/PHASE_6_NATIVE_OWNED_EXPERIMENT.md#explicit-operator-budget-restart--2026-10-07):
USD 87 was archived locally, the generation-bound counter restarted at USD 0, and
all historical attempt evidence stayed intact. This exception does not authorize
automatic refunds or future resets. Keep the 5400+1080-second real wait, existing
authority and subsequent failed charges. Retain the audit coverage limitation.
Image use/IAP and actual resource/failure paths are qualified for this four-cell
experiment. Larger presets and the full five-member set remain open; an empty
cleanup PASS is not full readiness. Full 6C remains open; paid experiments require separate
exact-request confirmation and user triggering.
The original Phase 0 planning-only restrictions below describe that earlier task.

## Self-contained development map

The revision 0.1 proposal's development material is integrated at the following
canonical destinations. This handoff retains the useful import, provenance and
review guidance; future development uses these repository documents directly.

| Material | Destination |
| --- | --- |
| Current development entry and historical navigation | [Root roadmap](../../DEVELOPMENT_ROADMAP.md) |
| Complete document navigation | [Documentation index](../README.md) |
| V5 overview and preserved authority map | [V5 README](README.md) |
| Version sequence, references and proposed acceptance boundaries | [V5 roadmap](ROADMAP.md) |
| Cross-version scope, compatibility, reads, operations and evidence rules | [Next-development addendum](NEXT_DEVELOPMENT_ADDENDUM.md) |
| V5.1 design task, D01-D12, E01-E12 and six planned deliverables | [Phase 0 entry plan](v5.1/PHASE_0_ENTRY_PLAN.md) |
| Research status and provisional V6 release labels | [V6 overview](../v6x/README.md) |
| Partitioning, remote queries, atomicity, views, relocation and scaling | [V6 architecture preview](../v6x/ARCHITECTURE_PREVIEW.md) |

The original patch, duplicate document copies, import commands, checksum list and
packaging reports are delivery material, not additional development contracts.
They are not prerequisites for using this map. Do not reapply the original patch
over these already integrated documents.

## Start the next design assignment

1. Inspect applicable repository/ancestor agent instructions, `git status --short`
   and `git rev-parse HEAD`. Reconcile changes since the reviewed source. Preserve
   unfinished user work; do not silently stash, reset, overwrite or switch branches.
2. Read the root roadmap, documentation index, [accepted charter](DEVELOPMENT_CHARTER.md)
   and V5 roadmap above. Published guarantees and accepted version-specific contracts
   govern; a newer proposal does not supersede them by its filename or date.
3. Read the V5.0 [public-admission contract](v5.0/PUBLIC_ADMISSION_CONTRACT.md),
   [runtime record](v5.0/PUBLIC_ADMISSION_RUNTIME.md),
   [API delta](v5.0/PUBLIC_ADMISSION_API.md),
   [public 1.1 format](v5.0/PUBLIC_ADMISSION_FORMAT_1_1.md),
   [recovery/failure contract](v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md) and
   [release reconciliation](v5.0/RELEASE_CHECKLIST.md). Distinguish historical internal
   1.0 fixtures from the admitted public 1.1 authority and later acceptance records.
4. Review the current implementation surfaces listed by the V5.1 entry plan and
   the existing [documentation gate](../../scripts/verify-v50-phase0-contract.sh),
   [change classifier](../../scripts/ci_changes.py) and [CI workflow](../../.github/workflows/ci.yml).
5. Once the user explicitly starts V5.1 Phase 0, use its entry plan as the design
   specification. Produce the six documents named in its
   [deliverables section](v5.1/PHASE_0_ENTRY_PLAN.md#7-concrete-phase-0-deliverables),
   resolving decisions through source inspection, counterexamples and review.
   That assignment still stops before separately authorized Phase 1 work.

At the original integration boundary D01-D12 were OPEN, E01-E12 were planned evidence
families, and the six Phase 0 output documents had not been produced. Do not invent
protocol proof, API compatibility, numerical defaults or acceptance evidence to
close them. A planning-document merge does not establish a completed Phase 0.

## Review boundaries to retain

Every later design review must preserve these distinctions:

- Published V5.0 guarantees, future V5.1-V5.4 scope and unapproved V6 research.
- V4.4 search/storage truth and V5.0 immediate replication compatibility.
- V5.1 leader-read safety and later public follower reads.
- Compatible configured-leader use and the proposed opt-in automatic mode.
- Indeterminate mutations and proven, safely retryable pre-dispatch rejections.
- Learner catch-up and safe voting-configuration transitions, including the existing
  V5.0 same-NodeId replacement boundary.
- Same-version rolling restart and mixed-version rolling upgrade.
- Per-shard atomic operations and a batch spanning multiple shards.
- A local Java Query lambda and a supported remote query AST.
- A vector of pinned shard views and a globally simultaneous snapshot.
- Fixed-load correctness evidence and measured physical scaling.
- Adopting an entry plan, accepting a full protocol and authorizing implementation.

Keep the accepted charter, V5.0 documents, release hashes and registered evidence
unchanged during this planning work. Preserve historical acceptance sections in
the root roadmap and V5 navigation. Historical corrections require an explicitly
identified erratum; they must not conceal an incompatibility in a later proposal.

The integration and documentation-only Phase 0 scopes do not include
production or test code, declaration classes, fixtures, version/dependency changes,
workflow changes, cluster startup, fault execution, paid cloud runs or publication.
Commit, push and merge remain user-owned operations. V6 research may proceed as
separately assigned design work; its proposed production gate remains a mature
V5.4 handoff unless explicitly revised through review.

## Provenance and integration review

The original proposal was revision 0.1 dated 2026-09-19, based on the reviewed
source above. All four original Git blob identities matched the actual checkout:

| Original file | Base Git blob |
| --- | --- |
| V5 README | `04b3218e31121bc2faf9b209da5043310703da07` |
| V5 roadmap | `926bf1551f7e67b161da7853b0eccc87c9f55165` |
| Root development roadmap | `d5fb7c56db5cc7893f4688476d088c341d4a13c1` |
| Documentation index | `272ff7a17617f7e37a508123064ef3c9420ac17f` |

Original patch SHA-256:
`e76de7161a2336bfdac2c11debf59ba1f34632ffb5acb2ad86156dcd3607fd9d`.
This identifies the imported patch, not a release artifact or the subsequently
clarified working tree. The full package checksum list passed before removal.

The package author had reviewed complete V5 README/roadmap content but only prefixes
of the two larger indexes. Its 119-reference check and patch application used
retrieved fixtures; it did not run the actual repository gate. Local integration
subsequently checked the real base blobs, ran `git apply --check` successfully and
applied all four modifications plus four additions without conflict. The package
was not copied on top of the applied patch.

Review added three clarifications: integration versus a separately assigned design
task, pre-dispatch rejection versus indeterminate mutation, and fixed-identity disk
replacement versus membership change. This handoff then consolidates the remaining
development guidance, bringing the proposed repository change to nine Markdown files.

The published V5.0 commit remains `e6afb5349c018fe163d4938d7637a4de8854d4ea`;
its measured cloud source remains `340df06148bc7d5a25a29a55c3ee928c9472dd09`.
Neither is relabelled as this documentation review source.

## Validation and reporting

Run the existing lightweight checks from the repository root:

```bash
git diff --check
scripts/verify-v50-phase0-contract.sh
python3 -m unittest scripts.test_ci_changes
git status --short
```

Also check every added or changed Markdown document, including `docs/v6x/`, for
local targets, anchors, balanced fences, trailing whitespace, final newlines,
proposal status, source identities and path containment. Include untracked files;
`git diff` alone omits them. Verify the accepted charter and V5.0 files against the
reviewed source and compare the preserved historical sections byte for byte.
The existing V5 gate covers a limited required-file list, so it does not replace
the expanded document walk. Let the existing classifier decide CI scope.

Local integration passed whitespace, the V5 contract gate, all 14 classifier tests,
the expanded document checks and preservation of all 60 protected charter/V5.0
files. No Java, runtime, consensus, cloud or publication validation was rerun for
this documentation task. The external etcd/Elastic references retained in the
design documents are comparisons, not evidence of GSE protocol correctness.

Report the exact reviewed source, local changes, commands/results, actual conflicts,
incomplete checks and unresolved design decisions. Record protected-review and
exact-master CI acceptance only after they occur. Stop at the assigned phase boundary.

The [Phase 6R recovery controllers](v5.2/PHASE_6_RECOVERY_CONTROLLERS.md) now execute
both M04 fault schedules with closed observer controls, exact original calls,
retained pre-reopen bytes and owned-process cleanup. Two fresh development
histories pass general physical validation. Independent generation/token/query,
resource and portable M04 admission remains open before the complete machine
freeze and formal measurements. No production Java or workflow topology changes.

The [Phase 6S recovery evidence](v5.2/PHASE_6_RECOVERY_EVIDENCE.md) binds M04's exact
process generations, pre-reopen proven authority, fault schedule, actual query
results and per-process resources, retaining the SIGKILL sampling prefix explicitly.
Portable original/relocated replay and negative cases are implemented. The full
machine freeze and fresh formal 28-history M01–M04 cohort remain next; no paid run,
production Java change or push is authorized by this evidence stage.

The [Phase 6T machine/cohort entry](v5.2/PHASE_6_MACHINE_COHORT.md) now binds a
separate committed implementation and machine-only freeze commit, with complete
28-history original/relocated qualification. Unit fixtures are not measurements.
Next build the exact committed implementation, commit its machine plan, execute
the fresh full cohort and retain every original failure. Hosted acceptance and
fresh cloud admission remain required; paid execution remains operator-owned.

The [Phase 6U replay optimization](v5.2/PHASE_6_REPLAY_EFFICIENCY.md) follows the
first frozen cohort's agent-aborted independent replay. Its first complete M01
window and failure receipt remain intact. Verified temporary trace bytes remove
repeated chunk reconstruction while preserving every semantic check. A new
exact-source freeze and fresh full cohort are required; the old history is used
only to qualify replay equivalence, not to fill a new measured repetition.

The [Phase 6V M01 drain correction](v5.2/PHASE_6_M01_DRAIN.md) follows the second
cohort's retained observation failure. All original requests were dispatched;
seven queued legacy responses completed after the former 35-second drain.
The revised 125-second common observation allowance accounts for the unchanged
consumer queue and API interval. Frozen business parameters and M02–M04 remain
unchanged. Controller regressions pass; a fresh complete cohort remains required.

The [Phase 6W baseline observer correction](v5.2/PHASE_6_BASELINE_RETIREMENT.md)
follows a retained reactor-test preparation failure. A deterministic lost-source
response reproduces the mismatch between a 60-second recovery lease and the
former 30-second baseline observation. The fixture now covers the original lease
plus its convergence allowance and retains bounded rejection diagnostics. The
original transport cause remains unconfirmed; new exact-source build and complete
measurements remain required before cloud preparation.

The [Phase 6X cloud suite contract](v5.2/PHASE_6_CLOUD_SUITE.md) groups the unchanged
28 formal histories and five separate untimed readiness histories into experiment,
failure-drill and three canonical members. Members may be selected in any order;
the closed set binds one exact source/sequence/build/package/control identity and
rejects duplicate attempts or partial histories. Selection is not admission or
execution evidence. Local complete measurement, remote transport/bootstrap/replay,
owned no-GCP qualification and final exact-master/provider admission remain open.

The [Phase 6Y remote preparation boundary](v5.2/PHASE_6_REMOTE_BOOTSTRAP.md)
now validates explicit topology and performs receiver-local public bootstrap from
one immutable V4.4 seed under both published V5.1 and candidate V5.2 JARs. Six
unstarted receiver authorities pass original and relocated inspection; duplicate
preparation and wrong seal paths reject. This is preparation qualification only.
Persistent remote commands, actual remote voter operation, complete no-GCP
workloads and live cloud admission are still required.

The [Phase 6Z receiver pipe bridge](v5.2/PHASE_6_REMOTE_RUNTIME.md) reuses the
existing public consumer, observation hooks and whole untimed smoke program over
three receiver-local bootstrap roots. Its separate validator checks receiver paths,
actual topology and loaded artifacts before applying the same physical/query/read
checks. Development source drift was retained as an invalidated attempt; source
checks now stop on drift before accepting a member. Both five-mode entries and
the existing large-package replay pass locally, with 100 receiver negative variants
at each location. Cross-host command ownership and cloud qualification remain open.

The [Phase 6AA command foundation](v5.2/PHASE_6_REMOTE_COMMANDS.md) now retains
immutable V5.2 history/node/session claims and queries original results after a
lost response. Soft total time warnings coexist with finite exchange deadlines,
bounded failure thresholds and dead/reused-process detection. Twenty-one unit
cases and four real subprocess cases pass; no engine or cloud workload is claimed
by those markers. Next connect stable semantic command slots and persistent guest
execution, then complete cross-host identity and M01–M04 portable qualification.
