# Phase 3 qualification inventory and remaining work

[Store ownership across failed drain](PHASE_3_STORE_LISTENER_DRAIN.md) now
separates revocation/drain from parent storage and lock release. Original
checkpoint/head callback and interrupted-close failures exposed three prematurely
released POSIX locks. Scoped resource and fresh-JVM lock observations cover the
corrected retries; constructor, replacement/recovery and full native custody
qualification remain OPEN.

[Retained-owner failed close](PHASE_3_PENDING_LISTENER_DRAIN.md) now requires
listener drain before storage release or voter handoff. Checkpoint/head callback
and interrupted-close cases retain original storage for an external retry, with
independent continuous-lease replay. This conditional scope does not qualify
enclosing store cleanup, constructor rollback or full native joining; Phase 3
and final-source qualification remain OPEN.

[Native cleanup binding and listener drain](PHASE_3_NATIVE_CONTROL_CLOSE.md)
now qualify 96 cleanup intervals against original multi-session source ownership.
Two deterministic TCP regressions also correct checkpoint/head endpoints reporting
closed before their cancelled I/O workers drain. Thirteen native close negatives
pass. These scoped results do not close Phase 3; full joining/required-four,
remaining resource/custody and final-source qualifications remain OPEN.

[Source-component cleanup intervals](PHASE_3_CONTROL_CLOSE_RESOURCES.md) now
bind the cleanup-performing service, trace and session calls to original resource
sequences and child leases. Four TCP histories pass 12 intervals, 64 close
mutations and 76 existing source mutations. Joining endpoint and native close
integration, other resource categories and final-source qualification remain
OPEN; final zero accounting alone is not successful close evidence.

[Native source resources](PHASE_3_NATIVE_SOURCE_RESOURCES.md) now bind multiple
original sessions in the complete short native physical/accounting pipeline.
The retained two-slot history covers 444 source CONTROL reservations and 17
exact negatives. Strict replay refuses missing/legacy bindings; compatibility
mode explicitly reports them unobserved. Service-close intervals, other resource
categories and final-source qualification remain OPEN.

[Source control resources](PHASE_3_SOURCE_CONTROL_RESOURCES.md) now bind logical
requests, cached responses, session metadata and completed trace caches to exact
original request/session identities. Short TCP loss/retry histories and coherent
negative replay qualify this component; multi-session native integration and
other CONTROL/storage obligations remain OPEN. Phase 3 is not closed.

[Unsent transport resources](PHASE_3_UNSENT_RESOURCES.md) now bind buffers that
fail before the connected write callback to their exact request and local attempt.
Four native histories / eight failed allocations and 48 exact negatives pass;
the existing two late-terminal histories and 32 negatives also pass. Old unobserved
allocations and other CONTROL lifetimes remain gaps until qualified on new
originals. Phase 3 and final-source qualification remain OPEN.

[Owner close observations](PHASE_3_OWNER_CLOSE_RESOURCES.md) now bind resource
release to an actual close invocation and successful return. One new short TCP
history qualifies three owners / 20 released leases with twelve close negatives
and fifteen existing accounting negatives. Historical collections explicitly
remain unobserved for this scope; new required-four close qualification and the
remaining combined resource/final-source obligations are still OPEN.

[Persistent BASIS resource binding](PHASE_3_BASIS_RESOURCE_BINDING.md) now derives
packet/image charges from original grants and requires continuous ownership
through retirement or a proven owner transition. The unchanged complete native
original passes 26 source / 58 lease bindings, 22 retirements, three reopens and
seventeen exact negatives; 181 related tests pass. Ordinary generation reloads do
not authorize release/reacquire gaps. Unmarked old-owner shutdown ordering and
remaining physical/control scopes remain open; Phase 3 is not closed.

[Receiving resource binding](PHASE_3_RECEIVE_RESOURCE_BINDING.md) now derives
transfer leases from original packet/image bytes and authorized generation
metadata, and checks scratch release only after the exact remote floor copy is
forced. The unchanged full original passes 165 receiving bindings, 117 handoffs
and nineteen exact native negatives; 164 related tests pass. Atomic learner
handoffs preserve charges; individual post-handoff file
custody and other storage/control lifetimes remain separate qualifications.
Phase 3 stays OPEN. Earlier notes retain their historical source-bound scope.

