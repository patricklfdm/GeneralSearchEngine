# Phase 3: replay the complete declared hosted history set offline

Status: offline original replay entry implemented; Phase 3 remains OPEN.

The [seed gate](PHASE_3_SEED_COHORT.md) reconciles independent preparations.
`scripts.v53.phase3_history_cohort` now consumes that same complete twelve-subset
index and **raw original artifacts**, calls every owning downloaded verifier,
then calls every owning aggregate. It never consumes downloaded PASS receipts
as a substitute for replay and never calls a producer, Maven or GitHub.

The current catalogue is **544 declared whole histories in 238 execution groups**,
stored in **478 raw archives**. The difference is intentional: joining-process
has 120 groups containing three separate originals each, while transfer and
automatic groups contain several whole histories in a single archive. A lease,
source or continuous history is not divided for replay. These counts are not
the 3310 frozen Phase 5 scenarios and do not establish coverage by themselves.

## Inputs and invocation

Use a clean checkout at the exact recorded source, with the existing tools
required by the owning readers. The index and seeds use the unchanged
[seed-set contract](PHASE_3_SEED_COHORT.md#input-contract). Select each exact
run/attempt explicitly and retain failed/superseded attempts separately.

```text
seed-set.json
seeds/<cohort>/manifest.json
seeds/<cohort>/bundle.tar.gz
raw/<cohort>/<original-raw-artifact-name>/manifest.json
raw/<cohort>/<original-raw-artifact-name>/bundle.tar.gz
raw/joining-process/<original-raw-group-artifact-name>/<case-slug>/manifest.json
raw/joining-process/<original-raw-group-artifact-name>/<case-slug>/bundle.tar.gz
```

Artifact names and joining case slugs come from the existing owning adapters;
they retain the original workflow/run/attempt binding. Missing or extra cohorts,
groups, child archives and files reject. Copy downloaded artifacts unchanged.

```bash
python3 -u -m scripts.v53.phase3_history_cohort \
  --index target/v53-phase3-cohort/seed-set.json \
  --seeds target/v53-phase3-cohort/seeds \
  --inputs target/v53-phase3-cohort/raw \
  --output target/v53-phase3-cohort/history-audit-01
```

The output must be new and outside all inputs. It retains the chosen index,
complete archive/manifest hash inventory, seed audit, per-group reader receipts
and progress, each owning aggregate and the final receipt. Group changes are
printed immediately and the entry emits a heartbeat every minute. `active` and
the completed-group counter are saved throughout the run.

Extraction is sequential to avoid retaining hundreds of expanded seed/build
copies. After a successful reader, only its newly created scratch is removed;
small receipts/progress and every input archive remain. Failure stops the outer
cohort without retry, retains the failing scratch and records its location in
`failure.json`. The joining owner still collects the three outcomes in its
existing group before rejecting that group. It does not retry a failed history.

## Validation and scope

The entry first inventories every raw archive and checks workflow/context/case
bindings, regular bounded files, hashes, duplicate JSON keys, and complete group
membership. The existing seed gate then checks complete Git source, actual
classes, tools, dependencies and each distinct reader set. Every owner reopens
its original archive, runs its existing original-first physical/history/network
checks and exact negative vectors, and verifies original producer/plan bindings.
Only these newly generated verifier receipts enter the owning aggregate.

All twelve aggregate functions accept an explicit keyword-only
`offline_replay=True` for this caller. It requires both workflow result arguments
to be `None` and changes the successful receipt to `PARTIAL`,
`offlineEvidenceOnly: true`, `workflowExecutionAttested: false`. All other checks
and scope fields remain. Their CLI/workflows continue using the default mode,
which requires successful execute and verify stages. No workflow is changed.

The complete raw inventory, seed archive identities, index, catalogue and clean
checkout are rechecked after the final replay. Successful overall output is:

```json
{
  "status": "PARTIAL",
  "allDeclaredHistoriesReplayed": true,
  "historiesReplayed": 544,
  "groupsReplayed": 238,
  "rawArchives": 478,
  "workflowExecutionAttested": false,
  "runtimeQualified": false,
  "frozenScenarioCoverageQualified": false,
  "combinedPeakResourcesQualified": false,
  "phase3Complete": false
}
```

This is the output contract, **not an observed full native result**. The current
development validation uses synthetic archives and orchestration readers for
the complete routing test, real owning seed readers, all twelve actual aggregate
contracts, and the actual REMOVE and three-original joining downloaded verifiers
with synthetic physical oracles. It proves routing, provenance, rejection and failure retention. It does
not execute 544 JVM histories. See the [development receipt](phase3-evidence/history-cohort.json).

An authorized final-source hosted set, independently attested workflow stages,
precise Phase 3 coverage, missing protocol axes and simultaneous resource-limit
qualification still remain. This entry does not close those requirements or
relax any workload parameters, limits, CI checks or cloud admission.
