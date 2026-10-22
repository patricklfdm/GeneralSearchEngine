# V5.3 development status

## 2026-10-21 — local entry

- Created `feat/v53-cluster-operations` from merged master
  `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`.
- Reviewed actual three-voter configuration, fixed two-basis/proof path, ranked
  ballot checks, manifest-bound frames and V5.2 read-token identity.
- Added the local batching/integration policy, Phase 0 decisions, bounded scope
  proposal and independent evidence plan.
- V5.2 native run `39678504498/1` was in progress at entry. Its state is an
  observation, not V5.2 acceptance or permission to alter its experiment.

Phase 0 is **OPEN**. No V5.3 Java/API/POM/CI change, runtime acceptance, published
predecessor pin or cloud result exists at this entry.

## 2026-10-21 — executable quorum/certificate research

- Added an independent Python model with an explicitly bounded six-identity domain
  and all one-voter add/remove/replace transitions between stable sets of 3–5.
- Complete traversal: **PASS**, 41 configurations, 510 transitions, 12,480 receipt
  subsets, 53,760 certificate checks and 82,770 quorum intersection checks.
- Retained concrete direct-switch, either-majority and union-majority counterexamples.
  Rejected 19 receipt-context/voter mutations after original positive validation.
- **18 tests PASS**, including three deliberately faulty implementations,
  incomplete exploration/non-overwrite behavior and rejection under Python `-O`.
- Local logs: `target/v53-membership-entry/unit-tests.log` and
  `target/v53-membership-entry/quorum-research-20261021/receipt.json`.
  A small tracked copy is [membership-research.json](membership-research.json).
- The receipt honestly records design commit `0326655d1c9033aefebf3b2ea628a3825e297dd5`
  plus the then-uncommitted model files' SHA-256 hashes. It is not relabelled as
  clean-HEAD CI. Compare those bytes to the subsequent model commit for provenance.

No production model was imported by this research checker. No Maven workload,
cloud operation or existing CI job was run or changed for this batch. Documentation
paths and whitespace checks passed. There is no hosted acceptance result.

## 2026-10-21 — durable ballot and recovery research

- Added a single-slot event model with distinct message delivery, disk force,
  frozen-basis replies, crash/restart, ballot selection and ACCEPT/PROOF phases.
  It uses an already established old/joint/new view; it does not activate views.
- **40 tests PASS** across both research suites. New coverage includes two live
  candidates racing PREPARE/ACCEPT at their shared voter, all six before/after-force
  crash cuts, duplicate/lost/delayed replies, removed/learner exclusion, optimized
  Python rejection, retained failure traces and non-overwriting CLI output.
- The history oracle catches five deliberately unsafe implementations with their
  specific safety exceptions. An executable direct-switch counterexample passes
  isolated configuration checks but fails the combined root/index check.
- Complete declared schedule matrix: **2,884 cases, 21 contexts, 340,850 events,
  2,884 recovered publications**. Four fault/recovery families cover all ordered
  pairs of inclusion-minimal quorums in seven size/change profiles and three views.
  This is not an enumeration of every asynchronous interleaving.
- **14 retained histories replayed** from JSON: 12 positive examples and the two
  conflicting direct-switch histories. Trace digest and exact model/test hashes
  are recorded in [ballot-research.json](ballot-research.json).
- Evidence: `target/v53-ballot-research/qualification/`, test log
  `target/v53-ballot-research/unit-tests-qualification.log`, resource log
  `target/v53-ballot-research/qualification-resources.log`. Earlier local attempts
  remain in the same parent directory, including the intermediate CLI inventory
  test failure corrected before final qualification.
- The receipt binds parent `4b9935641b777b35928eebe6d232ba4fe328ad66` and exact
  then-uncommitted source/test bytes. It is local evidence, not clean-source hosted
  CI. No production Java, POM, workflow, release pin or V5.2 cloud operation changed.

The [ballot/handoff research](BALLOT_AND_HANDOFF_RESEARCH.md) records the D01/D03
identity and ballot proposals and the remaining D02/D06 handoff obligations.
**Phase 0 remains OPEN**; this is not production or full distributed-transition
qualification. Only local commits are authorized for this development branch.

## 2026-10-21 — predecessor-certified transition model

- Added an executable multi-slot protocol candidate: old-majority INTENT, joint
  PREPARE/ACCEPT/PROOF for FINAL, then new-majority data. Every receiver derives
  authority from its own forced predecessor chain; no speculative next-slot votes.
