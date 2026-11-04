# Native publication storage observations

This development gate follows the [completion image handoff](PHASE_3_PUBLICATION_RESERVATION.md)
and [atomic generation reload](PHASE_3_GENERATION_RELOAD.md). It checks the actual
storage reservations of ordinary journal publishers. It does not raise a limit,
extend a receiving lifetime, enable public APIs or declare Phase 3 complete.

## Original collection and authority

`V53PublicationResourceCapture` is enabled only by the test property
`v53.publication.resources=true`. It records eleven existing callbacks per new
publication: validation, candidate reservation, candidate parent force, all five
current-reader force boundaries, completed selector reload, covered application
retirement and final return. Old owners, the joining owner and the reopened
joint-floor owner share one content-addressed collection.

Each callback retains the exact original owner inventory, bytes and before/after
resource usage. Both inventories and their storage charges must remain unchanged
while copied. The collector inserts no protocol event, retries no observation,
and preserves a partial collection on failure. Event indexes identify existing
node/scope callbacks; cross-owner collector order need not equal event order.
All original images are retained once by digest, not omitted as regenerable data.
Event loading uses the existing complete-history envelope (32 MiB and 65,536
rows), including canonical JSON and individual-row bounds. The smaller legacy
stable-reader envelope is not used to load this complete transition's events.

`publication_resource_evidence.py` first runs the corresponding complete native
reader. Stable BARRIER/DATA uses original bootstrap, selection, grants, applied
images, receipts, floor confirmation and TCP replay. The interrupted 5-REPLACE
entry uses the whole physical/network/export/maintenance reader and continuous
peer, learner, future and ballot ledgers. A callback from independent publication
derivation supplies expected pre/post files; observed counters or captured files
never supply expected authority. The stable reader's extra collection is an
explicit opt-in; its default exact root layout remains unchanged.

The resource reader compares **all files** at each captured boundary, including
old generations, covered application files, selector and pending vote. Index,
scope, callback order, completeness, object digests, regular-file rules, bounded
inventory, canonical JSON and absence of unreferenced data are also checked.

## Independently derived reservations

The fixed journal and current-authority charges are 32 MiB and 2 MiB. Generation
metadata, retained source packets, floor copies and application images are counted
from the independently derived original bytes. Separate physical copies remain
separate charges even when their image bytes have the same digest.

| Boundary | Completion and generation charges |
| --- | --- |
| Publication validated | Original storage plus four 64 MiB image reservations: applied end, two replay images and future publication |
| Candidate reserved | New metadata is charged before files exist; the same publication image reservation is handed to the candidate |
| Candidate parent force through current directory force | Old and candidate generations stay charged; the candidate image retains its 64 MiB reservation |
| Publication selector forced | The complete reader pair has committed; candidate image shrinks to actual bytes; three completion images remain reserved |
| Covered application retired | Applied-end and replay reservations are released; original physical generation/source copies remain charged |
| Publication before return | Completed future/peer ledgers are compared to independently derived final bytes |

The reader bounds CONTROL/WAITER observations and checks the recorded total lease
count, but does **not** independently derive their network lifetimes here. That
separate scope belongs to [transfer reply resource replay](PHASE_3_TRANSFER_RESOURCE_LIFETIME.md).
This gate checks observed publication boundaries, not every instant between them,
the full 384 MiB metadata maximum, every profile or process-death recovery.

## Reproduction and rejection qualification

Build/test one original at a time; do not overwrite the shared Maven output while
another native test is running. Preserve each printed `v53NativeDispatchEvidence`
directory. The original failures and all source/receipt hashes belong in the
development evidence index; a corrected reader replays the unchanged original.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.publication.resources=true \
  '-Dtest=V53NativeDispatchTest#nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener' test
python3 -m scripts.v53.publication_resource_evidence "$STABLE_RAW" --qualify

mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.publication.resources=true \
  -Dv53.joint.floor.recovery=true \
  '-Dtest=V53JointFloorRecoveryTest#originalFourCopyFloorResumesOverTcpBeforeFinalAndStableBarrier' test
python3 -m scripts.v53.publication_resource_evidence "$JOINT_RAW" --profile 5-REPLACE --qualify
```

The 26 declared negatives include missing/foreign events, changed original files,
early selector or vote cleanup, lost old-generation charges, premature or late
candidate shrink, lost/leaked completion reservations, linked/unreferenced
objects and malformed accounting. Qualification first accepts the unmodified
original, then mutates only copied observations against the same independent
derivation. Every negative requires its exact rejection reason; an unrelated
original failure cannot count as a rejection success.

The [development receipt](phase3-evidence/publication-resources.json) records
two actual native originals: four stable publications (44 boundaries) and 33
publications in the complete interrupted 5-REPLACE history (363 boundaries).
Both original-first qualifications pass all 26 declared negatives (52 rejection
checks); 161 focused/adjacent Python tests pass. The complete native transition
took approximately 19 minutes on this development machine. Its whole physical,
network/export, maintenance and continuous four-ledger precondition also passed.
Observed publication maxima were six application reservations and one retained
SOURCE; this is deliberately not substituted for the separate interrupted-floor
peak or the unqualified full metadata envelope.

The first adapter replay used the legacy 8 MiB event envelope and refused this
8,541,213-byte original after all history layers passed. The bounded shared
32 MiB reader corrected that adapter mismatch; the exact same native bytes were
replayed successfully. A regression covers a valid history above 8 MiB and the
unchanged row ceiling. The failed replay log is retained with the receipt.

This development evidence adds no accepted final-source cohort slot.
The twelve hosted subsets and 544 planned histories remain unchanged. Broader
combined physical peaks, additional lifecycle/profile/fault axes, phase-wide
admission and final-source execution remain open. Rollback removes this optional
collector/reader and the independent derivation callback together; production
storage behavior and the preceding reservation corrections are unaffected.
