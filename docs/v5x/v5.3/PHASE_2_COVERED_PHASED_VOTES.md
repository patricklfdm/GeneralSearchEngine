# Unapplied phased votes behind an authenticated published prefix

Phase 2 remains **OPEN**. Extending the admitted covered-prefix scenario to a
real forced PROOF reproduced `settlement requires bare original ACCEPT`. A
disjoint majority had actually applied and published the same entry, while the
lagging voter had not applied it. The later all-voter selected prefix was valid;
retrying could not bypass the old phase restriction.

The [bare-vote transaction](PHASE_2_COVERED_MINORITY.md) now accepts an original
PROOF or certificate only under its existing complete authority checks. The old
selector, generation, PROMISE/SELECTED and original voting record must agree;
persisted phased witnesses are checked against that original parent and identity.
The new stable-view prefix must authenticate the old parent, cover the pending
slot and bind a strictly newer installed decision. Its exact local BASIS source
must retain the entire original packet, including every original phased record
and payload. A malformed witness or missing phase refuses before cleanup.

This does not create remote observations from receipt hashes. First admission of
PROOF/certificate still requires actual owner observations. Cleanup recognizes the
original local attestation and retains it in the pinned source. It returns no old
vote response or application ACK. Original generation/source deletion still needs
the separate complete governing-floor retirement path.

The implementation keeps its refusal of replay scratch, applied-end files and
protected pending context. Configuration-changing adoption is separate. No
phase transition, frozen byte format, quorum rule, journal budget, resource limit
or public runtime change is implied. Empty-vote replacement still occurs only
after the new selector is forced and repeats the exact guard at every boundary.

The qualification producer begins with public 3/4/5-voter EMPTY/verified-backup
bootstrap. All original ACCEPTs and the majority's PROOF/certificate, typed apply,
checkpoint and publication are real owner operations. Lagging voters retain the
same actual PROOF or certificate without applying. All twelve initial profiles
then install, reclaim old authority, run a fresh campaign and publish a BARRIER;
the chosen document must appear exactly once. Five-voter profiles check both
lagging voters.

Repeated IOException cases cover twelve selector/clearing positions for each
phase. Recovery's opening force must match the bytes it still owns: PROOF or
CERTIFICATE before advanced installation, ACCEPT after exact empty replacement.
An initial test-driver attempt incorrectly targeted ACCEPT in the former case;
that failure and its exact producer source are retained, and the corrected
interruption matrix is qualified separately.

A separate refusal test replaces the pending PROOF/certificate with another
structurally valid witness set after advanced selector validation. Reopening must
reject its mismatch with the pinned original source twice, without rewriting any
byte or leaking reservations. Its first draft stopped at candidate-selector force,
which precedes active-selector rename and therefore did not exercise settlement;
that failed draft is retained. The corrected test asserts the changed selector
and published cut before changing a witness.

The process matrix uses the same admitted originals at their original paths,
halt/SIGKILL at each position, a second fresh-worker interruption and a third
completion worker: 48 cases, 144 workers and 24 separately retained lock probes.
Independent replay derives complete phased/source inventory, installed selector,
both interrupted states, force order, final retained originals and exit/lock
results. Original-first mutation checks, optimized Python and relocated replay
must agree. Exact executed counts, failures and compiled-source provenance are in
the [evidence index](phase2-evidence/covered-phased-votes.json).

The runtime expansion remains limited to unapplied original votes in a stable
view. Protected-context/staged-application covered recovery, integrated cross-view
lifetime, maximal bytes/headroom, power-loss behavior and the complete Phase 2
audit remain outstanding. Typed application semantics are checked by Java;
physical Python replay does not become an independent application implementation.
No V5.2 experiment, workflow, release or cloud operation is part of this batch.
