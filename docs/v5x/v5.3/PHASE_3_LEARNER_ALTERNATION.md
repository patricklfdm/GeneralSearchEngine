# Phase 3 — alternate the two fixed learner slots

After B → A selection and B reclamation, the same owner can now install B again
and continue alternating A/B. It retains one selected image and either one pending
or one retiring image. The two source paths, two typed paths, slots lock and
immutable legacy seed metadata remain fixed. Completed old plans are replaced;
they do not accumulate per revision.

The [A28 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a28--bounded-alternating-learner-plans)
binds each new plan to the exact current head, completed original vacancy and
covered old metadata identities. A complete new candidate is forced before its
inode replaces the old plan. The covered old installed marker is removed and its
parent forced before the original source moves. Recovery distinguishes each of
these states without retransferring or automatically selecting a pending image.

Selection and retirement retain the existing ordering: actual typed owners,
forced original head, old-view revocation, covered deletion, parent forces,
forced new vacancy, then old resource release. Copying a plan/marker, changing its
replacement binding or removing old metadata too early cannot authorize recovery.
Sequence exhaustion is an explicit refusal, never a wrap to an earlier slot.

## Validation boundary

`V53LearnerAlternationTest` defines continuous fixed-path B1 → A2 → B3 → A4
component histories, cold semantic reopen, exact resource counts and unchanged
immutable seed metadata. It also defines replacement-plan and deleted-marker
recovery, original new-vacancy candidate/rename cuts across opposite slots, and
unchanged-original negatives. These use conditional voting fixtures, actual
original transfers and core decoding. Exception cuts are not halt/SIGKILL tests.

Complete autonomous native histories, all five joining profiles, maximum combined
resource bounds, cancellation and matching local INTENT remain OPEN. The
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md) still requires full
original physical/wire replay on one final source and build. Phase 3 is not closed.

[Component receipt](phase3-evidence/learner-alternation.json) binds eight passing
unique methods to identical production sources and compiled production files:
the four alternation/sequence methods, three existing rotation methods and the
existing TCP reuse regression. The continuous cycle and overflow boundary ran
separately from the recovery/regression selection. All successful executions
have zero failures, errors or skips. This is not a full reactor qualification.

The retained earlier attempt failed during test compilation because a new
negative fixture inferred `ArrayList<?>`; the corrected fixture uses
`ArrayList<Object>`. It executed no tests and is excluded from qualification.
No production source changed between these attempts. The archive includes each
snapshot's inputs, source, compiler identity, reports and logs; temporary JUnit
fixture trees are not claimed as retained native physical-history evidence.
