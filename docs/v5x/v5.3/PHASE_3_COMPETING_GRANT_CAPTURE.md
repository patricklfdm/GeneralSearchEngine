# Original grants from competing owners

The [existing competition reader](PHASE_3_COMPETING_REPLAY.md) qualifies one
successful campaign and two published slots. Arbitrary competing campaigns can
leave grants whose original source files retire before the final snapshot. A
wire digest or the eventual winner cannot recover those bytes. Repeating the
test until a simpler history appears would not qualify the missing histories.

## Collection and ordering

`V53CompetingNodeQualification` now uses the existing test-only `V53GrantCapture`
at every `GRANT_BEFORE_RETURN` callback, including grants from a losing or later
superseded proposer. It copies the original replica under that journal's writer
lock, compares inventories before/after copying, and preserves source packets,
images, original grant journal, generations and retention files. The existing
64-copy, 512-member, 64-MiB-file and 256-MiB-total collection bounds remain.

`V53CompetingGrantCapture` keeps the original monotonic owner/transport trace
unchanged. A separate `grant-capture-events.json` binds each completed copy to
its exact grant-return event, the last trace event observed after copying, and
the original monotonic timestamp. Other owners can continue recording events
during disk I/O. No same-owner write may occur between its grant return hook and
copy completion. Failed copies have no completion marker; failure traces and
partial directories remain, and duplicate output paths are refused.

`scripts.v53.competing_grant_captures` admits the original bootstrap and exact
before-network files, verifies every copy against the admitted permanent owner,
and checks complete PROMISE/source/BASIS write ordering. It uses the existing
joining collection and grant-order readers. Stable competing owners explicitly
require the learner ledger and its frozen wrapper to be absent; joining readers
still require both. Missing learner evidence never triggers a permissive fallback.

Each original grant callback must have exactly one bound copy. Duplicate,
missing, foreign, out-of-order or out-of-interval links fail. Captured inventories,
source images, frozen peer ledger and canonical metadata must match. Unaccounted
source-write callbacks fail even if the producer claims success.

The existing single-campaign reader accepts either its historical layout or the
complete new attachment pair. New attachments receive this additional check;
unsupported campaigns still fail the existing physical/network gate. No older
receipt is upgraded to a new-source execution.

## Validation and scope

The focused Java test opens an admitted real writer, grants two ballots from
different proposer identities, verifies the first copy stays unchanged, and
probes the live original lock from a separate JVM after each capture. Together
with the existing capture tests, four Java tests pass. These are writer tests,
not an autonomous election schedule. The first test compilation exposed a
test-only parser helper typo; its failed log is retained alongside the corrected
successful build.

The independent collection gate accepts those two originals as **PARTIAL**,
including after copying to another directory, and rejects all **23** declared
mutations: twelve copied-byte cases and eleven timeline/force cases. Two further
real-byte checks reject using either ledger profile for the other fixture.
Original failure is checked before any mutation; unrelated errors and accepted
mutations cannot count as successful rejections. Validation details are retained
in the [development receipt](phase3-evidence/competing-grant-collection.json).
All 2,217 V5.3 Python tests and 57 focused tests under optimized Python pass.
The retained historical single-campaign original also passes its unchanged
physical/network scope with the extended reader; it is not current-source evidence.

For a new competing run, inspect its original captures with:

```bash
python3 -B -m scripts.v53.competing_grant_captures "$RAW" --qualify
```

This remains a collection prerequisite. It does not derive the intervening
grant retirement, arbitrary selected/install histories, every network response,
publication, process death or a failover SLA. The complete automatic competition
has not been rerun for this batch. There is no new hosted cohort, dispatch,
runtime Java change, workflow change, protocol retry or deadline adjustment.

Next, use these originals to derive all observed competing campaigns, including
losers and later selections, then bind the complete producer/reader to the
final-source cohort. The [qualification audit](PHASE_3_QUALIFICATION_AUDIT.md)
continues to track the same six hosted subsets and five OPEN work groups.
Phase 3 remains **OPEN**.