[Floor storage lifetimes](PHASE_3_FLOOR_RESOURCE_BINDING.md) now bind copied
metadata/images and pinned local generations to the original event/resource
sequences. Conditional regressions and eleven coherent negative cases cover
wrong extents, copy identity and gaps between callbacks. The complete required-four
original now passes all eleven slots, cold reopen and corrected full original
replay, including all four continuous ledgers. Its first replay failure exposed
a reader's incorrect ACK requirement for a departing FINAL owner; that failure
remains retained. Resource replay binds 56 floors / 358 leases and 81031 changes.
Receiving scratch, other control/storage owners, complete negative matrices,
combined physical maxima and final-source admission remain open. Earlier batch
notes below describe their historical evidence state, superseded only for the
specific original scope qualified here.

[Transport frame lifetimes](PHASE_3_TRANSPORT_RESOURCE_BINDING.md) now bind
original invocation IDs to exact request/reply leases. Two real TCP retry/failure
histories qualify 15 frame lifetimes and 32 exact negatives. This covers connected
frame buffers, not pre-connection failures or service/export/cache CONTROL
lifetimes; the required-four resource entry retains those remaining gaps.

[Native resource accounting](PHASE_3_NATIVE_RESOURCE_ACCOUNTING.md) now binds
the actual old/joining budgets to original identities and every observed event.
A short TCP history independently passes 3576 mutations, 1788 event boundaries,
44 publication boundaries and 15 exact negatives. Complete required-four native
qualification and non-publication physical/control lifetime derivation remain
pending; no final-source or whole-runtime physical peak is claimed.

[Resource transitions](PHASE_3_RESOURCE_TRANSITIONS.md) now observe accounting
mutations between existing publication/transport callbacks. Six component traces
cover all 19 event kinds and 210 transitions; two incomplete traces are rejected.
Per-owner accounting peaks do not qualify whole-runtime physical maxima. The
native producer/event integration is covered above; complete required-four
execution and physical/control lifetime qualification remain pending.

[Required-four continuous ledgers](PHASE_3_REQUIRED_FOUR_LEDGERS.md) now connect
the four existing chain readers to the required-four original and pinned-floor
maintenance. The entry retains all six final owners and 86 component mutations;
conditional regressions do not qualify a native run. Corrected-source complete
replay, resource/process coverage and final-source execution remain pending.

[Required-four maintenance](PHASE_3_REQUIRED_FOUR_MAINTENANCE.md) now composes
original pin custody and exact floor lifetime checks behind physical/network/
export admission. Thirteen conditional regressions and a historical diagnostic
of 22 captured floors pass; the 20 native negatives and corrected-source complete
entry are pending. Continuous ledgers/resources and final-source execution remain
open; no frozen coverage or native PASS is inferred from this entry.

[Required-four export composition](PHASE_3_REQUIRED_FOUR_EXPORTS.md) now binds
content and control authorization to the explicit four-required-voter topology
behind the complete physical/network precondition, with 26 required negatives.
Historical original-byte lifetime and transfer-only diagnostics pass their narrow
scope. Corrected-source complete replay, continuous ledger/resource composition
and final-source execution remain pending.

[Joining connection integration](PHASE_3_JOINING_CONNECTIONS.md) now threads
original socket metadata through old-owner and scoped joining collectors and the
shared phase/network readers. Actual overlapping retries through these collectors
pass independent replay and eight exact negatives. A fresh required-four native
execution passed, but independent replay rejected twelve replies whose production
endpoint decorators dropped connection observations. Those two decorators are
corrected with real TCP regressions; corrected-source whole-history qualification,
remaining lifetime/resource composition and final-source admission remain pending.
Both the older ambiguous trace and the newer incomplete trace keep their original
scope and remain unmodified.

