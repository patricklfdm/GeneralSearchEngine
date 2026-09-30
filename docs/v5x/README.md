# GeneralSearchEngine V5.x development line

- **Status:** V5.0 published and independently verified; V5.1 Phases 3–5 and 6A/6B accepted; 6C implementation accepted through 6C3C30 independent cleanup state review; native activation pending; V5.2-V5.4 planned
- **Stable comparison release:** GeneralSearchEngine `4.4.0`
- **Architecture boundary:** replicated single-shard search

V5.x builds one replicated group over the frozen V4.4 durable/search semantics. V5.0
first establishes correct replication under one configured leader. Later V5 minors
add automated leadership, explicit replica reads, membership operations and final
hardening. Sharding and distributed query are not V5 work.

## Next development entry

The [development handoff](NEXT_DEVELOPMENT_HANDOFF.md) records the reading order,
review boundaries, source identities and validation guidance in this repository.

**Planning status:** V5.1 Phase 2 was accepted in PR #187 and Phase 3 was separately
authorized by the user. Later-minor/V6 refinements remain proposals; they do not
authorize runtime work, paid execution or publication beyond an accepted phase entry.

Start with the [V5.x roadmap](ROADMAP.md), then the
[proposed next-development addendum](NEXT_DEVELOPMENT_ADDENDUM.md) and
[V5.1 Phase 0 entry plan](v5.1/PHASE_0_ENTRY_PLAN.md). The user subsequently assigned
the design task: its [six-document contract](v5.1/PHASE_0_CONTRACT.md)
records D01-D12 and E01-E12, accepted through PR #184. The user authorized
[Phase 1 foundation](v5.1/PHASE_1_FOUNDATION.md), accepted in PR #185 with exact-master CI
`35491646610`. The user has entered [Phase 2 storage](v5.1/PHASE_2_ENTRY_PLAN.md);
Batch A was accepted in PR #186 with exact-master CI `35495493715`.
[Batch B recovery](v5.1/PHASE_2_RECOVERY.md) was accepted in PR #187 with exact-master
CI `35503107173`. The user entered [Phase 3](v5.1/PHASE_3_ENTRY_PLAN.md); its
[transition kernel](v5.1/PHASE_3_PROTOCOL.md) was accepted in PR #188 with CI `35507802486`.
The [runtime batch](v5.1/PHASE_3_RUNTIME.md) was accepted in PR #189 with CI `35527143425`.
[Phase 3C](v5.1/PHASE_3_REJOIN.md) was accepted in PR #191 with exact-master CI `35542143840`.
[Phase 4A](v5.1/PHASE_4_BOOTSTRAP.md) is accepted in PR #192 (master
`fce35d955e0b6b973014959e23fc38eb95dd2745`, CI `35547603482`).
[Phase 4B](v5.1/PHASE_4_PUBLIC_RUNTIME.md) is accepted through PR #193 (master
`6ca9418ae14bb3434e3ee2aa8dcc6ba2cd7e45b6`, exact-master CI `35554352587`).
[Phase 4C](v5.1/PHASE_4_PUBLIC_QUALIFICATION.md) is accepted through PR #194 (master
`6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4`, exact-master CI `35560692475`).
[Phase 4D](v5.1/PHASE_4_PUBLIC_FAULTS.md) is accepted through PR #195 (master
`da9f3e9fe957e61c0fe45cf041431a5c4c74cd79`, exact-master CI `35570118695`).
[Phase 4E](v5.1/PHASE_4_PUBLIC_RECOVERY.md) is accepted through PR #196 (master
`15eb04054f28ecb52b896eedb79775c257736e00`, exact-master CI `35579584390`).
[Phase 4F](v5.1/PHASE_4_PUBLIC_PROTOCOL.md) is accepted through PR #197 (master
`764cbf4a41bd6afc79e39cb3f97e612a3d66d39d`, exact-master CI `35591386329`).
[Phase 4G](v5.1/PHASE_4_PUBLIC_RECLAMATION.md) is accepted through PR #198 (master
`4833bddf08b95a9cd28d63ee0b1c78e2e3de16dc`, exact-master CI `35664882661`).
[Phase 4H](v5.1/PHASE_4_PUBLIC_BOUNDS.md) is accepted through PR #199 at
`fdf9482781e04727e20326fa0e32bcd281242f04` (exact-master CI `35688926607`).
[Phase 4I](v5.1/PHASE_4_PUBLIC_PROMISES.md) is accepted through PR #200 at
`6a781ac33945016645961ec1c6564d8975cd82fd` (exact-master CI `35693468905`).
[Phase 4J](v5.1/PHASE_4_PUBLIC_CANDIDATES.md) is accepted through PR #201 at
`04106a0c2e88010c2c14c43ad485bc3113ed1d05` (exact-master CI `35698045261`).
[Phase 4K](v5.1/PHASE_4_PUBLIC_PRESSURE.md) is accepted through PR #202 at
`3bb84b250800c7871745450491e56b6821195d1d` (exact-master CI `35705020751`).
[Phase 4L](v5.1/PHASE_4_RESOURCE_LIMITS.md) is accepted through PR #203 at
`a5595f8efad34ec96a3f6e883e5c9c9491004279` (exact-master CI `35712922357`).
[Phase 4M](v5.1/PHASE_4_BACKPRESSURE.md) is accepted through PR #204 / #205
at `39332feb71f877d3cbd976631e8a26a9cf2f607c` (exact-master CI `35753082195`).
[Phase 4N](v5.1/PHASE_4_PUBLIC_SELECTION.md) is accepted through PR #206
at `3f5b0b25b6484bf6ddc062dd25527bee0ddaedb4` (exact-master CI `35779031221`).
[Phase 4O](v5.1/PHASE_4_LIFECYCLE_HARDENING.md) is accepted through PR #207,
master `1a043615ec4a8de5b7f110d999c5f7268e5e165c` (exact-master CI `35794875603`).
[Phase 4P and full Phase 4](v5.1/PHASE_4_FINAL_COVERAGE.md) are accepted through
PR #208, master `b0d586f32b01f59aadfa940d7f778a8a2b5ea078` (exact-master CI `35802660895`).
[Phase 5A](v5.1/PHASE_5_COMBINED_RECOVERY.md) is accepted at master
`04d12316bd6971ac477cfcb08c5073b2252ecf2a` (exact-master CI `35818964327`, all 19 jobs passed).
[Phase 5B](v5.1/PHASE_5_COMBINED_LIFECYCLE.md) is accepted through PR #213 at
`fc1feca4dee6ee346e45d3afb22c4df9b9e0d945` (exact-master CI `35826641489`, all 19 jobs passed).
[Full Phase 5](v5.1/PHASE_5_ACCEPTANCE.md) is accepted through PR #214 at
`15c8c68011e37370dfcd31ee855f91247c3771d8` (docs-only master CI `35830149418`;
unchanged-runtime full CI `35826641489`). The [Phase 6 entry](v5.1/PHASE_6_ENTRY_PLAN.md)
is accepted through PR #215 at `243434f6e1dc94422b57997b33eabb3cc1e8f64d`
(docs-only master CI `35831892351`). The [rich model foundation](v5.1/PHASE_6_MODEL_FOUNDATION.md)
was accepted through PR #216 (master `bcac615aeef93dadcab6636162a86ce2156e5515`,
full CI `35841378072`). The [local runtime candidate](v5.1/PHASE_6_LOCAL_PERFORMANCE.md)
and corrections passed full master CI `35920225478` through PR #219. The
[6A review](v5.1/PHASE_6_LOCAL_ACCEPTANCE.md) reconciles original measurements;
the [6B cloud workload contract](v5.1/PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) adds a
closed fifteen-cell plan and trace-backed local calibration. 6A/6B were accepted
through PR #222. The [6C1 control foundation](v5.1/PHASE_6_REMOTE_FOUNDATION.md)
was accepted through PR #223, exact-master CI `35942555519` (nineteen jobs,
25 V5.1 gates). [6C2A rich JVM integration](v5.1/PHASE_6_REMOTE_RICH.md)
was accepted through PR #224, exact-master CI `35961961431` (twenty jobs,
26 V5.1 gates). The twelve [6C2B faults](v5.1/PHASE_6_REMOTE_FAULTS.md) were
accepted through PR #225. PR #229 accepted the
[full-size runtime](v5.1/PHASE_6_FULL_SIZE_RUNTIME.md) at master
`57622552e02addfae991642786e1a87a0633fb43`, exact-master CI `36094121631`
(all 27 jobs), closing 6C2. The current
[accepted 6C3A control](v5.1/PHASE_6_CLOUD_CONTROL.md) qualifies ownership,
admission and cleanup decisions without GCP. Actual cloud integration remains
open in the [checklist](v5.1/PHASE_6_CHECKLIST.md). PR #230 passed exact-master CI `36105310891`. The
[accepted 6C3B guest/provider gate](v5.1/PHASE_6_CLOUD_PROVIDER.md) adds source-bound
packaging and offline HTTP adapter qualification (PR #231, master CI `36113872308`).
The [6C3C1 guest service](v5.1/PHASE_6_GUEST_SERVICE.md),
[6C3C2 bootstrap](v5.1/PHASE_6_GUEST_BOOTSTRAP.md),
[6C3C3 startup](v5.1/PHASE_6_GUEST_STARTUP.md) and
[6C3C4 helper delivery](v5.1/PHASE_6_GUEST_DELIVERY.md) are accepted through PRs
#232–#235. The [6C3C5 deadline slice](v5.1/PHASE_6_GUEST_DEADLINES.md) is accepted
through PR #236, master `3cf47ac19a71c24fdc1e10689c646c8bbceb0a53`, exact-master
CI `36212673545` attempt 2 (all 27 jobs). The
[6C3C6 root-admission slice](v5.1/PHASE_6_ROOT_ADMISSION.md) is accepted through
PR #237 / master CI `36281785824` attempt 1 (27 jobs). The
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
The following owned controls, complete experiment, read-only preflight and offline
cleanup integration are now accepted through
[6C3C27](v5.1/PHASE_6_CLEANUP_CREDENTIALS.md), PR #261, master
`27d6f7fa23377dbf305a1ac719ac5f8a6e97df9c`, exact-master CI `36695145198`
attempt 1 (all 29 jobs). The [Phase 6 checklist](v5.1/PHASE_6_CHECKLIST.md)
records each intermediate acceptance. The subsequent
[disabled identity configuration](v5.1/PHASE_6_CLEANUP_ACTIVATION_REVIEW.md)
was separately authorized, applied and read back as `STAGED_MATCH` on 2026-09-30.
All three identities/pools/providers remain disabled. Actual-identity permission
qualification, native credential/cleanup activation and remaining remote integration
remain open. Inherited IAM is unassessed under the later scope amendment below.
The [6C3C28 scoped network entry](v5.1/PHASE_6_CLEANUP_NETWORK.md) is accepted
through PR #263, master `e8a349096383a092b47c4ac6774dd3c8f9b12684`, CI
`36706204243`: 29 final successful jobs after failed-job rerun (attempt 2), with
the original public-fault failure retained. The
[6C3C29 deployment review](v5.1/PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md) adds separate
runnable workflow proposals, exact enable/disable plans and read-only state checks.
It is accepted through PR #264/#265, master `5ec1e13d64b3236c4aa87dec2d63496d6ea6d1ed`,
CI `36756473536` attempt 1 (29 jobs). The
[6C3C30 independent state review](v5.1/PHASE_6_CLEANUP_STATE_REVIEW.md) is accepted
through PR #266/#267, corrected master `9243bc31dc3727a132b50740430426b3512fc5c8`,
CI `36785256345` attempt 1 (all 29 jobs). The original outbound-admission failure
and its correction remain recorded. The operator-authorized
[IAM scope amendment](v5.1/PHASE_6_CLEANUP_STATE_REVIEW.md#iam-admission-scope-amendment--2026-09-30)
makes ancestor-policy reads optional without adding permissions. Actual-identity
required/forbidden checks, cleanup activation and provider qualification remain
open; the amendment's protected CI is pending.
Native cloud writes and full 6C remain open; paid experiments require separate
exact-request confirmation and user triggering.

The accepted [V5 charter](DEVELOPMENT_CHARTER.md) and V5.0 records below remain
unchanged. V4.4 is the inherited search/storage reference; published V5.0 is the
immediate replication reference for the next minor. Proposed files do not supersede
accepted guarantees by being newer.

[V6 architecture research](../v6x/README.md) may develop in parallel with V5.x design,
but sharding implementation is not V5 work. The proposed gate for V6 production is
a mature V5.4 replicated-group handoff, not V5.0 publication alone.

## Authority map

- [V5 development charter](DEVELOPMENT_CHARTER.md)
- [V5.x roadmap](ROADMAP.md)
- [V5.0 Phase 0 contract](v5.0/PHASE_0_CONTRACT.md)
- [V5.0 architecture and authority](v5.0/ARCHITECTURE_AND_AUTHORITY.md)
- [V5.0 API and compatibility](v5.0/API_COMPATIBILITY.md)
- [V5.0 protocol, recovery and failure contract](v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md)
- [V5.0 Phase 1 transport and frame decision](v5.0/TRANSPORT_AND_FRAMING.md)
- [V5.0 read-only cloud availability record](v5.0/cloud-availability.json)
- [V5.0 testing and evidence plan](v5.0/TESTING_AND_EVIDENCE.md)
- [V5.0 Phase 0 checklist](v5.0/PHASE_0_CHECKLIST.md)
- [V5.0 Phase 1 entry plan](v5.0/PHASE_1_ENTRY_PLAN.md)
- [V5.0 Phase 1 baseline](v5.0/PHASE_1_BASELINE.md)
- [V5.0 Phase 1 checklist](v5.0/PHASE_1_CHECKLIST.md)
- [V5.0 Phase 1 machine-readable plan](v5.0/phase1-plan.json)
- [V5.0 Phase 2 entry plan](v5.0/PHASE_2_ENTRY_PLAN.md)
- [V5.0 Phase 2 storage format](v5.0/PHASE_2_STORAGE_FORMAT.md)
- [V5.0 Phase 2 baseline](v5.0/PHASE_2_BASELINE.md)
- [V5.0 Phase 2 checklist](v5.0/PHASE_2_CHECKLIST.md)
- [V5.0 Phase 3 entry plan](v5.0/PHASE_3_ENTRY_PLAN.md)
- [V5.0 Phase 3 leader path](v5.0/PHASE_3_LEADER_PATH.md)
- [V5.0 Phase 3 baseline](v5.0/PHASE_3_BASELINE.md)
- [V5.0 Phase 3 checklist](v5.0/PHASE_3_CHECKLIST.md)
- [V5.0 Phase 4 entry plan](v5.0/PHASE_4_ENTRY_PLAN.md)
- [V5.0 Phase 4 recovery and snapshots](v5.0/PHASE_4_RECOVERY.md)
- [V5.0 Phase 4 baseline](v5.0/PHASE_4_BASELINE.md)
- [V5.0 Phase 4 checklist](v5.0/PHASE_4_CHECKLIST.md)
- [V5.0 Phase 5 entry plan](v5.0/PHASE_5_ENTRY_PLAN.md)
- [V5.0 Phase 5 runtime hardening](v5.0/PHASE_5_HARDENING.md)
- [V5.0 Phase 5 baseline](v5.0/PHASE_5_BASELINE.md)
- [V5.0 Phase 5 checklist](v5.0/PHASE_5_CHECKLIST.md)
- [V5.0 public-admission contract amendment](v5.0/PUBLIC_ADMISSION_CONTRACT.md)
- [V5.0 public-admission API delta](v5.0/PUBLIC_ADMISSION_API.md)
- [V5.0 public-admission implementation and acceptance plan](v5.0/PUBLIC_ADMISSION_ENTRY_PLAN.md)
- [V5.0 public-admission Step A foundation](v5.0/PUBLIC_ADMISSION_FOUNDATION.md)
- [V5.0 public-admission Step B offline authority](v5.0/PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md)
- [V5.0 public-admission Step C public runtime](v5.0/PUBLIC_ADMISSION_RUNTIME.md)
- [V5.0 Phase 6 performance and cloud entry plan](v5.0/PHASE_6_ENTRY_PLAN.md)
- [V5.0 Phase 6A local performance and evidence](v5.0/PHASE_6_LOCAL_PERFORMANCE.md)
- [V5.0 Phase 6B cloud runner and preflight](v5.0/PHASE_6_CLOUD_RUNNER.md)
- [V5.0 Phase 6 full cloud workload plan](v5.0/PHASE_6_CLOUD_WORKLOAD_PLAN.md)
- [V5.0 Phase 6 cloud workload and evidence implementation](v5.0/PHASE_6_CLOUD_WORKLOAD.md)
- [V5.0 Phase 6 runner preset qualification](v5.0/PHASE_6_RUNNER_PRESETS.md)
- [V5.0 Phase 6 remote workload execution and evidence](v5.0/PHASE_6_REMOTE_WORKLOAD.md)
- [V5.0 Phase 6C cloud setup and readiness](v5.0/PHASE_6_CLOUD_SETUP.md)
- [V5.0 Phase 6 cloud baseline](v5.0/PHASE_6_BASELINE.md)
- [V5.0 Phase 6 canonical review](v5.0/PHASE_6_CANONICAL_REVIEW.md)
- [V5.0 Phase 6 checklist](v5.0/PHASE_6_CHECKLIST.md)
- [V5.0 cloud baseline registry](v5.0/cloud-benchmark-baselines.json)
- [V5.0 Phase 7 acceptance](v5.0/PHASE_7_CHECKLIST.md)
- [V5.0 release reconciliation](v5.0/RELEASE_CHECKLIST.md)
- [V5.0 release notes](v5.0/RELEASE_NOTES.md)
- [V5.0 public-admission 1.1 byte specification](v5.0/PUBLIC_ADMISSION_FORMAT_1_1.md)
- [Published V4.4 to V5 handoff](../v4x/v4.4/V5_HANDOFF.md)

Phase 0 was accepted through protected PR #145 at `105537c8`; exact-master CI run
`34919817954` passed. Phase 1 was accepted through protected PR #146 at `2e78bddd`;
exact-master CI `34930568130` passed. Phase 2 was accepted through protected PR #147 at `1895598`; exact-master CI
`34934537274` passed. Phase 3 was accepted through protected PR #148 at `911c9de`;
exact-master CI `34940262703` passed. Phase 4 was accepted through protected PR #149
at `a67e654`; exact-master CI `34950041552` passed. Phase 5 was accepted through
[PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150) at `4a8fd3d`;
[exact-master CI 34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066)
passed with the Phase 1–5 gates executed. The public bootstrap/lifecycle contract
amendment was accepted in PR #151 and [Step A](v5.0/PUBLIC_ADMISSION_FOUNDATION.md) in PR #153.
[Step B offline authority](v5.0/PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md) was accepted in PR #154,
with exact-master CI `35020203126` passing. [Step C public runtime](v5.0/PUBLIC_ADMISSION_RUNTIME.md)
was accepted through [PR #155](https://github.com/patricklfdm/GeneralSearchEngine/pull/155)
at `836137aba672c010d0c7e3fc07bc194359543d9f`, with
[master CI 35031124266](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35031124266)
passing all admission and Phase 1–5 gates. The [Phase 6 entry plan](v5.0/PHASE_6_ENTRY_PLAN.md)
was accepted in PR #156 at `3eb0dc1067b3001c04768190a2844be69c137da3`, with
[master documentation CI 35039318340](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35039318340)
passing. [6A local performance and evidence](v5.0/PHASE_6_LOCAL_PERFORMANCE.md) was
accepted in PR #157 with exact-master CI `35043760510` passing.
[6B cloud runner and preflight](v5.0/PHASE_6_CLOUD_RUNNER.md) was accepted through
[PR #158](https://github.com/patricklfdm/GeneralSearchEngine/pull/158) at
`72137865f39535e8f41052b455bbfdd0e01be163`, with
[master CI 35051728286](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35051728286)
passing all six jobs and executing 6A/6B. The
[full cloud workload plan](v5.0/PHASE_6_CLOUD_WORKLOAD_PLAN.md) was accepted in PR #159
with master documentation CI `35053778177` passing.
[Cloud workload and evidence](v5.0/PHASE_6_CLOUD_WORKLOAD.md) were accepted in PR #160
with exact-master full CI `35058372449`.
[Runner preset qualification](v5.0/PHASE_6_RUNNER_PRESETS.md) was accepted through
PR #161/#162 and exact-master CI `35069706211`.
[Remote workload execution and evidence](v5.0/PHASE_6_REMOTE_WORKLOAD.md) was accepted
through PR #163 and exact-master CI `35079404376`. Setup/preflight was accepted
through PR #164 and exact-master CI `35089239868`. Subsequent runner corrections
culminated in measured source `340df06148bc7d5a25a29a55c3ee928c9472dd09`, with full
CI `35384694759`. Three canonical repetitions, experiment and failure-drill now
pass all 49 cell executions and independent complete-set validation. The
[6D review](v5.0/PHASE_6_CANONICAL_REVIEW.md) records measurements, cleanup, retention
and the user-authorized pre-candidate IAP rollback. The
[registration checklist](v5.0/PHASE_6_CHECKLIST.md) is closed by PR #179/#180 and
exact-master CI `35421934224` at `3e5da79c0fae47d4d1e8e50022c928fb3d0b1d60`.
[Phase 7](v5.0/PHASE_7_CHECKLIST.md) was accepted through PR #181 at
`e6afb5349c018fe163d4938d7637a4de8854d4ea`, with exact-master CI `35427118768`.
Phase 8 published signed tag `v5.0.0` through workflow `35428718030`; all twelve
published files pass signature/checksum verification, all nine canonical JAR hashes
match Central, and clean V1–V5 consumers pass. See the
[migration guide](v5.0/MIGRATION_GUIDE.md), [release checklist](v5.0/RELEASE_CHECKLIST.md)
and [release notes](v5.0/RELEASE_NOTES.md).
