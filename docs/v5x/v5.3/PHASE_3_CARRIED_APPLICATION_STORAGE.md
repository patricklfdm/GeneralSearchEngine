# Phase 3 — application recovery maintenance storage ownership

Phase 3 remains **OPEN**. This entry composes the
[same-history maintenance captures](PHASE_3_CARRIED_APPLICATION_MAINTENANCE_PREFIXES.md)
with the original resource journals. It requires the complete application crash,
old-end retirement, campaign, FLOOR and ordinary-retirement capture chain before
checking resource ownership. It reuses original evidence without executing or
retrying the workload.

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

The interrupted application and old-end retirement captures are prerequisites,
but their own callback file inventories are not yet charge-bound by this entry.
Remaining vote, normal completion, ledger and general replay composition still
requires separate work. `allSevenFamiliesCaptured`,
`applicationAndRetirementChargeBindingQualified`,
`wholeRuntimeResourcesQualified`, `cohortAdmitted` and `phase3Complete` remain
false.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_storage_coverage \
  scripts.v53.test_native_carried_storage_coverage \
  scripts.v53.test_storage_coverage_binding scripts.v53.test_replica_storage_coverage
python3 -B -m scripts.v53.native_carried_application_storage_coverage \
  ORIGINAL_APPLICATION_MAINTENANCE_WRAPPER --qualify
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

Rollback removes the dedicated reader, tests and plan references together and
restores the shared owner's single full-family signature. Keep the original
capture evidence. No runtime Java, persisted format, configured limit, workflow,
cloud experiment or final-source admission changes are involved.
