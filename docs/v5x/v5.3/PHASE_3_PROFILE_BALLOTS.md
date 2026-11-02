# Phase 3 — profile ballot and membership-fence composition

This follows [profile future and learner ledgers](PHASE_3_PROFILE_LEDGERS.md).
The full original continuation, attempted network, export, control, maintenance,
peer, future and learner chain must pass before ballot qualification begins.
The profile supplies actual old voters and the joining identity; callback labels
and producer summaries cannot supply certificate or promise authority.

## Original authority and adoption

The shared ballot reader now obtains the placement certificate from the original
CURRENT capsule and checks it against the corresponding original history item.
It no longer assumes that item occupies one fixed array slot. Reservations,
self-grants, unused reservations, every promise force and cold allocator bytes
remain part of one continuous derived chain.

Adoption uses the highest **membership** certificate ballot in the incoming
capsule, selecting the last membership item on a ballot tie, as required by
`MembershipCapsule.membershipCertificateFence`. A terminal range/barrier does
not replace that authority. In particular, the retained ordinary 3-REPLACE
history's terminal cut 11 legitimately uses membership certificate 10. The
preceding exploratory audit's suspicion about those two indexes was not a
runtime defect; this batch removes the fixed-slot assumption in the reader.

The reader binds each actual VALIDATED/FENCED/BEFORE_RETURN transaction to its
original adopted generation and owner lifetime. The prior promise comes from
original bootstrap/placement or a bound original grant/adoption force before
that transaction. A higher membership ballot requires exactly one forced
null-basis promise with the certificate's root, authority and full ballot. An
equal or stronger local promise is preserved byte for byte, including its view
and basis identity, without another append or allocator reservation. Missing,
extra, reordered or unbound force and adoption callbacks fail.

An ADD history with no original adoption is valid without fabricating one.
Conditional tests exercise stronger/equal retained promises, nonterminal
membership fences, ties, interleaved owner boundaries and actual larger-profile
owner identities. They are not larger-profile native execution evidence.

## Qualification and portability

```bash
python3 -B -m scripts.v53.joining_profile_ballot_evidence /path/to/original \
  --profile 5-REPLACE --qualify --workers 2
```

The adapter applies nineteen shared allocator/promise negatives and two adoption
negatives. Complete original validation runs first. Each disposable mutation
preserves physical files, wire bytes, directories and unrelated observations,
and must reach its exact designated ballot rejection. The mutated prerequisite
chain is not separately replayed. Invalid originals, missing expected targets,
unrelated errors and accepted mutations fail. Replay concurrency is bounded to
one through four workers; no workload or measurement is retried.

Only observed absence establishes `NOT_APPLICABLE`: no original adoption makes
its fence mutation inapplicable; no derived adoption promise append makes its
force mutation inapplicable. These are recorded separately from rejections.
The historical 3-ADD has neither transaction. Same-view validation continues
through its existing complete chain and negative driver.

The [receipt](phase3-evidence/profile-ballots.json) records measured tests,
original input inventories, frozen reader source, exact rejections and extracted
replay with assertions disabled. Original producer source and the current reader
are separate identities. Failed collection attempts remain retained.

Measured validation: all 1,893 V5.3 Python tests pass, including 21 new conditional
regressions. Ordinary 3-REPLACE rejects 21 exact negatives; historical 3-ADD
rejects nineteen and reports its two absent adoption targets as not applicable.
The same-view history rejects nineteen more. Its complete result and the
ordinary REPLACE ballot result remain identical to their preceding audits.
The old reader's ADD failure at a nonexistent adoption boundary is corrected.

The first qualification attempt exposed a negative-driver assumption: the retained ordinary
3-REPLACE history has no continuation capture at which to move an unused reservation.
The corrected mutation crosses the original owner-switch boundary instead.
Its regression fails with the original driver and passes after the correction;
both failed original attempts and the frozen readers remain retained.

All three extracted original histories replay with Python assertions disabled
and return identical results. The 30,631,031-byte archive contains
16,935 files, including the complete qualified reader, original
histories, producer manifests and diagnostic records. Original and extracted
inventories are unchanged. This reuses historical evidence without rerunning
native measurements or claiming new current-source profile execution.

## Remaining closure and rollback

This completes the profile ballot reader composition. Final-source seven-profile
native, whole-history process/fault cohorts, combined resource bounds and frozen
S/N coverage remain OPEN. Phase 3 is not complete. Long cohorts remain in the
[deferred hosted acceptance plan](PHASE_3_DEFERRED_ACCEPTANCE.md).

This batch changes Python evidence readers, tests and documentation. It does not
change Java, POMs, workflows, persisted formats, workloads or timing/resource
limits. Rollback restores the previous shared ballot reader and removes the new
profile adapter while retaining original evidence and reader manifests.
