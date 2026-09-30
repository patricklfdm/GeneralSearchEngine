# V5.1 Phase 6 checklist

**Status:** entry/model foundation accepted; runtime and its corrections merged
through PR #219 at `54e203eeca6c087b7ba03954d546c7682e8338f2`. Exact-master CI
`35920225478` passed all nineteen jobs and all 24 V5.1 verification steps, including
public bounds, resources and local performance. The [6A acceptance record](PHASE_6_LOCAL_ACCEPTANCE.md)
reconciles original evidence and downloaded replay. Its final review and the [6B cloud contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md)
were subsequently accepted through PR #222 as recorded below.
PR #220 merged these candidates at `717bed8f578019c71ffe3d739deaf067ec0fa8d2`.
Master CI `35927462738` passed the performance gate but failed Phase 5A's
[post-restart write assumption](PHASE_5_COMBINED_RECOVERY.md#post-pr-220-correction-a-recovered-read-does-not-lease-leadership).
PR #221 merged the recovery-write correction at `af68d8473f9998628e49189a2d8be658b8bfe116`.
Master CI `35932225694` then failed the
[per-round proof sampling boundary](PHASE_5_COMBINED_RECOVERY.md#post-pr-221-correction-confirm-proof-before-recording-a-drained-round)
and a [V5.0 retry fixture](../v5.0/PHASE_5_HARDENING.md#post-pr-221-follow-up-target-the-add-exchange).
PR #222 accepted both corrections at `33aa89bf8a6b4b0587fa6a127e481d73671a60ec`.
Exact-master CI `35937300754` passed all nineteen jobs and 24 V5.1 verification steps.
6A/6B are accepted. [6C1 remote control foundation](PHASE_6_REMOTE_FOUNDATION.md)
was accepted through PR #223, master `833da4947266b4edfbee2a0e6fe10055ed3be00c`;
exact-master CI `35942555519` passed all nineteen jobs and 25 V5.1 verification steps.
[6C2A rich JVM integration](PHASE_6_REMOTE_RICH.md) was accepted through PR #224,
master `28cd5edc0a63fd82a9c01dad028623acc529c9f2`, exact-master CI `35961961431`
(twenty jobs, 26 V5.1 gates). The [6C2B fault workloads](PHASE_6_REMOTE_FAULTS.md) were accepted through PR #225,
master `22328ed4dc358e0adc7fde1399528295ebf8d2a3`, exact-master CI `35989431966`
(all 21 jobs). PR #227 closed [rich CI sharding](../../CI_V51_RICH_SHARDS.md) at
`2db90846606547325c2f35a466813c622cc1ffac`, exact-master CI `36064320654` (all 26 jobs).
The [512-slot component gate](PHASE_6_FULL_SIZE.md) was accepted through PR #228,
master `3c3d9d19c8aa1d24aa88f971c983235bd186033d`, exact-master CI `36072038218`.
[Public 512-slot runtime integration](PHASE_6_FULL_SIZE_RUNTIME.md) was accepted
through PR #229 at `57622552e02addfae991642786e1a87a0633fb43`, exact-master CI
`36094121631` (all 27 jobs). 6C2 is closed. The
[6C3A owned control implementation](PHASE_6_CLOUD_CONTROL.md) is accepted through
PR #230, master `2db3ebb645907eaa8b02fa849302c35accb03ff4`, exact-master CI
`36105310891`. The [6C3B guest/provider gate](PHASE_6_CLOUD_PROVIDER.md) is accepted through
PR #231, master `5b101a6e73a83ef9091ea369997f4d01e6ca4c26`, CI `36113872308`.
The [6C3C1 guest slice](PHASE_6_GUEST_SERVICE.md) is accepted through PR #232,
master `2183dafa618238f0b824fc0a3b3d42624ce24782`, CI `36124423253` (27 jobs).
The [6C3C2 bootstrap slice](PHASE_6_GUEST_BOOTSTRAP.md) is accepted through PR #233,
master `d27da43086406384ab41cab6704541015aa0a1bf`, CI `36149275698` (27 jobs).
The [6C3C3 owned startup slice](PHASE_6_GUEST_STARTUP.md), accepted through PR #234 /
CI `36185893530` attempt 2 (27 jobs), adds numeric-ID facts,
Linux observations, one-shot modeled disk setup and retained cleanup/accounting.
The [helper delivery slice](PHASE_6_GUEST_DELIVERY.md) is accepted through PR #235,
master `d40d7d8be1320a3e989ab551536715f4e47795be`, exact-master CI `36206334728`
attempt 1 (27 successful jobs). The [6C3C5 deadline slice](PHASE_6_GUEST_DEADLINES.md)
is accepted through PR #236 / exact-master CI `36212673545` attempt 2 (27 jobs).
The [6C3C6 root-admission slice](PHASE_6_ROOT_ADMISSION.md) is accepted through
PR #237 / exact-master CI `36281785824` attempt 1 (27 jobs).
[6C3C7 package/services](PHASE_6_PACKAGE_DELIVERY.md) is accepted through
PR #238, master `ef7562bc60a0a15ab4202367c5e286fe6250cbdb`, exact-master CI
`36302498537` attempt 2 (all 27 jobs). The initial rich healthy failure remains
recorded; its successful rerun does not establish a timing cause. The
[6C3C8 owned services](PHASE_6_OWNED_SERVICES.md) is accepted through
PR #239, master `1feeb2f1941367ef29cbb1cdabd3cead6715ebb8`, exact-master CI
`36370271323` attempt 2 (all 27 jobs). Attempt 1's automatic-healthy lane-busy
failure remains recorded; the rerun does not establish its cause. The
[6C3C9 guest evidence](PHASE_6_GUEST_EVIDENCE.md) is accepted through PR #240,
master `0ef49cb8f5f6c793b9fe03db4b4069dd04e059ac`, exact-master CI `36378226619`
attempt 1 (all 27 jobs). It independently validates the existing guest warmups;
complete owned workload execution remains open.
The [6C3C10 owned bootstrap](PHASE_6_OWNED_BOOTSTRAP.md) is accepted
through PR #241, master `87e0cdda3f38dbadce149e54eb1cc45f0f634e28`, exact-master CI
`36388477710` attempt 1 (all 27 jobs). The original non-private mount-backing
failure remains recorded. The [6C3C11 source transfer](PHASE_6_SOURCE_TRANSFER.md) is accepted
through PR #242, master `41bee83b675bdd903d335fc9f1e0cc62cb350429`, exact-master CI
`36395914043` attempt 1 (all 27 jobs). The
[6C3C12 source producer](PHASE_6_SOURCE_PRODUCER.md) is accepted through PR #243, master
`eb56fa6d2565770bd8aac7f76e484834f563a0f3`, exact-master CI `36407418156`
attempt 1 (all 27 jobs). Its original hardening and warmup timing failures remain
recorded; the successful run does not establish a timing cause. The
[6C3C13 owned healthy tape](PHASE_6_OWNED_WORKLOAD.md) is accepted through
PR #244, master `71ca5d9e52139815a5bd4dfddf330c4d0d9fe800`, exact-master CI
`36462747697` attempt 1 (all 27 jobs). The original large-part collection failure
and diagnostic replay remain recorded. The [6C3C14 physical evidence](PHASE_6_OWNED_PHYSICAL_EVIDENCE.md)
is accepted through PR #245, master `d07fe8a5ca27e28ebf1b20c157337ed0f078ea5e`,
exact-master CI `36486236193` attempt 1 (all 27 jobs). It qualifies each stopped
voter's own authority and joint force/publication/read replay for the 90-call tape.
The [6C3C15 backup/restore](PHASE_6_OWNED_BACKUP.md) is accepted through
PR #246, master `2846bbc2758f2336e0ed73dbc45001dfe83d8f6a`, exact-master CI
`36498232963` attempt 1 (all 27 jobs), including the owned Linux backup/restore gate.
The [6C3C16 configured healthy control](PHASE_6_OWNED_CONFIGURED.md) is accepted
through PR #247, master `dfae45670330ffe2a3974982bcc020c534861309`, exact-master CI
`36505526404` attempt 1 (all 27 jobs), including the configured Linux workload gate.
The [6C3C17 published V4.4 healthy control](PHASE_6_OWNED_V44.md) is accepted
through PR #248, master `b6c055df306e9e8dbb155924fa4a834fe751e786`, exact-master CI
`36514227052` attempt 2 (all 27 jobs). Attempt 1's V5.0 prerequisite-build failure
remains recorded; retry success does not establish its cause.
The [6C3C18 configured physical/backup evidence](PHASE_6_OWNED_CONFIGURED_EVIDENCE.md)
was accepted through PR #249, master `7273f00ce8f291797c2d74cd9d830b4f993aaceb`,
exact-master CI `36523283002` attempt 2 (all 27 jobs). Attempt 1's automatic-healthy
rich shard failure remains recorded; retry success does not establish its cause.
The [6C3C19 three-mode owned healthy integration](PHASE_6_OWNED_THREE_MODE.md)
was accepted through PR #250, master `2f8da1d96a1080a4c8f29d89d71b984e10722b58`,
exact-master CI `36534342886` attempt 2 (all 27 jobs). Attempt 1's healthy lane
occupancy and concurrent burst-spread failures remain retained; a successful
rerun does not establish their scheduling cause.
The [6C3C20 owned experiment fault qualification](PHASE_6_OWNED_EXPERIMENT_FAULTS.md)
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
New identities remain unapplied. The 6C3C24 retained cleanup reconstruction was
accepted through PR #256, master `2ea9dbbfbf2821afc859663c87925a0e1d93322c`,
exact-master CI `36655860450` attempt 1 (29 jobs). The 6C3C25 native record formats
and closed cleanup HTTP policy were accepted through PR #257, master
`133b05e5cc02560877a74902911b21efacf2ba4c`, exact-master CI `36664035569` attempt 2
(29 jobs). Attempt 1's automatic-healthy warmup `LANE_BUSY` remains recorded;
retry success does not establish its latency cause. The 6C3C26 candidate adds
bound manual/scheduled cleanup entries, inactive workflow proposals and 28
fresh-process offline entry cases. Native IAM/cleanup activation and paid admission
remain open.
Native cloud writes and full 6C remain open; paid experiments require separate
exact-request confirmation and user triggering.
Governing documents: [entry plan](PHASE_6_ENTRY_PLAN.md),
[local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md).

- [x] Phase 5 accepted through PR #214, master `15c8c68011e37370dfcd31ee855f91247c3771d8`.
- [x] Exact-master docs CI `35830149418` and unchanged-runtime full CI `35826641489` distinguished.
- [x] Local corpus/control/mode semantics, counts, timing, resource/evidence bounds and independent validation specified.
- [x] Cloud E-row mapping, planning ceilings, operator sequence choices and fresh admission boundaries specified.
- [x] Protected entry/local-contract acceptance: PR #215, master `243434f6e1dc94422b57997b33eabb3cc1e8f64d`, docs CI `35831892351`.
- [x] 6A model candidate: closed machine-readable preset, independent rich decoder/projection and adversarial fixtures.
- [x] 6A model candidate: 90-call published V4.4 semantic execution, actual backup/checkpoint/reopen checks and three isolated core compilations.
- [x] Protected acceptance of the [model foundation](PHASE_6_MODEL_FOUNDATION.md): PR #216, master `bcac615aeef93dadcab6636162a86ce2156e5515`, exact-master full CI `35841378072`.
- [x] 6A implementation candidate: materialized plan/schema and isolated external published-control/candidate probes.
- [x] 6A local implementation: all three healthy modes and bounded concurrent failover/rejoin history pass.
- [x] PR #217 runtime implementation merged; exact-master CI `35889987294` passed all nineteen jobs.
- [x] Resource recovery follow-up: corrected-runtime resource/performance gates passed exact-master CI `35920225478`.
- [x] 6A runtime: physical/semantic/timing/resource negatives, relevant regressions and exact-source full CI pass at PR #219.
- [x] 6A review candidate: original downloaded performance evidence independently revalidated; receipt/source/member identities retained.
- [x] Protected acceptance of final 6A review and portable replay: PR #222, exact-master CI `35937300754`.
- [x] 6B candidate: trace-backed local calibration and synthetic full-slot encoding retained, with cloud execution explicitly absent.
- [x] 6B candidate: closed cloud plan, three rich tapes, fifteen cells, exact allocations, evidence ceilings and numerical completion criteria.
- [x] 6B: workload hash/calibration accepted through PR #222; full rich concurrency/remote schedule execution remains a 6C prerequisite.
- [x] 6C1 implementation candidate: durable command claims, fixed-arrival executor, disjoint time accounting and bounded binary evidence parts.
- [x] 6C1 local control qualification: real lost-response/duplicate/SIGKILL/cancel processes, complete synthetic tapes and independently checked collection.
- [x] 6C1 protected acceptance: PR #223, exact-master CI `35942555519`; control-only receipts do not qualify a GSE workload.
- [x] 6C2A implementation candidate: persistent JVM lanes, full frozen rich tapes, concurrent captured-cut oracle and portable binary replay.
- [x] 6C2A protected acceptance: PR #224, exact-master CI `35961961431`.
- [x] 6C2B fault implementation: twelve frozen public JVM schedules, bounded history/physical/resource validation and binary replay.
- [x] 6C2B fault-document amendment and fault qualification protected acceptance: PR #225, exact-master CI `35989431966`.
- [x] 6C2 full-size component implementation candidate: 512 forced slots, real TCP chunks, same-slot reproposal, pinned application view and two generations.
- [x] 6C2 component protected acceptance: PR #228, exact-master CI `36072038218`.
- [x] 6C2 public 512-slot runtime accepted through PR #229 (exact-master CI `36094121631`): public recovery/pinned read, complete transfer and terminal full-basis selection.
- [x] 6C2 full-size boundary: 512 actual slots, full basis/wire/transfer/re-proposal/pin and two-generation retention.
- [x] 6C2: persistent JVM adapter, full rich concurrent cut validation, twelve fault cells and full-size retention qualification.
- [x] 6C3A implementation candidate: source-bound control admission, append-only budget/sequence, exclusive lease, original-command polling, exact-ID cleanup and retained no-GCP failures.
- [x] 6C3A protected acceptance of the control-only gate through PR #230 / exact-master CI `36105310891`.
- [x] 6C3B implementation candidate: source/build-bound guest package and generation/operation/ID-bound HTTP adapters, with live mutations disabled.
- [x] 6C3B protected acceptance through PR #231 / exact-master CI `36113872308`.
- [x] 6C3C1 implementation candidate: packaged persistent guest, explicit endpoints, receipt-only reconnect and binary transport qualification.
- [x] 6C3C1 protected acceptance: PR #232, exact-master CI `36124423253`.
- [x] 6C3C2 implementation candidate: exact-path bootstrap, independent mount views, SSH access/host-key binding and offline volume planning.
- [x] 6C3C2 protected acceptance: PR #233, exact-master CI `36149275698`.
- [x] 6C3C3 implementation candidate: owned facts/host pins, disk observations and once-only offline startup qualification.
- [x] 6C3C3 protected acceptance: PR #234, exact-master CI `36185893530` attempt 2; the initial arrival-spread failure remains retained.
- [x] 6C3C4 implementation candidate: [authenticated helper delivery](PHASE_6_GUEST_DELIVERY.md), consumed claims and real loopback SSH receipt queries.
- [x] 6C3C4 protected acceptance: PR #235, exact-master CI `36206334728` attempt 1, all 27 jobs.
- [x] 6C3C5 implementation candidate: guest-clock deadline mapping, boot identity and retained non-renewing installation budgets.
- [x] 6C3C5 Linux SSH qualification and protected acceptance: PR #236, exact-master CI `36212673545` attempt 2.
- [x] 6C3C6 implementation candidate: trusted root receiver, consumed admission/deadline claim, verified helper self-check and isolated root/controller qualification.
- [x] 6C3C6 protected CI and exact-master acceptance: PR #237, master `de3264cb41e594e10e641748d1cdd75fe7c3a8ad`, CI `36281785824` attempt 1.
- [x] 6C3C7 implementation candidate: bounded complete-package transfer, consumed claims and delivered persistent services over SSH.
- [x] 6C3C7 protected acceptance: PR #238, exact-master CI `36302498537` attempt 2 (27 jobs).
- [x] 6C3C8 implementation candidate: fresh mount/service admission and owned stop/retention/cleanup integration, qualified offline and through loopback SSH.
- [x] 6C3C8 protected acceptance: PR #239, exact-master CI `36370271323` attempt 2 (27 jobs); initial automatic-healthy failure retained.
- [x] 6C3C9 implementation candidate: [independent guest warmup evidence](PHASE_6_GUEST_EVIDENCE.md), controller/JVM/scheduler binding and logical/resource replay.
- [x] 6C3C9 protected acceptance: PR #240, master `0ef49cb8f5f6c793b9fe03db4b4069dd04e059ac`, CI `36378226619` attempt 1 (all 27 jobs).
- [x] 6C3C10 implementation candidate: [owned initial bootstrap](PHASE_6_OWNED_BOOTSTRAP.md) before service admission, using shared local source paths and SSH controls.
- [x] 6C3C10 protected Linux qualification and exact-master acceptance: PR #241, CI `36388477710` attempt 1.
- [x] 6C3C11 implementation candidate: [bounded source transfer](PHASE_6_SOURCE_TRANSFER.md), receiver-local import and consumed chunk claims.
- [x] 6C3C11 protected Linux qualification and exact-master acceptance: PR #242, CI `36395914043` attempt 1.
- [x] 6C3C12 implementation candidate: [authenticated producer and download](PHASE_6_SOURCE_PRODUCER.md), one preparation and bounded immutable reads.
- [x] 6C3C12 protected Linux qualification and exact-master acceptance: PR #243 / CI `36407418156` attempt 1 (27 jobs).
- [x] 6C3C13 implementation candidate: [owned automatic healthy tape](PHASE_6_OWNED_WORKLOAD.md), 90 calls and independent logical replay.
- [x] 6C3C13 protected acceptance: PR #244 / CI `36462747697` attempt 1 (27 jobs).
- [x] 6C3C14 implementation candidate: [joint owned physical evidence](PHASE_6_OWNED_PHYSICAL_EVIDENCE.md), sealed authority, force/publication/read replay and rejection controls.
- [x] 6C3C14 protected acceptance: PR #245 / CI `36486236193` attempt 1 (27 jobs).
- [x] 6C3C15 implementation candidate: [owned healthy backup/restore](PHASE_6_OWNED_BACKUP.md), original auxiliary barrier, independent bytes and separate published V4.4 restore.
- [x] 6C3C15 protected acceptance: PR #246 / CI `36498232963` attempt 1 (27 jobs).
- [x] 6C3C16 implementation candidate: [owned configured healthy tape](PHASE_6_OWNED_CONFIGURED.md), once-only node-1 activation and independently replayed 90-call published V5.0 control.
- [x] 6C3C16 protected acceptance: PR #247 / CI `36505526404` attempt 1 (27 jobs).
- [x] 6C3C17 implementation candidate: [owned V4.4 healthy tape](PHASE_6_OWNED_V44.md), one authenticated source/issuer and independently replayed 90-call published control.
- [x] 6C3C17 protected acceptance: PR #248 / CI `36514227052` attempt 2 (27 jobs).
- [x] 6C3C18 implementation candidate: [configured physical/backup evidence](PHASE_6_OWNED_CONFIGURED_EVIDENCE.md).
- [x] 6C3C18 protected acceptance: PR #249 / CI `36523283002` attempt 2 (27 jobs).
- [x] 6C3C19 implementation candidate: [one-lease three-mode healthy integration](PHASE_6_OWNED_THREE_MODE.md).
- [x] 6C3C19 protected Linux qualification and exact-master acceptance: PR #250 / CI `36534342886` attempt 2.
- [x] 6C3C20 implementation candidate: [owned leader-loss and no-quorum](PHASE_6_OWNED_EXPERIMENT_FAULTS.md).
- [x] 6C3C20 protected native-UID qualification and exact-master acceptance (PR #251, CI `36551903980`).
- [x] 6C3C21 implementation candidate: [owned complete experiment](PHASE_6_OWNED_EXPERIMENT.md).
- [x] 6C3C21 protected complete experiment qualification and exact-master acceptance: PR #252 / CI `36566870122` attempt 1 (29 jobs).
- [x] Complete owned experiment preset: healthy, leader-loss, maintenance and no-quorum in one execution.
- [x] 6C3C22 implementation candidate: [source/provider observations and independent manual workflows](PHASE_6_CLOUD_PREFLIGHT.md).
- [x] 6C3C22 corrected-source protected CI and read-only provider qualification: PR #254 / CI `36635538287`, preflight `36643330675`.
- [x] Observer WIF/IAM/environment and Private Google Access configured with authorization; explicit settings read back.
- [ ] Effective organization/folder IAM review (parent policy read remains unavailable).
- [x] 6C3C23 implementation candidate: [disabled runner/cleanup identities and explicit read-back audits](PHASE_6_CLOUD_IDENTITIES.md).
- [x] 6C3C23 protected acceptance: PR #255 / CI `36648030423`, all 29 jobs.
- [x] Separately authorized disabled identity application and exact readback on 2026-09-30: 45 commands, 33 audit reads, `STAGED_MATCH`; all identities remain disabled.
- [ ] Native identity/cleanup activation review and qualification.
- [x] 6C3C24 implementation candidate: [retained cleanup reconstruction](PHASE_6_CLOUD_CLEANUP.md), shared reconciliation and fresh-process HTTP qualification.
- [x] 6C3C24 protected acceptance: PR #256 / CI `36655860450`, attempt 1, all 29 jobs.
- [x] 6C3C25 implementation candidate: [native formats and cleanup HTTP policy](PHASE_6_NATIVE_CLEANUP.md), shared invariants and offline native-format reconstruction.
- [x] 6C3C25 protected acceptance: PR #257 / CI `36664035569`, attempt 2, all 29 jobs.
- [x] 6C3C26 implementation candidate: [bound cleanup entries and inactive workflow proposals](PHASE_6_CLEANUP_ENTRIES.md), both entries through shared native reconciliation.
- [x] 6C3C26 corrected-source protected acceptance: PR #259 / CI `36679824140`, attempt 1, all 29 jobs.
- [x] 6C3C27 implementation candidate: [bound cleanup credential exchange](PHASE_6_CLEANUP_CREDENTIALS.md), exact identity, expiry-aware refresh and integrated offline reconciliation.
- [x] 6C3C27 corrected-source protected acceptance: PR #261 / CI `36695145198`, attempt 1, all 29 jobs.
- [x] [Disabled identity configuration and activation review](PHASE_6_CLEANUP_ACTIVATION_REVIEW.md): authorized staging applied/read back; inherited IAM and native activation remain open.
- [x] 6C3C28 implementation candidate: [scoped cleanup network API and formal entry](PHASE_6_CLEANUP_NETWORK.md), shared reconciliation and loopback TLS failure qualification.
- [x] 6C3C28 protected acceptance: PR #263 / CI `36706204243`, final 29 jobs successful after failed-job rerun (attempt 2); original public-fault failure retained.
- [x] 6C3C29 implementation candidate: [cleanup deployment review package and readback](PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md); no workflow deployment or identity enablement.
- [ ] 6C3C29 corrected-source protected CI acceptance.
- [ ] Real-provider cleanup, identity and activation qualification.
- [ ] Native cloud source transport and complete owned engine workload cells (controlled SSH source transfer/producer accepted through 6C3C11/12).
- [ ] Remaining 6C3C: actual cloud SSH/mount setup, complete remote faults and evidence validation.
- [ ] 6C3: V5.1 runner, workflows, identities, remote adapter and same-path fake failures qualified.
- [ ] 6C: fresh configuration/IAM/image/quota/retention/cleanup readiness; exact-source full CI.
- [ ] 6D: priced complete-sequence request and fresh user confirmation; user-triggered paid execution only.
- [ ] 6D: experiment and failure-drill independently valid, with failures/costs retained.
- [ ] 6D: all three canonical repetitions valid on one admitted source/artifact/workload set.
- [ ] 6D: every member's raw evidence retained and cleanup/absence verified; no leftovers.
- [ ] 6E: independent set review and append-only baseline registration accepted.
- [ ] Full Phase 6 acceptance; only then a separate Phase 7 entry.

An entry merge does not check implementation or cloud boxes. The current
`scripts/v51/cloud_plan.py` is fake-control-plane-only. Existing V5.0 cloud evidence,
cleanup receipts, budget approvals and sequences do not satisfy V5.1 admission.
