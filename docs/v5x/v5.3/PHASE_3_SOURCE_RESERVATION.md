# Phase 3 — retain floor and retirement charges on refused expansion

Phase 3 remains **OPEN**. This extends the
[generation reservation correction](PHASE_3_GENERATION_RESERVATION.md) to
original floor and retirement files. It qualifies conditional storage recovery,
not simultaneous native maximum-resource use or a final-source hosted cohort.

## Failure and correction

At baseline `dc1499c2`, both full-floor and retirement reservation paths closed
their existing leases before requesting the complete plan. Four deterministic
disk regressions reproduce an undercount after capacity refusal: each loses the
1,118-byte partial manifest charge; the two image cases also lose the existing
30-byte application image charge. Every original file remains unchanged. The
poisoned journal has not closed, so those resources still belong to its owner.

The per-copy floor handoff has a related failure: it can grow metadata before
failing to acquire an image slot, leaving a partially expanded reservation.
It retains the original files, but does not restore the pre-admission usage.

[`MembershipResources`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipResources.java)
now shares the original atomic expansion implementation between generation and
source groups. Source groups accept only SOURCE/APPLICATION handles, bound the
group to six sources plus seven images, and preserve all existing capacity and
completion-headroom checks. Failure rolls back growth and newly acquired handles
under the same monitor; original handles remain charged until owner close.

[`MembershipFloorFiles`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipFloorFiles.java)
reserves a non-handoff plan as a whole and a handoff one copy at a time. It still
forces a replacement before releasing its receiving owner, retains remote-first
ordering, and writes floor authority last. It does not reserve every replacement
up front during a handoff.

[`MembershipRetirementFiles`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipRetirementFiles.java)
retains its source and image handles during expansion. Exact-image borrowing,
original-prefix verification, deletion authority, cleanup ordering, durable
formats and all limits remain unchanged. Capacity refusal does not retry a
command; recovery reopens the same original files with available capacity.

## Verification

[`V53SourceReservationTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53SourceReservationTest.java)
adds five original disk refusal/resume cases and two resource transaction cases.
The disk tests compare all retained files and usage before/after rejection,
require no handoff on partial admission, and then complete the original operation
after close/reopen. Competing reservations are explicit accounting pressure,
not invented physical receiving copies. The transaction tests check simultaneous
metadata/staging rollback, category and owner isolation, duplicate/closed handles,
group bounds and preservation of larger existing extents.

The [development receipt](phase3-evidence/source-reservation.json) records the
original failures, isolated baseline replay, targeted regressions and source
hashes. Existing sequential handoff, interrupted floor/retirement boundaries and
borrowed-image tests remain part of the selected validation. Long native hosted
matrices are not rerun or counted as passing by this correction.

```bash
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53SourceReservationTest,V53GenerationReservationTest,V53ResourceTransferTest,V53FloorFilesTest,V53RetirementTest,V53RetirementImagesTest test
```

The inventory remains twelve hosted subsets and 544 planned histories. Combined
physical peaks, transport/publication lifetimes, admitted FINAL under full
pressure and final-source phase admission remain open. Rollback would revert the
three production files and restore the reproduced accounting defects; retain the
original failure evidence when assessing any rollback.