- Competing target descriptors share one old-authority slot. Recovery preserves a
  chosen intent even after every acknowledgement is lost. Certificate witness-set
  or ballot changes cannot alter that entry's logical identity.
- **61 tests PASS** across all three research suites. New checks cover learner
  adoption before/after force, lagging/removed leaders, serialized prefix install,
  missing/foreign authority, preserved promises, certificate representation and
  three deliberately unsafe implementations detected by the independent oracle.
- Complete declared transition matrix: **196 cases, 73,835 events, 784 publications**.
  A separate **13-slot** 3→4→5→4→3 walk completed all four changes. This is a bounded
  schedule matrix, not an exhaustive search of asynchronous interleavings.
- **15 retained histories replayed from compressed JSON**. Receipt:
  [transition-research.json](transition-research.json). Evidence directory:
  `target/v53-transition-research/qualification/`; logs:
  `target/v53-transition-research/unit-tests-final.log` and
  `target/v53-transition-research/qualification-resources.log`. The complete command
  took 15.04 seconds, peaked at 100,816 KiB, and retained 159,044 bytes of compressed
  example histories.
- The receipt binds parent `ee0967e` (full SHA inside the receipt) and the exact
  then-uncommitted model/test hashes. Earlier local runs remain in the evidence
  directory. No protected CI, Maven, Java/POM/workflow change or cloud operation.

The [transition research](TRANSITION_CHAIN_RESEARCH.md) records the candidate and
its limits. Its full-chain transfer does not qualify application snapshots or
compaction. D02/D06 have concrete progress but **Phase 0 remains OPEN**. The model
also assumes unique ballot allocation; production global-promise integration,
read policies, operation IDs and physical storage still need their contracts.

## 2026-10-21 — checkpoint, floor and retained authority

- Reviewed the actual V5.2 `AutomaticRecoveryFiles` / `AutomaticStore` selectors,
  complete floor sources, above-floor tail refusal and resumable retirement. Added
  an isolated candidate model for old/joint/new floor authority and exact tail
  preservation through checkpoint and inactive-generation deletion.
- The candidate retains a complete certificate chain, a monotonic abstract root
  promise and an immutable prior basis. It proposes allowing retirement of an
  above-floor ACCEPT only when the exact owned copy is already forced in the
  active generation. This extends the current Java refusal rule; it is not enabled
  in production or claimed to implement global election/activation semantics.
- **85 tests PASS** across all four research suites, including 24 new regressions.
  Coverage includes partial-copy refusal, selector loss, corrupt retirement bytes,
  current-view floor quorums, removed voters, root promise/basis retention,
  interrupted deletion, slot/identity reuse and actual certificate/change limits.
  Five deliberate unsafe implementations fail specific independent-oracle checks.
  Relabelled tail histories cannot substitute for missing coverage cases.
- Complete declared matrix: **42 input histories, 1,080 crash observations and
  16,638 recovery events across those observations**. Prefix events are replayed
  at multiple cuts; this is not 16,638 distinct operations. All **42 final histories**
  replay from compressed JSON, covering 1,164 recovery events and 126 file deletions.
  Each uses the first minimal quorum for its view, not every quorum or interleaving.
- Receipt: [recovery-research.json](recovery-research.json). Evidence:
  `target/v53-recovery-research/final/`; test log:
  `target/v53-recovery-research/unit-tests-final-source.log`; resource log:
  `target/v53-recovery-research/final-resources.log`. Earlier executions remain
  alongside these. The receipt binds parent `5a890bf` and exact uncommitted
  model/oracle/driver/test hashes, not a clean protected-CI source.
  The complete command took **32.63 seconds**, peaked at **114,236 KiB**, and
  retained **201,747 bytes** of compressed examples.
- Research caps refuse history beyond 16 certificates/four INTENTs. Full authority
  remains retained; this is **not** unlimited-history compaction or a production
  storage budget. No Java, POM, workflow, release, Maven or V5.2 cloud operation.

See [the candidate and exclusions](RECOVERY_AND_RETENTION_RESEARCH.md).
**Phase 0 remains OPEN**. D06/D09 now have executable checkpoint/retirement
boundaries; bounded production authority representation and physical behavior
still require specification and qualification.

## 2026-10-21 — global promise and activation adapter

