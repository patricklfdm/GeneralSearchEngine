# Phase 3 implementation and deferred hosted acceptance

A26 adds pending A reuse under the same lock. Keep the eventual B→A→B→A history
continuous: include current/pending ownership, unchanged fixed paths, replacement
selectors, vacancy replacement, cold/process cuts and copied/stale decision
negatives. `V53LearnerReuseTest` only covers the first reused installation with
conditional voters; it is not a completed native or repeated-cycle gate.

The operator authorized deferring expensive complete qualification on 2026-10-28.
Implementation continues on the local branch, with focused checks before each
commit. Phase 3 remains **OPEN** until the complete
[entry checklist](PHASE_3_ENTRY_PLAN.md) has its original required evidence.
This file is an acceptance queue, not an executed workflow or acceptance receipt.

## Current learner-store queue

| Gate | Unit of execution | Required final evidence |
| --- | --- | --- |
| `V53LearnerStoreTest` and preparation tests | Focused component suite | All assertions on the final source; explicitly conditional historical fixtures do not become native distributed evidence |
| `V53LearnerStoreRevalidationTest` | One actual TCP history | Normal original installation, disconnect, reopen and unchanged-byte refusal; independent original-first review reader |
| `V53LearnerStoreNetworkTest` | Twelve independent whole histories: six cuts × halt/SIGKILL | Original native source, interrupted process, normal resume, locks, forces and exact physical bytes; all twelve required |
| Store negative qualification | Complete unchanged matrix first | Every declared mutation rejected for its exact reason, including portable optimized replay |
| `V53LearnerMaterializationTest` and native smoke | Focused typed backup and READY receipt | Exact original PREPARE image, actual core semantic decode, forced receipt, reopen and independent original-first replay |
| Typed learner process-death qualification | Independent complete native histories | Halt/SIGKILL at typed plan, backup and receipt cuts, fresh-process semantic reopen and unchanged refusals; not replaced by synchronous exception cuts |
| Prepared learner selection and refresh | Focused components and complete native two-revision history | Original selection forces, same-pool coexistence and authenticated successor, full original-first wire/physical replay |
| Prepared selection process-death qualification | Independent whole halt/SIGKILL histories | Partial marker recovery, conservative reopen, live owner revocation and unchanged original source; no component exception substitution |
| Installed successor components and native smoke | Original complete source, installation, close/reopen | Same-pool reservations, exact source identity, complete original plan, both move parents forced, selected successor with no voting rights |
| Installed successor process-death matrix | Independent complete halt/SIGKILL histories | Original candidate plan and source move/selection cuts, fresh-process resume or exact incomplete refusal; preserve failed attempts |
| Installed successor typed receipt | `V53SuccessorTypedTest` methods as separate independent units; one whole `V53SuccessorTypedNetworkTest` history | Current receipt/source binding, separate retained backup, original force trace and portable negative replay; focused TCP smoke does not replace process-death cases |
| Successor typed process-death qualification | Independent complete native histories | Halt/SIGKILL during compact plan, backup and receipt writes; original-only resume, preserved refusals and same-pool accounting |
| Original ownership handoff | `V53LearnerHandoffTest` and `V53LearnerHandoffCutsTest`, each independent history | Source/receipt/member binding, forced head before handle revocation, original-only cold reopen; synchronous cuts do not establish process-death behavior |
| Original predecessor retirement | `V53LearnerRetirementTest`, independent conditional histories | Exact complete decision, covered deletion and parent forces before lease release; partial decisions and changed remaining/current originals preserved; semantic current backup reopen |
| Current typed acquisition head | `V53LearnerCurrentHeadTest` and one complete `V53CurrentHeadNetworkTest` | Same-pool acquisition after original retirement and cold semantic reopen, current ancestry and closure revocation; the native three-revision history and its independent replay must actually execute before acceptance |
| Inactive slot installation | `V53LearnerSlotTest` plus one whole `V53LearnerSlotNetworkTest` | Exact pending plan, source move, real typed decode, original-only cold resume and unchanged current head; all five shapes, maximum combined resources, complete native execution, physical replay and halt/SIGKILL remain required |
| First rolling head and seed retirement | `V53LearnerSlotHeadTest` conditional histories and one whole `V53LearnerSlotHeadNetworkTest` native history | Native PREPARE 1/2/3, closed-download selection, exact covered removal, original identities and cold semantic recovery. The native entry is compiled, not run; original wire/physical replay and halt/SIGKILL remain required. Snapshot-layer checks alone report PARTIAL |
| Durable vacancy | `V53LearnerVacancyTest` and complete native histories | Head/inode-bound cleared-slot decision, force-before-release, conservative missing-marker recovery, exact candidate resume and copied/partial/recreated-root refusal; later reusable plans must bind this same decision. Portable vacancy binding is a PARTIAL layer, not native/force acceptance |
| Native handoff and retirement | One continuous multi-revision native history, plus independent halt/SIGKILL histories | Exact physical/transport replay, original candidate and head, explicit covered deletion, resource release and bounded slot reuse; remains outstanding |
| Successor lifecycle | One continuous original learner history | Install, select and retire bounded originals across revisions, cancellation and locally forced matching INTENT before votes |
| Final Phase 3 protocol audit | Complete prescribed scenarios | Learner ADD/REPLACE, all seven transitions, alternative-leader continuation and maximum combined resource bounds; component results cannot substitute |

