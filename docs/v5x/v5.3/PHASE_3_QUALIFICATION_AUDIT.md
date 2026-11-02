# Phase 3 qualification inventory and remaining work

Phase 3 remains **OPEN**. This inventory originated from baseline `867df7c4`;
the current table also includes the subsequent learner-history cohort. It does
not execute a native history, accept an old receipt as current-source evidence,
or declare the implementation complete.

The [machine plan](phase3-qualification-plan.json) and
[source inspector](../../../scripts/v53/phase3_qualification_plan.py) provide
the current navigation for remaining work. Earlier documents retain their
original scope and results. A historical sentence saying an endpoint or reader
is missing must be read together with its later implementation, not copied into
the backlog as a new feature.

## Implemented entries

| Whole-history cohort | Members | Execution groups | Current scope |
| --- | ---: | ---: | --- |
| [Ordinary profiles](PHASE_3_PROFILE_HOSTED.md) | 7 | 7 | All seven ordinary ADD/REMOVE/REPLACE histories |
| [Joining reply loss](PHASE_3_JOINING_FAULT_HOSTED.md) | 3 | 3 | Three reply-loss boundaries in a complete 3-ADD history |
| [REMOVE process](PHASE_3_REMOVE_PROCESS_HOSTED.md) | 52 | 52 | Declared departure/retirement process subset |
| [Node renames](PHASE_3_NODE_RENAME_MATRIX.md) | 4 | 4 | ACCEPT/PROOF rename, halt/SIGKILL, original disks |
| [Joining initialization](PHASE_3_JOINING_PROCESS_HOSTED.md) | 360 | 120 | Five joining profiles, 36 cuts, two death modes |
| [Continuous learner histories](PHASE_3_LEARNER_HISTORY_COHORT.md) | 2 | 2 | Six revisions and retained READY/CANCEL, complete cold reopen |

These **428 planned native histories** are complementary subsets. This is neither
a pass count nor a count of covered rows in the frozen S matrix. The inspector
reads their actual Python catalogues and checks declared counts and ordered-case
hashes. Joining groups must partition all 360 whole histories exactly. Workflow
and implementation references must exist as regular repository files. This
checks inventory drift, not workflow scheduling behavior.

Existing per-workflow admission binds its own source/build, tools, reader, seed
and run/attempt. Those gates are not redeveloped by the inspector. Separate preparations do
not automatically form one accepted phase-wide cohort; that admission still
needs integration. No hosted workflow was dispatched for this audit.

## Current obligation map

The machine plan has 12 review groups with concrete production/tooling, test,
reader and documentation paths, related frozen families, existing hosted subsets
and unresolved work. References locate implementation; the inspector cannot
prove its semantics.

| Group | Existing implementation and evidence | Remaining qualification |
| --- | --- | --- |
| 3A activation | Durable grant, selected sources, fence and original deadline | Final-source schedules and exact failure coverage |
| 3B transfer | Bounded native TCP, receiving custody, retries and process readers | Current-source component cohorts; combined lifetimes |
| 3B recovery | Retained ancestry, owned reopening and cross-view adoption | Final-source restart/discovery coverage |
| 3C learner | Six-revision/cancellation producers, source retention, readers and hosted pair | Complete final-source histories and profile coverage |
| 3C initialization | Actual joining owner, three-ledger initialization and 360-case entry | Final-source matrix; combined bounds |
| 3C joint | Private INTENT/FINAL/BARRIER coordination for all seven profiles | Final-source profiles and interrupted transitions |
| 3D rounds | Carried-first publication, two durable phases and round reuse | Current-source carried/stable/process qualification |
| 3D automatic | Competing owners, heartbeat, single-campaign replay, original grant capture and competing-prefix derivation | Maintenance/install/publication across competing campaigns, final-source complete competition and failure coverage |
| 3D removal | Departure fencing, retirement and original-disk recovery | Final-source original/negative process matrix |
| 3E resources | Accounting, bounded transfers, publication refusal and conditional-prefix tests | Simultaneous physical peak and admitted completion |
| 3E coverage | Frozen finite inventory and this dependency map | Concrete schedule/evidence/rejection mapping |
| 3E cohort | Six source-bound subset gates | Complete final admission, execution and closure audit |

