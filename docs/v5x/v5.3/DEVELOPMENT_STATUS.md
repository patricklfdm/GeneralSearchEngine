# V5.3 development status

## 2026-10-25 — Phase 2 local closure

The [final audit](PHASE_2_CLOSURE_AUDIT.md) and [receipt](phase2-evidence/closure.json)
record the completed local storage scope, source-bound validation, retained failures
and remaining runtime qualifications. Local commits are complete through Phase 2;
unified operator review is pending. Phase 3, push, protected CI, paid cloud and
integration with the eventual released V5.2 are not performed under this closure.
The older entries below describe their respective source snapshots.

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

## 2026-10-22 — Phase 2B2a physical original-source retention

Added [retained source storage](PHASE_2_BASIS_SOURCES.md) under the existing journal
owner. Each original packet and all image bytes are forced with their directory
entries before BASIS. Exact duplicates/reopen use original bytes; missing, partial,
corrupt, linked, unbound or replaced source files refuse further use. Shared source,
application and journal reservations rebuild on reopen; insufficient capacity
refuses before a new PROMISE. No durable source deletion is implemented.

80 focused Java tests, 41 Python/build-contract tests and 25 optimized-Python tests
passed. The physical matrix passed 69 cases / 258 fresh JVMs, eleven exact negative
mutations and relocated replay. The previous 45-case grant and 48-case allocator
matrices also passed with their original negative/replay gates. Exact bytes, raw
receipts and development corrections are indexed in
[basis-sources.json](phase2-evidence/basis-sources.json); local evidence remains at
`target/v53-phase2-sources/`.

Phase 2B2 remains **OPEN** for current-generation/parent/tail ownership binding;
the input capsule's remote ownership observations are still conditional. Complete
selected generation recovery, retirement and public protocol integration follow.
No inherited runtime, frozen format, POM, workflow or V5.2 experiment changed.
This batch is local commit only, without push or hosted acceptance.

## 2026-10-22 — Phase 2B2b current local generation capture

Added the [current-generation entry](PHASE_2_CURRENT_GENERATION.md): exact physical
selector/manifest/packet/image/PROMISE/owned-tail binding under the journal's
exclusive owner. `prepareCurrent` samples that immutable selected generation under
the writer monitor; callers cannot substitute sources. Rechecks reject live inode
replacement and a selected cut inconsistent with retained grants. Local tail
observations bind the node/storage/original record/parent; remote historical
ownership is still a separate conditional verifier input.

89 focused Java tests, 49 Python/build-contract tests and 33 optimized-Python tests
passed. All 90 current-generation process cases / 360 JVMs, thirteen reason-specific
negatives and portable replay passed. The unchanged source, grant and allocator
matrices also passed (69 / 45 / 48 cases respectively), including their negative
and relocation gates. All four raw receipt inventories were checked. The
[summary](phase2-evidence/current-generation.json) records exact implementation
hashes, the initial corrected Python fixture mutation and retained originals under
`target/v53-phase2-current-generation/`.

Phase 2 remains **OPEN**. Generation installation/selector switching is explicitly
sequenced into 2C with adoption/ancestry, recovery and source lifetimes. No install,
repair or reclamation API is exposed here; inactive/selected-installation generations
are refused. Public bootstrap, power-loss qualification, complete physical S/N and
unified acceptance remain pending. No inherited runtime, frozen format, public API,
POM, workflow or V5.2 experiment changed. Work and commit remain local, without push.

## 2026-10-22 — Phase 2C1 durable original selection

Added [SELECTED persistence](PHASE_2_DURABLE_SELECTION.md) to the existing private
journal. It derives local original-source ownership from retained bytes, recomputes
the complete decision, forces it once, and refuses same-ballot reselection through
reopen/lost response. Selected followers validate their own original grant and
proposer inclusion. Higher observations fence write/force/return without waiting
for the writer monitor. Selection metadata alone grants no installation ACK.

98 focused Java, 58 Python/build-contract and 42 optimized-Python tests passed.
The final physical matrix passed 54 cases / 270 JVMs, eleven exact negatives and
portable replay. Current-generation (90 / 360 / 13) and grant (45 / 180 / 8)
regressions passed with portable replay. All raw receipt inventories were verified;
the [summary](phase2-evidence/durable-selection.json) records exact local bytes and
the superseded first fixture run with reused cross-ballot remote basis UUIDs.

