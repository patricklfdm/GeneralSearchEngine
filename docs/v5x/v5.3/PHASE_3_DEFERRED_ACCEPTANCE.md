# Phase 3 implementation and deferred hosted acceptance

[Forced learner custody](PHASE_3_LEARNER_CUSTODY.md) now transfers the actual
prepared learner's locks and complete storage group after forcing an original
handoff decision, then revokes the old object graph. Original payload installation,
joined admission and native joint voting remain **OPEN**.

[Inspection-safe descriptor custody](PHASE_3_FILE_CUSTODY.md) corrects a reproduced
POSIX lock loss during hash/read/force operations. V5.3 owned files now reuse the
original descriptor; separate JVMs check actual exclusion. Earlier passing
component tests did not cover that boundary. Joined-voter takeover and complete
Phase 3 remain **OPEN**.

[Joining-voter staging](PHASE_3_LEARNER_VOTER_STAGE.md) now prepares and forces
an exact dormant installation from the live matching-INTENT owner. It derives a
local certificate fence, allocator and generation without copying the peer's
BASIS/SELECTED authority. Explicit recovery checks original prefixes and the
completed inode seal. Native voter ownership takeover, minimum-quorum INTENT
delivery and complete Phase 3 acceptance remain **OPEN**.
[Atomic ownership prerequisites](PHASE_3_OWNERSHIP_TRANSFER.md) now preserve the
actual lock descriptor and storage accounting while revoking old handles; the
full joined-voter transaction still needs to consume them.

[Matching INTENT retention](PHASE_3_LEARNER_INTENT.md) now binds a complete
certified source to the actual forced typed receipt and preparation revision,
then forces the original files before returning a live capability. CANCEL and
INTENT share recovery machinery while preserving the existing CANCEL format.
Voter installation, native minimum-quorum joining, independent replay and full
Phase 3 remain **OPEN**.

[Durable head confirmation](PHASE_3_LEARNER_CONFIRMATION.md) now retains the
original QUERY/ACK through the source ledger and selected-source merge, keeping
newer uncertain offers while discharging proved older ones. Pending physical
renewals survive local narrowing until selected-source reconciliation. Ordinary
decoded-plan merging stays conservative. Independent replay of this path, process cuts,
repeated refresh, matching INTENT and complete Phase 3 remain **OPEN**.

[Head queries](PHASE_3_LEARNER_HEAD_PROTOCOL.md) now connect a real forced
learner head to a native source through bounded, correlated TCP exchanges.
Replies are checked against the source's original ancestry; late/malformed
replies and revoked owners are refused. This read-only path leaves the durable
ledger unchanged; the durable consumer above is a separate operation. Repeated
refresh, matching local INTENT and full Phase 3 acceptance remain **OPEN**.

[Forced-head observation](PHASE_3_LEARNER_HEAD_OBSERVATION.md) now binds local
retention narrowing to a real selected typed learner head, preserves newer
uncertain offers and rejects revoked owners. This is a local capability, not a
remote acknowledgement. The durable confirmation component above now preserves
remote evidence through frozen-source selection; complete independent acceptance
of that new path remains OPEN.

[Native cancellation replay](PHASE_3_LEARNER_CANCELLATION_NATIVE.md) exposed a
source-side retention gap: actual READY/CANCEL publication pruned the learner's
original PREPARE endpoint. Five native slots and 59 exchanges replay exactly;
the learner correctly refuses the missing ancestry. [Bounded local obligations](PHASE_3_LEARNER_RETENTION_LOCAL.md)
now preserve exact learner endpoints through local publication and reopen.
[Frozen-source capture and selected merge](PHASE_3_LEARNER_RETENTION_SELECTION.md)
now preserve their union across installation, interrupted completion and later
CANCEL. [Native quorum recording](PHASE_3_LEARNER_RETENTION_QUORUM.md) now adds
explicit forced ACKs for the original stable endpoint. [Protected source serving](PHASE_3_LEARNER_RETENTION_SERVING.md)
now consumes that exact live recording before exposing prefix/generation bytes,
including cached completion replies. [Independent retained-history replay](PHASE_3_LEARNER_RETENTION_REPLAY.md)
now qualifies that native READY/CANCEL/cold-reopen history, including original
ledger/selection/publication bytes, forces, 59 learner exchanges and 31 exact
negative cases. The runtime snapshot precedes the final serving cut guard;
current-source/all-profile acceptance is still separate. Matching INTENT,
process replay and full Phase 3 remain **OPEN**.