- Audited actual `AutomaticStore.prepare`, `AutomaticRecovery.select`, and the
  PREPARE/INSTALL/ACCEPT/PROOF/publication paths in `AutomaticProtocol`. Added an
  isolated adapter mapping root-wide grants, durable ballot allocation, immutable
  selected quorums and current-ballot barrier publication onto the transition model.
- A grant forced without its basis cannot be resampled at the same ballot. Sources
  unavailable after selection require a fresh campaign; late complete bases cannot
  rewrite the forced selection. All selected installation ACKs precede ACCEPT.
- Added a candidate certificate-derived adoption fence before installing a prefix
  above the retained promise. Crash after fence force retains the higher promise
  and old prefix. This is a proposed new operation, not enabled Java behavior.
  Prefix installation and root-grant writes exclude each other in both orders.
- **109 local tests PASS**, including 24 new tests. Five deliberate unsafe variants
  fail their specific safety checks. Directed cases cover source loss, alternate
  quorum, partial basis, stale installation/callback, accepted INTENT recovery,
  removed proposer, counter exhaustion, lost READY on restart and evidence mutation.
- Complete declared matrix: **420 cases, 1,008 campaigns, 714 completed publication
  callbacks and 434 activations**, with **119,708 adapter events** (including nested
  transition observations). A healthy pre-crash case can activate again after
  restart, so activation count exceeds case count. This is not all interleavings.
- **60 representative histories replayed** after gzip/JSON serialization, covering
  14,656 events and 62 activations. They represent all view/tail/cut combinations
  for the first size profile; every size profile contributes to the full trace digest.
- Receipt: [activation-research.json](activation-research.json). Logs and artifacts:
  `target/v53-activation-research/final/`, `unit-qualified.log` and
  `final-resources.log` in the same parent directory. Earlier local logs remain,
  including the initial mutant-test setup error corrected before qualification.
  The receipt binds parent `aa69189` and exact then-uncommitted model/test bytes;
  it is not a clean-HEAD protected-CI result.
  Final matrix and serialized replay took **40.59 seconds**, peaked at
  **254,380 KiB**, and retained **431,590 bytes** of compressed histories.

See [the actual-code mapping and limits](GLOBAL_PROMISE_AND_ACTIVATION_RESEARCH.md).
**Phase 0 remains OPEN.** Fresh ballots per recovered slot, explicit prefix sync and
certificate-derived adoption are conservative research choices. Production round
policy, bytes, source scheduling, steady-state service and long-lived authority
retention still need resolution. No Java, POM, workflow, Maven or cloud operation.

## 2026-10-21 — authority representation and learner identity

- Read the actual bootstrap/admission, wire, rejoin, local config, store and
  fixed-manifest replacement code. Existing manifest/member guards cannot open
  a non-voter; production remains unchanged.
- Chose a candidate authority representation: new forced majority endorsements
  for stable DATA/BARRIER ranges, with complete INTENT/FINAL certificates retained.
  A finite lifetime membership-change budget refuses new changes without spending
  another change on ordinary DATA. Physical incremental compaction, complete
  identity catalogs and actual byte budgets remain open.
- Added durable exact-cut learner reservation/image/receipt/authority boundaries.
  INTENT commits the full prepared-request hash, including new voter/storage/
  endpoint identity. Restart invalidates old sessions; readiness alone cannot vote.
  `eligible` is an admission result, not a protocol vote or public read.
- The source fixture uses existing voters only. The first matrix exposed a test
  setup problem during review: the generic source builder could use the learner
  in replacement quorums. Corrected the builder and added independent rejection
  of circular preinstalled/voting-learner input; earlier outputs remain retained
  and are not the qualifying result. Source watermarks also reject future
  endorsements, and replay checks actual crash cuts/quorum choices against labels.
- **135 local tests PASS**, including 26 new tests. Complete declared matrix:
  **220 cases, 660 capsules, 7,172 capsule/learner events and 340 eligibility
  observations**. Counts exclude the separately validated source consensus events.
  Healthy/late-force schedules can report eligibility before and after restart;
  observations are not distinct admitted members or actual votes.
- **55 portable representative histories replayed**, covering 1,793 events and
  85 eligibility observations. All size/prefix/quorum/cut combinations contribute
  to the full matrix trace digest; portable examples retain every profile/cut at
  prefix length 1 and the first endorsement majority.
