# Mixed ACCEPT context recovery across process death

Phase 2 remains **OPEN**. This extends the [mixed retained ACCEPT correction](PHASE_2_CONTEXT_MIXED_ACCEPTANCE.md)
with halt and externally delivered SIGKILL. The preceding actual three-owner chain
retains original ACCEPT ballots 20/21/21, selects tail 21, and installs ballots
22, 23 and 24. The original ENTRY remains at origin 20.

The successor-acceptance cases start from node 1 at installed ballot 24 with its
original certified ACCEPT 20 and governing floor 21. Twenty-seven positions cover
ACCEPT candidate/active persistence, context withdrawal and floor reclamation,
including death after a second floor-file deletion. A second fresh owner halts at
`ACCEPT_ACTIVE_FORCED`; a third completes the exact successor and its duplicate.
Only explicit calls after open may return the ballot-24 ACCEPT identity.

The source-retirement cases start from node 2 after installed ballot 22 and old
generation retirement, before reclaiming its ballot-21 source. Its original vote
is ACCEPT 21, while the obsolete source's original BASIS retains ACCEPT 20. The
higher selected tail and exact retained original bytes authorize this cleanup.
Fifteen positions include journal replacement and a second source-file deletion.
The second process halts while forcing the context's separate backing source.
The third finishes the saved exact deletion and preserves the original vote/context.

Together the two modes execute 84 cases, 252 fresh workload JVMs and 42 separate
live owner-lock probes. The producer checks exact final inventories against the
uninterrupted original chain, existing resource bounds at every callback and zero
leases after close. Small images exercise image-count reservations; this is not
maximal byte-capacity qualification.

Independent Python replay first validates that original chain. It derives both
interrupted physical states, final state, complete force/death/return order,
original ENTRY and ACCEPT identities, process counts and scope. Twenty-two
mutations must fail for their intended reason, including altered old authority,
lost sources, retained context/floor, premature or wrong responses, invalid death
markers and capacity claims. Normal Python, optimized Python and relocated replay
must agree. The [evidence index](phase2-evidence/context-mixed-process.json) binds
the tested sources, producer classes, runtime classes, JARs, logs and raw inventories.

This batch changes test producers, independent validation and documentation only.
The 706 production class files equal the preceding finalized corrected artifact.
Public membership runtime remains disabled. Local process death does not establish
power-loss behavior, network liveness, admitted-bootstrap lifetime or coordinated
old/joint/new profiles. Distinct minority ENTRY adoption and maximal storage remain
separate requirements in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