The operator now authorizes continuing locally through Phase 2 closure and committing
each validated batch. The [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) preserves
all remaining installation/adoption/proof/floor/retirement/rotation/provisioning
and physical audit obligations. Phase 2 is **OPEN**; remote ownership is still
conditional, and full S/N runtime qualification remains pending. No push, workflow,
POM, frozen format, inherited runtime or V5.2 cloud action occurred.


## 2026-10-22 — Phase 2C2 selected local generation installation

Completed the private [installation transaction](PHASE_2_GENERATION_INSTALL.md)
under the existing exclusive journal owner. The immutable source decision now
materializes into the inactive slot, retaining its original parent/catalog/image,
exact carried tail and required authenticated ancestry. Semantic validation and
shared reservations precede staging; file/directory/selector forces precede the
local receipt. Interrupted exact prefixes resume only the same plan. Reopen seals
the selected generation and a subsequent grant captures its new state. Both old
and new generations remain retained pending governing-floor retirement.

The final gate passed 174 cases / 696 fresh JVMs, 12 exact-reason negatives and
portable replay. Existing capture and selection regressions passed 90 and 54
cases respectively. All 109 focused Java tests, 65 Python/build-contract tests
and 49 optimized-Python tests passed. The [hash index](phase2-evidence/generation-install.json)
retains the source/build and original failure provenance.

This is a local installation receipt, not an authenticated network ACK or READY.
Remote historical force observations are still conditional fixtures. Cross-view
adoption, real ACCEPT/PROOF/certificate and application persistence, floor and
retirement, journal rotation, complete offline initialization and the integrated
physical closure audit remain required. Phase 2 remains **OPEN**; local development
and per-batch commits continue without push or V5.2 cloud operations.

## 2026-10-22 — Phase 2C3a certificate-derived adoption fence

The [adoption fence](PHASE_2_ADOPTION_FENCE.md) records only the highest full ballot
from an authenticated membership certificate actually referenced by the incoming
capsule. Its original governing view stays intact. A forced null-BASIS PROMISE
fences lower/same-ballot resampling while preserving old source and selector bytes.
An existing higher promise and original basis stay byte-for-byte unchanged.

Final qualification passed 66 cases / 330 fresh JVMs, 12 exact-reason negatives
and portable replay in 182.312 seconds. The source-retention regression passed
69 cases / 11 negatives. All 118 focused Java tests, 72 Python/build-contract
tests and 56 optimized-Python tests passed. The [hash index](phase2-evidence/adoption-fence.json)
records all provenance, including older regressions and replay-only evidence.

This is not prefix installation or permission to vote/serve. The next batch must
connect the fence to new-state installation and invalidate obsolete-view work.
Remote historical observations remain conditional fixtures. The operator's
[expanded instruction](LOCAL_DEVELOPMENT_SEQUENCE.md) now covers local work through
all pre-cloud stages; Phase 2 and the overall completion audit remain OPEN.

## 2026-10-22 — Phase 2C3b local prefix adoption transaction

The [adoption transaction](PHASE_2_ADOPTION_INSTALL.md) now validates current and
original-source ancestry, retains a complete exact reservation across PROMISE
force, then installs and forces the candidate and selector. A new null-BASIS fence
without its prefix blocks old-view campaigns. A higher original promise survives
byte-for-byte while obsolete sources cannot vote; known removed identities reopen
with history and refuse grants. Old generation/source bytes remain retained.

A new regression exposed same-content inode replacement accepted at a write/force
callback. The shared installer now checks identity immediately after these
boundaries. Final qualification passed 234 cases / 1170 fresh JVMs, 14 negatives
and portable replay in 567.824 seconds. Shared selected installation
and fence regressions passed 174 and 66 cases. All 129 focused Java, 69 Python
and 53 optimized-Python tests passed. The [hash index](phase2-evidence/adoption-install.json)
records final source bindings, raw evidence, earlier results and fixture corrections.

No network ACK, READY, public runtime or cloud acceptance is claimed. Actual
application/phased vote storage, governing floor/retirement, bounded rotation,
offline initialization and integrated Phase 2 audit remain open. Development now
continues with exact governing-copy floor admission and retirement recovery, under
the existing local commit/no-push authorization.


## 2026-10-22 — Phase 2C4a retained governing floor

- Added explicit floor-capable storage open, complete original generation/image
  copies, exact local ownership and governing old/joint/new quorum admission.
- Preserves promises, selectors, generations and original grant sources. Complete
  copies are forced before FLOOR; partial writes resume only the same proposal.
  Existing floor replacement requires later bounded rotation. No deletion added.
