# Phase 3 — hosted ordinary membership profiles

Status: the isolated workflow, portable seed, seven whole-history collectors and
seven independent downloaded verifiers are implemented. The first authorized
hosted campaign at `5652d074` exposed missing connection observations in both
REMOVE originals. The correction below requires a new matching-source execution;
the final-source cohort and Phase 3 remain OPEN.

## First hosted attempt and connection capture correction

[Run 42418110516](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42418110516),
attempt 1, executed the frozen `5652d074` source on the existing experiment branch.
The separate required-four preparation had identical source, class, toolchain
and offline dependency fingerprints. This establishes matching preparation only.

The `4-REMOVE` and `5-REMOVE` JVM histories passed once in 400.956 and 475.776
seconds, respectively, and both base physical/semantic replays passed. Their
subsequent retirement-prefix gate failed inside complete network replay with
`joining failure missing caller terminal`. The complete original ZIPs, logs and
failure receipts remain retained; neither run was retried or relabelled PASS.

In the four-node original, request `5cd86f89...` was sent at event 859 and read
at 861. Its caller timed out at 1575, then sent the identical retry at 1582.
The retry was read at 1586 before the old receiver's terminal at 1661. The
legacy hash-only observations cannot reliably associate that late terminal
with its original connection. The existing strict reader correctly refuses
this ambiguous record; later success cannot fill the missing identity.

All seven ordinary profile commands now enable the existing
`-Dv53.transport.connections=true` collector. The matrix requires that exact
command and complete connection metadata on actual transport observations and
response rows. Existing connection replay then derives original invocation,
socket, endpoint and delivery relationships. Partial or total metadata removal
cannot fall back to legacy matching. Protocol/runtime Java, deadlines, capacities,
retry policy and negative verdicts are unchanged. Historical originals are not
given reconstructed connection identities.

The [review and validation index](phase3-evidence/profile-hosted-connections.json)
records the failed job/artifact identities and exact hashes. New regression
assertions fail before the correction; 100 focused Python tests pass afterwards.
One local native test covers late-handler and late-response overlap through the
existing collectors; independent original-first replay and all eight negatives
pass. Its local OpenJDK toolchain and component scope do not substitute for a
corrected-source whole profile on the pinned hosted tools. The initial sandbox
socket denial is retained separately from the permitted loopback execution.

The authorization to expand the remaining twelve workflows was conditional on
both initial workflows passing. That condition failed, so expansion is held.
Other initial jobs may finish and retain their evidence. A corrected-source
campaign must remain distinct from this source and its failed originals.

## Entry and topology

[The workflow](../../../.github/workflows/v53-membership-profiles.yml) has only
`contents: read` permission. It accepts manual dispatch or a push to the dedicated
`experiment/v53-membership-profiles` branch. It has no PR/schedule trigger, GCP
identity, release authority or change to existing CI/Required. Source, workflow,
event/ref, run and attempt are validated against the checked-out commit.

| Stage | Execution | Result scope |
| --- | --- | --- |
| Prepare, one job | Freeze source, reference class inventories, pinned tools and offline dependencies; run short allocator tests | PARTIAL, preparation only |
| Execute, seven jobs | One complete original profile per worker, including its original semantic checks and REMOVE capture sidecar | PARTIAL, preserved original |
| Verify, seven fresh jobs | Download seed and original, validate provenance, replay the complete implemented chain and exact ballot negatives | PARTIAL, one qualified member |
| Aggregate, one job | Require all execution/verification jobs and exactly seven bound verifier receipts | PASS for ordinary profile composition only |

The frozen profile list is `3-ADD`, `4-ADD`, `4-REMOVE`, `5-REMOVE`, `3-REPLACE`,
`4-REPLACE`, `5-REPLACE`. Both matrices have `max-parallel: 7` and
`fail-fast: false`. Bootstrap, acquisition, initialization, INTENT/FINAL,
publication, retirement and cold reopen stay within one original worker/history.
No fragment from another execution or retry can supply a missing phase.

Verifiers start after the execution matrix ends and inspect available originals
even if another execution failed. Any failed, skipped or cancelled execution or
verifier blocks acceptance. Missing originals fail their corresponding verifier.
No original execution or replay is automatically retried.