[Connection-scoped transport observations](PHASE_3_CONNECTION_ATTEMPTS.md) now
preserve the actual socket pair and local invocation identity across late failure
callbacks. Two real overlapping identical-request histories and eight independent
negative replays pass. Collector/shared-reader integration now passes its short native gate. Fresh
required-four whole-history qualification remains OPEN; old traces are not
upgraded by this component result.

[Required-four physical replay](PHASE_3_REQUIRED_FOUR_PHYSICAL.md) now derives
all eleven slots through cold reopen, including three pinned maintenance floors,
22 source-retirement transactions / 330 prefixes and the departing nonvoting
FINAL owner. Separate slot-force replay checks 34 transactions and 5,234 callbacks.
The same original also passes 34 publication resource transactions / 374 boundaries
and 26 exact capture negatives; whole-runtime/control maxima remain OPEN.
Strict network qualification remains OPEN: identical ACCEPT retries overlap late
server terminals, and the retained trace lacks unambiguous attempt correlation.
The original failed network gate is retained; no timeout or acceptance rule is
relaxed. Complete resource composition and final-source admission remain OPEN.

[Pinned-floor process recovery](PHASE_3_PINNED_FLOOR_PROCESS.md) now passes all
36 halt/SIGKILL cases, 108 fresh worker executions and eleven exact negative
replays. Expected crash/reopen/final/cold bytes and force order come from original
conditional seed bytes; this does not claim native fault-history or power-loss
qualification. Phase 3 remains OPEN for complete native maintenance / resource
composition, frozen coverage and final-source admission/execution.

[Pinned local floor originals](PHASE_3_PINNED_FLOOR.md) now resolve the conditional
installed-generation capacity conflict by keeping the already charged current
generation and copying three remote originals. Four logical voters and the frozen
six-source/seven-image bounds remain unchanged. The corrected required-four
history now passes FINAL, stable BARRIER, cold reopen and independent semantic /
34-publication replay with thirteen exact negatives. Full native maintenance /
resource composition and final-source qualification remain OPEN.

Phase 3 remains **OPEN**. This inventory originated from baseline `867df7c4`;
the current table also includes the subsequent learner, transfer and round cohorts. It does
not execute a native history, accept an old receipt as current-source evidence,
or declare the implementation complete.

The [machine plan](phase3-qualification-plan.json) and
[source inspector](../../../scripts/v53/phase3_qualification_plan.py) provide
the current navigation for remaining work. Earlier documents retain their
original scope and results. A historical sentence saying an endpoint or reader
is missing must be read together with its later implementation, not copied into
the backlog as a new feature.

## Implemented entries

| Whole-history cohort | Members | Execution groups | Current scope |
| --- | ---: | ---: | --- |
| [Ordinary profiles](PHASE_3_PROFILE_HOSTED.md) | 7 | 7 | All seven ordinary ADD/REMOVE/REPLACE histories |
| [Joining reply loss](PHASE_3_JOINING_FAULT_HOSTED.md) | 3 | 3 | Three reply-loss boundaries in a complete 3-ADD history |
| [REMOVE process](PHASE_3_REMOVE_PROCESS_HOSTED.md) | 52 | 52 | Declared departure/retirement process subset |
| [Node renames](PHASE_3_NODE_RENAME_MATRIX.md) | 4 | 4 | ACCEPT/PROOF rename, halt/SIGKILL, original disks |
| [Joining initialization](PHASE_3_JOINING_PROCESS_HOSTED.md) | 360 | 120 | Five joining profiles, 36 cuts, two death modes |
| [Continuous learner histories](PHASE_3_LEARNER_HISTORY_COHORT.md) | 2 | 2 | Six revisions and retained READY/CANCEL, complete cold reopen |
| [Transfer lifetime/process matrices](PHASE_3_TRANSFER_HISTORY_HOSTED.md) | 21 | 2 | Three continuous owner histories and eighteen two-process recoveries |
| [Native carried/stable rounds](PHASE_3_NATIVE_ROUND_HOSTED.md) | 7 | 7 | Four carried BARRIER phases and three guarded round histories |
| [Native carried DATA](PHASE_3_CARRIED_DATA_HOSTED.md) | 4 | 4 | Four old DATA phases, carried completion and the next fresh BARRIER |
| [Native carried INTENT/FINAL](PHASE_3_CARRIED_TRANSITION_HOSTED.md) | 2 | 2 | Complete carried transitions through stable BARRIER, six reader layers and actual retirement bytes |
| [Automatic lifecycle components](PHASE_3_AUTOMATIC_HISTORY_HOSTED.md) | 50 | 3 | Competition, higher-ballot restart and the complete 48-case PROMISE reply-revocation matrix |
| [Joint-floor process histories](PHASE_3_PROCESS_JOINT_HOSTED.md) | 32 | 32 | Four copy ordinals, four cut callbacks, halt/SIGKILL, same-scratch recovery and full continuation |

