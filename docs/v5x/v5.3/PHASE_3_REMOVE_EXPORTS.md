# Phase 3 — REMOVE export authority and complete-copy floors

This extends [REMOVE network replay](PHASE_3_REMOVE_NETWORK.md) on the same two
original `4-REMOVE` and `5-REMOVE` histories. No Java workload is repeated, no
snapshots are stitched, and no production Java, workflow, limit or retry policy
changes. The separately frozen reader requires the complete original physical
and attempted-network precondition before interpreting any export.

## Authority derived from original bytes and times

`remove_export_evidence` derives current-generation intervals from the original
before-network state, selected installations and publications. A generation is
available only after its return boundary and before the next selector rename;
the rename-to-return interval supplies no completed generation authority.
Unselected voters retain their actual original generation.

Original journals and source packets provide each frozen PROMISE/BASIS pair.
New source lifetimes begin at their matching observed grant return. An exact
installed-to-applied inventory difference identifies the source retired in that
round; its retirement event ends the capability. Repeated event names do not
identify a source by themselves. Every grant and source-retirement interval must
be accounted for, and a later snapshot cannot authorize an earlier export.

The shared export reader then checks exact content, reference aliases, permanent
identities, views/ballots and complete session intervals for current generations,
frozen sources, journal records, pending entries/payloads, native vote receipts
and applied/published checkpoints. REMOVE has no learner or pending joining ACK.
Every committed transfer in these histories belongs to a checked family.

Maintenance composes the same actual transfers with STATUS discovery, original
borrowed image bytes, complete manifests/members, floor reservation and all
copy/write/force/handoff/release events. Both old and new majorities remain
required. Network floor/copy/discovery counts are derived from the original
selected sets for the three campaigns, including maintenance before later
grants; an empty trace cannot pass vacuously. No direct fixture copy is accepted
as a network-acquired floor. The original pre-grant and pre-slot placement checks
also run on the observations under review.

## Recorded qualification

The [batch receipt](phase3-evidence/remove-exports.json) retains the original
producer/source/build identities, raw inventories, independent reader source,
logs, archive manifest and relocated results.

| Profile | Bound sessions / committed transfers | Generation / frozen-source intervals | Network floors | Complete copies / remote acquisitions |
| --- | --- | --- | --- | --- |
| `4-REMOVE` | 145 / 269 | 20 / 12 | 13 | 35 / 22 |
| `5-REMOVE` | 190 / 358 | 23 / 14 | 15 | 45 / 30 |

Each original passes 22 export/maintenance negatives. Every mutation first passes
the full transport and durable-reply reader and preserves every non-observation
file and directory; an unrelated network error cannot count as an authority
rejection. Cases include changed content/aliases, export after the exact source
retirement, vote receipt before force, delayed discovery/copy delivery, omitted
copy force/handoff/release and omission of every floor event.

The mutation driver now targets the precise repeated retirement occurrence and
always changes the selected owner/voter value. The initial accepted mutation
diagnostic is retained: it had moved the transfer past an earlier equal-looking
event, while the intended source was still live. This was a test-injection defect,
not a native runtime failure. The corrected mutation rejects at the intended
capability check.

The relevant 683-test Python suite passes. Historical ADD export replay produces
exactly its previously recorded result with the default three-owner adapter;
that is compatibility evidence, not a new-source ADD execution. Sealed originals
replayed after relocation with Python assertions disabled produce identical
positive and negative results.

```bash
python3 -B -m scripts.v53.remove_export_evidence RAW_DIRECTORY --profile 4-REMOVE --qualify
python3 -B -m scripts.v53.remove_export_evidence RAW_DIRECTORY --profile 5-REMOVE --qualify
```

## Remaining Phase 3 scope

The receipt stays **PARTIAL**. Continuous peer/future-retention revision and
recovery composition, complete retirement transaction callbacks, process-fault
histories, the current-source seven-profile matrix, automatic election scheduling
and the frozen acceptance mapping remain required. These observed export and
floor lifetimes do not close Phase 3 or enable a public membership API.
