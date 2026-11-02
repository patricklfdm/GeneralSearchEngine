# Competing campaign originals before maintenance and installation

Phase 3 remains **OPEN**. This follows
[original grant capture](PHASE_3_COMPETING_GRANT_CAPTURE.md) with a new native
diagnostic and independent derivation of its competing activation prefix. It
does not replace the remaining whole-history obligation with a prefix gate.

## Original execution and discovered gap

One predeclared execution of
`V53CompetingNodeQualification#threeAutomaticOwnersConvergeAndPublishOneOriginalData`
ran from an immutable copy of `e1af4813`, with the original defaults, no chosen
winner and no retries. Source, toolchain, class inventories, JUnit and raw output
are retained. Maven completed successfully in 104.791 seconds; the producer
correctly returned **PARTIAL**, awaiting independent replay.

The original contains four grants and two competing ballots. Both counters are
2, but the proposers are node-1 and node-3; comparison must use the complete
ballot, not the counter alone. Node-1 durably selected its node-1/node-2 pair,
then lost to the higher node-3 ballot. Node-3 selected node-1/node-3 and completed
the BARRIER and DATA operations. The original node-1 diagnostic records a
`HIGHER_BALLOT` loss and a second round. These observations must not be replaced
with a freshly rerun single-campaign history.

The previous single-campaign reader first refused the source-retirement/journal-
rotation vocabulary. The trace parser now recognizes those exact existing
callbacks. Recognizing a callback is not accepting its authority: the old gate
keeps its single-campaign physical/network checks, and the new prefix gate
explicitly stops before maintenance or installation.

## What is independently checked

`scripts.v53.competing_campaign_prefix` consumes the unmodified original:

- Admit the public bootstrap and original before-network files; require the
  exact initial owner-open/recovery observations.
- Pair sends, server reads, responses and client deliveries using original
  bytes and permanent identities. A rejected or undelivered request supplies
  no delivered promise. Every PREPARE and SELECTED send, including abandoned
  candidates, must bind to its original local grant or forced decision.
- Derive every allocator update in the supported prefix, then each complete
  PROMISE/BASIS, peer-ledger wrapper, source packet/image and journal append.
  Only the fresh source UUID and causally bound incoming ballot are observations;
  captured directories are comparison targets. Compare all four inventories
  byte-for-byte, including the earlier, later superseded SELECTED record.
- Recover every retained SELECTED record from the original grant journals in
  captures and the final files. Bind all three actual SELECTED write transactions
  to two immutable decisions. A decision must use original proposer-inclusive
  majority sources, their exact common cut, and no invented carried entry.
- Require the selected peer's delivered PROMISE before proposer selection, and
  the original proposer selection/send before remote selection. The mere
  presence of the final installed record cannot supply earlier authorization.
- Refuse missing writes, unaccounted promises, unobserved allocator changes or
  unrelated owner work. Later grants beyond the first maintenance/installation
  boundary require continuation replay; they are never silently ignored.

The native prefix reaches the first `FLOOR_RESERVED`. Its two allocator
reservations, four complete copied grants and three selected write transactions
pass. This does not yet derive that floor, source retirement, installed
generations, subsequent publication, transfer availability or all exports.
The ordinary same-cut, empty-tail prefix is explicit; later-state/accepted-tail
inputs fail until their continuation is implemented. All broad qualification
flags remain false.

## Negative evidence and next work

Thirteen original-first mutations reject for their exact intended reasons.
They cover selection write/force order, missing delivery, substituted PREPARE
and SELECTED references, the superseded choice's invented carried entry,
rehashed extra copied files/allocator bytes, lost reservations and unbound
promise/allocation/publication work. A development mutation initially exposed
that an unused SELECTED request escaped the checks; the reader now checks every
outgoing proposal, and regression tests cover both unused request types.

The shared 23-case grant collection qualification remains separate. Failed
originals, unrelated errors and accepted mutations cannot count as successful
rejections. The [development receipt](phase3-evidence/competing-campaign-prefix.json)
records the actual checks and their source boundaries. This batch makes no
production Java, workflow, deadline, retry or resource-limit change, and starts
no hosted or paid-cloud run.

```bash
python3 -B -m scripts.v53.competing_campaign_prefix "$RAW" --qualify
```

Next, continue from this same original into its governing-copy maintenance,
same-counter/higher-proposer source retirement, selected installations and
publication. Compose complete physical, transport/export and lifecycle replay
before adding general competing-owner final-source admission. The six existing
hosted subsets and five open groups in the
[qualification audit](PHASE_3_QUALIFICATION_AUDIT.md) remain unchanged.
