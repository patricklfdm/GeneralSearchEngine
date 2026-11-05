# Phase 3 exact candidate witnesses

Status: source audit implemented; native qualification and Phase 3 remain OPEN.

The [witness plan](phase3-coverage-witnesses.json) associates all twelve Phase 3
requirements with nineteen specific candidate witnesses in the existing twelve
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

The existing schedule remains **544 histories, 238 execution groups and 478 raw
archives**. This audit adds no hosted job and changes no workload or budget.

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

## What this does not close

- Native carried-process halt/SIGKILL qualification is not replaced by the older
  Phase 2 conditional `carried_process_evidence` matrix. Node-rename process
  witnesses cover their specific cuts, not every carried completion boundary.
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
```

The command retains the inspected plan, deduplicated catalogue, exact source
hashes and receipt. Existing output is rejected without overwriting it. Failure
is retained as `FAIL`; success means `source-selector-audit-only`, with zero
native histories executed and all runtime/phase acceptance flags false.

The focused tests exercise partition preservation, catalogue drift including
unselected negatives, stage collisions, conditional applicability, scope
promotion, deterministic read-only inspection and preservation of failed output.
See the [development receipt](phase3-evidence/coverage-witnesses.json).
