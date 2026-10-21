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

## Next local batch

Build the multi-slot, predecessor-certified configuration-transition model, with
competing intent descriptors, partial joint/final proofs, local view adoption and
old-era fencing. Evaluate the proposed conservative final seal rather than merely
changing quorum counts. Add snapshot/compaction authority before declaring D02/D06
resolved, and specify durable ballot allocation, exact formats and D04–D10 before
freezing Phase 0. The current single-slot model is a reusable component of that
work, not a substitute for it.
