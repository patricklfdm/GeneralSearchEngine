# V5.3 local development and later integration

## Operator instruction, 2026-10-21

Develop V5.3 on one new local branch while V5.2 cloud work continues. Make coherent
local commits, do not push, and collect the final acceptance work after development.
Merge only after V5.2 publication. This instruction replaces the usual
operator-owned commit boundary for this branch, not the push/publication boundary.

Branch: `feat/v53-cluster-operations`.
Base: `73f3bd5c21c97eee564397ab11af7b66bc1b13a3` (PR #349).
The preceding local fix commit `0aaba1ae79e49fa03e407da5fbb9234f73aedd68`
has the same tree; the branch uses the actual merged master commit.
The V5.2 run observed at entry is `39678504498/1`, still in progress at that time,
on the base source and the separate D-backed self-hosted Runner.

## Work rules

- All development edits and commits stay on this branch. Do not push, open a PR,
  merge, tag, publish or dispatch a V5.3 cloud experiment under this instruction.
- Keep the running V5.2 Runner checkout, artifacts, lease, configuration, budgets
  and workflows untouched. A local branch is not the source of its running job.
- Run focused local checks for each changed component and retain their results.
  Deferring final acceptance does not mean accumulating untested changes. Avoid
  concurrent large workloads on the host currently supervising V5.2 cloud work.
- Intermediate protected CI may be deferred on this local branch. Do not label
  local research or a passing unit test as an accepted consensus protocol.
- New design/model files start under `docs/v5x/v5.3/` and `scripts/v53/`. Preserve
  existing Java, POM, CI, frozen inventories and release pins in this entry batch.
  Phase 1 must open aligned V5.3 coordinates before adding production declarations;
  do not silently ship V5.3 runtime changes under the V5.2 version.
- No assumption that V5.2 will need only harness fixes. Record and incorporate
  later V5.2 runtime fixes as separate integration commits and rerun affected checks.

## Local implementation order

| Stage | Deliverable / local exit |
| --- | --- |
| Entry research | Fixed-membership audit and arithmetic complete locally; single-slot ballots and bounded multi-slot handoff tested; compaction/production integration open |
| Phase 0 | Complete authority/transition/recovery contract, exact API and bytes, resource limits, adversarial schedules; resolve all blocking decisions |
| Phase 1 | Aligned coordinates, declaration-only APIs, independent election/transition model, byte fixtures, process/network scaffolding |
| Phase 2 | Configuration-aware storage, promises, proof validation, snapshot and recovery; reject ambiguous authority |
| Phase 3 | Learner lifecycle, joint transition, generalized activation and finalization under deterministic faults |
| Phase 4 | Public add/remove/replace, queryable operation identities, retirement and same-version maintenance |
| Phase 5 | Combined read/election/reconfiguration/restart/resource hardening and independent physical evidence |
| Phase 6 | Freeze and execute local workloads; prepare the separately authorized cloud plan |
| Integration | Incorporate released V5.2, pin actual controls, run unified compatibility/build/runtime/evidence acceptance, then request push/PR |

Phases may have several local commits. Entry research now includes quorum arithmetic
and single-slot ballots plus a bounded multi-slot transition model. It still does
not satisfy the complete Phase 1 storage/transition gate; see
[the precise limits](TRANSITION_CHAIN_RESEARCH.md).

## Integrating the released predecessor

After V5.2 publishes, verify the signed tag, released source and actual artifact
digests. Review changes since the recorded base. Merge the released master into
this local branch, preserve both histories, and resolve conflicts by semantic
ownership rather than selecting an entire side. Do not merge V5.3 into master yet.

Pay particular attention to shared replication classes, the read-token contract,
version alignment, compatibility consumers, shared build manifests, suite registry,
workflow generators and exact-source cloud consumers. Qualify V5.3 against the
real released V5.2 controls before calling the accumulated work ready. Neither
the running V5.2 experiment nor its source may be relabelled as V5.3 evidence.
