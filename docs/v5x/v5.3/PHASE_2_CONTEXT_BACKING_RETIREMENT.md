# Retiring intermediate context backing sources

Phase 2 remains **OPEN**. The private local owner can now repeatedly capture a
fresh protected source and retire a covered intermediate source while the same
original pending vote remains retained. This extends
[protected capture](PHASE_2_CONTEXT_CAPTURE.md); later selected installation and
replacement of the governing floor remain separate integration work.

## Exact permission

The existing predecessor-source permission remains available. An intermediate
source additionally requires all of the following:

- A complete forced context reconstructs the exact original ENTRY, payload,
  ACCEPT and any original PROOF/certificate against the newest retained backing.
- The source's original PROMISE/BASIS has the same root, view and local voter. Its
  ballot lies strictly between the installed selection and newest backing ballot,
  and its accepted tail is exactly the original ACCEPT.
- Before publishing a retirement decision, the complete original source retains
  those same original entry/vote phase bytes. Existing source-retirement checks
  still validate parent ancestry, floor coverage, images and the exact inventory.
- The original generation is already gone. The installed generation/source and
  governing floor remain pinned. Latest backing is never eligible for deletion.

The deletion mechanism is unchanged: force the exact retirement decision, remove
its original journal group through forced rotation, delete only the recorded
files, then release reservations and clear the decision. Once journal frames have
been removed, recovery uses the original frames retained in that decision; it
never obtains missing authority from partially deleted files. The same strict
intermediate-ballot and original-ACCEPT checks also apply to that recovery path.

Cleanup under a later volatile observation remains possible, but does not lower
that observation or return an old grant/ACCEPT ACK. New capture cannot replace the
context during a pending deletion transaction.

## Local qualification

The source/build-bound receipt is
[context-backing-retirement.json](phase2-evidence/context-backing-retirement.json).
Its retained logs include a red execution of the original implementation: the
first attempted intermediate retirement is rejected by the former
predecessor-only permission.

The actual three-voter fixture runs seven sequential fresh captures, counters
22–28, with six intermediate deletions and reopen between rounds. Original vote
20 and installed selection 21 are unchanged. Peak APPLICATION reservations stay
at seven; steady reservations stay at six. These are six/five physical image
files respectively plus one empty publication-completion reservation. Each steady
state retains only the installed source and newest backing.

Fourteen first deletion/rotation exception cuts are each followed by a second
recovery interruption. A separate test interrupts two successive physical deletion
boundaries after the original journal frames are gone. Focused tests also cover
higher-observation fencing, corrupt retained authority and altered saved decisions.
Live lock probes run in separate JVMs; snapshots never reopen a live lock inode.

The independent Python replay derives exact source packets/context replacements,
retirement inventories, compacted journals and interrupted byte/force prefixes
from the validated original fixture. Its negative variants remove or alter the
original vote, context, either pinned source, floor, journal, force trace and
scope claims. Original-first and relocated replay run with and without Python
assertions enabled.

These exception cuts are not new halt/SIGKILL or power-loss qualification. The
fixture's historical bootstrap/quorum observations remain conditional. This does
not establish maximal byte usage, coordinated old/joint/new lifetime, later
selected-generation reuse, online runtime support or Phase 2 closure.