These **544 planned native histories** are complementary subsets. This is neither
a pass count nor a count of covered rows in the frozen S matrix. The inspector
reads their actual Python catalogues and checks declared counts and ordered-case
hashes. Joining groups must partition all 360 whole histories exactly; transfer
groups must preserve their complete three-owner and eighteen-recovery matrices.
Automatic groups preserve both whole campaigns and the complete 48-case matrix.
Workflow and implementation references must exist as regular repository files. This
checks inventory drift, not workflow scheduling behavior.

Existing per-workflow admission binds its own source/build, tools, reader, seed
and run/attempt. Those gates are not redeveloped by the inspector. Separate preparations do
not automatically form one accepted phase-wide cohort; that admission still
needs integration. No hosted workflow was dispatched for this audit.

The [joint-floor process component gate](PHASE_3_PROCESS_JOINT_COHORT.md) now
adds local admission of 32 whole v2 histories with 1,544 predeclared exact
negatives. Its [hosted adapter](PHASE_3_PROCESS_JOINT_HOSTED.md) now adds the 32
planned entries above; their final-source executions remain open.

## Current obligation map

[Deferred grant capture](PHASE_3_DEFERRED_GRANT.md) implements the clean-source
reclamation order with unchanged incomplete-PROMISE recovery and capacity rules.
Its [fourteen fresh-process cases](PHASE_3_DEFERRED_GRANT_PROCESS.md) now pass
conditional physical replay and ten exact negatives. The later required-four
native follow-up passed preparation but failed in installed-generation
maintenance at eight required images. Pinned-floor reuse subsequently completed
that native history and passed semantic/publication replay; full maintenance
composition and combined-resource gaps stay OPEN.

[Required-four replacement](PHASE_3_REQUIRED_FOUR.md) adds a development
topology with live common members 1/2, departing member 3 and joining member 6;
common members 4/5 remain offline. Unlike the earlier four-copy floor, this
joint view needs all four available voters. Its original semantic/publication
reader does not add a hosted subset or qualify the full physical/resource peak.
The first native execution failed before FINAL at floor reservation: three
retained sources plus four required floor copies exceed the six-slot SOURCE
limit. The corrected runtime now passes the complete native semantic/publication
slice and thirteen negatives, recorded in the
[native follow-up index](phase3-evidence/required-four-pinned-native.json).
The conditional capacity diagnosis itself is still only a reproducer; this does
not qualify the remaining full physical/network/resource composition.

[Floor/retirement refusal accounting](PHASE_3_SOURCE_RESERVATION.md) now retains
the charges for incomplete original files and rolls back partial handoff growth.
This follows the generation reservation correction. Its conditional regressions
add no hosted histories and do not close the combined physical-peak obligation.

The machine plan has 12 review groups with concrete production/tooling, test,
reader and documentation paths, related frozen families, existing hosted subsets
and unresolved work. References locate implementation; the inspector cannot
prove its semantics.

