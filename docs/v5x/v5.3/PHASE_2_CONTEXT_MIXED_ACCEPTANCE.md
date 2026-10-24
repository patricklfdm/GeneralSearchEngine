# Same ENTRY under different retained ACCEPT ballots

Phase 2 remains **OPEN**. This extends
[repeated context installation](PHASE_2_CONTEXT_INSTALLATION_LIFETIME.md) to
actual owners holding ACCEPT ballots 20, 21 and 21 for the same original ENTRY.

## Problem and authority

Selecting the higher ballot is valid, but its ACCEPT digest differs from the
older owner's original vote. Exact digest equality at installation, obsolete
source retirement and floor release rejected this continuation. The retained
red execution stops at `context installation changed original tail`; subsequent
executions expose the separate floor-release and saved-source-decision checks.
These failures and their compiled inputs remain in the local evidence directory.

The correction applies only to an already verified retained context, or to a
verified current successor vote during floor release. Root, authority, ENTRY,
index and original payload are unchanged. The selected ACCEPT cannot regress
its ballot. Every original ACCEPT, ENTRY and payload byte must still occur in
the forced current generation; a matching logical result alone is insufficient.
Existing callers without a retained context keep their strict ownership checks.

Protected PREPARE captures the higher of the current selected tail and the
original pending vote, as ordinary capture already does. Rebinding the context
preserves the exact older vote and original generation metadata. Generation and
source deletion still require the governing floor, parent ancestry, exact local
ownership, selector, complete original inventory and a forced retirement decision.
Current-generation, floor and latest-backing references remain pinned.

Completion first forces the exact successor ACCEPT. Only then may it withdraw
the old context and release the floor. Read-only completion admission may inspect
the proposed vote; deletion uses the forced current vote verified by its owner.
After a partial cleanup, the retained original decision supplies the exact
remaining inventory. No format, timing or resource limit changes are involved.

## Local validation

The [evidence index](phase2-evidence/context-mixed-acceptance.json) records the
actual tested inputs, compiled classes and JARs, failures, producer snapshots,
independent replay and negative results.

The compiled-input audit found that the unchanged core sources were recompiled
with different class output than the previous retained artifact. A separate
`javac --release 21 -g -parameters` compilation reproduces all directly compiled
core class bytes; Maven also emits empty package-info metadata. Both artifact
sets remain retained. The 61 existing storage regressions are repeated against
the rebuilt core; the index records class changes separately from source changes.

Three local owners start from the independently replayed context-publication
chain. Two force ACCEPT 21; the third retains its certified ACCEPT 20. They
select and install 22, then capture/install 23 and 24 while retaining their own
original votes. Nodes 2/3 establish floor 22; node 1 retains floor 21. Exact
obsolete sources are reclaimed and attempts to delete pinned sources leave the
inventory unchanged. All three finally force ACCEPT 24, PROOF and certificate,
apply the original DATA exactly once, and publish cut 2 / application sequence 43.

The additional cleanup matrix injects IOException at eight ACCEPT/context/floor
handoffs and four source-retirement handoffs. Every case is interrupted again
after reopening, then resumed under a new local owner. The final inventories
must equal the uninterrupted chain. Independent Python replay derives every
first/second interruption, final state, force order and explicit return boundary.
This matrix uses repeated owner opens in one JVM, not process death.

The independent model derives captured packets, immutable source sets, selected
generations, contexts, floors, exact deletion and publication from the preceding
originals. Negative qualification validates the original first, checks exact
rejection reasons and also replays a relocated copy. Typed image semantics are
checked by the producer using the actual core reader; Python independently checks
physical bytes and protocol bindings.

## Remaining work

This is a small-image, stable three-voter storage qualification with conditional
historical bootstrap. It does not establish maximal journal/image/staging
headroom, distinct minority ENTRY adoption, admitted-bootstrap full lifetime,
coordinated old/joint/new profiles, online membership or power-loss behavior.
[Mixed-ballot process recovery](PHASE_2_CONTEXT_MIXED_PROCESS.md) now covers the
corrected completion path at 84 repeated-death cases. Earlier process matrices
still describe their own original compiled runtime. The [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) remains open.
