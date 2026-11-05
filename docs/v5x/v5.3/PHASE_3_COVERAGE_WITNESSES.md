# Phase 3 exact candidate witnesses

Status: source audit implemented; native qualification and Phase 3 remain OPEN.

The [witness plan](phase3-coverage-witnesses.json) associates all twelve Phase 3
requirements with twenty specific candidate witnesses in the existing twelve
hosted subsets. A witness names its original archive, complete history set,
reader suite/stage, exact negative case and expected rejection reason. It also
states its limited scope and the remaining work for the requirement. These are
reviewed candidate associations, not proof that the requirement is covered.

The [inspector](../../../scripts/v53/phase3_coverage.py) derives its catalogue
from the actual owning cohort/reader modules. It checks the plan against the
entire catalogue hash, including unselected negatives, and against the unchanged
acceptance-plan hash. Unknown cases, suite/stage aliases, reason drift, omitted
members and silent conditional-to-unconditional promotion fail inspection.
It executes no producer, Maven command, network request or evidence replay.

## Whole-history boundaries

The current schedule has **552 histories, 246 execution groups and 486 raw
archives**. Carried DATA v2 adds eight indivisible whole-group process executions
to the same hosted subset. Its cross-life delivery rejection supplies the twentieth
candidate witness. The source inspector itself runs no job or workload.

| Source unit | Required boundary |
| --- | --- |
| Joining-process group | Three distinct, complete archives; each keeps its own negative vector. |
| TCP lifetimes | One archive containing all three stable-size histories and its shared vector. |
| Transfer process recovery | One archive containing all eighteen original process histories. |
| Reply revocation | One archive containing all forty-eight histories and its shared vector. |
| Other units | One complete archive per declared member. |

A negative attached to a shared matrix is not separately attributed to every
child history. An individual cell, crash/recovery segment, source generation or
resource lease must not be extracted as an independent passing witness. The
catalogue deduplicates identical *source definitions* only; it does not deduplicate
runtime histories or substitute one original for another.

## Conditional evidence

Four registered witnesses depend on observations in the original. Adoption
fences/promises can be absent; a late unused PREPARE may never occur; joining
authority negatives depend on the actual source/learner observations. The
inspector retains their conditional status. It does not manufacture an original
to select an expected result, and `NOT_APPLICABLE` remains distinct from a
rejection established by mutation and replay.

The source catalogue also retains both supported automatic competition branches.
Only the original reader can choose `pregrant` or `superseded`. Capture-dependent
reason templates remain unbound at audit time. An unsupported original shape
must retain its failure; the audit does not authorize retrying until a preferred
shape appears.

## Observations from offline replay

The [whole-history cohort](PHASE_3_HISTORY_COHORT.md) now loads and validates this
plan before replay. After each owning verifier returns, the internal
[observation hook](../../../scripts/v53/phase3_witness_observations.py) rechecks
its complete result contract and extracts the exact selected rows. Each row is
bound to the current workflow context, original archive hash and owning replay
hash. A joining-process witness must come from its own child archive, even when
three children share one execution group.

Conditional absence is copied from the owning reader's checked original; late
unused PREPARE absence is derived from its checked network observations. An
unrelated failure, missing negative, wrong child, stale attempt or invented
rejection fails the cohort. This hook has no standalone receipt-admission CLI
and does not replace original physical replay.

The cohort retains `coverage-plan.json` and incremental
`witness-observations.json`. Only after all original replays, owning aggregates
and final inventory/source checks succeed does it write `coverage.json`, with
separate rejection and not-applicable counts for all twenty witnesses. Its
status remains `PARTIAL`; observing every candidate does not close a requirement
or qualify the frozen S/N matrix. A replay failure preserves earlier diagnostics
without retrying the original. See the
[integration development receipt](phase3-evidence/witness-observations.json).

## What this does not close

- Native carried-process halt/SIGKILL qualification is not replaced by the older
  Phase 2 conditional `carried_process_evidence` matrix. The carried DATA
  subset now includes eight native whole-group histories; final-source execution
  remains required. Node-rename witnesses retain their own distinct scope.
- Simultaneous runtime resource maxima, admitted FINAL/recovery and stable DATA
  after resource exhaustion still require original evidence.
- These candidate associations do not establish complete Phase 3 schedule or
  rejection-family coverage. All 3310 frozen S rows and 24 N families retain
  their existing Phase 5 acceptance ownership; no rows are marked covered.
- The final-source twelve-subset replay and exact-attempt workflow attestation
  remain separate. A source audit receipt cannot replace any of those checks.

## Run and validation

From the repository root, choose a new output directory:

```bash
python3 -m scripts.v53.phase3_coverage --output target/v53-phase3-coverage/audit-new
python3 -m unittest scripts.v53.test_phase3_coverage scripts.v53.test_phase3_qualification_plan
python3 -m unittest scripts.v53.test_phase3_witness_observations scripts.v53.test_phase3_history_cohort
```

The command retains the inspected plan, deduplicated catalogue, exact source
hashes and receipt. Existing output is rejected without overwriting it. Failure
is retained as `FAIL`; success means `source-selector-audit-only`, with zero
native histories executed and all runtime/phase acceptance flags false.

The focused tests exercise partition preservation, catalogue drift including
unselected negatives, stage collisions, conditional applicability, scope
promotion, deterministic read-only inspection and preservation of failed output.
See the [development receipt](phase3-evidence/coverage-witnesses.json).

The [carried DATA v2 integration receipt](phase3-evidence/carried-process-cohort.json)
records the current expanded catalogue checks. Earlier development receipts
retain their original smaller catalogue and are not rewritten as new execution.