- Counts floor copies against the same six SOURCE/seven APPLICATION reservations.
  Capacity failure occurs before persistent floor writes. Reopen verifies original
  bytes, and later adoption/selection preserves the floor's proven parent.
- **315 cases / 1260 fresh JVMs**, 14 original-first exact negatives and portable
  replay PASS in 716.248 seconds. The process cuts cover the first
  occurrence of each of 17 establishment boundaries at sizes 3/4/5 and old/joint/new
  cuts. Historical membership force observations/application images remain fixtures.
- Focused reactor **142 tests PASS**; final **15 floor tests PASS**, including two
  additional lifecycle cases (144 distinct tests). **38 Python/build-contract
  tests PASS**, both normal and optimized. Build-coordinate fixtures now follow
  the earlier Phase 2 prerequisites as well as the floor additions.
- [Scope and reproduction](PHASE_2_GOVERNING_FLOOR.md), [retained source/build/hash
  index](phase2-evidence/governing-floor.json). Raw evidence remains under
  `target/v53-phase2-floor/`; earlier draft and focused-test logs remain retained.

Phase 2 and the pre-cloud checklist remain OPEN. Next work is forced retirement
and interrupted deletion, followed by coordinated source/floor/journal lifetimes,
actual phased vote/application storage and complete offline recovery. No push,
remote CI, public runtime, cloud execution or V5.2 Runner change occurred.


## 2026-10-22 — Phase 2C4b governing-floor retirement

- Added explicit retirement-capable open and a forced exact inventory bound to
  current root/owner/selector and the retained governing floor. A complete saved
  original is forced before deletion; shared source/image limits still apply.
- Delete only the approved inactive generation, then its saved copy; force each
  deletion and clear retirement authority last. Partial deletion and another crash
  during recovery retain the same original decision. Active generation, root
  promises, original BASIS sources and floor copies remain unchanged.
- Above-floor owned bytes need their exact forced active copy. Pending retirement
  blocks authority mutations and slot reuse. An old floor cannot retire a newer
  generation; source/floor/journal rotation remains a separate obligation.
- Regressions found and corrected older-selected pending detection and the omitted
  saved-copy deletion guard. Both negative reproductions remain retained. The
  first smoke probe also retained its stale-JAR linkage failure; qualification ran
  after the final reactor package completed.
- **549 cases / 2214 fresh JVMs**, **18 exact negatives**, relocated replay
  PASS in 1665.544 seconds. **155 Java tests** and **39 Python/build
  tests** (also under `-O`) passed. [Scope/reproduction](PHASE_2_RETIREMENT.md),
  [receipt index](phase2-evidence/retirement.json), raw data at
  `target/v53-phase2-retirement/`.

Phase 2 and pre-cloud closure remain OPEN. Next: bounded journal rotation,
coordinated source/floor lifetimes, actual phased vote/application persistence and
complete offline recovery. This batch changes no workflow, frozen format/resource
bound, public runtime, cloud experiment or V5.2 Runner. Local commits only.


## 2026-10-22 — Phase 2C4c1 bounded grant-journal compaction

- Added explicit rotating open, exact original grant-group compaction and a 1 MiB
  candidate within existing MISC. Force before atomic replacement and parent force;
  interrupted exact prefixes resume before new mutations.
- Preserve every physical source's original PROMISE, including capture interrupted
  before BASIS, all original BASIS/SELECTED frames, current/floor manifests and
  highest forced promise. Higher volatile observations still fence future grants.
- A BASIS-only predicate mutant reproduced orphaned-source rejection on reopen.
  The corrected implementation and regression retain its original ownership.
- **135 cases / 558 fresh JVMs**, **15 exact negatives**, portable replay
  PASS in 488.473 seconds; **165 Java tests**, **46 Python/build tests**
  normally and under `-O` passed. [Scope/reproduction](PHASE_2_JOURNAL_ROTATION.md),
  [receipt index](phase2-evidence/journal-rotation.json). Failed mutant and draft
  probes remain retained under `target/v53-journal-rotation/`.

Phase 2 remains OPEN. All six original source slots still count and exhaustion
refuses further capture. Continue floor/source release, coordinated bounded
progress, phased vote/application storage and complete offline recovery. This
local batch does not change workflows, frozen formats/limits, public service or
V5.2 experiments; no remote push.


## 2026-10-22 — Phase 2C4c2 obsolete floor-copy release

