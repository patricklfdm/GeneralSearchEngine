# Phase 3 — application recovery maintenance storage ownership

Phase 3 remains **OPEN**. This entry composes the
[same-history maintenance captures](PHASE_3_CARRIED_APPLICATION_MAINTENANCE_PREFIXES.md)
with the original resource journals. It requires the complete application crash,
old-end retirement, campaign, FLOOR and ordinary-retirement capture chain before
checking resource ownership. It reuses original evidence without executing or
retrying the workload. The default binds the three maintenance families;
`--include-application` additionally binds the original interrupted write and
old-end retirement files. Neither mode is full transient-family admission.

## File lengths at their original callback

The independent application-history model supplies the expected file inventories;
the prerequisite compares these inventories with actual captured bytes. All
campaign, FLOOR and ordinary-retirement callbacks must be present exactly once
across both original process lifetimes, including the four local-generation pin
callbacks. These inventories are joined to the same node, lifetime, event index
and resource sequence through the existing physical coverage reader.

Every file path contributes its complete logical length, including identical
images stored in different locations. The combined bytes for an owner at one
callback must fit that owner's live reservation. A foreign owner, later charge,
released charge or transfer claim cannot cover the file. Full resource traces,
including transitions between captured file callbacks, remain mandatory. The
crash lifetime retains outstanding reservations; the recovered lifetime must
close normally.

The result reports individual owner/callback peaks. It does not add peaks from
different times or nodes and does not claim filesystem blocks, heap/RSS, all
internal writes or a saturated whole-runtime resource envelope.

## Explicit partial scope and negatives

Nine actual storage-owner cases are required here: GENERATION, SOURCE, JOURNAL,
MISC, generation image, FLOOR image, source image, retirement image and applied
end. Each negative renames one real required owner throughout a temporary
in-memory trace, preserving original totals and checkpoints. Physical binding
must reject it specifically as a missing original charge owner. An unrelated
error or an accepted substitution earns no negative credit.

The existing seven-family entry keeps its default ten-owner requirement,
including control replay input. The new three-family scope cannot admit that
full gate. Both missing required witnesses and an unknown scope reject.

In the default mode, the interrupted application and old-end retirement captures
are prerequisites whose callback file inventories are not charge-bound.
Remaining vote, normal completion, ledger and general replay composition still
requires separate work. `allSevenFamiliesCaptured`,
`applicationAndRetirementChargeBindingQualified`,
`wholeRuntimeResourcesQualified`, `cohortAdmitted` and `phase3Complete` remain
false.

## Five-family extension

`--include-application` derives the first-ACK and old-end inventories from their
existing independent original-history models, then checks each family's count
against the already admitted captures. The five families must be complete and
have disjoint callback identities. Their combined inventories bind the original
resource sequence at every callback, with the same original lifetime close rules.
This mode requires all ten actual storage-owner witnesses, including the typed
control replay input used while retiring the old end.

The two exact `applied-end/retirement.gsat` and
`applied-end/retirement.gsat.next` file names now map to the shared JOURNAL owner.
`MembershipAppliedEndFiles` already reserves their metadata in that journal
allowance; it keeps `application.image` under a separate APPLICATION reservation.
The correction changes the reader's file vocabulary only. A marker cannot borrow
the image reservation, a zero-byte candidate still requires its journal owner,
and unknown suffixes still reject. The complete original capture comparison
continues to validate marker bytes and the authority/deletion sequence.

The extended result sets `applicationAndRetirementChargeBindingQualified=true`
for these captured callbacks. It leaves `allSevenFamiliesCaptured`,
`wholeRuntimeResourcesQualified`, `cohortAdmitted` and `phase3Complete` false.
Ten owner categories do not establish the remaining interrupted vote, normal
completion, general replay or peer/future ledger capture families. The evidence
still measures observed file extents rather than all runtime resource peaks.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_storage_coverage \
  scripts.v53.test_native_carried_storage_coverage \
  scripts.v53.test_storage_coverage_binding scripts.v53.test_replica_storage_coverage
python3 -B -m scripts.v53.native_carried_application_storage_coverage \
  ORIGINAL_APPLICATION_MAINTENANCE_WRAPPER --qualify
# Also bind this original's first-ACK and old-end retirement captures.
python3 -B -m scripts.v53.native_carried_application_storage_coverage \
  ORIGINAL_APPLICATION_MAINTENANCE_WRAPPER --include-application --qualify
```

Short tests use synthetic traces and mocked prerequisite authority. Their
success cannot qualify an original runtime. Development replay is retained
separately with the original producer/build inventory, reader source and exact
negative results.

## Development replay

The [retained development index](phase3-evidence/carried-application-storage-development.json)
records 59.129 seconds of independent replay against the same unretried
`FINAL/SIGKILL` original. All 2,131 maintenance callbacks bind to eight original
owner lifetimes, and all nine balanced substitutions reject for the exact reason.
All 8,677 original files (67,206,586 bytes), the producer's source and compiled
classes remain unchanged. The reader uses a separately frozen `fba8c41d` baseline
plus three Python changes; no native execution was repeated.

All 50 focused Python tests pass normally and under optimized Python; these are
the same tests in two interpreter modes, not 100 distinct cases. The previous
142 capture negatives remain retained in their own index and were not rerun as
new negative evidence in this batch. Other native axes, final-source execution
and the remaining resource obligations are still pending.

The [five-family follow-up index](phase3-evidence/carried-application-end-storage-development.json)
records a separate 60.225-second portable replay of that unchanged original:
2,217 callbacks (2,131 maintenance, 32 first-ACK and 54 old-end), eight owner
lifetimes and ten exact balanced-owner rejections. The original files, producer
source and compiled classes remain unchanged. This follow-up reader records
baseline `ba62cd93` plus four Python changes; it is not final-source admission.
All 59 focused tests pass normally and under optimized Python. The original
marker vocabulary fails the four candidate/active-marker and empty/nonempty
positive combinations; the corrected mapping passes them with the shared
journal and exact file-name checks retained.

To roll back only the five-family extension, remove the explicit option and its
projection/tests and restore the two-name mapping change. The prior three-family
entry and its historical receipt remain independently retained.

Rollback removes the dedicated reader, tests and plan references together and
restores the shared owner's single full-family signature. Keep the original
capture evidence. No runtime Java, persisted format, configured limit, workflow,
cloud experiment or final-source admission changes are involved.
