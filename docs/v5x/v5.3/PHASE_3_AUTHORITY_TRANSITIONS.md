# Native publication across authority changes

Status: locally qualified for the explicit scope below. This batch connects explicitly driven native
INTENT and FINAL slots to their original publication replies. It does not close
Phase 3 or enable public membership operations.

## Reproduced problems and corrections

Four original failed attempts remain under `target/v53-authority-transition/`.
The four-voter INTENT fixture first exhausted the six SOURCE reservations while
holding received copies and reserving a complete replacement floor. After that
boundary was corrected, sequential publication changed the first receiver's view
before the next receiver's future-retention quorum could finish. A completed
publication also failed its outer activation guard. Finally, the next receiver
could not fetch the first receiver's original checkpoint ACK after that receiver
had changed views. A separate FINAL fixture then exposed an old-view retention
ledger at the next native grant.

The changes preserve the original resource, voting and format limits:

- Copy remote floor members before the local member. Reserve each complete copy
  before writing it; force its contents and directory parents before releasing
  only its matching received scratch. The final FLOOR authority remains last.
  Reopened partial files remain charged, and their reservations grow before
  completion. Original retained sources are not removed by this handoff.
- Record every intended receiver's future-retention quorum before sending any
  PUBLISH. Retain the bounded original capabilities through dispatch and close.
- Allow only the exact completed PUBLISH_ACK through the old activation wrapper.
  Ordinary controls still require the original current authority. Duplicate
  acknowledgement continues to recheck the certificate, selection, generation,
  identity, higher ballot, deadline and owner.
- Let that completed publication export only original CHECKPOINT records ending
  at its exact target and this node's original CHECKPOINT_ACK at that target.
  Grant/vote/payload exports and another node's ACK are not authorized by this
  path. Existing old transfer traces cannot migrate into the completed service.
- Before a new ordinary native grant, force the existing conservative retention
  reconciliation if the current configuration changed. Remaining peer endpoints
  are preserved. A joining voter still requires an actual complete joining copy;
  a new configuration alone cannot manufacture learner readiness.

## Qualification boundary

The two real TCP histories use four admitted voters and original storage-driven
RESERVE/PREPARE/READY/SEAL preparation. One history publishes INTENT natively; the
other prepares INTENT through storage and publishes FINAL natively. They test the
original ACK, ended old authority, exact duplicates, wrong certificates, restricted
checkpoint exports and higher-ballot fencing. They do not constitute one complete
autonomous REMOVE, nor ADD/REPLACE learner qualification.

The independent reader reconstructs public bootstrap, all preparation slots,
fresh grants/selection, applied images, publication generations and retention
ledgers. It checks both receiver ACKs and requires both retention quorums before
any publication send. FINAL's ACCEPT/PROOF certificate still has the governing
joint quorum; its resulting stable checkpoint uses the new view's majority.
The complete wire-transfer matrix and automatic post-FINAL fresh barrier remain
separate open obligations. The reader reports `networkQualified=false` and
`phase3Complete=false` rather than claiming their completion.

The sequential-floor process gate covers stable and joint four-voter fixtures,
clean duplication, halt and SIGKILL at copy-force, copy-handoff and final-authority
force, with exact recovered files and independent original-first negatives. This
worker uses a callback which deletes no network data: live receive replacement is
covered by the actual native Java histories, not inferred from the process gate.
Historical membership in these floor fixtures remains conditional, as in the
existing floor qualification. Neither gate emulates power loss.

## Qualification results

The corrected immutable Java snapshot passes 54 tests across authority-changing
publication, floor storage, resource ownership, retained peer files/sources,
record exchange and transfer service. Both actual INTENT and FINAL histories pass
independent physical and publication-boundary replay, including 28 exact negative
mutations. The four-voter stable/joint floor process matrix passes all fourteen
cases and seventeen exact negatives. Its build inventory is checked before and
after execution. A collector failure from an implicit empty classpath entry is
retained separately; explicit absolute classpath entries now reject that input
before executing workers.

Four unchanged stable/carried continuation, cancellation and higher-ballot
regressions pass against identical Java sources, with fifty independent original-first
negative mutations. All 688 V5.3 Python tests pass. Archived-reader replay
under Python optimization reproduces both authority histories, both stable/carried
histories, all fourteen process cases and all ninety-five exact negative results.
The [source-bound receipt](phase3-evidence/authority-transitions.json) records
original failures, both immutable builds and the archive digest. The full Phase 3
checklist stays open. Next integration must join old-stable INTENT, native
joint activation, FINAL and a fresh new-stable barrier in one actual continuous
history, then cover learner ADD/REPLACE and the complete autonomous lifecycle.