| Group | Existing implementation and evidence | Remaining qualification |
| --- | --- | --- |
| 3A activation | Durable grant, selected sources, fence and original deadline | Final-source schedules and exact failure coverage |
| 3B transfer | Bounded native TCP, receiving custody, retries/process readers and [complete transfer matrix admission](PHASE_3_TRANSFER_HISTORY_COHORT.md) | Final-source transfer execution; combined lifetimes |
| 3B recovery | Retained ancestry, owned reopening and cross-view adoption | Final-source restart/discovery coverage |
| 3C learner | Six-revision/cancellation producers, source retention, readers and hosted pair | Complete final-source histories and profile coverage |
| 3C initialization | Actual joining owner, three-ledger initialization and 360-case entry | Final-source matrix; combined bounds |
| 3C joint | Private INTENT/FINAL/BARRIER coordination for all seven profiles; [carried INTENT/FINAL physical replay](PHASE_3_CARRIED_TRANSITIONS.md) for four-voter REMOVE | Final-source profiles and carried pair execution, other profiles and interrupted transitions |
| 3D rounds | Carried-first publication, two durable phases, round reuse, [seven-history admission](PHASE_3_NATIVE_ROUND_COHORT.md) and [carried INTENT/FINAL physical/lifecycle replay](PHASE_3_CARRIED_TRANSITIONS.md) | Final-source native round execution; carried DATA has a [four-history local entry](PHASE_3_CARRIED_DATA_COHORT.md); the [carried transition pair](PHASE_3_CARRIED_TRANSITION_COHORT.md) has six-layer admission; final-source execution, other payload axes and process faults remain |
| 3D automatic | Competing owners, heartbeat, original grants, both campaign networks, maintenance, installation/publication, [observed export authority](PHASE_3_COMPETING_EXPORTS.md), [actual lifecycle collection](PHASE_3_AUTOMATIC_LIFECYCLE.md) and [pre-grant-loss whole replay](PHASE_3_PREGRANT_LOSS_REPLAY.md) | All-kind export lifecycle beyond the [PROMISE reply-boundary component](PHASE_3_TRANSFER_REPLY_LIFETIME.md), complete recovery, final-source competition and failure coverage |
| 3D removal | Departure fencing, retirement and original-disk recovery | Final-source original/negative process matrix |
| 3E resources | Accounting, bounded transfers, publication refusal, conditional-prefix tests, [nine actual receiving-overlap histories](PHASE_3_COMBINED_RECEIVE_RESOURCES.md), and [one native 5-REPLACE interrupted-floor recovery](PHASE_3_JOINT_FLOOR_RECOVERY.md) through FINAL/BARRIER with continuous authority replay | Full simultaneous physical peak, remaining admitted transition and process-death axes |
| 3E coverage | Frozen finite inventory and this dependency map | Concrete schedule/evidence/rejection mapping |
| 3E cohort | Twelve source-bound subset gates | Complete final admission, execution and closure audit |

`MembershipStorageOperations` still refuses public learner operations and
`MembershipSearchEngine` keeps reads disabled. Phase 3 private protocol work does
not silently enable Phase 4 interfaces. The frozen [acceptance register](ACCEPTANCE_REGISTER.md)
and machine plan assign the complete **3,310 S rows to Phase 5**. Public consumer,
read and maintenance axes cannot be counted as covered by private Phase 3 tests.
Phase 3 must qualify their protocol dependencies; this audit moves or waives no
final requirement. All 24 negative families still require appropriate original
evidence and exact rejection mapping. Related family IDs are not that mapping.

## Execution sequence

