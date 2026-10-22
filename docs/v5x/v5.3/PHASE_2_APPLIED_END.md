# Phase 2C5d — forced application end before checkpoint ACK

Status: **local storage component PASS; shared-owner integration OPEN**.

One private staging area retains an exact plan inventory, original selector and
certificate, complete new catalog, exact checkpoint statement, application image
and local CHECKPOINT_ACK. The plan uses canonical ordered path/hash/length rows.
All metadata plus the eventual ACK fit the caller's remaining already-reserved
JOURNAL allowance. One full 64 MiB APPLICATION slot is reserved before writing;
partial reopen charges it conservatively. No new resource unit or selectable
generation is introduced. Exhaustion refuses before new files or an ACK.

Every surviving file prefix must match the supplied original plan. Complete metadata
and application are forced, followed by staging and parent directories, **before**
the local ACK is created. The ACK and directories are then forced before return.
The component repeatedly checks the exclusive owner's supplied guard/fence,
filesystem identity, inventory, original file hashes and shared journal reservation.
Same-byte inode replacement during a live write is a rejection. Failure retains
partial authority; no truncation, replacement, deletion or recursive cleanup occurs.

The local identity must belong to the checkpoint's next authority. Merely computing
ACK bytes or listing their hash in the plan does not establish their force. A torn
or complete existing ACK requires every preceding original end file to be complete.
Reopen resumes only a revalidated matching plan and re-forces the full order.

## Scope and remaining integration

The caller must bind the plan to its **actual** current selector, retained phased
certificate and promise/fence, compute the shared remaining metadata allowance and
reserve typed replay/scratch resources. This helper does not replace the journal
owner, authenticate a synthetic history, expose a public read, update a selector or
retire a source. The next batch must integrate this component with those actual
owner paths, complete capsule/ancestry installation and stage lifetime recovery.
A materialized end plus one local ACK does not establish a governing quorum.

## Retained validation

- **46 distinct Java tests** passed across a 38-test focused execution and a later
  23-test execution (overlap counted once). Nine applied-end tests cover exact
  persistence/reopen, all write cuts, repeated interruption, revoked ownership,
  same-byte replacement, corrupt/missing files, foreign voters and resource limits.
- **42 halt/SIGKILL cases / 126 fresh JVMs** cover all 21 named cuts. Every case
  suffers another halt during recovery before a fresh process completes it. These
  workers use an actual exclusive file lock; original protocol history remains an
  explicitly conditional fixture. Process crashes do not emulate power loss.
- Three separate actual staged ends supply checkpoint observations for a joint
  quorum in a focused test; a removed voter cannot endorse the FINAL successor.
- Independent Python replay checks complete inventories, exact interrupted byte
  prefixes, certificate/catalog/statement/image/ACK bindings and complete force/
  return order. Seven corruptions reject after original validation; relocated
  replay and Python optimized mode produce the same PASS/result set.

The first focused execution exposed an inventory encoding error: filenames were
used as keys unsupported by the existing canonical JSON encoder. Ordered path rows
fixed the construction; the original failed log is retained. No deployed protocol,
core encoder or frozen format was changed to accommodate it.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53AppliedEndFilesTest,V53CheckpointPlanTest,V53ResourceTransferTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53AppliedEndProcessEvidence directory printed by that test:
python3 -m scripts.v53.applied_end_evidence <retained-process-directory>
```

[Source/build/raw-log index](phase2-evidence/applied-end.json).
Local logs: `target/v53-applied-end/`; raw JVM snapshots/logs remain under
`general-search-engine-replication/target/v53-applied-end-process/`.
The earlier 292-test checkpoint gate covers its earlier implementation. Complete
source-bound integrated publication, protected CI and pre-cloud closure remain OPEN.
