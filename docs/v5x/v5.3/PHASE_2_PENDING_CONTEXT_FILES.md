# Pending-context persistence and process recovery

Status: private file component, locally qualified. Phase 2 remains **OPEN**.

The [context codec](PHASE_2_PENDING_CONTEXT.md) preserves the exact original
generation and vote description. `MembershipPendingContextFiles` persists that
description as `pending.context`, using one `pending.context.next` candidate.
This component is not yet admitted by the complete journal owner's inventory and
does not authorize source retirement, change a ballot, or enable the public runtime.

## Transaction

The caller holds the exclusive directory owner and one existing shared JOURNAL
reservation. It authenticates and pins the backing source, authorizes the exact
transition in its guard, and supplies an allowance after deducting all other
journal users. The file component reserves no additional resource unit.

First installation requires no active context. Replacement compares the complete
old context bytes. The bounded candidate is written and forced, its directory is
forced, then it atomically replaces the active file; the directory is forced again
before return. Both active and complete candidate count against the allowance,
up to **2,933,600 bytes**. Existing partial candidates count by their actual length;
the remaining completion space must be admitted before writing.

Opening reads and checks files without repairing them. A candidate may resume
only from the exact requested prefix. A complete active file must decode and bind
to the original root/node/storage; a good candidate cannot repair corrupt active
authority. Every guard/cut rechecks directory and file identity, lengths and hashes.
Any failed operation poisons that object until it is reopened.

After an interrupted rename, active bytes already equal to the requested context
may be re-forced with the original prior bytes supplied. This recovers a lost
return; it is not proof that the caller may change the backing authority. The
caller still authorizes the transition. Snapshot getters confer no force authority.

## Qualification

The targeted reactor run passes **53 Java tests**, including ten file-component
tests. They cover create/replace/replay, exact prefixes and conflicts, corrupt
active/candidate files, identity and inode substitution, failed guards, shared
JOURNAL loss, completion capacity and zero leaked reservations.

A separate producer executes **32 scenarios in 96 fresh JVMs**:

- Seven write/force/rename boundaries for both first creation and replacement,
  each tested with halt and parent-directed SIGKILL.
- Two active re-force boundaries with both termination modes.
- Every case is interrupted once more during recovery, then reopened to complete.

The independent Python replay first validates the original 32-case evidence. It
checks exact input metadata, candidate prefixes, preserved old active bytes,
each force/return event sequence, parent-observed child exit codes and the final
single active context. It then rejects 22 mutations and verifies relocated replay.
Normal and optimized Python must return identical results. See the retained
[source/build/raw index](phase2-evidence/pending-context-files.json).

The fixture uses actual encoded ACCEPT and certified contexts from the same old
generation, but the process worker receives an already authorized transition.
The Python process replay does not receive all original backing objects and does
not independently re-prove their protocol authority. File forces and process
crashes do not establish power-loss behavior or complete owner recovery.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53PendingContextFilesTest,V53PendingContextTest,V53SourcePacketTest,V53FloorTest,V53ResourceTransferTest,V53DeclarationsTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53PendingContextProcessEvidence directory printed by the test.
python3 -m scripts.v53.pending_context_process_evidence <process-evidence-directory>
python3 -O -m scripts.v53.pending_context_process_evidence <process-evidence-directory>
```

## Remaining owner integration

Load and verify the context before detached old-vote recovery, preserve a separate
historical authority view, pin/rebind exact backing sources, account the complete
shared budget, and retain live higher observations. Qualify three-, four-, five-
and joint-voter maintenance plus repeated higher campaigns before claiming the
original progress deadlock repaired. This file component alone permits no deletion.

The subsequent [pure capture/rebind qualification](PHASE_2_PENDING_TRANSFER.md)
preserves one original context across six new backing sources and admits their
exact protected inventories. Live owner use and retirement ordering remain pending.