- Receipt: [admission-research.json](admission-research.json). Qualifying evidence:
  `target/v53-admission-research/qualified/`; logs `unit-qualified.log`,
  `qualified.log`, `qualified-resources.log` in the parent directory. The receipt
  binds parent `93c61ae` and exact dirty script/test hashes, not clean protected CI.

See [the candidate, source audit and exclusions](AUTHORITY_AND_LEARNER_RESEARCH.md).
**Phase 0 remains OPEN.** No Java, POM, workflow, Maven or cloud operation. This
batch does not establish byte-for-byte clone fencing, unlimited history retention
or the integrated readiness-before-INTENT/global-promise protocol.

## Next local batch

Connect certified operation records, learner readiness and authority capsules to
the transition/global-promise adapter. Freeze exact API/byte/resource decisions
and the full acceptance register, then audit Phase 0 against all D01–D10 obligations.
Continue local commits under the explicit closure instruction; preserve V5.2's path.

## 2026-10-21 — continuous Phase 0 closure, operation lifecycle

- The operator authorized continuing to Phase 0 closure with intermediate local
  commits. [Closure worklist](PHASE_0_CLOSURE_PLAN.md) separates local contract exit
  from the deferred protected/runtime acceptance and prohibits push/cloud changes.
- Defined stable sequential client operation IDs, exact duplicate/conflict behavior,
  separately versioned preparations, forced learner receipts and a certified SEAL
  boundary before INTENT. Client timeout detaches only; explicit CANCEL must commit
  before SEAL. Terminal retirement retains a monotonic high watermark and permanent
  bounded identity reservations, including cancelled learners.
- Defined known-removed/draining capture refusal and same-version maintenance with
  a fresh challenge and surviving majority excluding the target. An isolated node
  unaware of removal retains only the already explicit local-read semantics.
- Added isolated committed-operation reducer and independent replay. **160 V5.3
  tests passed**; the final focused 25-test rerun also covers unknown/start/stop
  role refusal. **308 cases, 2,436 committed controls/data entries and 6,290 events**
  passed and all 308 histories replayed from serialized evidence. These are
  certified-application assumptions, not observations of consensus or real disks.
- Receipt: [operation-research.json](operation-research.json); retained output
  `target/v53-operation-research/qualified/`, with `unit.log` and
  `unit-focused-final.log` in its parent. Receipt binds `acba545` plus exact dirty
  source/test hashes. Previous outputs remain intact. No production/CI/POM change.

See [operation and maintenance decisions](OPERATION_AND_MAINTENANCE.md). D05/D07
have concrete candidate selections and counterexamples; **Phase 0 remains OPEN**
while certification integration, formats, resources and the final audit continue.

## 2026-10-21 — certified operation and learner integration

- Connected operation commands to the global-promise adapter's actual PREPARE,
  selected installation, ACCEPT/PROOF and forced-prefix events. Per-replica catalogs
  advance only after their own prefix force. Learner images and receipt forces
  precede READY/SEAL and voting eligibility after INTENT. CONTROL cannot disguise a
  membership entry. Accepted SEAL is recovered against a competing CANCEL request.
- Corrected the integration helper's proposer-inclusive quorum construction: 5→4
  FINAL can need the removed proposer plus three survivors. Filtering globally
  minimal joint quorums for local inclusion incorrectly excluded that valid set.
- **172 tests PASS**, including 12 new integration tests. Complete matrix:
  **126 cases, 1,141 campaigns, 4,884 local catalog applications and 135,883 events**;
  174 vote-stage/force observations involve the originally non-voting identity.
  These counts include repeated replica observations, not distinct client changes.
- **21 portable histories replayed**, covering 182 campaigns, 858 catalog applies
  and 22,456 events. Actual interrupted-force observations validate case labels.
  Receipt: [integrated-research.json](integrated-research.json). Qualified output:
  `target/v53-integrated-research/qualified/`, `unit-qualified.log` and
  `qualified-resources.log` in the parent. Source binds `ee38852` plus exact dirty
  model/test hashes. Earlier source/setup outputs remain retained.

See [integrated protocol research](INTEGRATED_PROTOCOL_RESEARCH.md). Fresh recovery
ballots per command and complete retained prefixes are explicit reference choices.
Steady-state round reuse and incremental metadata compaction remain to be specified
and tested before the local contract can freeze. **Phase 0 remains OPEN.**

## 2026-10-21 — stable rounds and complete catalog capsules