1. **Complete component cohort entries.** The focused 3-ADD learner pair now has
   its entry. [Competing grant capture](PHASE_3_COMPETING_GRANT_CAPTURE.md) now
   retains losing/superseded grants. The [new native prefix](PHASE_3_COMPETING_CAMPAIGN_PREFIX.md)
   derives four grants and both choices; [preinstall maintenance](PHASE_3_COMPETING_MAINTENANCE.md)
   now derives its original floor/source release and final grant/source projection.
   [Installation/publication continuation](PHASE_3_COMPETING_PUBLICATION.md) now
   derives the selected generations, both slots, client completion and drained
   scratch from that original. [Activation network](PHASE_3_COMPETING_ACTIVATION_NETWORK.md)
   now includes both choices and the losing incomplete transfer. Observed temporal
   exports are checked; [pre-grant-loss replay](PHASE_3_PREGRANT_LOSS_REPLAY.md) now
   accepts that unchanged zero-retirement original with exact applicable negatives.
   [Observed automatic restart](PHASE_3_RESTART_LIFECYCLE.md) now binds an actual
   higher-ballot loss, session replacement and fresh READY to one original's
   complete current physical/network replay and unchanged deadline. It adds no
   hosted subset or final-source qualification. General lifecycle/fault coverage
   and competition admission remain open.
   [Native transfer reply revocation](PHASE_3_TRANSFER_REPLY_LIFETIME.md) now adds
   48 original TCP cases for PROMISE exports at offer/data/commit/cached-retry
   boundaries. Its 30 negatives preserve exact clocks, bytes and resource drain;
   this component does not qualify other export kinds or add a hosted cohort.
   [Automatic lifecycle component admission](PHASE_3_AUTOMATIC_HISTORY_COHORT.md)
   now binds competition, restart and the complete reply matrix to one exact
   source/build/toolchain/reader. It replays original layers and exact applicable
   negatives across three complete groups. Its
   [hosted adapter](PHASE_3_AUTOMATIC_HISTORY_HOSTED.md) now freezes one seed and
   requires all 50 original plans and three downloaded verifier receipts from
   the exact run/attempt. Final-source execution remains open. Retained historical
   originals are not new cohort slots.
   The [transfer matrix entry](PHASE_3_TRANSFER_HISTORY_COHORT.md) binds the existing
   complete TCP lifetime and two-process recovery matrices to one recorded
   source/build/toolchain/reader and independently replays both originals. It is
   a component entry; its [hosted adapter](PHASE_3_TRANSFER_HISTORY_HOSTED.md) now
   adds two complete-matrix groups with exact seed/run/attempt binding. Neither
   local development evidence nor the unexecuted adapter fills final-source slots.
   The [native round entry](PHASE_3_NATIVE_ROUND_COHORT.md) now captures the four
   carried BARRIER phases and three guarded rounds, including their complete
   underlying physical and lifecycle negatives. Its [hosted adapter](PHASE_3_NATIVE_ROUND_HOSTED.md)
   now retains seven independent whole histories and exact downloaded replays.
   The [carried DATA entry](PHASE_3_CARRIED_DATA_COHORT.md) adds four original
   phases, unchanged payload completion and the next BARRIER with 129 negatives.
   Its [hosted adapter](PHASE_3_CARRIED_DATA_HOSTED.md) now prepares four native
   executions and four downloaded replays. The existing node-rename matrix
   already covers DATA ACCEPT/PROOF process cuts and is not redeveloped here.
   The [carried INTENT/FINAL reader](PHASE_3_CARRIED_TRANSITIONS.md) now independently
   replays two complete four-voter REMOVE originals and 60 exact negatives,
   preserving old entry bytes through fresh stable readiness. This development
   physical/lifecycle component is now complemented by
   [attempted-network qualification](PHASE_3_CARRIED_TRANSITION_NETWORK.md): two
   new request-observed originals, complete durable replies and 153 exact network
   negatives per kind. Older response-only records cannot supply this scope.
   [Temporal export and floor replay](PHASE_3_CARRIED_TRANSITION_EXPORTS.md) now
   authorizes all 416 observed transfers and 20 complete-copy floors in those same
   originals, with 44 exact negatives. [Ledger/retirement replay](PHASE_3_CARRIED_TRANSITION_RETENTION.md)
   now adds continuous peer/future chains, all observed retirement callbacks and
   154 exact negatives. [Retirement prefix capture](PHASE_3_CARRIED_TRANSITION_PREFIXES.md)
   now adds actual writer-held bytes and compares them to those derived states,
   with separate carried kind/result binding. The
   [source-bound cohort and hosted pair](PHASE_3_CARRIED_TRANSITION_HOSTED.md) now
   require all six reader vectors (602 negatives) and both complete sidecars.
   Final-source execution, process-death coverage and other profiles remain open.
   Other carried payload/process axes remain; conditional Phase 2 fixtures cannot
   substitute for native originals. Continue competing-owner and transition
   recovery entries and uncovered learner profiles. Reuse existing producers/readers.
   Historical qualification remains scoped to its source, not a new cohort slot.
   The six-revision history's recorded final-CANCEL deadline failure remains a
   failure; retrying, extending budgets or reconstructing observations cannot
   turn that original into a pass.
