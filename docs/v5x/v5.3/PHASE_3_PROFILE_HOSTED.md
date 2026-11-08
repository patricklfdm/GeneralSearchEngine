# Phase 3 — hosted ordinary membership profiles

Status: the isolated workflow, portable seed, seven whole-history collectors and
seven independent downloaded verifiers are implemented. The first authorized
hosted campaign at `5652d074` and its replacement at `37b0bf4f` remain failed
originals. The latter completed all eight native histories across the two groups,
but exposed further replay assumptions and Java-download failures. The corrections
below require a new matching-source execution; the final-source cohort and
Phase 3 remain OPEN.

## Second hosted attempt: original retries and nonselected grants

[Profiles 42463390918](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42463390918)
and [required-four 42463390938](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42463390938)
used `37b0bf4f191f84ba8464305748db8252afadcb6f`, attempt 1. All seven ordinary
native JVM histories and the required-four native history completed. The two
REMOVE producer jobs subsequently failed retirement-prefix replay; their native
success does not make those jobs successful. Three profile jobs (3-ADD replay,
5-REPLACE replay and aggregate) failed while downloading the pinned Temurin JDK
with repeated HTTP 504 responses, before their qualification code ran. The
3-REPLACE and 4-ADD downloaded verifiers passed. See the
[retained failure and validation index](phase3-evidence/hosted-retry-replay.json).

The following reader corrections preserve original attempts and strict physical
comparison:

- A SELECTED operation can finish while its first connection times out, then
  return the same ACK on an identical retry. Bind one durable installation to
  the earliest original request and response boundaries, and require an actual
  delivered ACK before proposer installation. All socket attempts remain in
  causal replay; changed requests/responses, missing initial triggers, missing
  delivery and more than three attempts still fail.
- REMOVE handler diagnostics exclude failures after the handler has produced
  its response. The paired transport terminal remains mandatory. Recovered
  controls must match an already qualified operation with a delivered response;
  failed attempts never supply votes. Activation correlation uses the actual
  original contiguous send sequence, including unsuccessful nonselected PREPAREs.
- In 4-REPLACE, node-5 froze a ballot-8 grant after being solicited, although
  node-1 selected nodes 1, 2 and 3. Derive every captured grant for that ballot
  from preceding owner state, compare its complete original inventory, and
  install only the selected cohort. The retained regression fixture fails with
  the old reader's exact node-5 inventory mismatch. No snapshot is copied in
  place of state derivation and no extra voter is counted.
- Also in 4-REPLACE, node-5 committed two generation metadata objects from
  node-2, whose selector then changed before the next object could be served.
  The three identical failed next-object requests terminate that trace. Admit
  only a committed prefix matching independently derived generation members,
  an exact physical selector boundary and the expected missing reference.
  Missing bytes never become a completed transfer or a retention proof. The
  export receipt records this abandoned prefix separately. Mid-object failures,
  continued dead traces, foreign selectors and altered bytes remain rejected.

Local diagnostic replay uses the unchanged downloaded originals, not fabricated
success receipts or a rerun of their workloads. The index records the completed
original chains, regression checks and their hashes. It does not upgrade failed
producer receipts or source/attempt pins, and does not substitute for the complete
hosted negative matrices on a new source. A separate stale Python fixture now
uses the current segmented queue-completion v2 schema so its negative check
reaches the intended layout guard.

Only these two initial workflows are authorized for replacement. The remaining
twelve groups stay held until both pass. Runtime Java, tool pins, workflow
topology, workloads, deadlines, capacities and the three-attempt policy are
unchanged. The HTTP failures need a fresh hosted execution; they do not justify
changing the pinned JDK. Partial-job reruns still cannot mix attempt-bound seeds
and originals.

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
All nineteen jobs in the two initial workflows have now finished. A corrected-source
campaign must remain distinct from this source and its failed originals.

## Complete first-attempt review and physical reader correction

