# Phase 3 — atomic publication-image reservation handoff

Phase 3 remains **OPEN**. This corrects the transfer of one already-reserved
completion image to an inactive generation. It does not qualify the whole
transition's physical peak or all subsequent generation-reload lifetimes.

## Failure and correction

At baseline `d300b60d`, both publication and carried-vote installation released
the journal's `publication-completion` reservation before the inactive generation
reserved its plan. These are separate synchronized resource operations. A
receiver sharing that resource owner could use the released count/bytes before
the candidate reacquired them. If the candidate's metadata admission failed,
the poisoned journal also lost its completion reservation before owner close.

Two native original-owner regressions observed the prior release/reacquire
behavior at `INSTALL_RESERVED`: staging fell from 268,440,380 to 201,332,353
bytes during publication, and from 268,447,921 to 201,339,894 during carried
installation. The replacement image was only 837 bytes, replacing a previously
reserved 64 MiB maximum. These observations demonstrate the changed reservation;
they do not claim an observed remote receiver won that race.

A third regression, run with isolated baseline classes, reproduces the refusal
case: metadata admission fails while the disk inventory remains original, but
staging drops from 268,440,380 to 201,331,516 bytes and application leases drop
from six to five. The full 64 MiB completion reservation is lost. The corrected
test keeps the original usage and completes that certificate after close/reopen.

[`MembershipResources`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipResources.java)
now admits the complete generation group and transfers the exact original image
handle under one monitor. The successor retains the original maximum extent and
image count. All new handles, growth and replacement-map allocations must succeed
before the old handle is revoked. A rejection restores original extents, closes
only new handles and leaves the completion handle live. A stale predecessor's
close cannot release its successor. Existing metadata, staging, count and
headroom limits remain unchanged.

[`MembershipGenerationFiles`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipGenerationFiles.java)
binds this handoff to one new image in the verified plan. Other candidate images
are charged independently under the existing seven-image maximum. Its metadata
reservation and original partial-file growth use the same transaction. The existing install
then consumes that exact reserved plan; no force, selector or deletion authority
changes. [`MembershipGrantJournal`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipGrantJournal.java)
forgets the predecessor only after successful reservation. Refused journals
retain their original charge until close and recover from their original files.

## Verification scope

[`V53PublicationReservationTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53PublicationReservationTest.java)
has seven checks:

- Full seven-image count and an exact staging budget permit handoff without an
  eighth slot. A receiver waiting on the same monitor still cannot acquire one.
- Metadata/staging refusal and target collision roll back grouped growth while
  preserving the original maximum reservation.
- Foreign, closed or undersized handles, wrong categories, occupied targets,
  missing/duplicate image descriptors and self-growth are rejected.
- Additional candidate images still require their own bytes and slots; their
  refusal rolls back the entire group, including the proposed handoff.
- Public offline bootstrap plus real native votes apply and publish BARRIER and
  DATA on three original owners, retaining the complete image through candidate
  reservation. The typed application and exact duplicate publication are checked.
- A real carried certificate installs under a new native ballot on all three
  original owners without relinquishing its future image slot.
- Actual native publication under a metadata bound refuses without changing any
  original disk bytes or reservation. Close/reopen with available capacity then
  completes the same original certificate.

Native votes in these focused tests are explicitly orchestrated local calls,
not a network scheduling experiment. Capacity competitors are declared
accounting pressure, not invented physical receiving copies. Their deterministic
reservation checks are complemented by existing publication-boundary and native
5-REPLACE recovery checks. The [development receipt](phase3-evidence/publication-reservation.json)
records actual outcomes, source and retained logs; it supplies no final-source
cohort slot.

The continuation run started before the final multi-image generalization. Its
source inventory is retained separately from the final focused-test inventory;
the receipt identifies the two changed source files. That continuation must not
be treated as a run of the final source. The final focused run covers the complete
seven-test class, including additional-image admission and the three native cases.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53PublicationReservationTest,V53GenerationReservationTest,V53SourceReservationTest,V53ResourceTransferTest test
```

## Remaining resource work

The separate `reloadGenerations` path currently closes both generation owners
before reconstructing their reservations from the forced selector. Its ownership
handoff and refusal behavior need dedicated analysis and regression coverage;
this correction must not be described as eliminating every resource-accounting
gap. A separate passive original-owner probe completed publication and observed
15 `CURRENT_*` callbacks across three owners with two physical generation
directories but only one generation charged. It establishes the accounting gap,
not an observed competing receiver or physical-capacity overrun. Its first
diagnostic serializer failed on file-name map keys; a separate corrected probe
retains file inventories as path/hash rows and preserves that failed attempt.
Full permitted controller overlap, admitted FINAL under combined maximum
pressure, transient physical observations and phase-wide final-source admission
remain open. Twelve hosted subsets and 544 planned histories are unchanged.

Rollback reverts the three production files and the corresponding regression
test together. It restores the observed release/reacquire behavior, so a rollback
is not a correctness remedy. Retain failed originals and receipts.
