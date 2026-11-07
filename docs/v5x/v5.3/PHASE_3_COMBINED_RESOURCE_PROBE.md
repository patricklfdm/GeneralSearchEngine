# Phase 3 — retained combined-resource pressure failure

**Native outcome: FAIL. Phase 3 and combined-resource qualification remain OPEN.**
This diagnostic does not establish that the automatic runtime permits the imposed
receiving lifetimes. No production fix or wider resource limit follows from it.

## Original experiment and failure

[`V53CombinedTransitionResourcesTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53CombinedTransitionResourcesTest.java)
starts an actual four-voter bootstrap and admits RESERVE, PREPARE, READY and SEAL.
It retains two complete original receiving copies on required voter `node-2`,
one charged as SOURCE and one as LEARNER. They share that voter's native budget,
but are deliberately held by the fixture across the following automatic rounds.
They are neither distinct voters nor a separately admitted learner operation.

The first native activation installs successfully. Before INTENT can collect its
ACCEPT quorum, node 2 fails during floor construction. Two generations and two
original source images account for four physical images; the imposed receiving
copies add two. The first forced floor copy brings the count to seven. The next
floor copy would require an eighth image, beyond the existing APPLICATION limit.

The diagnostic callback observes seven application leases and five SOURCE leases
after the first floor handoff. Byte headroom is still ample. The source reservation
for the next copy therefore fits the six-source count, while its image does not
fit the seven-image count. The server records `resource ownership/count`, then
rejects the two existing identical transport retries as `grant journal closed or
failed`. The client ultimately sees an incomplete wire frame. This is an observed
capacity failure, not evidence of an experiment timeout.

Node 1 has already forced a local ACCEPT; node 2 has not. No PROOF or publication
of INTENT is established. A locally accepted unresolved entry must not be treated
as either a committed operation or proof that nothing happened. Node 2 retains
its exact installed authority and the first complete floor copy plus proposal;
there is no completed floor authority and no permission to delete original data.

The initial attempt failed in 187.832 seconds. A fresh source execution after
adding failure/handoff observations failed in 156.348 seconds. Both originals,
commands, source/build/toolchain records and JUnit errors are retained. The
second execution adds diagnosis; neither fills a successful cohort slot. The
planned 5-REMOVE case was not reached. No history is retried to manufacture a pass.

## Independent diagnosis

[`combined_resource_probe.py`](../../../scripts/v53/combined_resource_probe.py)
reconstructs the actual bootstrap, all four admitted prelude slots and the first
native installation. It derives the floor proposal and every offered generation
from those originals, checks the exact first forced copy and unchanged authority,
and binds captured resource counts to the original writer-event indices. The
receiving copies must remain exact original bytes, with the exact initial charge
increment. The partial floor cannot be relabeled as complete authority.

Its result is `DIAGNOSED` with `nativeOutcome=FAIL`, zero completed profiles and
`automaticRuntimeReachabilityQualified=false`. Fourteen copied-evidence negatives
check false success, changed authority/floor/source bytes, missing observations,
lost receiving files, changed accounting, the original unresolved ACCEPT and
unrelated failure causes. Diagnosis
is not positive completion qualification. Original inventories are preserved.

The initial positive-completion reader prototype was not admitted or added to CI:
there is no successful original for that proposed scope. It remains in the local
diagnostic workspace for review. The native probe is explicitly opt-in, using
`-Dv53.combined.transition.probe=true`; no existing test or Required job changed.
Its current explicit invocation is expected to fail as described above.

## Lifecycle question that must be resolved

The [nine receiving-boundary histories](PHASE_3_COMBINED_RECEIVE_RESOURCES.md)
qualify accounting/refusal and allocator work, not the ability to complete FINAL
while arbitrary callers keep extra copies live. The new probe likewise does not
prove a production liveness bug. Its external SOURCE and LEARNER receivers are
not owned by the native activation, maintenance or learner controllers.

The next acceptance work must establish actual permitted ownership overlap:

The [activation receive lifetime regressions](PHASE_3_ACTIVATION_RECEIVE_LIFETIME.md)
now directly exercise successful drain and fail-closed cleanup on the original
activating pool, plus the three handoffs of one native REMOVE completion. They
resolve that scoped controller-boundary question; they do not establish maximum
byte pressure, every concurrent endpoint lifetime or required-four completion.

1. Follow the native controllers' receiving lifetimes. The activation driver's
   round closes its selected receiving tasks after installation. Generation
   maintenance borrows matching images, then drains a received copy only after
   its replacement floor copy and parents are forced. A joining learner's actual
   custody/handoff must be observed on its real owner; the diagnostic's old-voter
   LEARNER allocation is not a substitute.
2. Exercise the largest **required** old/joint/new floor quorum using original
   available voters, including a joint configuration requiring four distinct
   voters in 5-REPLACE when only two common voters plus the departing and joining
   voters remain available. Verify the needed counts
   through native FINAL and the new-stable barrier. A nominal three-voter happy
   path cannot establish every joint availability shape.
3. If a permitted overlap can consume completion capacity, correct admission or
   the actual ownership/drain sequence and add a deterministic regression. Do not
   raise seven to eight, release a charge before deleting its physical copy,
   treat duplicate images as independent votes, or suppress the original failure.
4. Qualify recovery from an original partial floor and unresolved ACCEPT under
   the original ownership rules. The present diagnostic stops at failure; it
   does not establish cold recovery, FINAL completion or the metadata maximum. A subsequent
   [cold majority continuation](PHASE_3_COLD_RESOURCE_CONTINUATION.md) observes
   FINAL and BARRIER through other voters while the partial-floor owner remains
   fenced; it does not qualify recovery of that owner.

The 324 MiB expression remains a conservative metadata reservation envelope,
not proof that all category maxima may coexist in every role or that one short
history exercised them. Physical maxima, admitted completion and interrupted
rotation remain separate required work. The eleven optional hosted subsets and
their 512 planned histories are unchanged; this probe adds no accepted subset.

## Reproduction and receipt

Use a fresh isolated source/build and retain failure output:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.combined.transition.probe=true \
  -Dtest=V53CombinedTransitionResourcesTest test
python3 -B -m scripts.v53.combined_resource_probe "$FAILED_ORIGINAL" --qualify
```

The [development receipt](phase3-evidence/combined-resource-probe.json) identifies
the original failed executions and completed diagnosis checks. Removing this
optional probe/reader is a test-only rollback; retained failures must survive.
