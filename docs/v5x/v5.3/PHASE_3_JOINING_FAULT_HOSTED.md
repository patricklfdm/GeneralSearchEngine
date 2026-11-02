# Phase 3 — hosted joining source-reply faults

The isolated hosted entry now connects the
[complete reply-loss composition](PHASE_3_JOINING_FAULT_COMPOSITION.md) to one
prepared source/build and three independent original histories. This batch
implements orchestration and tests its authority boundaries. No new native
history or GitHub campaign has run; final-source execution and Phase 3 closure
remain OPEN.

## Whole histories and independent replay

[The workflow](../../../.github/workflows/v53-joining-source-faults.yml) permits
only manual dispatch or a push to `experiment/v53-joining-source-faults`. It has
`contents: read` permission, no cloud identity and no release authority. It does
not alter regular CI, Required or the existing ordinary-profile/REMOVE workflows.

| Stage | Expanded jobs | Work and result scope |
| --- | --- | --- |
| Prepare | 1 | Freeze source, reference classes, actual tool identities and offline dependencies; PARTIAL |
| Execute | 3 | One complete original `3-ADD` history per reply kind; PARTIAL |
| Verify | 3 | Download each original; independently replay the full original and both negative families; PARTIAL |
| Aggregate | 1 | Require the exact three successful same-attempt verifier receipts and workflow stage results; PASS for this fault subset only |

The exact cases are `SOURCE_OFFER`, `CHUNK` and `TRANSFER_COMMIT`. Both matrices
use `max-parallel: 3` and `fail-fast: false`. Each worker preserves bootstrap,
initial learner acquisition, INTENT, FINAL, publication and cold reopen in one
continuous filesystem history. No stage can be filled from a different worker,
retry or ordinary-profile execution.

Preparation reuses the existing `remove_process_hosted.prepare_source` routine,
which runs the short ballot allocator tests and freezes reference class bytes.
Each original uses `joining_history_run --fault CASE --source-from SEED
--portable-toolchain`, builds offline and must reproduce all three reference
class inventories. Preparation shares immutable source and dependencies; it does
not eliminate worker compilation or copy prepared runtime state into a history.

Verification begins after the execution matrix finishes, including when another
member failed. Available originals can still produce independent diagnostics;
a missing or failed member blocks final acceptance. A failed, skipped or cancelled
execution/verification stage cannot pass the aggregate. No automatic measurement,
JVM or semantic-replay retries are configured.

Each downloaded original must pass the complete implemented physical,
continuation, transfer, export, maintenance, peer/future/learner and ballot chain
before any fault negative. Fourteen exact fault cases and twenty-one declared
ballot cases are checked separately. Only adoption cases without a target in the
validated original may be `NOT_APPLICABLE`. The aggregate checks these exact
vectors and provenance; it does not repeat the expensive physical replay after
all three independent verifiers have already done so.

## Artifact and attempt authority

Every seed, original and verification artifact is bound to workflow, source SHA,
run ID, attempt and artifact role; member artifacts also bind the exact reply
kind. The new schema prevents substitution from the ordinary-profile or REMOVE
workflow even when other identity fields happen to match. Source, build, tool
and reader pins are checked against original bytes; copied plan identities and
raw archive hashes cannot fill more than one cohort slot.

The aggregate requires exactly three named verifier directories, each containing
its one receipt, with all execution/verification jobs successful. Partial reruns
cannot borrow seed or member artifacts from an earlier attempt. A replacement
qualification requires the complete new attempt, retaining the earlier failure.

The bounded archive helpers verify hashes and extracted inventories and reject
linked/traversing archive members. Raw files are rechecked after replay. Failed
originals are also archived when possible. If packing fails, the receipt records
that failure separately; an existing native failure remains the primary error,
and a previously successful execution becomes failed. The workflow additionally
retains available execution logs and diagnostics even if packing failed.

All twelve expanded artifact names are unique and retain evidence for ninety
days. Complete producers and source/build manifests remain necessary for later
replay; aggregate summaries alone are insufficient. All stages use the existing
sixty-second progress reporter. GitHub summaries show source, run/attempt, reply
kind, result scope, available pins and separate negative counts. Jobs retain the
platform's configured 360-minute ceiling; protocol and resource limits are unchanged.

## Entry and validation

The workflow invokes `python -B -m scripts.v53.joining_fault_hosted`:

```text
plan
prepare --output NEW_PREPARATION
execute --seed EXACT_ATTEMPT_SEED --case CHUNK --output NEW_EXECUTION
verify --seed EXACT_ATTEMPT_SEED --inputs ORIGINAL_RAW --case CHUNK --output NEW_VERIFIER
aggregate --seed EXACT_ATTEMPT_SEED --inputs THREE_VERIFIERS --output NEW_AGGREGATE
```

The entry validates actual GitHub workflow/ref/checkout/run/attempt context.
Outputs must be new directories. Local diagnostic readers remain available
through `joining_fault_cohort` and `joining_fault_evidence`; they cannot fabricate
a hosted context or promote old-source diagnostic replay into this cohort.

The [implementation receipt](phase3-evidence/joining-fault-hosted.json) records
synthetic seed/archive round trips, single-call native execution stubs, original
failure refusal, cross-source/attempt/case/schema substitution, dependency and
class drift, both exact negative families, missing/duplicated histories, failed
workflow stages and preservation of simultaneous native/archive failures.
These tests qualify orchestration behavior, not native or hosted execution.

All 1,991 V5.3 Python tests pass. The 21 new hosted/workflow tests also pass
with Python assertions disabled, and 61 related profile, REMOVE and fault-cohort
regressions pass. YAML expansion and nine shell commands were checked: eight
expanded jobs, twelve unique artifact names, matching download patterns and
ninety-day retention. These are local implementation checks; no Actions job or
native membership measurement was executed.

Final-source ordinary profiles, this fault cohort, remaining process/fault
histories, combined resource bounds, complete original-observation coverage and
the frozen S/N dependency audit remain required. No production Java, POM, frozen
protocol/workload, paid-cloud execution or release behavior changed in this batch.