All five ADD/REPLACE native producers succeeded, but their downloaded readers
rejected `joining initialization exact prepared grant suffix`. The producer may
write a fresh PROMISE, reclaim a superseded unselected source, then freeze BASIS.
The ordinary reader incorrectly required the obsolete source's journal prefix
to remain. The required-four reader already derived this bounded deferred path;
both readers now use that same implementation for preparation and subsequent
campaigns. It still checks the exact original promise, source ownership,
complete inventory and journal bytes. An occupied inactive generation, changed
promise, truncated prefix or altered source cannot authorize reclamation.

The original `3-ADD` also retained two identical successful PREPARE response
observations after a timeout/retry. The physical reader now counts that grant
once, permits at most the original three attempts, and requires identical
request/response bytes and delivery policy. Connection observations may differ
between attempts; all original attempts remain subject to the separate complete
causal/network gate. Changed responses, excess retries and a missing voter fail.

The unchanged retained originals for `3-ADD`, `4-ADD`, `3-REPLACE`, `4-REPLACE`
and `5-REPLACE` pass the corrected physical continuation through cut 11. This is
component replay, with `status=PARTIAL`; it does not repair missing connection
metadata, relabel the hosted campaign, or establish full network qualification.
The compressed regression fixture records the original 3-REPLACE grant capture
and independently derived preceding inventory. Its positive case fails against
the old reader; the corrected focused suite passes 104 tests. See the
[artifact and validation index](phase3-evidence/profile-hosted-replay.json).

The separate [required-four run 42418110955](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/42418110955)
failed the native original after installation at cut 9: the joining node's
ACCEPT exhausted three 30-second transport attempts. Its verifier correctly
refused a failed execution. This is a separate runtime timing investigation,
not resolved by the physical-reader correction. Its original evidence and local
diagnostic execution are retained at `target/v53-hosted-final-debug`.

## Required-four local investigation

The hosted original retained 104 transport failure observations and terminated
after the joining ACCEPT exhausted its three original 30-second attempts.
The installed-cut-9 control path includes real generation maintenance and remote
floor-copy validation before the vote. A timeout message alone does not identify
GitHub scheduling, a deadlock or storage latency as its cause.

An unchanged local runtime diagnostic completed in 1,667.391 JUnit seconds with
two active JVM processors and JFR enabled. It retained four transport failure
observations and completed FINAL, BARRIER and cold reopen. Thus the hosted terminal
failure was not reproduced locally. Profiling did expose repeated format-regex
compilation and repeated authentication of the same freshly read ancestry within
one owner check. Precompiled equivalent regexes and one capsule-bound immutable
ancestry projection now remove that repeated computation. Every owner check still
reads/checks its original files and all three ledgers; the projection cannot cross
capsules, owner checks, callbacks or durable operations. No timeout, retry count,
resource limit, protocol record or voting rule changes.

All 46 focused Java format, ancestry and retention tests pass, including
corruption between owner checks and failed-owner poisoning. The corrected runtime
completed the same local history in 1,587.554 JUnit seconds (26m49s including the
build), retaining ten recoverable transport failure observations. Both local runs
used OpenJDK rather than the pinned hosted Temurin and had different profiling
and background load, so their times do not establish a controlled speedup. The
small owner-check probe also showed no improvement. These results do not prove
that hosted retry exhaustion is eliminated.

Independent replay of the unchanged local original exposed and corrected the
[request-inside-install export boundary](PHASE_3_REQUIRED_FOUR_EXPORT_ENTRY.md#request-received-during-installation).
Both complete original resource replays pass. The unchanged runtime's duplicate
negative gate was stopped after its 16 voting-control negatives passed; that
diagnostic remains PARTIAL with its retained log. The corrected runtime's complete
original-first replay and all 147 exact negatives pass in 2,469.835 seconds,
with its original inventory preserved. Neither local original can
fill a final-source hosted cohort slot; both
initial workflows still require a new, matching-source execution before expansion.
The [follow-up evidence index](phase3-evidence/hosted-failure-followup.json)
records exact copied sources, original logs, diagnostics, reader hashes and the
scope of each completed check.

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
