# Phase 3 — joining reply-loss composition and final-source cohort

The three original `3-ADD` reply-loss histories now have an explicit validation
path through the full implemented joining composition. This extends the
[earlier fault matrix](PHASE_3_JOINING_FAULT_MATRIX.md) with the later continuous
future/learner ledgers and [ballot checks](PHASE_3_PROFILE_BALLOTS.md).
A separate cohort entry binds future executions to their actual current reader
source. This batch runs diagnostic replay of retained originals; it does not
execute a new JVM history or qualify a final-source cohort. Phase 3 remains OPEN.

## Original first, then both negative families

The `--full-chain` option selects the complete ordinary `3-ADD` ballot reader,
including its physical, continuation, network, export, control, maintenance and
continuous peer/future/learner prerequisites. The fault reader then requires one
original declared SOURCE_OFFER, CHUNK or TRANSFER_COMMIT loss and its matching
recovery. The learner's original request, start, deadline and donor authority
remain bound to that same continuous history.

Only after the complete original passes may the fourteen fault mutations run.
Ballot qualification independently replays its original again, checks its
result matches the preceding original, and runs its twenty-one declared cases.
Each rejected variant must fail for the exact expected reason. Adoption variants
may be `NOT_APPLICABLE` only when the validated original has no corresponding
adoption. Both families mutate copies; the retained raw inventory must remain
unchanged. This does not claim every preceding layer's negative suite or full
physical prerequisite replay for every mutated variant.

```bash
python3 -B -m scripts.v53.joining_fault_evidence ORIGINAL_RAW \
  --full-chain --qualify
```

The legacy default remains peer-ledger qualification with its existing result
shape. Existing historical receipts and `joining_fault_matrix` are not silently
reclassified as full-chain or current-source evidence. Full-chain composition
also retains the earlier conservative broad completion flags; the explicit
`fullImplementedCompositionQualified` field describes this additional scope.

## Final-source producer binding

`scripts.v53.joining_fault_cohort` requires exactly three distinct complete
producers, one per reply kind. Each retains one original full joining method,
its immutable source and build manifests, compiled class inventories, exact
Maven fault selector, successful execution and collection receipts, unmodified
raw inventory and successful single JUnit case with no flaky/rerun records.
The original collection is independently derived again from retained bytes.

The reader pin includes all V5.3 Python modules, the V4.3 format dependency,
format catalogue and frozen acceptance plan. Those actual reader files must
belong to every producer's recorded source. An old history accepted by a new
reader remains useful diagnostic evidence, but cannot fill this new final-source
cohort. Tool identity uses the existing portable version/binary hash pin;
original host diagnostics and their hash remain retained separately.

For a later authorized native campaign, prepare one immutable source/build and
run all three complete collectors from it. A representative command is:

```bash
python3 -B -m scripts.v53.joining_history_run NEW_CHUNK_PRODUCER \
  --fault CHUNK --source-from PINNED_SOURCE_PRODUCER --portable-toolchain \
  --maven /opt/maven/bin/mvn
```

Bootstrap, learner initialization, INTENT, FINAL, continuation and cold reopen
stay within each original worker. Do not substitute the ordinary profile
collector or assemble stages from different histories. The portable tool option
is opt-in; existing local collection retains its earlier tool recording default.

Inspect the actual current reader pin and declared input directory names:

```bash
python3 -B -m scripts.v53.joining_fault_cohort plan > PLAN.json
```

Place the three complete producer directories under `INPUTS/source_offer`,
`INPUTS/chunk` and `INPUTS/transfer_commit`. Supply the frozen source/build
manifest hashes, comparable toolchain pin and reader pin:

```bash
python3 -B -m scripts.v53.joining_fault_cohort aggregate NEW_RESULT \
  --inputs INPUTS --workers 3 \
  --source-sha256 SOURCE_SHA256 --build-sha256 BUILD_SHA256 \
  --toolchain-sha256 TOOLCHAIN_SHA256 --reader-sha256 READER_SHA256
```

`member NEW_RESULT --producer PRODUCER --case CHUNK` with the same four pins
qualifies one member. Aggregation allows one to three whole-history replay
workers and emits progress at completion and sixty-second polling intervals.
Producer metadata and raw bytes are rechecked after each replay and again after
all members finish; the reader pin is also rechecked. Missing, extra, duplicated,
failed, mixed, changed or previously retried producers cannot pass. Other members
finish when one replay fails, with every failure retained. New output directories
must not already exist. Neither reader entry executes or retries native code.

## Evidence and remaining work

The [implementation and diagnostic receipt](phase3-evidence/joining-fault-composition.json)
records the exact frozen reader, original producers, tests, replay results and
retained failed test attempt. The original producer source predates this reader;
its explicit rejection by the new cohort is recorded separately from successful
historical diagnostic replay. No successful original is replaced or rerun.

All 1,970 V5.3 Python tests pass, including 60 focused compatibility/metadata
checks and 16 new tests repeated with Python assertions disabled. The three
retained originals pass full-chain diagnostic replay: 42 fault rejections,
57 ballot rejections and six original-justified adoption cases marked
`NOT_APPLICABLE`. All three historical producers are separately rejected by
the final-source cohort because they do not contain the new reader. The
1,417 checked Java, POM, workflow and frozen inputs are unchanged.

The result is limited to the three initial reply losses on complete `3-ADD`
histories. The [hosted fault entry](PHASE_3_JOINING_FAULT_HOSTED.md) was implemented
in the following batch; its final-source execution remains pending. Remaining
process/fault histories, all-seven-profile execution, combined resource bounds,
complete original-observation coverage and frozen S/N dependency mapping remain
OPEN. The original composition batch changed no runtime Java, POM, workflow,
frozen workload, Required check, paid-cloud execution or release behavior.
