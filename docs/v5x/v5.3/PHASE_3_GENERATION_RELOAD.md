# Phase 3 — preserve generation reservations during reader reload

Phase 3 remains **OPEN**. This follows the
[publication-image handoff](PHASE_3_PUBLICATION_RESERVATION.md); it closes a
different accounting gap after the selector has already been forced.

## Observed failure

At baseline `20f1d89b`, `reloadGenerations` closed both old readers before
constructing the selected reader and then the inactive reader. Their original
files remained present. A passive publication probe observed 15 `CURRENT_*`
callbacks across three native owners with two physical generations and only one
charged generation. Two new native regressions also fail with isolated baseline
classes: validation loses the inactive generation's charges, and interruption
inside selected-reader validation loses both readers' charges before journal
close. The original selector/files are still retained.

These are accounting observations, not an observed physical-space overrun or a
claim that a remote peer won a scheduling race. The first passive probe's JSON
serialization failure is retained separately from its corrected path/hash-row
serializer. The native baseline assertions use the unchanged tests' bodies and
the recorded original production classes.

## Ownership change

[`MembershipResources`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipResources.java)
now prepares a transaction covering the exact original current-authority,
generation and generation-image handles. Pending reader handles claim those
same keys and no greater extents; they cannot grow, release original storage, or
consume an extra slot. Other live storage and control work keep their existing
owners. The original group remains fully charged while both readers inspect and
force their original files.

Commit requires every original member to be claimed once and every original
handle/extent still unchanged. It allocates the replacement map before switching
ownership under the resource monitor. The final readers then hold the actual
verified file extents; surplus maximum reservations may shrink only at this
successful switch. Closing a stale predecessor cannot release a successor.
Closing any pending reader aborts the pending group without releasing originals.

[`MembershipGrantJournal`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipGrantJournal.java)
constructs both replacement readers before committing the transaction. A failed
validation keeps the original reservations with the poisoned journal until its
normal close. Initial open and joined-owner custody still use their existing
admission paths. This changes no persistent format, force/selector boundary,
membership authority, deletion rule, resource ceiling or deadline.

## Development checks

[`V53GenerationReloadTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53GenerationReloadTest.java)
covers:

- Full generation/image slots during pending validation, a separate competing
  receiver, unchanged unrelated control work, and stale-handle close after commit.
- Missing/duplicate/oversized claims and pending-reader close preserving the
  original group; original storage remains usable after abort.
- Changed or closed original handles refusing commit without undoing unrelated
  legitimate changes, and incomplete/foreign original groups refusing preparation.
- Native BARRIER and DATA publication on three original owners: all 30 reader
  callbacks retain the complete admitted group and refuse a spare generation.
- Native interruption after current files are forced, exact original files and
  charges retained until close, and completion from the same files after reopen.

Native calls here are explicitly orchestrated local operations. The receipt
records the actual focused and compatibility results and their source inventory:
[generation reload development evidence](phase3-evidence/generation-reload.json).
The prior batch's long native 5-REPLACE continuation is historical evidence of
its earlier source; it is not counted again for this changed runtime.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53GenerationReloadTest,V53PublicationReservationTest,V53GenerationReservationTest,V53SourceReservationTest,V53ResourceTransferTest test
```

Full simultaneous physical peaks, all permitted controller overlaps, admitted
FINAL at combined maximum pressure, remaining lifecycle/process axes and
phase-wide final-source admission/execution remain open. The twelve hosted
subsets and 544 planned histories are unchanged; these development checks add no
accepted cohort slot. Rollback reverts the four production files and this test
together and restores the diagnosed gap; keep original failed evidence.