- Added stable-round extension seeded by the validated global-activation model.
  Selected sources and original basis stay fixed; every slot requires new durable
  ACCEPT/PROOF. INTENT and leader restart end the round; late callbacks are refused.
- Added checkpoint statements binding application and full catalog state, with
  original membership certificates/full sealed descriptors retained after query
  result retirement. Future/unforced endorsements and hidden boundaries reject.
- 17 new regressions; 49 portable histories replayed, 252 publications, 70 capsules
  and 5,504 extension/endorsement observations. Receipt binds parent `53ac701` and
  exact local source bytes: [continuity-research.json](continuity-research.json).
  Outputs and unit log: `target/v53-continuity-research/`.
- [Decisions and limits](STEADY_ROUNDS_AND_CATALOG.md) distinguish reference models
  from future same-round catalog integration and physical incremental compaction.
  No Java, POM, workflow, Maven or cloud changes. Phase 0 remains **OPEN** pending
  formats/resources, the frozen acceptance register and final requirement audit.

## 2026-10-21 — exact contract/format candidate

Added concrete additive APIs, 24 storage / 21 wire kinds, 45 independent syntax
fixtures, nine control payload fixtures and the unchanged token v1 fixture.
Resource accounting includes all selected sources and generations (324 MiB reserved
within a 384 MiB ceiling). Frozen S/N/C/M register and Phase 1 entry are present.
Focused fixture/plan checks pass; the coherent all-model closure audit is next.
No production Java, Maven, workflow, cloud or release changes.

## 2026-10-21 — Phase 0 locally closed

- The coherent final audit passed 198 tests and all nine research drivers on exact
  script bytes at `4676673` (plus the recorded local format-status/fixture metadata).
  Original retained examples replayed successfully; older batch receipts remain
  historical. Final receipts: [phase0-evidence](phase0-evidence/membership_model.json)
  and [closure index](phase0-closure.json).
- D01–D10 now have concrete protocol/API/byte/resource/acceptance decisions and
  mapped executable counterexamples. The final review clarified all seven existing
  consumers, stale-operation/history error codes, fresh maintenance observations,
  and verified discovery before campaigning from an obsolete configuration.
- Scope diff against `73f3bd5c21c97eee564397ab11af7b66bc1b13a3` contains only V5.3
  docs/scripts. Production Java/POM/workflows and V5.2 runner/evidence are untouched.
- **Phase 0: LOCALLY CLOSED. Phase 1: NOT STARTED.** Protected review, real public/
  physical runtime, published V5.2 integration, performance/cloud and release remain
  later gates. See [audit](PHASE_0_CLOSURE_AUDIT.md) and [Phase 1 entry](PHASE_1_ENTRY_PLAN.md).


## 2026-10-21 — Phase 1 declarations and disabled process foundation

The operator explicitly authorized progressing through local Phase 1 closure with
intermediate local commits. [Batch 1](PHASE_1_FOUNDATION.md) aligns 5.3 snapshot
coordinates, adds 24 public membership declarations and preserves all existing API
fixtures. An actual-source review required a separate variable-membership status;
the unpublished inheritance choice is amended without relaxing the fixed-three API.

Local reactor: 1,018 tests, four existing skips, no failures/errors. Eight consumer
projects: 26 tests passed. V5.3 Python: 199 tests passed; coordinate/build-bundle and
release-fixture checks: 28 passed. Three fresh JVMs verify disabled admission and
exact JAR origins. All ten portable evidence negatives reject after the unchanged
original passes; relocated replay passes. See the [retained summary](phase1-evidence/declarations.json).

Phase 1 remains **OPEN**: production byte codecs/contextual readers and complete
steady-round/catalog/compacted-source composition still need implementation. No new
runtime, cloud, CI job, release, push or PR is enabled by these declarations.


## 2026-10-21 — Phase 1 exact-byte syntax codec

[Byte foundation](PHASE_1_BYTES.md) adds a bounded internal 1.3 encoder/decoder and
retains an independent schema/fixture boundary. All 24 storage and 21 wire frames,
nine control payloads and the unchanged token match their golden bytes. Twenty-three
focused Java tests and nine format Python tests passed; a fresh JVM produced all
45 frames for independent Python replay. Original source/cut authority, transfer
ownership and the composed model remain pending. No runtime or hosted activation.

## 2026-10-21 — Phase 1 contextual byte and transfer foundation

