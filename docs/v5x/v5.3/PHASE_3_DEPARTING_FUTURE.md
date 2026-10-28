# Phase 3 nonvoting future proof

Status: locally qualified representation and applied-end binding. Full Phase 3
remains OPEN. This extends [A09](PHASE_3_CONTRACT_AMENDMENTS.md#a09--nonvoting-completion-of-an-original-final)
with [A10](PHASE_3_CONTRACT_AMENDMENTS.md#a10--exact-nonvoting-future-proof).

The old GSFT reader required every pending target to carry a CHECKPOINT_ACK.
That cannot represent an original joint voter completing FINAL after its removal:
the node must retain its exact application result but has no successor vote.
The new nine-record form carries the original selector, promise, selected,
entry, accept, proof, certificate, catalog and statement. It preserves the same
owner and phased authority; it neither weakens successor ACK requirements nor
turns a received hash into an actual observation.

The decoded completion kind must match the owner's successor eligibility.
Nonvoters additionally satisfy the exact old-only FINAL and permanent-identity
checks. Native end reopening requires matching files and image, excludes every
ACK, and retains the canonical original plan. Flat inherited proof references
preserve original bytes and identity through a different capturing owner.

The isolated Java qualification includes five new tests across 4/5 REMOVE and
3/4/5 REPLACE, the existing departing-end tests, and the unchanged stable future
retention, frozen-source and selected-future proof regressions. Raw byte evidence
for the five new profiles is independently replayed, including altered proof,
inherited owner, image, extra ACK, omitted proof and changed parent negatives.
The receipt records exact test counts, source hashes, failures and portable replay:
[departing-future.json](phase3-evidence/departing-future.json).

Original consensus observations in the five new profiles are conditional test
fixtures. End-file force/reopen and inherited encoding are actual production
operations; distributed FINAL publication, native application ACK, departing
proposer/follower recovery and service fencing are not established by this batch.
Their integration remains next. No wire catalog, resource bound, public API,
workflow, protected CI, cloud experiment or V5.2 source is changed here.
