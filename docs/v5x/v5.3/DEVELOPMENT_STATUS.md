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

## Next local batch

Map the certified-chain candidate to GSE's global promise, selected recovery bases
and activation, including unavailable sources. Resolve the retained authority
lifetime/representation before freezing D02/D03/D06. Then complete learner fencing,
operation IDs/query/cancel, removed-node reads and API/byte/resource decisions
D04–D10. Continue local commits only; leave the V5.2 release/cloud path untouched.
