# Original learner payload placement

Phase 3 remains **OPEN**. `MembershipLearnerPlacement` consumes the live
[installation custody](PHASE_3_LEARNER_CUSTODY.md) to move the dormant payload
into the original replica directory. This component preserves the original
ROOT, NODE and replica-lock inodes, continuous kernel-lock ownership and every
existing storage charge. Explicit cold recovery reopens the original semantic
owners before continuing installation. It does not open a journal, admit a voter
or retire any predecessor.

## Original transaction and fixed moves

The private sibling `.gse-v53-learner-placement-<plan digest>` holds the two
64 KiB placement files, `placement.json` and `placed.json`. A41 also permits the
separate 64 KiB [joined admission](PHASE_3_JOINED_ADMISSION.md) record after
complete placement. The canonical original plan
binds the reviewed learner plan, actual custody decision inode/size/hash, its
own directory binding and the fixed move order. The completion marker binds the
plan bytes and inode, custody digest and that same order. These companions are
reserved before staging writes: stage companions 128 KiB + custody 256 KiB +
placement companions 128 KiB + joined admission 64 KiB = 576 KiB, plus actual
staged metadata, within the
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
without writes. The separate `recover` entry described below supplies actual
original ownership before continuing placement. Joined-voter admission remains
separate. Do not restore the old layout or delete these files as a rollback
shortcut.

## Cold original-owner recovery

`recover` requires an empty original resource pool, the reviewed learner summary
and its real typed application configuration. A private recovery projection
validates the complete placement decision, original custody decision and exact
physical move prefix. It is issued only inside this entry point, never from a
caller-provided inventory or from the physical inspection result.

Open the original operation and replica locks, complete admission decisions and
existing learner source. Reopen the initial, promoted successor or selected slot
through its existing semantic validators and actual locks. Retired originals
must remain absent under their exact prior retirement/head proofs. Reconstruct
conservative original reservations; after validating the original selected-slot
head and vacancy, restore its retired-seed/inactive-image flags before exposing
an internal current head. This only restores process-local state under the
retained custody proof; it does not delete or re-force any predecessor. Do not
fabricate missing old files or
delete newly discovered ones. Ordinary learner reopen retains its five-child
inventory and has no access to this projection. Recovery cannot fall back to
creating a missing replica, root lock or typed directory.

Reopen the original typed backup and rerun the core application decoder using
the captured configuration. Require the exact original receipt, complete typed
plan and selected head. The retained custody decision witnesses the earlier
forced preparation; these internal read-only objects cannot create a new
preparation or expose a public readiness result. Reopen and independently verify
the retained matching INTENT with the existing stored-source verifier. Derive
the same staged generation and validate its original plan and inode-bound seal
at the projected locations. There is no new stored-history token or supplied
set of historical voters.

The entire phase is read-only. Its internal getters use a scope-lifetime guard;
the complete physical inventory is checked before and after the phase, around
the explicit `LEARNER_PLACEMENT_RECOVERY_VERIFIED` boundary, and around every
subsequent custody force through the original-inventory check. This avoids
rescanning all nine roots for every nested property access without permitting
any write or returned capability from an unvalidated read scope. Each original
reader still validates its own bytes, identities and source history.

Only then re-force the original custody decision and transfer the reopened
locks and complete reservation group. Attach the existing placement plan and
completion prefix; continue using the same move/force procedure, including
re-forcing all already moved members. Closing historical wrappers cannot release
the transferred ownership. A failure closes provisional handles and leaves the
original files for explicit recovery. The read projection expires on exit and
is not the returned installation owner's authority.

The recovery entry still cannot campaign, vote, open a native journal, retire
learner predecessors or solve old-majority INTENT delivery. Cold component
reopen is not a halt/SIGKILL or full native history qualification.

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
reactor, native all-profile history or hosted measurement was executed there.

The separate [cold-recovery receipt](phase3-evidence/learner-placement-recovery.json)
records the new source and its actual test results. It retains two development
runs that collided on a shared fixed test port; those runs failed before reaching
the intended recovery assertions and do not count as passing evidence. Later
validation runs sharing those fixtures are serialized. The first complete
matrix also retained a real selected-slot failure: the original vacancy was
valid, but recovery omitted the retired-seed flag and the current-head check
correctly refused it. The correction restores only the state justified by that
original proof and tests that a corrupted vacancy still refuses before a force.

The corrected snapshot passes 23 Java cases with no failures or skips: three
cold-recovery cases (seven initial move prefixes, selected-slot recovery and
original/semantic refusals), one ordinary placement, ten descriptor, seven
resource-transfer, one custody-reopen and one stage-capacity regression. The
promoted-source cold case passed on the preceding snapshot and was not repeated
after the no-create guards and selected-slot state correction; its exact source
and the four changed source/test files are retained separately. Across these
two snapshots, 24 distinct cases have a passing execution. This does not claim
24 final-source cases or full native/process acceptance.