The configured per-job Actions timeout is 360 minutes. Existing native fixture
and resource bounds remain unchanged. A background progress reporter emits the
stage, profile and elapsed time every sixty seconds, including packing and replay.
Collectors also retain their native command progress. Summary tables display
source, run/attempt, profile, result scope and available evidence hashes/counts.

## Shared preparation and artifact binding

The existing [REMOVE hosted infrastructure](PHASE_3_REMOVE_PROCESS_HOSTED.md)
now exposes its preparation routine and bounded archive helpers for reuse. The
52-case entry retains its default schema, workflow identity, preparation command
and exact result scope. It is not replaced or relabelled as ordinary acceptance.

Preparation freezes one reference build and a private Maven dependency repository.
Each producer copies only recorded source into a new workspace, builds offline,
and must reproduce the reference class inventories. Generated runtime state is
never copied from preparation or another member. This is shared source/dependency
preparation and build comparison, not a claim that all worker compilation is
eliminated. Tool identity uses the existing version and binary hash record;
installation paths and host diagnostics remain retained separately.

The seed, raw and verifier names include source SHA, run ID and attempt; member
names additionally include the exact profile. Artifact manifests bind workflow,
role, profile, archive hash and the full extracted inventory. The profile schema
is distinct from the REMOVE process schema. Wrong source, attempt, workflow,
profile or role cannot be substituted. A partial job rerun cannot borrow an old
attempt's seed or members; any replacement qualifying campaign needs a complete
new attempt, with the original failure retained.

Original source files, three class inventories, exact JUnit/Maven command,
semantic replay, original inventories and REMOVE captures are checked through
[the seven-profile matrix](PHASE_3_PROFILE_MATRIX.md). The downloaded verifier
replays those original bytes before negative variants and rechecks them afterwards.
The hosted aggregate checks the same original-result/negative contracts and all
seven exact-attempt verifier receipts. It does not rerun all seven expensive
physical replays a second time in the aggregate job.

All 24 expanded artifact names are unique and configured for 90-day retention.
Both success and failure diagnostics are uploaded. If a native failure is followed
by an archive failure, both are recorded and the native exception is preserved.
An archive failure after successful execution also fails the job; it cannot
leave a success-looking receipt. Complete raw producers remain necessary for
later independent replay, not only the small aggregate receipt.

## Commands and validation boundary

The workflow invokes `python -B -m scripts.v53.profile_hosted` with these stages:

```text
plan
prepare --output NEW_PREPARATION
execute --seed EXACT_ATTEMPT_SEED --profile 3-ADD --output NEW_EXECUTION
verify --seed EXACT_ATTEMPT_SEED --inputs ORIGINAL_RAW --profile 3-ADD --output NEW_VERIFIER
aggregate --seed EXACT_ATTEMPT_SEED --inputs ALL_SEVEN_VERIFIERS --output NEW_AGGREGATE
```

The CLI requires the validated GitHub context; it is not a local bypass for
claiming hosted evidence. Use the ordinary matrix's local readers for diagnostic
replay. Outputs are exclusive and never overwrite prior attempts. This batch
implements the workflow without dispatching it or pushing the experiment branch.

The [implementation receipt](phase3-evidence/profile-hosted.json) records Python
checks, YAML/shell validation and expanded job/artifact checks. Synthetic archive
round trips and stubbed native executions test orchestration; they are not native
membership evidence or a successful GitHub run.

Measured implementation validation: all 1,954 V5.3 Python tests pass. The 23
new hosted/workflow regressions also pass with assertions disabled; 45 focused
new/existing hosted and topology tests pass together. YAML parsing, 17 expanded
shell blocks, 16 expanded jobs and 24 unique artifact names were checked.
The extracted shared preparation retains the same twelve original execution and
validation statements by AST comparison. These checks do not execute a native
cohort or provide an Actions run ID.

A successful aggregate may set `declaredMembershipProfileMatrixQualified=true`
for the implemented ordinary composition. It retains `phase3Complete=false`,
`processDeathQualified=false` and `originalObservationCoverageComplete=false`.
Process/fault cohorts, full observation coverage, combined resource bounds and
frozen S/N mapping remain required by the
[deferred acceptance plan](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback removes the profile workflow, adapter and tests. The shared helper
extraction can be reverted with the previous REMOVE entry intact. Preserve all
original data and diagnostics. Runtime Java, POMs, frozen formats, workload
parameters and V5.2 cloud workflows are unaffected.