- Added explicit maintenance open and bounded old-floor cleanup after inactive
  retirement completes. A forced exact existing-format RETIREMENT inventory binds
  root/owner/floor/current selector; remove floor authority before listed copies.
- Partial release is never advertised as a governing floor. Reopen completes only
  an exact original decision, preserves all current/source bytes, rechecks remaining
  bytes/inodes before each deletion and clears authority last. New mutations block.
- Repeated complete floor establishment/release returns reservations. A shared
  capacity regression releases at six SOURCE/seven APPLICATION slots without
  another copy; legacy modes, stale authority, corruption and inode swaps refuse.
- **261 cases / 1062 fresh JVMs**, **14 exact negatives**, portable replay
  PASS in 806.986 seconds. **176 Java tests**, **53 Python/build tests**
  normally and under `-O` passed. [Scope/reproduction](PHASE_2_FLOOR_RELEASE.md),
  [receipt index](phase2-evidence/floor-release.json); raw data under
  `target/v53-floor-release/`.

Phase 2 remains OPEN for original-source lifetimes, automatic backpressure, actual
phased vote/application storage, complete offline recovery and integrated audit.
No source deletion, new quorum, public-runtime, power-loss or cloud acceptance is
claimed. This local batch leaves frozen formats/resources, workflows and V5.2
experiments unchanged; no remote push.


## 2026-10-22 — Phase 2C4c3 bounded journal admission

Grant/SELECTED/adoption admission now invokes at most one safe existing compaction
at its byte ceiling, then rechecks space and refuses if insufficient. Pending or
occupied generations/floor/retirement cannot be discarded for space. Production
limits stay unchanged, incomplete grants are not retried, and higher observations
still fence the new append after maintenance.

All 184 focused Java tests (eight new regressions), 20 build-contract Python tests
and their optimized-Python run passed. [Scope/reproduction](PHASE_2_JOURNAL_BACKPRESSURE.md)
and [source/build/hash index](phase2-evidence/journal-backpressure.json) distinguish
this caller-level qualification from the earlier source's physical rotation matrix.
No full 32 MiB soak, public runtime or Phase 2 closure is claimed. Continue actual
phased vote/application storage, original-source lifetimes and complete-store
physical acceptance. Local commit only; no cloud or V5.2 Runner operation.


## 2026-10-22 — Phase 2C4c4a original-source retirement decision

The maintenance owner can plan removal of a completed obsolete original BASIS only
after a newer durable PROMISE and exact governing floor. Current/local-floor grant
references remain protected. Both ancestry and exact above-floor bytes/unresolved
ownership are required. The existing RETIREMENT frame lists only the original
packet/images; a separate in-memory journal candidate removes that exact old group,
including its SELECTED frame, while retaining surviving sources and highest promise.

All **195 Java tests**, including **11 new tests**, and **20 build-contract Python
tests**, also under `-O`, passed. [Scope](PHASE_2_SOURCE_RETIREMENT_PLAN.md) and
[hash index](phase2-evidence/source-retirement-plan.json) distinguish this read-only
component from the pending durable transaction. No source is deleted and no storage
reservation is freed. Continue forced cleanup/recovery, incomplete source capture,
full lifetime headroom and phased vote/application storage. Phase 2 and the overall
pre-cloud goal remain OPEN. Local only, no workflow or V5.2 experiment changes.


## 2026-10-22 — Phase 2C4c4b durable original-source retirement

Added explicit reclaiming open: force a bounded exact original decision, compact
that source's journal group before deletion, force every removal and clear cleanup
authority last. Complete decisions resume on reopen; incomplete unforced decisions
block other mutations and require the named intact original to resume. All current,
floor and newer source authority stays intact, including unresolved owned tails.
No extra source/image slot is needed; repeated cleanup returns only the obsolete
source reservations. A deterministic regression exposed release/reacquisition of
surviving leases in the initial implementation; the correction preserves their
identities continuously. Earlier physical evidence remains retained separately.

**297 cases / 1206 fresh JVMs**, **15 exact negatives** and portable replay
PASS in 958.164 seconds. **209 Java tests**, including 14 source-release
tests, and **41 Python/build tests** normally and under `-O` passed.
[Scope/reproduction](PHASE_2_SOURCE_RELEASE.md), [hash index](phase2-evidence/source-release.json).

This does not reclaim incomplete original captures or close maximal source/image
headroom, actual phased vote/application storage or Phase 2. No public runtime,
network ACK, power-loss, workflow, cloud or V5.2 Runner claim. Local commit only.


