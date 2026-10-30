# Owned joining initialization and cancellation

Phase 3 remains **OPEN**. `MembershipJoiningEndpoint.initialize(hint)` now owns
the exact-source acquisition, durable three-ledger initialization and voting
handoff as one explicit internal operation. A caller no longer has to separately
close an acquisition while switching the endpoint. It must still obtain the old
majority's preparation hint; automatic inter-owner scheduling is not implemented
by this method.

The hint remains routing data. Fresh endpoint construction still requires the
actual unused joined owner. Acquisition independently checks the hinted root,
JOINT cut, new identity, old-majority identities, ballot and exact BASIS digests.
It uses the endpoint's original start/deadline and existing bounded transport
retry policy. Only the original acquisition capability can enter durable
initialization. No decoded hint or lifecycle action can stand in for that owner.
The seed stays inside the acquisition's charged lifetime; the managed entry does
not return an extra seed buffer after its reservations have been released.

Initialization is single-use. A concurrent duplicate is rejected before creating
an acquisition and does not cancel the first caller. Voting promotion is private
to the managed flow. After force completion, the original initialization deadline
is checked again before handoff. If cancellation or expiry occurs after a durable
completion, the endpoint remains closed; the original retaining cold entry can
later validate and resume that completion. This does not undo or repeat a
completed force transaction and does not grant public READY.

`MembershipInitializationTask` manages only cancellation and task lifetime; it
has no ledger or voting authority. Close first revokes new endpoint requests and
closes the acquisition, cancelling pending transport reads. An already admitted
force transaction retains its original resources until it exits and is never
interrupted by this close path. The owning close waits for task completion before
releasing endpoint ownership. A bounded drain/cleanup failure retains references
and the endpoint's existing CONTROL reservation for a later explicit close.
No timeout manufactures successful initialization. Exceptions retain the original
failure and attach cleanup failures instead of replacing the primary cause.

The complete native TCP history now calls this managed entry, compares the actual
initialized ledger states with independently captured old-source expectations,
and then continues through retaining cold resume, actual new-voter FINAL and a
fresh BARRIER. This final-source history is **compiled, not executed here**.
It remains indivisible and is queued for hosted acceptance.

Local task tests deliberately use fake non-authoritative actions to exercise
pending-read cancellation, admitted-force draining without interruption,
drain timeout and cleanup retry, close during factory creation, duplicate calls,
and preservation of primary/cleanup failures. The existing read, handoff,
acquisition, old-majority and encoding tests retain their stated component scope.
The initial focused run passed **31 tests in 82.128 seconds**. After restricting
promotion to the managed entry and removing the returned seed buffer, the
final-source run passed **21 directly affected tests in 19.309 seconds**, with no
failures or skips. All main/test sources, including the deferred native history,
compiled. Documentation contract and its regression test also passed.
Results and both immutable source snapshots are indexed in
`phase3-evidence/joining-initialization.json`.

The [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md) still requires actual native
close-versus-force histories, process death, physical replay, all profiles,
maximum combined resource use and autonomous coordinator integration. No public
format, frozen bound, workflow, POM or V5.2 cloud execution changed.