`MembershipStorageOperations` still refuses public learner operations and
`MembershipSearchEngine` keeps reads disabled. Phase 3 private protocol work does
not silently enable Phase 4 interfaces. The frozen [acceptance register](ACCEPTANCE_REGISTER.md)
and machine plan assign the complete **3,310 S rows to Phase 5**. Public consumer,
read and maintenance axes cannot be counted as covered by private Phase 3 tests.
Phase 3 must qualify their protocol dependencies; this audit moves or waives no
final requirement. All 24 negative families still require appropriate original
evidence and exact rejection mapping. Related family IDs are not that mapping.

## Execution sequence

1. **Complete component cohort entries.** The focused 3-ADD learner pair now has
   its entry. [Competing grant capture](PHASE_3_COMPETING_GRANT_CAPTURE.md) now
   retains losing/superseded grants. The [new native prefix](PHASE_3_COMPETING_CAMPAIGN_PREFIX.md)
   derives four grants and both choices; continue its original maintenance,
   installation and publication before adding a general competition gate.
   Continue with competing owners, then inventory transfer, carried
   and transition recovery entries and uncovered learner profiles. Reuse existing producers/readers.
   Historical qualification remains scoped to its source, not a new cohort slot.
   The six-revision history's recorded final-CANCEL deadline failure remains a
   failure; retrying, extending budgets or reconstructing observations cannot
   turn that original into a pass.
2. **Qualify combined resources.** Review actual lifetime overlap, then exercise
   selected/current/inactive sources, learner staging and reserved completion on
   real owners. `V53ResourceTransferTest` reserves the accounting envelope;
   `V53PublicationCapacityTest` checks conditional-prefix refusal and stable DATA.
   Neither alone proves a simultaneous native physical maximum.
3. **Finish concrete protocol coverage.** Map exact schedules, original evidence
   selectors and rejection reasons; identify uncovered combinations. Inapplicable
   operations still require explicit refusal with unchanged bytes. Keep final
   public and combined-hardening obligations with their owning phase.
4. **Implement phase-wide admission.** Require the complete declared subsets,
   original-first replay, exact source/build/toolchain/readers and every
   workflow/run/attempt. Reconcile independent seed provenance. Missing/failed
   histories block acceptance; green summaries cannot replace the gate.
5. **Execute and audit the final source.** Long independent whole histories may
   run in parallel after separate push/dispatch authorization. Retain every failed
   attempt and original ownership chain. Fix reproduced failures, then close only
   the validated Phase 3 scope. This plan authorizes no dispatch.

Items 1 and 2 can be developed independently. Later dependencies are explicit;
the inspector rejects cycles and unknown work. All five gaps remain OPEN. No
duration estimate or completion percentage is inferred from case counts.

## Reproduce the inspection

From the repository root, select a new output directory:

```bash
python3 -B -m scripts.v53.phase3_qualification_plan \
  --output target/v53-phase3-audit/manual-001
python3 -B -m unittest scripts.v53.test_phase3_qualification_plan \
  scripts.v53.test_case_inventory scripts.v53.test_contract_check
```

Output retains the input plan, frozen acceptance plan and a receipt with baseline
HEAD, worktree status, inspected file hashes, actual catalogue member names, open
dependencies and zero newly executed native histories. Inspected bytes are
rechecked before PASS. Existing directories are never overwritten; failure
leaves a failed receipt.

`status=PASS` means **the source inventory is internally consistent**. The report
always says `execution=source-inventory-only`, `qualificationStatus=NOT_EVALUATED`,
`runtimeQualified=false`, `phase3Complete=false` and no covered scenario rows.
No supplied PASS receipt or closure flag can grant acceptance. Inspection runs no
native command, evidence mutation, Maven build, network request or cloud action.
Its hash index covers inspected files, not an entire runtime build.

Local tests cover missing/duplicate obligations, family/phase drift, altered
frozen axes, count/case drift, broken group partitions, missing/linked references,
dependency cycles, invented acceptance, input changes and preservation of
old/failed output. They establish inspector behavior only; no long native
qualification is repeated for this tooling/documentation batch.

Rollback removes this optional inspector, tests, plan and documentation links.
Runtime, record/wire formats, bounds, existing workflows, Required and V5.2
experiments are unchanged.
