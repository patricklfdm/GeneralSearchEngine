# Original learner payload placement

Phase 3 remains **OPEN**. `MembershipLearnerPlacement` consumes the live
[installation custody](PHASE_3_LEARNER_CUSTODY.md) to move the dormant payload
into the original replica directory. This component preserves the original
ROOT, NODE and replica-lock inodes, continuous kernel-lock ownership and every
existing storage charge. It does not open a journal, admit a voter, retire any
predecessor or implement cold write recovery.

## Original transaction and fixed moves

The private sibling `.gse-v53-learner-placement-<plan digest>` holds at most two
64 KiB files, `placement.json` and `placed.json`. The canonical original plan
binds the reviewed learner plan, actual custody decision inode/size/hash, its
own directory binding and the fixed move order. The completion marker binds the
plan bytes and inode, custody digest and that same order. These companions are
reserved before staging writes: stage companions 128 KiB + custody 256 KiB +
placement companions 128 KiB = 512 KiB, plus actual staged metadata, within the
existing GENERATION limit. No public resource or format limit changes.

Check the original custody inventory and byte equality of the preserved replica
headers before writing. Require stage and replica to be on the same filesystem;
there is no copy fallback. Force the complete original plan and parents before
moving, in order: genesis, allocator, grants, pending accept, sources,
generations, selector. Each move uses the original inode; directories move as
whole subtrees. Force each moved payload and both source/destination parents
before the next move. Force the full payload again before the completion marker.

Custody validates all nine original roots throughout the operation. Its exact
inventory may change only by a prefix of these seven relocations. Normalize
those relocations in memory and compare all original directory/file identities,
sizes and hashes. Duplicate or missing locations, copies with different inodes,
nonprefix moves, foreign files and changed predecessors refuse. No physical
repair is performed by this validation. Old object closes remain harmless and
the installation retains the original root/operation/typed/source locks.

## Interruption and inspection

Explicit `resume` requires the same live custody and its attached original
transaction. It cannot create a new plan, reconstruct a missing decision or
accept a torn plan. A complete original plan can be re-forced. Before moving any
new item, re-force the already moved prefix and both parents; otherwise a second
crash could persist a later move without the earlier move. A partial completion
marker may be finished under this same original plan and inode.

`inspectOriginal` only reports the physical layout as PARTIAL or PLACED. It
returns no ownership, durability proof, history admission or restart permission.
In particular, complete marker bytes alone do not prove that a force completed.
Ordinary learner reopen continues to reject the changed replica inventory,
without writes. Cold installation recovery must be implemented explicitly with
original authority, actual locks and resource ownership before this layout can
be used by a joined-voter runtime. Do not restore the old layout or delete these
files as a rollback shortcut.

## Qualification boundary

`V53LearnerPlacementTest` uses real typed preparation, TCP INTENT retention,
dormant staging and transferred custody. It checks actual original-inode moves,
unchanged usage, independent JVM lock exclusion, stale-close and ordinary-open
refusal; 25 sequential live exception cuts across the decision, all seven moves
and marker; torn/corrupted decisions; and duplicate, missing, copied, nonprefix
and foreign physical layouts. Historical quorum fixtures are conditional and
exception cuts do not substitute for process-death tests.

The [component receipt](phase3-evidence/learner-placement.json) retains executed
attempts, including an initial compile error. The
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md) still requires native
continuous histories, all applicable heads/profiles, maximum resources,
halt/SIGKILL and independent original-first physical/history/wire replay.
Native old-majority INTENT delivery before joint checkpointing, joined admission,
covered predecessor retirement, joint FINAL and the fresh barrier remain OPEN.

The focused matrix passes all four placement cases plus ten descriptor and seven
storage-transfer regressions. Two additional existing cases pass for stage
capacity refusal and pre-placement custody recovery across close/reopen. These
23 distinct cases use identical implementation/test inputs; the separate first
successful placement smoke is repeated coverage, not a 24th case. No full
reactor, native all-profile history or hosted measurement was executed here.