2. **Qualify combined resources.** The [partial-generation reservation correction](PHASE_3_GENERATION_RESERVATION.md)
   fixes a reproduced loss of accounting on failed install expansion. It retains
   original handles and rolls back unsuccessful grouped growth. The subsequent
   [floor/retirement correction](PHASE_3_SOURCE_RESERVATION.md) covers those refusal
   paths. [Native reply resource replay](PHASE_3_TRANSFER_RESOURCE_LIFETIME.md)
   now derives the existing PROMISE matrix's actual boundary charges and completed
   cache lifetimes. [Publication reservation handoff](PHASE_3_PUBLICATION_RESERVATION.md)
   now atomically consumes the already-admitted image for candidate installation;
   [generation reload](PHASE_3_GENERATION_RELOAD.md) now retains the original
   generation group through validation and commits only the complete reader pair.
   Its native interruption check keeps original charges until owner close and
   resumes the same forced files. [Publication storage observations](PHASE_3_PUBLICATION_RESOURCES.md)
   now capture eleven existing boundaries per native publication and independently
   compare their inventories and storage reservations. CONTROL/WAITER lifetimes,
   the full simultaneous maximum and final-source execution remain separate obligations.
   Review actual lifetime overlap, then exercise
   selected/current/inactive sources, learner staging and reserved completion on
   real owners. `V53ResourceTransferTest` reserves the accounting envelope;
   `V53PublicationCapacityTest` checks conditional-prefix refusal and stable DATA.
   Neither alone proves a simultaneous native physical maximum. The
   [native process v2 entry](PHASE_3_NATIVE_PROCESS_JOINT_FLOOR.md) now reuses the
   killed owner's exact receiving directories and budget. Its independent reader
   derives interrupted/resumed writers and cold scratch cleanup from original bytes,
   with twenty-one targeted negatives; transient acquisition/application publication and the
   complete final-source process matrix remain open.
   The new same-budget current/PROMISE plus receiving-copy histories now qualify
   image-count and exact/one-byte-short staging refusal with physical snapshots,
   including retained failed packet charges and post-refusal allocator force.
   They do not qualify two generations plus the full selected/learner metadata
   maximum, admitted FINAL/application completion or interrupted rotation.
   A new [native pressure probe](PHASE_3_COMBINED_RESOURCE_PROBE.md) failed during
   floor construction with seven live images. It deliberately extends external
   receiving lifetimes, so normal-runtime reachability is unproved. First map
   legitimate controller overlap and required joint quorum sizes, then qualify
   completion/recovery; neither suppress this failure nor assume an eight-image
   limit is the correction.
   The [cold continuation probe](PHASE_3_COLD_RESOURCE_CONTINUATION.md) now
   observes the surviving majority completing the inherited operation while the
   partial-floor voter remains unchanged and fenced. Exact original floor
   completion now has [explicit original-copy storage replay](PHASE_3_PARTIAL_FLOOR_RESUME.md).
   [Automatic resumption](PHASE_3_AUTOMATIC_FLOOR_RESUME.md) now stages exact
   originals sequentially and retains the original deadline and charges. Full
   remote-force/continuation replay and remaining interrupted states stay open.
   [Pending-floor byte reuse](PHASE_3_PENDING_FLOOR_BORROW.md) removes the redundant
   receiving slot for complete four-copy originals. Conditional joint storage
   tests do not replace admitted 5-REPLACE recovery or incomplete-body coverage.
   The new [native 5-REPLACE recovery](PHASE_3_JOINT_FLOOR_RECOVERY.md) now covers
   the complete four-original floor at the actual seed-maintenance boundary:
   exception/close/reopen, native TCP reacquisition and continuation through
   FINAL/BARRIER, with independent storage and catalog replay. It observes seven
   images and five SOURCE slots. Its later [whole-history and continuous-ledger extensions](PHASE_3_JOINT_FLOOR_RECOVERY.md)
   now qualify observed remote forces, exports and physical maintenance. It is
   not process-death or a simultaneous full SOURCE maximum; broader controller
   overlap remains open.
   A [32-history native process entry](PHASE_3_NATIVE_PROCESS_JOINT_FLOOR.md)
   now records actual fresh-JVM acquisition, halt/SIGKILL and same-directory
   continuation. Its composed reader now binds both cold owners to complete
   physical/network/maintenance replay and four continuous ledgers, with sixteen
   targeted negatives. Its v2 scratch reader now derives interrupted/resumed
   writer and cold cleanup charges. The component cohort binds those readers
   and the fixed cut-specific negative vectors; remaining native negative axes,
   transient transport/publication resources and the full final-source matrix
   remain open. Its hosted adapter now prepares one common seed, 32 complete
   originals and 32 downloaded replays. The hosted-plan count is 544; no
   final-source execution is claimed.
   [Partial joint-floor writer coverage](PHASE_3_PARTIAL_JOINT_FLOOR.md) now checks
   all four copy ordinals at four actual handoff-writer boundaries. With two real
   PROMISE sources, all sixteen conditional cases recover within six SOURCE slots
   and seven images; at full occupancy the incomplete last copy is local. This
   narrows the handoff-order gap without claiming native history, torn-file or
   process-death qualification. Non-handoff/context paths remain separate.
   The [native sixteen-history entry](PHASE_3_NATIVE_PARTIAL_JOINT_FLOOR.md) now
   captures actual admitted 5-REPLACE partial-copy cuts through complete TCP
   recovery and FINAL/BARRIER. Complete matrix execution, all negative layers
   and final-source admission remain separate from its local development checks.
