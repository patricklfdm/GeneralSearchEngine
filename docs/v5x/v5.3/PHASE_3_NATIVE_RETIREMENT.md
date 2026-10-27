# Phase 3 — native retirement of old application staging

This prerequisite removes caller historical voting observations from cleanup of
an already owned applied certificate. It does not transfer future dispatch proof,
replace the original pending vote, or enable automatic membership service.

## Authority and lifetime

The native `retireSupersededApplication(configuration, storage)` overload requires
the real native journal owner, the old original generation and certificate, and
the newer installed selection carrying the exact entry at the identical parent.
The native `retireCoveredApplication` overload additionally requires the actual
selected sources and authenticated covering prefix. Existing observation-taking
overloads retain their previous checks.

A private-constructor `CertifiedRetirement` capability binds the old original
packet, complete pending certificate and retained generation to this live owner.
The guard checks the unchanged current selector, PROMISE, BASIS, SELECTED and
pending bytes. The capability checks the actual original vote and generation
before and after delegated replay. The certificate and its parent directory are
re-forced before `NATIVE_RETIREMENT_CERTIFICATE_RETAINED`.

Typed replay reconstructs the old end solely to validate deletion of derived
staging. The existing retirement marker binds the original plan, exact file
inventory, both generations and retained original sources; its authority is
forced before deletion. An interrupted cleanup reopens from the same originals.
The original pending vote, certificate, sources and selector survive unchanged.
No application ACK or new remote vote observation is returned by cleanup.

A later observed ballot still fences application/voting. It does not revoke the
same exact derived-file cleanup authority, so a fenced owner can finish removing
its own superseded work. Reacceptance under the actual newer selection transfers
the original entry; a real governing floor then permits reclaiming the old
publication slot before the new certificate can publish. Cleanup alone cannot
skip either step.

No disk/wire format, resource bound, public API, workflow or V5.2 Runner changes.
The current future-retention verifier continues to pin an unresolved local target
to its original applied end. This batch does not remove that check or the
pre-SELECTED guard for unresolved imported future proofs.

## Qualification scope

The [source-bound receipt](phase3-evidence/native-retirement.json) retains the
exact build snapshots, failed attempts, original files and reports under
`target/v53-native-retirement/`.
The independent `scripts.v53.native_retirement_evidence` reader derives real
stable-three EMPTY bootstrap, initial activation, ACCEPT/PROOF/certificate, all
three applied ends, and the higher-ballot carried selection before checking any
interruption. It derives retirement marker bytes and every interrupted/recovered
file map, checks reseal/delete ordering and unchanged certificate/published cut,
and rejects old application ACKs. Negative qualification first validates the
unmodified evidence. A final snapshot or producer PASS is not an authority input.

Covered-prefix cleanup, observation fencing and subsequent new-ballot publication
are separate Java checks; they are not relabelled as the process reader's coverage.
The final native suite passes four tests, including twelve halt/SIGKILL cases,
24 fresh JVMs and six live lock probes. Normal, optimized and relocated independent
replay agree and reject twelve exact evidence mutations. Process crashes are not
power-loss evidence.

Fourteen existing tests pass in the preceding isolated snapshot with identical
production Java: three native-application, six staged-application and five covered
staging tests. The only differing Java source is the new continuation test. Its
initial inspector incorrectly requested floor authority while the carried vote
was still untransferred; its next version omitted real floor-based reclamation
before publication. Both failures remain retained. The corrected test reads the
selector/generation for diagnostics, then establishes an actual governing floor
after reacceptance before reclaiming the old publication slot. No storage guard
was relaxed to make the test pass.

All 661 V5.3 Python tests pass normally and under `-O`. Existing staged-handoff
replay retains its conditional historical bootstrap boundary and passes fifteen
negative checks. Existing covered-staging replay passes all six actual profiles,
36 in-process interruptions and seventeen exact negative checks. Those are
separate regression results, not additional new native process cases.

## Remaining Phase 3 work

Selected installation must retain every selected source's unresolved target proof
and durably take over its lifetime before old local staging can be discarded.
Carried application/publication must reconcile that proof without recursively
embedding prior election histories or creating fresh ACKs from stored hashes.
Actual quorum-gated dispatch, offline-survivor maintenance, learner/joint
completion and all remaining [3B–3E requirements](PHASE_3_ENTRY_PLAN.md) remain open.