## 2026-10-22 — Phase 2C4c4c covered capture-only retirement

A complete original capture interrupted before BASIS can retire after a strictly
later full governing floor covers every possible ACCEPT object. Preserve original
PROMISE/capsule binding, current/floor ancestry and all other resources; never
invent an empty BASIS. The new missing-BASIS regression fails against the preceding implementation: a
complete pending marker could otherwise conceal a removed original BASIS. The
correction requires the intact original group while its PROMISE remains.
Complete authority resumes only after the original journal
and remaining source inventory satisfy the same serialized transaction.

**44 cases / 178 fresh JVMs**, **14 exact evidence negatives**, portable replay
and **218 Java / 47 Python tests** (normal and optimized Python) passed.
The existing 297-case completed-BASIS artifact also replays unchanged; its source
attribution remains historical. [Scope](PHASE_2_CAPTURED_SOURCE_RELEASE.md),
[hash index](phase2-evidence/captured-source-release.json).

Same-cut/physically partial capture, maximal source/image headroom, actual phased
vote/application persistence and complete-store recovery still remain OPEN.
Continue the Phase 2 entry/closure obligations; no phase or public-runtime closure
is claimed. No push, workflow dispatch, paid cloud or V5.2 Runner change.


## 2026-10-22 — Phase 2C4c5a current-pinned capture recovery

An exact bounded intent binds the installed selector, new original PROMISE and
proposed BASIS before writing a source. Reopen completes only exact original
packet/image prefixes, with the current generation pinned and reservations held.
A completed BASIS requires complete source bytes; a partial intent cannot cover
already-created source files, and an empty intent cannot replace a lost new grant
with the installed generation promise. Higher observations fence returns.

**66 cases / 266 fresh JVMs**, **14 exact negatives**, portable replay and the final
**230 Java tests** passed. **351 V5.3 Python / 20 build tests** and 33 focused
optimized-Python tests passed. [Scope](PHASE_2_CAPTURE_RECOVERY.md),
[hash index](phase2-evidence/capture-recovery.json).

The next work is exact torn-journal recovery and actual pending ACCEPT/PROOF and
application/catalog persistence. Maximal source/image staging, coordinated lifetimes,
complete bootstrap/reopen, Phase 2 physical mapping and later phases remain OPEN.
No public runtime enablement, push, workflow, cloud or separate V5.2 Runner action.


## 2026-10-22 — Phase 2C4c5b exact torn BASIS continuation

The capture owner preserves a torn journal suffix and completes it only against
its full original intent, new PROMISE, unchanged generation and complete source.
It never truncates the original prefix or synthesizes missing source bytes after
BASIS append begins. Other journal damage, including torn PROMISE, stays refused.

**82 cases / 344 fresh JVMs**, **18 exact negatives**, portable replay, **235 Java**
and **31 focused Python/build tests** (normal and optimized) passed. The preceding
journal implementation rejects the retained half-BASIS snapshot; all 66 earlier
capture cases replay unchanged under their original source binding.
[Scope](PHASE_2_CAPTURE_JOURNAL_RECOVERY.md), [hash index](phase2-evidence/capture-journal.json).

Continue actual pending vote/application integration and coordinated maximal
lifetime completion. Phase 2 and later pre-cloud obligations remain OPEN. Local
commits only; no public runtime, push, workflow, cloud or V5.2 Runner action.


## 2026-10-22 — Phase 2C5a actual pending ACCEPT and source capture

The private voting owner now forces original ENTRY/payload/ACCEPT under the exact
installed selection, atomically selects a bounded candidate, and returns actual
local Owned only after parent force. Fresh PREPARE includes this physical tail;
earlier BASIS bytes remain unchanged. Active/candidate plus grants use the existing
32 MiB JOURNAL reservation; complete future source capacity is checked before force.

**42 cases / 270 fresh JVMs**, **12 exact negatives**, portable replay, **246 reactor
Java tests** plus the final **13-test pending suite** (two additional tests; 248
distinct Java tests), and **25 Python/build tests** (normal and optimized) passed.
[Scope](PHASE_2_PENDING_ACCEPT.md), [hash index](phase2-evidence/pending-accept.json).

Continue PROOF/certificate/application integration, covered-tail retirement and
stable next-slot progression. Partial-request abortion under a higher durable fence,
maximal lifetime completion, complete-store/public acceptance and later pre-cloud
work remain OPEN. All changes and commits remain local; V5.2 cloud stays separate.


