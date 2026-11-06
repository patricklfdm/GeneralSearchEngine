# Whole native learner history cohort

Status: immutable capture, a two-member exact-source gate and isolated hosted
wiring are implemented. Neither native history was executed on this final source
in this batch. Phase 3 remains **OPEN**.

## Exact scope

| Case | Existing native method | Required independent replay |
| --- | --- | --- |
| `alternating-slots` | `V53LearnerAlternationNetworkTest#nativeSixRevisionsAlternateFixedSlotsAndColdReopenWithinOneReservation` | Six PREPARE revisions, 25 retained snapshots, selected/retired A/B slots, final CANCEL and 12 exact negatives |
| `retained-cancellation` | `V53NativeLearnerBytePressureQualification#actualCancelledLearnerRejectsBytePressureAndCompletesColdRecovery` | Native READY/CANCEL, original prepared ancestor, two forced retention rounds, nonvoting cold reopen, four complete campaigns, original resource lifetimes, three same-original byte-pressure cold lifetimes and 62 exact negatives |

The pair is a focused **3-ADD** component qualification. It does not cover all
five joining profiles, process death, autonomous membership, the complete native
network schedule or maximum simultaneous resources. All those claims, and
`phase3Complete`, remain false even after this pair passes.

The existing 900-second revision-history and 600-second cancellation-history
budgets are unchanged. The cancellation method now captures the same admitted
learner resource pool and real close boundaries, then adds three explicit cold
lifetimes whose budgets are fixed from the same original files before opening. The [earlier final-CANCEL timeout](PHASE_3_LEARNER_CYCLE_REPLAY.md)
remains a failed original. This entry neither retries it nor extends its deadline.
The [historical retained-cancellation success](PHASE_3_LEARNER_RETENTION_REPLAY.md)
belongs to its earlier source and cannot fill a final-source cohort slot.

## Original resource integration

The cancellation member now uses the [native learner byte-pressure wrapper](PHASE_3_NATIVE_LEARNER_BYTE_PRESSURE.md).
Collection preserves the complete `original/` resource wrapper and every
`pressure/{pool-full,packet-short,source-exact}` mode. The exact JUnit method and
case-specific output directory are required. Source/build/toolchain/reader pins
and the original plan bind the entire indivisible history. Neither the legacy
cancellation producer nor the resources-only producer can fill this member.

Downloaded replay validates all original voter, learner, transfer and retention
evidence before any negative receives credit. Aggregation requires four
campaigns/eight publications, the original two generation handoffs/six closes,
every physical snapshot extent, and the three additional cold lifetimes with
exact derived byte limits, expected rejection/acceptance and nine further close
intervals. Each mode must use the same original extents. All 62 exact negatives
are mandatory: the existing 50 plus ten byte-pressure observation mutations and
two byte-pressure physical mutations. Namespaced byte cases cannot shadow an
existing resource or physical negative. Missing modes, changed limits, a wrong
rejection reason, different suites, early release or full-runtime overclaims
reject acceptance.

The pair remains two native executions and two downloaded replays. No workflow
job or additional expensive history is added; the optional workflow consumes
the updated catalogue dynamically. The phase-wide source witness map distinguishes
in-memory accounting mutations from physical evidence mutations. All global
scheduling counts are unchanged. Final-source execution and acceptance remain
pending; the local development original cannot satisfy the new exact method
and source/build pins.

The resources-only [integration index](phase3-evidence/learner-resource-cohort-development.json)
retains its earlier adapter replay and provenance tests. The new byte-pressure
integration record is `phase3-evidence/learner-byte-cohort-development.json`.
Adapter replay of the unchanged retained byte-pressure original passed all 62
cancellation negatives in 100.735 seconds. This exercised the actual collector,
composed replay and aggregate-result guards without another native execution.
It does not replace final-source provenance/admission. Earlier development
receipts below preserve their original scope and are not rewritten.

## Capture and admission

[`learner_history_run.py`](../../../scripts/v53/learner_history_run.py) creates a
new immutable source copy. It records source hashes, exact tool identities, a
single unretried Maven/JUnit method, compiled class inventories, native files and
logs. `--source-from` copies only the retained source, not generated state. Current
readers must belong to that source before the native command starts.

Collection runs from the immutable copy too. It checks the complete declared
file layout, fixture scope and observation containers, and records their hashes.
The result stays `PARTIAL`, with `nativeHistoryQualified=false`. It does not grant
authority merely because Java returned PASS. Failure retains the original source,
logs and any raw files, without starting a second native attempt.