The process test supports one exact whole case through the Maven system property
`gse.v53.learnerStoreCase`. With no property it executes all twelve. Empty, unknown
or misspelled selections fail before starting the history. Allowed names are the
six constants in `V53LearnerStoreNetworkTest.CUTS`, each suffixed `-halt` or `-kill`.
For example, from an isolated source checkout with Java 21:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53LearnerStoreNetworkTest \
  -Dgse.v53.learnerStoreCase=LEARNER_SOURCE_MOVED-kill test
```

The test prints its raw evidence directory. From that checkout's root:

```bash
python3 -m scripts.v53.learner_store_evidence RAW_DIRECTORY \
  --case LEARNER_SOURCE_MOVED-kill
```

The reader independently validates the complete selected history and reports
`PARTIAL`, never complete matrix acceptance. The ordinary reader without `--case`
still requires all twelve. `--case` and `--qualify` cannot be combined.

## Selected-slot native entry

`V53LearnerSlotHeadNetworkTest` extends the continuous PREPARE 1/2/3 helper as one
indivisible history. Existing current-acquisition and pending-install modes keep
their own entry points and result shapes. The selected mode closes the third
transfer before selecting B, then checks exact covered A removal and cold typed
reopen without A's source. Its original 900-second test profile is unchanged.
Compilation and the accompanying resource-owner tests do not execute that history.

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53LearnerSlotHeadNetworkTest test
```

The Java history prints `v53LearnerSlotHeadEvidence=...`. Seven snapshots preserve
admission/replica, initial typed, seed metadata/source/typed and B metadata/source/
typed roots, including explicit absent roots. They record original paths and
inodes before copying bytes. Resource usage is retained separately: conservative
cold accounting may differ in extent, while authority bytes and original
identities must remain unchanged. The whole-history physical/wire validator and
its exact negatives still need integration and real execution.

The new snapshot parser can inspect one retained stage, for example:

```bash
python3 -B -m scripts.v53.learner_slot_snapshot RAW_DIRECTORY/reopened-slot-head
```

This reads only the copied stage. Recorded original paths are data, never paths to
open; copy inodes are not original identities. Exact inventories, file hashes,
identity shapes, disjoint original roots and declared resource limits are checked.
Output is always **PARTIAL**, with native/history/selected-head/process-death
qualification false. It cannot authorize deletion or turn a Java result line into
complete acceptance. Its eleven small parser regressions use synthetic copied
snapshots, not native protocol evidence.

## Hosted campaign requirements

The eventual workflow must bind every artifact to one exact source and build,
pin Java and retain raw evidence, failed attempts and independently replayable
inputs. A missing/failed shard blocks aggregate acceptance; an unrelated original
failure must not count as a successful negative test. Process IDs from different
runners may coincide and must be scoped by execution identity. Each interrupted
and resumed process still belongs to the same original filesystem history.

Do not split a source acquisition from its installation, an INTENT from its FINAL,
or a crash from its restart across runners. Parallelism applies to independently
bootstrapped histories only. A future aggregate must validate the exact declared
set rather than merge pass counts. Workflow wiring and that source-bound aggregate
are pending; this change does not dispatch GitHub Actions, alter Required or touch
the V5.2 hosted/self-hosted experiment.

Earlier locally completed runs remain source-bound historical results. Long
matrices must be run against the final runtime before phase closure; neither a
short smoke nor an earlier source's green matrix proves that final requirement.
