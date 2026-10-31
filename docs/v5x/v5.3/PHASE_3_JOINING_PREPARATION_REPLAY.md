# Original joint preparation and continuation replay

`scripts.v53.joining_preparation_evidence` requires the new
[writer-held grant captures](PHASE_3_JOINING_GRANT_CAPTURE.md). The historical
[conditional continuation](PHASE_3_JOINING_CONTINUATION_REPLAY.md) remains a
separate reader for its unchanged archive. This reader never fills that archive's
missing middle with observations from another execution.

## Derivation boundaries

The reader starts from the original bootstrap and composes the old voters'
installations/publications, joining placement, predecessor retirement and native
initialization. The shared derivation hooks expose the **calculated** prepared
directories before selection. They do not make copied files the expected state.
Every captured grant must be consumed exactly once, including early old-voter
campaigns, the joining voter's own grant and both final activations.

At the intermediate preparation boundary it derives the next original ballot
from the allocator and promises. Only the fresh source UUID is observed. The
PROMISE, frozen peer/learner wrappers, packet, BASIS, images and complete journal
are calculated from the preceding derived state and compared against both old
voters' complete captures. The returned BASIS digest and original proposer
PROMISE transfer must refer to those calculated records.

Serving that preparation retires superseded sources under the governing-copy
coverage rules. The newest unselected preparation stays pinned. A separate fresh
activation then captures its source before it may retire the intermediate one.
The following selected installations, FINAL, BARRIER, complete owner inventories,
joining directory families and retaining cold reopen are derived on the same
history. There is no skipped ballot or conditional intermediate projection.

The event check also compares local retirement callback groups with the exact
source files removed between derived captures and the final owner state. It
requires decision force, journal replacement force/rename/parent force and
pruning before file deletion, directory deletion and completion. These generic
callback names do not carry the source ID: the reader checks local order and
file counts, not a separately retained identity-bound retirement decision or
complete cross-node force/network causality.

The later [source-retirement capture](PHASE_3_SOURCE_RETIREMENT_CAPTURE.md) adds
those transient observations for future executions. This archived execution
remains unchanged; its local order/count check is not upgraded by that addition.

`GRANT_CAPTURED` is an observation marker, not a protocol force event. The older
initialization-order reader now ignores only that marker while preserving exact
checks for all original force callbacks. Capture completeness and byte binding
are mandatory separate checks in this new reader.

## Evidence scope

One fresh complete `c8f5d616` execution passed without retries. Collection v2
retains 21,339 events, 2,209 wire pairs and all 19 complete grant captures. The
independent positive replay compares those 19 derived grants, 72 preceding owner
snapshots and 28 continuation owner snapshots through final cut 11, plus both
joining cold snapshots and 16 local source-retirement callback groups. The
intermediate preparation and subsequent fresh activation now derive from the
same original history without the old conditional projection.

The [batch receipt](phase3-evidence/joining-preparation-replay.json) records the
fresh producer source/build/history, original collection, reader source, negative
qualification and portable replay. The producer runs once in an isolated source
copy using the original whole-history entry point. Reader development and
negative replay use its retained bytes; they do not rerun or splice workloads.

Negative cases first pass capture collection and the preceding initialization
reader. They preserve valid checksums where needed and then reject at the exact
new derivation/order boundary: extra allocations/files, a prematurely removed
source, a substituted frozen ledger, a restored obsolete source, duplicated
capture, missing force or extra deletion. Downstream image, standalone journal
and cold-ledger checks remain mandatory too. Invalid originals and unrelated
rejections cannot count as successful qualification.

All 12 original-first negative cases passed with the declared rejection reasons;
167 joining Python tests passed, including nine new boundary/driver tests. The
unchanged historical conditional archive still passes its separate reader. The
batch changes Python evidence readers and documentation; the producer's 705
production/build/workflow/frozen inputs remain unchanged.

```bash
python3 -B -m scripts.v53.joining_preparation_evidence <new-original-raw> --qualify
```

Successful replay qualifies original intermediate preparation and unconditional
continuation for this one `3-ADD` history. `completePhysicalQualified`,
`forceAndNetworkQualified`, `processDeathQualified` and `phase3Complete` remain
false. Identity-bound transient retirement decisions, complete transport/force
composition, actual process-death boundaries, all seven profiles and the frozen
requirement mappings remain explicit closure work. Independent histories can
later run on hosted measurement jobs; each history's steps remain indivisible.
