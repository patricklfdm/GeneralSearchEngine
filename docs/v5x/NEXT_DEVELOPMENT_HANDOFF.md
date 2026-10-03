# Next-development documentation handoff

**Status:** local documentation integration and review record, 2026-09-19.
The V5.1-V5.4 refinements and V6 preview remain PROPOSED. Integration does not
constitute protected acceptance of a protocol or authorization to implement it.

**Reviewed source:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

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
Grace WAITING and expired cleanup/audit review remain pending on that exact source.
The [scheduled cleanup entry](v5.1/PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md#scheduled-deployment-candidate--2026-10-02)
is prepared on a branch; the user holds merge until reporting the two follow-ups
and their independent review. Preserve the original collector checkout. Schedule
and runner identities remain disabled; schedule enablement needs its separate
review/approval after protected acceptance. Do not resume the failed preparation
or declare full topology/cleanup readiness from preparation or active WAITING.
The user approved the [USD 200 cumulative ceiling](v5.1/PHASE_6_CLOUD_CONTROL.md#approved-cumulative-ceiling-amendment--2026-10-01);
the single-disk proposal stays USD 1 and previous charges remain recorded.
Keep the 5400+1080-second real wait, existing authority and failed charges; no
backdating, fake-record upload or ledger reset. Conditional object/IAP and actual
resource/failure-path qualification remain open; empty PASS is not full readiness.
Native cloud writes and full 6C remain open; paid experiments require separate
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