## 2026-10-22 — Phase 2C5b actual ACCEPT-quorum PROOF persistence

The same private owner now validates real eligible ACCEPT observations before
forcing the exact PROOF, retains it across duplicate ACCEPTs, reopens partial/full
candidates correctly, and carries original proof bytes into fresh PREPARE sources.
Admission reserves proof-completion space inside unchanged journal/source limits.

**45 cases / 342 fresh JVMs**, **12 exact negatives**, portable replay, **256 reactor
Java tests** plus one later real higher-ballot proof-preservation test (**257 distinct
Java tests**), and **32 Python/build tests** (normal and optimized) passed.
[Scope](PHASE_2_PENDING_PROOF.md), [hash index](phase2-evidence/pending-proof.json).

The initial applied history/application is still a fixture; actual new phased votes
come from separately owned local directories. No network/public readiness, cloud
acceptance or phase closure is inferred. Continue certificate/application and
covered-tail integration, then the remaining complete-store/pre-cloud obligations.
All changes and commits remain local, separate from the V5.2 cloud experiment.


## 2026-10-22 — Phase 2C5c original phased-quorum certificate persistence

The private owner now validates both actual local ACCEPT and PROOF quorums before
persisting the exact certificate. Earlier-phase duplicates preserve it; complete
candidate recovery requires the actual active PROOF; new PREPARE preserves all
original phased bytes. Application/catalog/cut remain unchanged until publication.

**45 cases / 396 fresh JVMs**, **14 exact negatives**, portable replay, **265 reactor
Java tests**, **36 Python/build tests** (normal and optimized), and unchanged prior
ACCEPT/PROOF artifact/negative replay passed. [Scope](PHASE_2_PENDING_CERTIFICATE.md),
[hash index](phase2-evidence/pending-certificate.json).

Partial request wording now distinguishes immutable surviving bytes from an
unwritten witness suffix: the latter is not durable authority, requires full quorum
revalidation, and cannot replace any complete/forced original. No frozen contract
was changed. Continue actual application/sequence/catalog publication, covered-tail
and complete lifetime/bootstrap integration. Phase 2/pre-cloud closure remains OPEN.
Only local work/commits; no V5.2 cloud, workflow or public readiness change.


## 2026-10-22 — Phase 2C5d actual core application images

The private image adapter now wraps exact existing metadata/checkpoint payloads,
normalizes only administrative manifest fields in a new byte array, and validates
through real core backup semantics. Dynamic indexes, history/sequence, document order,
source preservation and bounded hostile input checks have local coverage.
**293 Java tests**, including **eight new image tests**, passed. The initial sandbox
socket restriction and test compilation error remain retained in the
[evidence index](phase2-evidence/application-image.json).

[Scope and commands](PHASE_2_APPLICATION_IMAGE.md). This is application image
encoding/verification, not durable publication or complete bootstrap. Continue actual
application replay, catalog projection, checkpoint endorsements and publication
under original selected ancestry. Phase 2 and pre-cloud completion remain OPEN.


## 2026-10-22 — Phase 2C5d actual application operation replay

Private replay now reuses all eight existing operation codecs/semantics, binds the
original image/history/sequence, preserves control-only images and exports DATA
results deterministically across intermediate recovery bases. **29 focused Java
tests** passed, including five new replay tests and eight save/reopen cut comparisons.
[Scope](PHASE_2_APPLICATION_REPLAY.md), [hash index](phase2-evidence/application-replay.json).

Two retained old public facade failures exposed a missing FOLLOWER/application-cut
prerequisite after backup. The fixture now waits within a finite bound, then keeps
its exact original error/outcome assertions; the corrected run passed. No old
production election/read behavior changed. Catalog reduction, original certified
publication/checkpoint/source lifetime and full storage closure remain required.


## 2026-10-22 — Phase 2C5d exact catalog projection

The reducer now binds ENTRY/application results and projects every frozen control
transition without mutating inputs. **60 focused Java tests** passed, including
seven new tests and 63 byte-exact historical transition comparisons. Actual DATA
replay integration, allocator exhaustion and permanent identity checks are covered.
A retained red test exposed READY accepting another inventoried image; admission
and catalog reopen now require the exact prepared image. [Scope](PHASE_2_CATALOG_PROJECTION.md),
[evidence index](phase2-evidence/catalog-projection.json).

Actual checkpoint ownership, forced publication under original selected ancestry,
covered-tail retirement and full lifetime/bootstrap integration remain pending.
Phase 2/public runtime/pre-cloud closure remain OPEN. Work and commits stay local.