A30 adds explicit original-proof cancellation retention and cold recovery. Its
conditional source fixtures and 13 injected exception cuts must be followed by
continuous native cancellation histories, actual halt/SIGKILL and independent
original-first physical/force/network validation. Include initial and alternating
prepared heads, pending/selected sources and restart without old-receipt reuse.
No new source or experiment retry may replace incomplete original evidence.

A28 implements alternating inactive-plan replacement and general slot/sequence
routing. Continuous component histories now cover both fixed paths and new-clear
replacement cuts. Complete native/process histories must still include every
old-plan/new-plan/old-marker/new-marker state, source placement, selection and
retirement. Do not split one alternating history across runners or treat these
conditional exception cuts as native acceptance.

A27 adds original replacement-head recovery and covered B retirement. The complete
native history must also exercise old-clear/new-clear coexistence, cuts during
new vacancy replacement, subsequent B plan/marker replacement and further cycles.
The local conditional exception cuts do not replace any halt/SIGKILL or physical
history replay requirement.

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
| Descriptor custody through takeover | Each complete native takeover history; the two learner inspection component histories may run independently | Independent-process lock attempts around reads, fingerprints, forces, rename and stale close; preserve original failure evidence; helper tests do not replace joined-member process cuts |
| Learner current-endpoint quorum | Independent whole native ADD/REPLACE histories | All five joining profiles and process cuts, exact forced ACKs and wire replay, source-exposure binding and authentic head confirmation; the focused three-voter ADD test does not close the full gate |
| Frozen learner retention and selected merge | One native continuous history plus independent whole halt/SIGKILL cases | Exact source-bound ledgers, selection/installation completion, all process cuts and original-first physical/force replay; five Java component cases are executed, not complete process or quorum qualification |
| `V53LearnerVoterStageTest` and joined-voter takeover | One original typed learner/INTENT/staged generation through takeover and restart | Native old-majority INTENT before joint checkpoint, exact ownership transfer, interrupted install, predecessor coverage/retirement, joint FINAL/barrier, independent original-first replay and maximum resources; staging does not enable voting |
| `V53LearnerCancellationTest` and native cancellation | One original prepared learner history through certified CANCEL and local retention/restart | All five joining profiles, initial/promoted/alternating heads, original forces and source ancestry, bounded resources, halt/SIGKILL, precise evidence negatives and automatic integration; component exception cuts do not replace these gates |
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
| Native six-revision alternation | One whole `V53LearnerAlternationNetworkTest` history (local timeout at final CANCEL; final source hosted gate pending) | PREPARE 1–6 in one original reservation, B1/A2/B3/A4, original source/typed ownership and cold reopen; The [replay reader](PHASE_3_LEARNER_CYCLE_REPLAY.md) matches all 25 snapshots in a partial diagnostic; complete physical/wire/force replay and twelve exact negatives still require a successful original history. Never shard revisions |
| Native handoff and retirement | One continuous multi-revision native history, plus independent halt/SIGKILL histories | Exact physical/transport replay, original candidate and head, explicit covered deletion, resource release and bounded slot reuse; remains outstanding |
| Prepared learner progress | `V53LearnerProgressTest` and `V53LearnerProgressNetworkTest`, followed by whole native histories | Exact request-bound terminal/joint acquisition, complete generation and prepared-parent ancestry, unchanged local receipt/authority, lost-response bounds and closed-owner refusal. Conditional voter fixtures do not qualify native CANCEL/INTENT or local durable installation |
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