- Added disabled-path internal context, resource, transfer and exchange helpers.
  Application images are separately bounded from 32 MiB capsule metadata; legacy
  configured/fixed-three paths remain unchanged.
- Qualified seven concrete byte histories with 63 original certificates, independent
  catalog derivation and 18 portable corruption negatives. Fixture file-force
  calls describe the single test producer only, not live cluster durability.
- 37 focused Java tests, 205 V5.3 Python tests, 20 build-contract tests and five
  optimized-Python reader tests passed. New current-coordinate build prerequisites
  preserve every previous suite and add context/resource execution checks.
- [Context foundation](PHASE_1_CONTEXT.md) and its
  [retained receipt](phase1-evidence/context.json) record scope, failures corrected
  during development, source/JAR hashes and pending obligations.

Phase 1 remains open for complete frozen-source capsules/selection, full model
composition and its finite S/N coverage, and the final requirement audit. No push,
workflow, release or V5.2 runner operation was performed.

## 2026-10-21 — Phase 1 source packet inventory

- Defined the previously unspecified bounded GSCP inventory container with separate
  application transfers and nonrecursive capsule/index/transfer digest bindings.
  No storage/wire kind or public API fixture changed.
- Java and independent Python readers checked real initial and accepted-tail byte
  packets. All 30 malformed variants and relocated replay passed; 23 focused Java
  tests and 31 Python checks passed. [Receipt](phase1-evidence/source-packet.json).
- Basic tail checks preserve exact ENTRY/payload/root/view/parent and ballot order.
  The packet cannot establish checkpoint authority or authorize source selection.

The [full capsule authority walk](PHASE_1_SOURCE_PACKET.md), original frozen-source
selection, same-round/catalog/compacted-source model and closure audit remain open.
New runtime stays disabled; work is committed locally only.

## 2026-10-21 — Phase 1 complete capsule verification

- Added the conditional ROOT-to-current capsule walk, historical governing-view
  certificate verification, explicit member edges and next-view checkpoint quorums.
- Actual compacted fixtures cover all seven profiles at cuts 0..9: 70 packets,
  524 checkpoint ACK copies, 16 original-first corruption variants and relocation.
  Ordinary entries and historical full catalogs are absent from packed inventories.
- 45 focused Java and 34 Python tests pass. Build bundles require the additional
  executed suite and exact fixture classes/resources. [Receipt](phase1-evidence/capsules.json).

The verifier assumes authenticated owned-record observations; fixture force logs
do not establish live replica/crash durability. [Scope and remaining work](PHASE_1_CAPSULES.md)
keep frozen-source selection, full model composition/S-N inventory and closure
audit pending. New runtime remains disabled; local commit only.

## 2026-10-21 — Phase 1 original frozen-source selection

- Added conditional selection over complete verified capsules: exact original
  source references, proposer-inclusive stable/joint quorums, compatible frozen
  cuts, longest prefix, highest next-slot tail, and one decision per campaign.
- Bounded supplementary existing-format checkpoints prove hidden stable ancestry
  without resampling a basis. Known conflicting anchors always fail closed.
- Independently replayed 28 concrete selection fixtures / 117 frozen sources and
  all 13 original-first negatives with relocated replay. Covered minority tails
  remain original evidence; selected proof settles their slots.
- 52 focused Java tests, 217 V5.3 Python tests and 20 build-contract tests pass.
  [Selection scope](PHASE_1_SELECTION.md) and [receipt](phase1-evidence/selection.json).

These fixtures do not establish a causal distributed grant/install history or
activate the runtime. The same-round/catalog/compacted recovery model, complete
finite S/N inventory and final Phase 1 audit remain pending. Local commits only.

## 2026-10-21 — Phase 1 complete finite S/N inventory

Materialized all 3,310 frozen scenario combinations and 24 named negative families.
Every row is PLANNED; none is a runtime PASS. No inapplicable cross-product is
dropped: later execution must demonstrate explicit refusal with unchanged bytes.
Three focused coverage/drift tests passed. [Inventory and commands](PHASE_1_CASE_INVENTORY.md).
Full model composition and the requirement audit remain open.

## 2026-10-21 — Phase 1 causal protocol composition

The [composed model](PHASE_1_COMPOSITION.md) independently replayed 112 complete
histories / 159,286 events across all seven profiles, including steady DATA and
CONTROL, compacted heterogeneous sources and SEAL/INTENT/FINAL crash recovery.
Seventeen reason-specific negatives and relocated replay passed. Twenty-two
focused tests cover the model, observer and portable qualification driver.