## 2026-10-22 — Phase 2C5d certified checkpoint construction

The new plan joins original phased-certificate checks, actual core application replay,
catalog projection and exact new checkpoint statements. Completion requires explicit
applied-end endorsements and independently walks the complete capsule. Stable updates
replace the old range; original membership edges remain complete and immutable.

**292 V5.3/version-boundary Java tests** passed, including seven new tests, 63
byte-exact profile transitions and 100 bounded stable extensions. New fixture
endorsements are conditional; no actual checkpoint force or public publication is
claimed. [Scope](PHASE_2_CHECKPOINT_EXTENSION.md), [index](phase2-evidence/checkpoint-extension.json).

Continue the actual applied-end/ACK transaction, original selected ancestry,
covered-tail retirement and coordinated source/image lifetime. Phase 2/pre-cloud
closure remain OPEN. Only local work/commits; V5.2 experiments remain separate.


## 2026-10-22 — Phase 2C5d applied-end/ACK storage component

The private file transaction now reserves one full application slot, binds all
original plan bytes and forces the full end before a local checkpoint ACK. All
fault cuts recheck owner/fence/file identity. Partial files remain exact-prefix
resumable; unknown/missing/corrupt authority and exhausted resources refuse.

**46 distinct Java tests**, **42 process crash cases / 126 fresh JVMs**, independent
raw-byte/order replay, seven negative mutations, portable replay and Python `-O`
passed. The initial inventory JSON encoding failure remains retained. [Scope](PHASE_2_APPLIED_END.md),
[index](phase2-evidence/applied-end.json). Original protocol history is conditional;
actual lock and end-file force are tested, full integrated publication is not.

Continue actual journal certificate/fence/replay/staging integration, complete
capsule/ancestry selector installation, covered-tail retirement and bounded lifetime
progress. Phase 2/pre-cloud remain OPEN; no push, public readiness or cloud change.


## 2026-10-22 — Phase 2C5d actual journal application/ACK

The exclusive journal now applies its original locally certified first slot through
typed core replay and forces the exact end before issuing a checkpoint ACK. Bounded
scratch recognizes interrupted core backup staging; all destructive cleanup remains
limited to exact disposable members. Completion/reopen capacity is reserved before
ACCEPT and retained while the applied certificate remains unresolved.

Final targeted **66 Java tests PASS**; **22 actual journal crash cases / 66 JVMs**,
**36 scratch/core crash cases / 108 JVMs** and original-first independent journal
replay with seven negative mutations, relocation and Python `-O` pass. Earlier
77-test broad storage execution and the reproduced reopen-capacity regression are
retained separately. [Scope](PHASE_2_JOURNAL_APPLICATION.md),
[index](phase2-evidence/journal-application.json).

Initial provisioning remains a private fixture; selector publication, covered-tail
retirement, stable next-slot progression and coordinated lifetime work remain open.
No runtime enablement, protected CI, push or V5.2 cloud change. Continue local work
under the [pre-cloud closure checklist](PRE_CLOUD_CLOSURE_CHECKLIST.md).

## 2026-10-22 — original selected parent in complete published generations

The [complete generation component](PHASE_2_PUBLISHED_GENERATION.md) now carries
the original selected parent and exact certified first slot without rewriting
SELECTED. Complete checkpoint construction, generation reading and floor-copy
validation agree across stable, joint and successor stable views. Private coverage
metadata and retained certificate/ancestry remain within existing limits.

All 63 profile transitions, actual local journal DATA/INTENT/FINAL ends, installation
interruptions and eight fresh-process crash cases have local qualification. The
independent replay derives the control projection and exact new file inventory;
five mutations, portable replay and optimized Python checks pass. Exact tests,
source/build hashes and original failed development attempts are in the
[evidence index](phase2-evidence/published-generation.json).

Journal publication, covered-vote/stage retirement, additional ancestry ACK issuance
and same-round next-slot progression still require integration. Maintenance must
free inactive-generation/floor capacity before accepting work that reserves replay
completion. Full-size/all-profile lifetime qualification remains open. Continue
locally with no push or cloud dispatch.

## 2026-10-22 — actual first-slot publication and covered cleanup

The [journal publication transaction](PHASE_2_JOURNAL_PUBLICATION.md) now binds the
actual original vote and forced applied end, publishes the complete selector, then
retires only its covered staging and pending vote. Recovery revalidates the exact
previous immutable generation and original parent catalog/application. Unknown or
changed remaining files and foreign candidates refuse before deletion. The end
plan is deleted last; the empty-vote replacement is atomic and prefix-resumable.

