# Conditional native joining continuation replay

`scripts.v53.joining_continuation_evidence` extends the independently derived
[initialization](PHASE_3_JOINING_INITIALIZATION_REPLAY.md) into both selected
installations, FINAL, BARRIER and the final retaining cold reopen. It reads the
unchanged original `df22c398` `3-ADD` archive. Runtime Java, POMs, workflows,
persisted formats and frozen bounds are unchanged.

## Explicit historical gap

The original coordinator prepares the old majority at ballot 7, waits for joining
initialization, drains that preparation, then starts the separate activation at
ballot 8. The retained wire has the complete original node-1 PROMISE transfer and
node-2's correlated PROMISE reply containing a BASIS **digest**. It does not retain
the complete node-2 ballot-7 BASIS/source inventory. Those intermediate sources
were reclaimed before the first continuation-installed snapshot.

The reader validates the original promise bytes and transfer correlation. It
does not invent the missing UUID, frozen packet, images, or intermediate journal.
Its first boundary is a **conditional projection**: omit that already reclaimed,
unselected preparation, then derive the surviving storage from initialization
and the separately observed fresh ballot-8 source UUIDs. Equality of the later
directories does not prove the missing intermediate creation and reclamation.

Consequently `conditionalContinuationQualified` can be true while
`intermediatePreparationPhysicalQualified`, `completePhysicalQualified`,
`forceAndNetworkQualified`, `processDeathQualified` and `phase3Complete` remain
false. This receipt cannot close Phase 3 or replace a complete fresh execution.

## Independently derived surviving storage

1. Capture all three ballot-8 sources from the preceding derived generation,
   images and exact peer/learner ledger bytes. Only fresh source UUIDs are
   observed. Compare the complete BASIS, not a claimed hash or ready state.
2. Project exact same-cut maintenance copies, preserving bounded renewal debt.
   Keep current-generation and latest-promise sources pinned; retire only covered
   older sources and their journal groups. Preserve the adopted fence while it
   still belongs to the current joining generation.
3. Bind the fixed three-voter selected set to those original sources. Derive
   both selected-retention intents, the reachable packet, ancestry projection,
   selector and generation. Validate conflicts before any confirmed watermark
   can discharge older debt. The learner confirmation must name the current
   permanent identities; same-endpoint proofs use the canonical digest tie-break.
4. Derive FINAL's applied-end, publication and ledger promotion. Reconcile the
   resulting new-stable view while preserving all endpoint obligations. Derive
   fresh ballot 9 and its installation at cut 10, then BARRIER at cut 11.
5. Compare 28 complete node inventories across those seven boundaries, including
   the unchanged offline voter. Check standalone grant captures too. Compare all
   ten present joining families and five absent families at each boundary and
   final cold snapshot, preserving immutable original inode/path observations.
6. Check the final cold-open reseal callbacks precede open/close return. This is
   the fixture's same-JVM close/reopen, not a process-death experiment.

All 22 mutations first pass the preceding initialization reader, then fail their
exact declared new reason. They cover preparation correlation, unowned files,
peer/learner/future ledgers, inactive generations, retained images, allocations,
obsolete sources, adopted fences, standalone grants, cold immutable files,
original identity observations and an omitted reseal force. Inventory hashes are
refreshed where needed so rejection does not come from a stale copied manifest.

```bash
python3 -B -m scripts.v53.joining_continuation_evidence <original-raw-directory> --qualify
```

The [batch receipt](phase3-evidence/joining-continuation-replay.json) binds the
reader snapshot, original archive, tests, exact negative outcomes and portable
replay. Development failures remain retained separately.

## Next complete execution

The next original producer must capture the complete local PROMISE/BASIS and
source packet/image inventory for **both** old preparation voters before the
preparation is revoked or either source is reclaimed. Capture the corresponding
writer/capture/force, retirement-decision, journal-replacement and deletion
boundaries under their original owners, plus the already planned complete
send/arrival observations. Collection must reject missing captures rather than
silently treating a response digest as a full source.

Run that producer as one uninterrupted source/build/history-bound experiment;
do not combine this archive's prefix with a later run's missing middle. Its new
reader must derive ballot 7, its retirement and fresh ballot 8 without this
conditional projection. Independent profiles may later run in parallel on
GitHub; preparation, INTENT/FINAL and crash/restart within one history stay
together. Process-death cuts, all seven profiles and frozen mappings remain
separate closure work. Phase 3 is **OPEN**.
