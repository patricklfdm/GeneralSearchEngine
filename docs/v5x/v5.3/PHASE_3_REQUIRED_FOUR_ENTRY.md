# Required-four resource execution and downloaded replay

This opt-in entry executes one complete `5-REPLACE-required-four` history on
immutable source. It joins the existing [custody mapping](PHASE_3_JOINED_FILE_RESOURCES.md),
[continuous handoff](PHASE_3_JOINED_HANDOFF_RESOURCES.md), and original resource
accounting in one admission path. It does not split leases, votes, FINAL, stable
BARRIER or cold reopen across jobs. The entire original is produced once, then
downloaded and replayed by a separate job.

The implementation is ready for later hosted execution. The corrected-source
native original and its 71 original-first negative results are **pending**.
Historical diagnostic results cannot fill this slot. This supplementary entry
is outside the twelve-subset catalogue (566 histories, 260 execution groups,
500 raw archives and 544 selected jobs); it adds one original and three jobs
when explicitly selected. The five Phase 3 closure gaps remain OPEN.

## Pipeline and immutable inputs

[`v53-required-four-resources.yml`](../../../.github/workflows/v53-required-four-resources.yml)
has three jobs:

| Job | Work | Result authority |
| --- | --- | --- |
| prepare | Freeze complete source, reference classes, Maven dependencies and pinned toolchain | PARTIAL seed only |
| execute | Rebuild the identical classes offline and run the exact whole-history method once; collect originals | PARTIAL producer only |
| verify | Download the exact seed and raw archive; independently replay the complete original, then all negative families | PASS for this observed-ownership scope only |

The workflow permits explicit dispatch or push to
`experiment/v53-required-four-resources`. This development batch does not push
that branch or dispatch any workflow. The workflow has only `contents: read`,
uses the existing pinned V5.3 process tools, retains originals and failure
diagnostics for 90 days, and has no cloud credentials or Required integration.
Artifact names and manifests bind workflow, source SHA, run and attempt. A
successful execute job is required; reusing another attempt's seed or original
is rejected. Failure retains the original, without a measurement retry.

[`required_four_resource_run.py`](../../../scripts/v53/required_four_resource_run.py)
accepts only `V53JoiningIntentExportTest#requiredFourVotersCompleteReplacementFinalAndStableBarrier`
with all seven observation properties enabled: `joining.requiredFour`,
`publication.resources`, `resource.transitions`, `transport.connections`,
`resource.storage.transfers`, `resource.owner.close`, and `resource.joined.close`. A prefix, missing flag, extra JUnit test, skipped
test or Surefire rerun is rejected. Full source, generated classes, reader code,
portable toolchain and raw inventories are checked before and after replay.

The collector requires `original-plan.gsbp`, the continuation result, event and
wire records, and both resource and storage-transfer sidecars. It does not
require `joining-profile.json`, which belongs to the prefix-only producer.
Presence is collection credit only; the independent original reader derives the
actual topology and completed history from physical bytes.

Raw inventory keeps the existing 512 MiB reader bound. The archive keeps the
existing 1 GiB transport bound and extraction/member checks. These are evidence
transport bounds, not changes to runtime pool limits. The shared progress
reporter emits at least one status per minute during hosted stages; Maven logs
and the verifier's original/negative progress are retained. The 360-minute job
limit is the existing hosted execution ceiling, not a new experiment deadline.

## Original-first qualification

[`required_four_resources.py`](../../../scripts/v53/required_four_resources.py)
first calls the full native resource validator with `joined_files=True` and
`joined_closes=True`.
The existing physical, network, ledger, publication, source-request, transport,
FLOOR, receiving, BASIS and owner-close checks remain mandatory. File transfer, continuous handoff, network shutdown and all five
[joining journal close intervals](PHASE_3_JOINING_OWNER_CLOSE.md) must have passed
before any mutation can count.
All expected mappings are derived from the same original, including the actual
predecessor/successor pairs for distinct equal-content images.

| Negative family | Exact cases |
| --- | ---: |
| Original budget journals and event bindings | 15 |
| Continuous learner-to-voter custody and retirement | 19 |
| Placed-file identity and actual transfer pairs | 13 |
| Network owner close | 12 |
| Joining owner close across five original lifetimes | 12 |
| Total | 71 |

Every case must match its exact name, order, rejection status and reason.
Missing families, unrelated failures and an invalid original cannot satisfy
this entry. Mutations operate on decoded copies; the original inventory must
remain unchanged. Other resource/fault negative catalogues retain their own
obligations and are not replaced by these 71 cases.

`observedResourcesQualified` covers only these observations. Successful replay
still reports `combinedResourcesQualified=false` and `phase3Complete=false`.
It does not establish simultaneous byte maxima, intermediate file lifetimes,
physical shutdown order, process-death coverage, or final-source cohort
admission. Those requirements remain in the
[qualification plan](phase3-qualification-plan.json).

## Local verification and deferred execution

The focused tests cover exact commands, missing/changed source/classes/tools,
relocation, failed originals, incorrect attempts, damaged archives, missing
negative families, and original-before-mutation ordering. They use explicitly
synthetic orchestration fixtures and confer no native qualification.

The old retained 124,266,195-byte original (7,013 files) was also collected and
packed/unpacked through the actual transport entry without changing its
inventory. This is historical transport validation only: its previously
recorded missing-request-binding failure remains disqualifying. No Java
history was rerun in this batch. Validation details are retained locally under
`target/v53-required-four-entry/`.

After development, an authorized hosted execution must produce a new complete
history on the corrected source and obtain all 71 exact negatives. The final
Phase 3 audit must bind that result to its complete source cohort; the entry's
existence or its orchestration tests do not close that requirement.