Final qualification: **89 Java tests PASS**, including actual DATA/INTENT/FINAL
publication, later governing-floor retirement and fresh captures. **16 process
cases / 48 fresh JVMs**, eight evidence mutations, portable replay and Python `-O`
pass. The earlier focused suite covers 30 publication/cleanup interruption labels
and repeated recovery. [Exact source/build/evidence index](phase2-evidence/journal-publication.json).

Next: stable same-round continuation while retaining the original selected choice,
actual extra ancestry ACK issuance and full bounded storage lifetime. Removed-member
recovery, complete bootstrap and the Phase 2 closure audit remain open. Continue
local commits toward pre-cloud completion; public runtime, push and cloud dispatch
remain disabled.

## 2026-10-22 — actual immediate-parent checkpoint endorsements

The [parent checkpoint transaction](PHASE_2_PARENT_CHECKPOINT.md) now derives an
exact supplemental RANGE from the actual certified parent when compaction hides
it, forces the full applied end, then issues a distinct local ACK. Publication
validates that original local observation and real remote endorsements. Covered
cleanup reconstructs and checks the additional files before deleting anything.
The existing global journal/image limits and original SELECTED remain unchanged.

Targeted integration covers parents at cuts 1, 2 and 4, ten interruption/fence
labels, repeated recovery and altered or missing authority. Twelve process cases
use 36 fresh JVMs; independent original-first replay, eight evidence mutations,
portable replay and Python `-O` pass. Exact Java results and source/build/raw hashes
are retained in the [evidence index](phase2-evidence/parent-checkpoint.json).

This advances first-slot publication only. Renewal for older hidden BASIS/floor
ancestors and authenticated stable same-round continuation remain next, followed
by the remaining coordinated-lifetime, bootstrap/recovery and Phase 2 audit work.
Public runtime and all later cloud acceptance remain open.

## 2026-10-22 — bounded original ancestor renewal

[Ancestor renewal](PHASE_2_ANCESTOR_RENEWAL.md) now preserves older authenticated
BASIS/floor endpoints through an enlarged RANGE. Each new local endorsement follows
the actual forced application end. Publication and covered cleanup bind the exact
extra statements and ACKs, with at most six groups, nineteen stage files and one
application image under the existing global limits.

Targeted qualification: **43 Java tests PASS**, sixteen extra write interruption
labels and **12 process cases / 36 fresh JVMs**. Independent original-first replay,
ten evidence mutations, portable replay, Python `-O` and replay of the previous
parent-only evidence pass. The [evidence index](phase2-evidence/ancestor-checkpoint.json)
retains source/build/raw hashes and both failed development attempts. Historical
checkpoint/bootstrap authority remains conditional; new votes, captures and end
forces are actual.

Phase 2 remains OPEN. Next are safe ancestry pruning and pre-ACCEPT publication
headroom, original-choice-preserving stable continuation, and complete bounded
lifetime/bootstrap/recovery qualification. No public runtime, push or cloud action.

## 2026-10-22 — publication headroom before new ACCEPT

The application-capable journal now checks conservative next-publication ancestry
groups and exact private coverage bytes before accepting a new request. The
seventh-group regression previously returned a vote; it now refuses with
`CAPACITY_EXCEEDED / NOT_SUBMITTED` and unchanged disk/resource state. Original
acknowledged votes remain readable and duplicate-safe; oversized legacy application
refuses before scratch with `INDETERMINATE`.

Qualification: **42 distinct Java tests PASS**, including six targeted admission
tests and three actual owners completing a six-group publication/reopen. Application,
journal publication and generation component crash matrices total **46 cases / 138
fresh JVMs**; independent original-first replay, twenty evidence mutations and
portable replay pass. The [evidence index](phase2-evidence/publication-admission.json)
binds the exact raw directories printed by the completed run. Initial fixture
errors and a separately replayed older directory are retained and excluded from
new-source acceptance. Test-only corrections were rerun; production did not change
during the broad regression. [Scope](PHASE_2_PUBLICATION_ADMISSION.md).

This is conservative admission, not ancestry reclamation. Safe source/floor-aware
pruning, original-choice-preserving same-round continuation, full-size/profile
lifetime and the remaining Phase 2 bootstrap/recovery audit stay OPEN. Continue
local commits toward pre-cloud completion without push or V5.2 cloud changes.
