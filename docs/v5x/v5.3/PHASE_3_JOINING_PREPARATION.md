# Old-majority preparation before joining initialization

Phase 3 remains **OPEN**. `MembershipJoiningRetentionCampaign` adds the bounded
old-side preparation step that previously required direct calls to each old
journal. It reuses the existing activation PREPARE format and receiver, but
never passes replies to source selection. Ordinary activation can select as soon
as both majorities are present; initialization preparation must not accidentally
install a joint round or claim READY.

The native wrapper binds the actual old proposer, current JOINT cut, exact new
identity, resource pool, observed fence and original deadline. It uses existing
pre-grant maintenance before allocating one fresh ballot, registers the actual
local grant on its endpoint, then contacts old voters in canonical order until
an old majority has replied. The receiving endpoint still fetches the proposer's
original PROMISE, forces its own original source and completes required source
maintenance before replying. No new wire record, resource cap or longer deadline
is introduced.

The reusable old-side exchange operates on that live grant and returns only a
routing hint: root, exact cut, joining identity, ballot and each responding old
voter's BASIS digest. It does not import remote bytes into SELECTED, count the
joining identity, install a generation, create ledger authority or advance the
application. The proposer is part of the old majority. A lost reply permits at
most three identical requests (or the caller's smaller bound). Only exhausted
transport IO/deadline failures may try another old voter on the same ballot.
Explicit rejection, changed correlation, capacity and closed ownership stop.
A correlated higher promise fences the proposer. Deadline expiry, cancellation
and close cannot renew the invocation; failed close/drain retains ownership.

The new owner may supply this hint to its existing retention acquisition. It
then reads only those old identities, requires the exact advertised BASIS bytes
and ballot, and still independently verifies every original fragment and the
complete conservative ledger union. The hint is immutable data, never an
initialization capability. A stale/missing/changed member cannot silently be
replaced by a different source. The existing live original-owner initializer and
durable three-ledger transaction remain mandatory.

The whole native joining test now calls the old-side preparation step over TCP
and uses its hint for the joining acquisition under one shared preparation/read
deadline. Direct old-journal reads remain an expected-byte oracle, rather than
the inputs which initialize the new owner. Before this step, the actually
installed joining directory serves only STATUS and bounded prefix/generation
reads; it refuses voting requests. This permits old-voter governing-floor
maintenance to obtain its complete copy before the new ledgers exist. Those
temporary serving resources close before the joined journal closes. FINAL,
stable reactivation, fresh BARRIER and original cold reopen stay in that same
indivisible history.

Local final-source validation passed **38 tests in 54.178 seconds**, with no
failures or skips. Eight new tests exercise the real old-side exchange over
conditional joint fixtures: all five add/replace profiles, lost replies,
unavailable peers, stricter retry bounds, explicit/higher rejections, changed
correlation, original deadline, cancellation, unchanged selection and hint
binding. They also verify that the native prelude refuses conditional history
before allocating another ballot. Five fragment-network tests, twelve seed
tests, two initialization-file tests and eleven existing activation tests pass.

These are component tests. The native wrapper's complete maintenance and
new-owner history is compiled but **not executed in this increment**. Its exact
entry remains
`V53JoiningIntentExportTest#actualJoiningVoterAcquiresRetentionOverTcpThenCompletesFinalAndBarrier`
in the [hosted acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Complete physical
replay, process-death recovery, alternative old proposers, maximum resource
combinations and final-source all-profile histories remain required. Autonomous
runtime scheduling and inter-owner handoff of preparation hints are still pending;
this class is an explicit internal coordinator step, not the complete coordinator.

Source snapshots, both local executions and the portable archive are indexed in
`phase3-evidence/joining-preparation.json`. No full reactor suite, hosted dispatch,
paid cloud run, workflow or V5.2 experiment was changed or executed.
