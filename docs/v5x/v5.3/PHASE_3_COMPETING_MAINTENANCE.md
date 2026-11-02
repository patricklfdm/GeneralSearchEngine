# Competing bootstrap maintenance before installation

Phase 3 remains **OPEN**. This continues the
[competing campaign prefix](PHASE_3_COMPETING_CAMPAIGN_PREFIX.md) using the same
immutable native original from `e1af4813`; no new workload execution or retry
is needed for this reader correction.

## Full ballot ordering

The original has two counter-2 grants on node-1. Its own earlier ballot loses to
node-3. Production `MembershipSourceRetirementFiles.Decision.bind` already
requires a strictly newer **complete ballot**, using counter, proposer and
incarnation. The shared Python `remove_retirement_evidence.source_plans` instead
required a larger counter. That unnecessarily rejected retirement of the
superseded source even though the original newer promise was durable.

The reader now uses the existing `grant_evidence.order`. This does not loosen
the other requirements: the journal must be strictly ordered, the source cannot
be current or latest, the governing copies must cover its exact original cut,
and its original packet, image, retained promise and final journal must agree.
Two encoded-record regressions fail against the original counter-only reader
and pass after the correction. Equal and decreasing ballots still fail.
Production Java, formats, time limits and retries are unchanged.

## Independent continuation

`scripts.v53.competing_campaign_maintenance` consumes the prefix's derived state:

1. Recover the original post-grant maintenance interval up to its complete
   floor release. Overlapping transactions and concurrent selections inside
   that interval require additional replay; they cannot be projected early.
2. Bind the governing peer to an original STATUS probe, then compare the
   downloaded current packet, generation manifest and promise to the already
   derived peer files. Every response must have its original send, receive and
   client delivery before floor reservation. STATUS alone grants no copy.
3. Derive the floor, retirement authority, compacted grant journal, per-file
   deletion sequence and release authority. Require every observed callback,
   including each image/member force and deletion, in the exact derived order.
4. Require the enclosing PREPARE to advertise its PROMISE only after maintenance
   completes. Consume all exchanges in this bounded interval; an unanswered
   send or reused transfer trace cannot disappear from the check.
5. Append subsequent independently checked selection decisions. Compare the
   resulting grants, allocator and entire source inventory to the unchanged
   after-close files, including absence of leftover retirement/rotation files.

The retained original derives **one** source retirement, **67** callbacks,
**10** exchanges and **two** complete transfers. The superseded selected grant
is removed, the current grant remains, and the winning SELECTED appends after
release. The continuation stops at the first `INSTALL_RESERVED`.

Fourteen original-first mutations cover missing/out-of-order floor, source,
journal and release boundaries; missing delivery; unaccounted sends; retained retired files;
missing surviving images; and a modified final journal. Each must reject for
its precise intended reason. Invalid originals and unrelated rejection errors
do not qualify a negative. The [development receipt](phase3-evidence/competing-maintenance.json)
records actual checks, original source/build bindings and implementation hashes.

```bash
python3 -B -m scripts.v53.competing_campaign_maintenance "$RAW" --qualify
```

## Remaining boundary

This is **PARTIAL**. The native producer did not capture every transient
retirement file, so callback/derived-authority and final-inventory checks do not
claim intermediate-byte capture or process-death coverage. Complete installation,
publication, all other network exchanges and export lifetimes remain to be
composed. A counter-only reader correction is not a runtime bug fix or a new
final-source execution. The six hosted subsets, 428 declared histories and five
open audit groups remain unchanged; no hosted or paid-cloud run is started.