[`learner_history_cohort.py`](../../../scripts/v53/learner_history_cohort.py)
recollects each original and verifies exact source/build/toolchain/readers,
command, JUnit and file identities. It rejects missing/extra histories, linked
inputs, changed classes, unavailable source, flaky/rerun JUnit and aliases of one
original. The same original plan cannot fill both slots. Recorded absolute paths
remain data for the independent reader; relocating an archive does not relocate
its authority.

The existing revision reader and composed resource/cancellation reader validate the
unmodified original before any evidence mutation. Cancellation always uses
`retained_learners=True` and `current_retention=True`; legacy diagnosis or a
legacy five-slot history is not an accepted substitute. All 74
negative entries must match their exact case/status/reason vector. An invalid
original or unrelated rejection fails. Producers and reader pins are checked
again after replay; mutations cannot escape into the retained original.

The two-history aggregate can use one or two independent replay workers. Each
history remains intact. Both terminal results are retained if one fails, with no
retry. Success can set only `declaredLearnerHistoryPairQualified`; it cannot close
the phase or erase the earlier failures.

## Hosted entry

[`v53-learner-histories.yml`](../../../.github/workflows/v53-learner-histories.yml)
accepts manual dispatch or push to `experiment/v53-learner-histories`. It has
`contents: read` only. No dispatch, push, PR or paid cloud run is performed by this
development batch; those actions remain separately authorized.

Six expanded jobs prepare one immutable source/build/dependency seed, execute
two whole histories, independently replay two downloaded originals, and aggregate
the complete pair. Execution and verification each allow two workers and use
`fail-fast: false`. The six revisions, cancellation and cold recovery within each
history cannot be split across runners. Both execution and verification stages
must succeed before the aggregate accepts anything.

Artifacts bind repository, workflow, source, run, attempt, role and exact case;
they are retained for 90 days, including failed originals and diagnostics.
The verifier checks downloaded bytes, seed identity and original receipts before
running its own original-first replay. The aggregate requires exactly two
same-attempt verifier receipts and distinct original plans/raw archives. A passing
receipt from another attempt cannot replace a failed member.

This entry reuses the existing pinned Java 21.0.12, Python 3.11, Maven 3.9.11 and
SHA-pinned Actions setup. Its 360-minute Actions job envelope does not change
native fixture deadlines. The wrapper prints progress every 60 seconds during
preparation, execution, packing and replay; summaries include source, run/attempt,
history, scope, pins and available negative counts. Existing CI/Required and
V5.2 workflows are unchanged.

## Local inspection and explicit execution

Inspect the commands and current reader manifest without running Java:

```bash
python3 -B -m scripts.v53.learner_history_cohort plan
```

After preparing offline dependencies, explicitly capture a whole history into a
new directory (this command runs the long native history):

```bash
python3 -u -m scripts.v53.learner_history_run \
  target/v53-learner-history-local/alternating-slots \
  --case alternating-slots --maven /opt/maven/bin/mvn
```

Use the hosted seed for comparable runs. A standalone `member` or `aggregate`
requires explicit `--source-sha256`, `--build-sha256`, `--toolchain-sha256` and
`--reader-sha256`; inspect `--help` for inputs. Its aggregate directory must contain
exactly `alternating-slots/` and `retained-cancellation/`. All output directories
must be new; prior evidence is not overwritten.

Local synthetic tests exercise source/build/tool drift, collection scope, exact
commands, JUnit rerun refusal, relocated originals, failed capture preservation,
original-first replay, exact negatives, unique history bindings and hosted stage
and attempt refusal. They establish admission behavior, not native success.
The earlier retained-cancellation original is used separately for portable
diagnostic replay; it remains historical evidence. Long final-source native
execution is deliberately deferred to the implemented hosted entry.

The [development receipt](phase3-evidence/learner-history-cohort.json) retains
input and validation hashes. The Python suite passed 2,205 tests; one additional
download-shape regression was then included in the final 52-test optimized
selection. Implementation was unchanged between those checks. Historical
portable replay passed all 31 cancellation negatives with original bytes intact.
YAML, five shell blocks, six expanded jobs and nine unique uploaded artifact
names were checked. `actionlint` was unavailable. These checks do not replace
the unexecuted final-source native pair.

Rollback removes the capture/cohort/hosted modules, optional workflow, tests and
inventory/documentation references together. No runtime or persisted-format
migration is required. Preserve all original evidence and failed attempts.
