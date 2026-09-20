# V5.1 Phase 0 candidate review checklist

**Status:** design candidate produced locally; protected acceptance pending.
**Reviewed checkout:** `09d2bf247f004eb134eb81c59ee88005affafe92`.
**Design authorization:** user's instruction to start according to the development
plan, 2026-09-19. This starts the entry plan's documentation-only Phase 0.

## Delivered local work

- [x] Read the accepted V5 charter and published admission/runtime/API/format/release
  records; reconcile the nine planning-document changes since the original base.
- [x] Inspect configured-leader assumptions in the actual public façade, node/store,
  entries/proofs/snapshots, manifest/wire, bootstrap admission and bounds.
- [x] Produce [contract and D01-D12 selections](PHASE_0_CONTRACT.md), with rationale,
  assumptions, exclusions and proposal status.
- [x] Produce [leadership/recovery](LEADERSHIP_AND_RECOVERY.md), including transitions,
  quorum selection, read ordering, safety arguments and falsifying schedules.
- [x] Produce [API/format/compatibility](API_FORMAT_AND_COMPATIBILITY.md), including
  the additive inventory, outcomes, lifecycle, finite policy/bounds and new-group path.
- [x] Produce [E01-E12 evidence design](TESTING_AND_EVIDENCE.md), independent negatives,
  crash cuts, public consumers and timing/measurement boundaries.
- [x] Produce [Phase 1 entry](PHASE_1_ENTRY_PLAN.md), with explicit non-production scope.
- [x] Pass local documentation checks and record their actual scope below.

These checked items mean documents/source review exist, not that a protocol has
passed runtime, model or cloud tests. D01-D12 now have candidate resolutions; none
is marked protected-accepted by this local checklist.

## Required review before Phase 0 acceptance

- [ ] D01/D03: accept the prepare/accept extension and chosen-value preservation
  argument, including its relation to charter principle 7 and V5.0 proof authority.
- [ ] D02/D08: accept durable promise/restart rules and the explicit exclusion of
  automatic same-group disk replacement; no implicit stable-state loss recovery.
- [ ] D04/D05: accept lifecycle and fresh-NO_OP/pinned-view read semantics, including
  the force/log cost, cursor behavior and callback/rebuild/close races.
- [ ] D06/D07: approve exact public inventory, outcome meanings, 1.2 separation and
  source-preserving new-group transition; keep all configured contracts unchanged.
- [ ] D09/D10: approve finite bounds/timing policy, lifetime exhaustion and observable
  evidence, without interpreting configuration defaults as measured SLAs.
- [ ] D11/D12: approve independent foundation/E01-E12 coverage and phase ownership.
- [ ] Resolve any review counterexample or compatibility objection in the owning
  document; do not turn it into an undocumented implementation choice.
- [ ] Record protected Phase 0 PR, accepted master commit and exact-master CI result
  with actual executed/skipped scope.
- [ ] Obtain the user's Phase 1 instruction before declarations or version opening.

## Acceptance identity

| Item | Current state |
| --- | --- |
| Reviewed planning checkout | `09d2bf247f004eb134eb81c59ee88005affafe92` |
| Published replication reference | V5.0 `e6afb5349c018fe163d4938d7637a4de8854d4ea` |
| Phase 0 acceptance PR / master commit | Pending; not inferred from planning PR #183 |
| Exact accepted-master CI | Pending |
| Phase 1 implementation authorization | Pending |
| New automatic model/runtime/cloud evidence | Not executed in Phase 0 |

## Validation record

Local checks on 2026-09-19, against the reviewed checkout plus this documentation diff:

| Check | Actual result |
| --- | --- |
| `git diff --check` | PASS; expanded scan also checks all six untracked candidate documents |
| `scripts/verify-v50-phase0-contract.sh` | PASS, existing V5.0 contract gate; its `phase=accepted` describes V5.0, not V5.1 acceptance |
| `python3 -m unittest scripts.test_ci_changes` | PASS, 14 existing classifier tests |
| Local Markdown/scope review | PASS, 13 changed/new files; 574 local links, 15 section anchors and 3 balanced fenced blocks |
| Decision/evidence/public inventory | PASS for structural completeness: D01-D12, E01-E12, I01-I08, ten distinct proposed top-level public types; not semantic or compiled compatibility proof |
| Historical preservation | PASS, charter plus 59 V5.0 files byte-identical to HEAD; historical navigation tails and release/measured commit identities unchanged |
| CI path classification | All 13 paths classified documentation-only by the existing classifier; no remote run claimed |

The expanded review used a temporary local checker, not a new repository test or
workflow. It checked file scope, all changed/new Markdown destinations and heading
anchors, fences/whitespace, register coverage, candidate API-name uniqueness,
commit references and pending acceptance state. It did not check protocol safety.

No Java/source, tests, scripts, dependencies, Maven coordinates, workflows, golden
bytes, accepted V5.0 documents, baseline registries or release identities change in
this batch. Documentation checks cannot close the unchecked review/acceptance items.
