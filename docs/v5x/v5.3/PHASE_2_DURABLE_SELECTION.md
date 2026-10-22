# Phase 2C1 — durable original selection

Status: **locally complete for SELECTED metadata under the storage owner**.
This records a campaign decision. It does not install a generation, authorize an
installation ACK/ACCEPT or enable the public runtime. Phase 2 remains open.

## Exact decision and original local source

`MembershipGrantJournal.selectCurrent` runs under the same exclusive owner and
writer monitor as PROMISE/BASIS. It recomputes the decision with the Phase 1
selection verifier: one complete ordered eligible quorum, containing the proposer,
compatible proven cuts, required ancestry and the highest applicable accepted tail.
The selected voter must also have its own completed original local BASIS in the set.
Both proposer and selected-follower recording are supported.

`originalSource` now derives the local BASIS/tail ownership observation from the
actual retained packet/images and forced journal. It rechecks identities, hashes
and capsule semantics. A caller's substitute local basis or packet is rejected.
Remote sources still require separately authenticated ownership observations; this
batch's remote fixtures are conditional inputs, not remote filesystem forces.

The existing 1.3 SELECTED frame is appended to the bounded journal. Replay binds
root, view, full ballot, the local original basis UUID/digest, distinct ordered
source identities, governing quorums and selected cut. It permits at most one
SELECTED per complete grant. A fresh higher PROMISE starts a new selection slot
while retaining the entire previous journal/source prefix. Live promise/basis
indexes are also updated after append for later storage integration.

Before append, the implementation checks remaining journal capacity. It then
observes `SELECTED_BEFORE_WRITE`, `SELECTED_WRITTEN`, `SELECTED_FORCED` and
`SELECTED_BEFORE_RETURN`, checking the ballot fence and physical owner before
return. Higher observations do not wait for a blocked writer monitor. A write,
force or return-boundary failure poisons the handle; close/reopen is required.

An exact duplicate verifies the offered decision and returns the original frame
without another write. A different quorum, source binding or recovered choice at
the same ballot is refused, including after reopen or a lost response. Selection
with a longer verified parent does **not** change the current generation/selector.

## Recovery and limits

| Durable state | Result |
| --- | --- |
| Complete local grant, no SELECTED bytes | A validated decision may be recorded |
| Complete SELECTED, response lost | Reopen seals the visible frame; only the exact original decision may repeat |
| Later complete PROMISE/BASIS | A new ballot may record its own decision; earlier bytes remain retained |
| Torn, duplicate, corrupt or rebound SELECTED | Refuse open without truncating, deleting or silently choosing another decision |
| Source unavailable before installation | Retain the recorded choice; the later protocol must abandon the campaign, not reselect at the same ballot |

Journal replay alone cannot re-establish remote source availability or authorize an
installation. The installer must fetch/reverify/force the selected state and issue
an ACK only after its own durable transaction. Bounded journal rotation, complete
generation recovery and repair of interrupted storage remain later Phase 2 work.

## Local evidence

[Summary and exact hashes](phase2-evidence/durable-selection.json) bind parent
`8c46f92` plus the validated local implementation before reporting edits. Originals
remain under `target/v53-phase2-selection/`.

- 98 focused Java tests passed, including nine new methods for exact persistence,
  duplicate/reopen/conflict, real local source derivation, higher fencing at every
  cut, blocked writer observation, lost response/concurrent duplicates, selector
  replacement, malformed journal, compacted longer source and selected follower.
- 58 Python/build-contract tests and 42 optimized-Python tests passed.
- The final matrix passed 54 cases / 270 fresh JVMs: each size 3/4/5, tail/no-tail,
  clean selection and halt/SIGKILL at every selection cut. Every history checks
  conflict refusal without mutation and a later fresh-ballot decision.
- Independent replay verifies actual local source/generation files, exact remote
  fixture bytes, selected references/choice, force events and process outcomes.
  Eleven original-first exact-reason negatives and relocated replay passed.
  Final elapsed time: 161.472 seconds.
- Current-generation regression: 90 cases / 360 JVMs / 13 negatives, 157.557 seconds.
  Grant regression: 45 cases / 180 JVMs / 8 negatives, 47.624 seconds. Both passed
  portable replay; all three raw receipt inventories/hashes were checked.

The initial passing matrix reused a remote fixture basis UUID across distinct
ballots. The worker now assigns deterministic distinct ballot/node UUIDs and the
reader rejects reuse. The full final matrix and regressions were rerun; the first
result is retained as superseded evidence. No workload measurement was retried.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_durable_selection_evidence \
  scripts.v53.test_current_generation_evidence scripts.v53.test_basis_sources_evidence \
  scripts.v53.test_grant_evidence scripts.v53.test_allocator_evidence \
  scripts.test_ci_v51_bundle
python3 -m scripts.v53.durable_selection_qualification \
  "target/v53-phase2-selection/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. These are local crash/force observations, not power-loss,
network consensus or public service evidence. The 5.3 shared-build contract adds
the suite and worker without removing any existing gate. No workflow, frozen format,
POM, inherited runtime, V5.2 cloud action or remote push changed.