Original entry/certificate bytes survive recovery; the model's decisions do not
consult the whole audit archive. Missing ancestry and selected-source loss refuse
or require a fresh ballot. Model forces are abstract and physical S/N rows remain
PLANNED. No Java runtime, workflow or V5.2 experiment changed. The final Phase 1
requirement/compatibility audit is next; this batch alone does not close Phase 1.

## 2026-10-21 — Phase 1 locally closed

The [requirement audit](PHASE_1_CLOSURE_AUDIT.md) and
[closure receipt](phase1-evidence/closure.json) close the operator-authorized local
Phase 1 scope. Fresh final validation passed 64 focused Java tests, 26 tests across
eight consumers, 242 V5.3 Python tests and 29 build-contract tests. Three fresh
public JVMs and every syntax/context/packet/capsule/selection fixture gate passed
against the current JARs; original-first negatives and portable replay passed.

The final 112-history composition and 3,310 S / 24 N inventory match their retained
sources. The physical S/N rows remain planned. Current thirteen POM coordinates
agree, inherited production code and predecessor workflow/cloud inputs are unchanged,
and the new runtime stays disabled. Existing V5.1 fixture tests changed only to
recognize the explicitly aligned current consumer coordinates.

Work remains local on `feat/v53-cluster-operations`; no push or experiment action
was performed. Phase 2 storage and the later real protocol/public/fault gates have
not started. Actual V5.2 publication/integration and unified protected acceptance
remain required before release readiness.

## 2026-10-22 — Phase 2A private allocation and exclusive ownership

Opened the [Phase 2 storage plan](PHASE_2_ENTRY_PLAN.md) and completed its first
private component: exact pre-provisioned ROOT/GENESIS/NODE authority, exclusive
directory ownership, separately forced counter allocation and bounded restart
handling. Missing authority never resets the counter; complete unreturned pending
reservations are burned. Empty/torn/stale/foreign pending bytes remain retained
and block open, pending the complete storage recovery/repair work.

The [storage foundation](PHASE_2_STORAGE_FOUNDATION.md) records 62 passing focused
Java tests, 23 Python/build-contract tests and seven optimized-Python tests.
All 48 real-process cases / 186 JVMs, ten reason-specific evidence negatives and
relocated replay passed. The [receipt](phase2-evidence/allocator.json) binds parent
`5ab987b` plus the current local bytes, before these final reporting additions.
Raw originals remain at `target/v53-phase2-allocator/qualified/`.

This is process crash/lock evidence, not physical power-loss, public bootstrap,
voter admission or distributed membership acceptance. New public runtime remains
disabled. Phase 2 is **OPEN**; root-wide promise/original basis storage is next.
No inherited production file, POM, frozen format, workflow or V5.2 experiment was
changed. Shared 5.3 build prerequisites add the new suite/worker; legacy gates
remain intact. Work and commit remain local with no push.

## 2026-10-22 — Phase 2B1 durable grant metadata

Completed the [private grant journal](PHASE_2_GRANT_JOURNAL.md): one shared directory
owner, separately forced PROMISE/BASIS frames, original duplicate replies, no
same-ballot resampling after an incomplete grant, and an atomic observation fence
checked across writes/forces/return. Reserve both frames before the first write;
reject unknown/corrupt/truncated/conflicting records without journal repair.

72 focused Java tests, 32 Python/build-contract tests and 16 optimized-Python tests
passed. The fresh-process grant matrix passed all 45 cases / 180 JVMs, eight exact
evidence negatives and relocated replay. All 48 previous allocator cases / 186
JVMs plus ten negatives passed against the changed shared owner. The
[receipt](phase2-evidence/grants.json) records parent `40e0866`, exact local bytes,
development corrections and retained outputs at `target/v53-phase2-grants/`.

The journal records references; it does not yet retain/establish current physical
capsule/application/accepted-tail ownership. Phase 2B2 must provide those sources
and lifetimes before any wire grant can use them. Adoption floors, SELECTED,
complete generation/floor recovery and rotation remain later work. Phase 2 is
**OPEN**; the public runtime is disabled and physical S/N rows remain PLANNED.
No inherited runtime, frozen byte catalog, POM, workflow or V5.2 experiment changed.
Only local commit is authorized; nothing was pushed or dispatched.
