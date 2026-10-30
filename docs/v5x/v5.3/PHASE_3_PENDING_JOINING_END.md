# Original pending joining end

Phase 3 remains **OPEN**. The pending learner transaction now retains the complete
original SEALED source and the exact native pending INTENT metadata before
forcing its own new-side `CHECKPOINT_ACK`. It does not publish JOINT, install a
voter, or make the learner publicly ready.

## Original provenance and retained state

Only `MembershipLearnerProgress` can create the private input to this transaction.
It requires the same completed SEALED prefix/generation transfer, same live typed
head and matching completed dedicated metadata exchange. Bare decoded metadata
cannot start retention. The receiver completes missing generation members in its
existing receiving directory; no additional source or generation is fetched.

The private `pending-intent.json` records the full operation and learner identity,
original typed receipt, selected prepared source anchor, original receiving path,
source directory/member inode identities, exact inventory and the pending
metadata bytes. The latter must still match the SEALED source, actual typed
receipt, old-side INTENT certificate, unchanged application and projected end.

The bounded plan uses the existing JOURNAL reservation (one owner, unchanged
32 MiB ceiling): twice the maximum private plan plus 2048 bytes for the ACK.
The private plan maximum is 64 KiB plus the existing bounded joining metadata
maximum. The reservation precedes plan serialization and recovery reads. Source
and image charges transfer with the existing receiving slot and are retained
until close. No public format, timing or resource limit changes.

## Force before acknowledgement

The original plan is written, forced and renamed before the receiving directory
moves into the fixed pending directory. Every original source member and the
relevant directories are forced. Only that completed transaction may derive the
exact new-side checkpoint statement and permanent local voter identity.

`joining-ack.gsr` is written under the same live owner, forced, and followed by a
parent-directory force before an endorsement is returned. Returning metadata or
a structurally valid certificate alone never returns an endorsement. The source
remains SEALED; the returned ACK is an applied-end witness, not a publication or
election vote. No fabricated SELECTOR, allocator or bootstrap record is created.

Pending state blocks new learner preparation, CANCEL/ordinary INTENT retention
and the existing published-JOINT custody path. Those old paths keep their original
names and formats. A later transition from this pending state to a complete
published JOINT installation is still required.

## Explicit recovery

Close releases live reservations without deleting the original evidence. Reopen
requires the actual original prepared learner and typed receipt, original source
paths/inodes and exact inventory. An incomplete original plan fails before any
recovery write. A complete original plan may re-force its original files and
finish the same move. A partial ACK is accepted only as an exact prefix of the
one deterministically derived acknowledgement, then completed and re-forced.
Copied/replaced source members, changed plan/source/ACK bytes, foreign files,
conflicting terminal state and insufficient JOURNAL capacity are refused. ACK
recovery validates its exact deterministic byte prefix and forces it again; it
does not infer an earlier force from the presence or inode of an ACK file.

## Qualification boundary

The [component receipt](phase3-evidence/pending-joining-end.json) records exact
source snapshots, test results and retained evidence. The focused typed-owner,
TCP, storage and reopen cases use conditional old voting histories. Nineteen
injected I/O cuts are deterministic component tests; they are not process-death
or independent physical-history qualification.

All 26 selected Java cases passed: four core pending-owner cases, nineteen I/O
cuts, two prior CANCEL/INTENT regressions and one native joining history. The
native history completed in about nine minutes. It starts from actual bootstrap
and old 2/3 certificate creation with node 3 unavailable: the old two ends alone
refuse, and the actual joining learner's forced ACK permits new 3/4 checkpoint
assembly. The live old owner remains at SEALED; this is not publication.

Coordinator ordering, ACK wire delivery, future retention/publication, pending-to-
joined installation, joint FINAL and the fresh barrier remain open. Complete
all-profile/process/original-history acceptance belongs to the deferred hosted
matrix; this component is not Phase 3 closure.
