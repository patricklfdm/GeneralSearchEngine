# Phase 3 — hosted REMOVE process qualification

Status: isolated workflow and portable handoff implemented; local preparation,
archive/offline restore and orchestration guards are recorded in the
[entry receipt](phase3-evidence/remove-process-hosted.json). **No hosted execution
has been performed by this increment.** The 52-member native matrix and full
Phase 3 acceptance remain OPEN.

## Execution boundary

[The workflow](../../../.github/workflows/v53-remove-process.yml) is separate
from existing CI/Required, release and cloud workflows. It has only `contents:
read` permission, no GCP authority, no automatic schedule and no PR trigger.
It runs on explicit dispatch or a push to `experiment/v53-remove-process`.
Normal development pushes do not launch this workflow. The existing CI push
filter remains `master`; opening a PR still follows existing CI policy.

The dedicated branch push permits qualification before adding the workflow to
the default branch. GitHub requires a workflow file on the default branch for
[manual dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).
Do not dispatch or push an experiment branch as part of merely implementing this
entry. A later authorized campaign must record its actual run and attempt.

| Stage | Work | Result authority |
| --- | --- | --- |
| Prepare | Freeze exact checkout source, compile three class inventories, run ten allocator short tests, retain pinned tools and offline dependencies | PARTIAL; preparation only |
| Execute, 52 jobs | One whole `4-REMOVE` or `5-REMOVE` history per declared cut/mode | PARTIAL; original collection only |
| Verify, 52 fresh jobs | Download original bytes, check provenance, replay the complete original reader chain and eighteen ballot negatives | PARTIAL; one independently qualified member |
| Aggregate | Require successful execution and verification jobs plus exactly 52 bound verifier receipts | PASS for this REMOVE subset only |

Each execution/replay matrix has `max-parallel: 6` and `fail-fast: false`.
Replays start after the execution matrix has finished and still inspect available
originals when another execution fails. Missing originals fail their verifier;
any failed, skipped or cancelled matrix prevents aggregate acceptance. Cancelled
workflow runs do not qualify. No original history or verifier is automatically
retried. Each bootstrap, acquisition, crash, original-filesystem resume and
continuation remains within one member. Nested negative replay uses one worker.

Long commands report stage/case/elapsed time every sixty seconds. Native fixture
bounds are unchanged. The workflow uses the platform's 360-minute per-job cap;
this does not promise unlimited execution. See
[GitHub Actions limits](https://docs.github.com/en/actions/reference/limits).
The existing V5.2 cloud time/cost policy is unaffected.

## Immutable handoff and portable tool identity

All artifact names include exact source SHA, run ID and attempt, plus the case ID
where applicable. Every manifest independently binds the same context, workflow
path, event and ref. CLI execution checks actual checked-out HEAD and workflow
SHA, rather than trusting a source label alone. A partial job rerun cannot borrow
the previous attempt's seed or successful members: **rerun the whole campaign**
if a new complete attempt is needed. Keep the original failure and its evidence.

The prepare seed includes original source bytes and hashes, all three compiled
class inventories, raw tool diagnostics, reader files and hashes, and a dedicated
Maven repository. It does not rely on a cross-run Actions Maven cache. Producers
copy only the recorded source into fresh workspaces and run offline. Generated
classes and dependency JAR/POM bytes must match preparation exactly. The current
reader must also match its bytes in the recorded producer source.

Portable toolchain v2 preserves raw Maven/Java diagnostics, including host kernel
and installation paths, in each original receipt. Cohort equality uses the exact
Maven version, Java runtime/vendor/VM/OS/architecture properties and hashes of the
actual Java executable/modules and Maven bin/boot/lib files. Thus an installation
path or kernel diagnostic cannot create a false tool mismatch; changed tool
binaries or versions cannot pass through that normalization. Legacy v1 producer
receipts still use their original raw toolchain hash unchanged.

Archives retain exact file/directory inventories and archive SHA-256, reject
links, traversal, duplicate members and special entries, and bound extraction to
1 GiB / 65,536 entries / 256 MiB per file. Dependency resolution metadata is
retained in the archive but only JAR/POM bytes form the portable dependency pin.
All successful and failed execution artifacts are retained for 90 days. A failed
archive upload also fails the execution job; diagnostics are retained separately
where possible. Force cancellation/platform termination can prevent final upload
and therefore cannot establish acceptance.

## Verification authority

The hosted aggregate consumes the 52 independent fresh-runner verification
receipts after checking successful workflow dependencies; it does not perform a
third full replay. Those receipts must all be from this trusted workflow's exact
source/run/attempt and seed, preserve exact negative reasons, bind unchanged
producer receipts, and refer to distinct original plans and raw archives.
Synthetic or externally copied receipts alone are not hosted evidence.

The separate [local matrix aggregate](PHASE_3_REMOVE_PROCESS_MATRIX.md) continues
to replay every retained producer itself. Use it when independently auditing a
downloaded cohort outside the trusted hosted workflow. Both acceptance paths
retain `phase3Complete=false`, `allMembershipProfilesQualified=false` and
`originalObservationCoverageComplete=false`: this subset cannot close the other
profiles, frozen scenario mapping or complete Phase 3 observation coverage.

## Validation and rollback

All 1,736 V5.3 Python tests pass, including 27 new guards. The 62 existing
CI change/composite/registry contract tests also pass. Local tests exercise
attempted source/build/tool/dependency/reader drift, hostile
archives, failed original replay, exact negative results, attempt mixing, missing
members, reused histories, workflow permissions and artifact retention. The full
52-receipt aggregate test uses explicit synthetic fixtures, not native results.
Local preparation and an archive-restored offline rebuild run the short allocator
suite (ten tests per build, 21.304 seconds for preparation and 16.047 seconds
for the offline rebuild); they do not replace the deferred 52 native histories. The earlier native
five-voter producer is rechecked and relocated without running another history.

Rollback removes this opt-in workflow, setup action and hosted orchestration,
then restores the two small portable-toolchain hooks in the collector/matrix.
Keep original artifacts and diagnostics. No Java implementation, frozen workload,
POM, existing Required gate or V5.2 experiment needs rollback for this increment.