3. **Finish concrete protocol coverage.** Map exact schedules, original evidence
   selectors and rejection reasons; identify uncovered combinations. Inapplicable
   operations still require explicit refusal with unchanged bytes. Keep final
   public and combined-hardening obligations with their owning phase.
4. **Implement phase-wide admission.** Require the complete declared subsets,
   original-first replay, exact source/build/toolchain/readers and every
   workflow/run/attempt. Reconcile independent seed provenance. Missing/failed
   histories block acceptance; green summaries cannot replace the gate.
5. **Execute and audit the final source.** Long independent whole histories may
   run in parallel after separate push/dispatch authorization. Retain every failed
   attempt and original ownership chain. Fix reproduced failures, then close only
   the validated Phase 3 scope. This plan authorizes no dispatch.

Items 1 and 2 can be developed independently. Later dependencies are explicit;
the inspector rejects cycles and unknown work. All five gaps remain OPEN. No
duration estimate or completion percentage is inferred from case counts.

## Reproduce the inspection

From the repository root, select a new output directory:

```bash
python3 -B -m scripts.v53.phase3_qualification_plan \
  --output target/v53-phase3-audit/manual-001
python3 -B -m unittest scripts.v53.test_phase3_qualification_plan \
  scripts.v53.test_case_inventory scripts.v53.test_contract_check
```

Output retains the input plan, frozen acceptance plan and a receipt with baseline
HEAD, worktree status, inspected file hashes, actual catalogue member names, open
dependencies and zero newly executed native histories. Inspected bytes are
rechecked before PASS. Existing directories are never overwritten; failure
leaves a failed receipt.

`status=PASS` means **the source inventory is internally consistent**. The report
always says `execution=source-inventory-only`, `qualificationStatus=NOT_EVALUATED`,
`runtimeQualified=false`, `phase3Complete=false` and no covered scenario rows.
No supplied PASS receipt or closure flag can grant acceptance. Inspection runs no
native command, evidence mutation, Maven build, network request or cloud action.
Its hash index covers inspected files, not an entire runtime build.

Local tests cover missing/duplicate obligations, family/phase drift, altered
frozen axes, count/case drift, broken group partitions, missing/linked references,
dependency cycles, invented acceptance, input changes and preservation of
old/failed output. They establish inspector behavior only; no long native
qualification is repeated for this tooling/documentation batch.

Rollback removes this optional inspector, tests, plan and documentation links.
Runtime, record/wire formats, bounds, existing workflows, Required and V5.2
experiments are unchanged.
