# V5.3 durable ballots and configuration handoff research

**Status:** executable single-slot research; Phase 0 remains open. No production
storage/wire contract, configuration activation rule or public API is accepted.
Reviewed Java source remains the V5.2 development base `73f3bd5`.

## What this batch establishes

The earlier model assumed that receipts represented authentic durable ACKs. The
[new event model](../../../scripts/v53/ballot_model.py) separates delivery, pending
writes, force, reply, message loss/duplication and crash/restart. A candidate can
lose every ACCEPT reply even after its value was accepted by a quorum. A later
candidate must recover that value from frozen durable bases; lack of a client
response does not authorize discarding it.

The model operates on **one slot and one already established configuration**.
It runs old, joint and new views independently. That is useful for election
selection research, but does not establish how a process safely moves between
those views. The retained direct-switch counterexample deliberately demonstrates
that two individually valid histories can conflict across configurations.

## D01: identity proposal

Keep an immutable root binding group ID, history ID and genesis authority. Give
mutable membership a separate generation, descriptor digest and predecessor
certificate. Bind each request/receipt to that root, configuration identity,
logical index and predecessor, as well as ballot, complete entry and phase.
A configuration digest must not replace the history root in a read token.

The independent fork checker groups decisions by **root and logical index**.
Grouping by configuration generation or predecessor digest would hide the very
fork it needs to detect. A different root represents a different history, not
permission to reinterpret an existing token.

This is a logical identity proposal only. V5.2 `ReplicaReadToken` still binds its
fixed manifest; its bytes, compatibility checks and source are unchanged. Exact
V5.3 root bytes, configuration-chain verification, migration and token fixtures
remain D01/D08 work.

## D03: ballot and frozen-basis proposal

Use a lexicographically ordered research ballot `(counter, proposer, incarnation)`.
The proposer is an eligible stable/joint voter. Before a new campaign, choose a
counter greater than both the observed counter and the locally allocated counter.
Counter exhaustion rejects. Membership list order and voter count do not determine
the ballot; changing from three to four members cannot reinterpret an old epoch.

A restart must not reuse a ballot for a different proposal. The model enforces
unique ballot allocation as a primitive and exercises fresh ballots after crashes.
It does **not** implement the durable allocator, authenticate an incarnation, or
specify its byte comparison. Those are requirements for the production format and
same-identity disk-loss fencing, not properties proved by this matrix.

The research voter performs:

1. Stage PREPARE, then force its promise and immutable accepted-value basis before
   acknowledging. A duplicate PREPARE returns that original basis, including after
   a later acceptance or restart; it cannot resample mutable state.
2. Select once from a configuration-appropriate quorum of frozen bases. Preserve
   the highest accepted ballot's value. Equal ballots with different values reject.
3. ACCEPT only under the promised ballot. Force before acknowledging. An old
   delayed request cannot override a higher promise, including across restart.
4. Verify a context-bound, distinct-voter ACCEPT certificate before forcing PROOF.
   Require a separate quorum of durable PROOF acknowledgements before publication.
5. Lose pending writes and proposer memory on crash; retain promises, bases,
   acceptances and proofs. In-flight messages can survive the process that sent them.

The history oracle reconstructs durable promises/acceptances and checks frozen
bases, force-before-ACK, proof certificates and publication independently of live
model state. It retains historical acceptances after overwrite, so a conflicting
later quorum cannot hide an earlier chosen value.

This selection follows the single-slot recovery obligation in
[Lamport, Paxos Made Simple](https://lamport.azurewebsites.net/pubs/paxos-simple.pdf):
a new proposer collects promises and preserves the highest accepted proposal
reported by its quorum; persistent acceptor information must survive restart.
The model's extra PROOF publication phase is GSE-motivated research, not a claim
that the paper specifies GSE's storage protocol.

### Actual implementation boundary

`AutomaticRecovery.select` currently takes exactly two bases including the local
proposer, checks consistent proven ancestry, chooses the longest proven prefix,
and selects an accepted tail above that prefix. `AutomaticProtocol` fixes one
peer for ACCEPT/PROOF. `AutomaticRecords` additionally validates three-member
ranked ballots and exact two-source records.

The single-slot model neither copies that prefix algorithm nor certifies replacing
its `2` with a variable quorum size. Its model proposers may obtain a quorum not
containing themselves. A production change must separately specify local-basis
inclusion, generalized prefix/floor selection, bounded basis transfer and recovery
from unavailable sources. No Java file changes in this batch.

## D02/D06: a concrete unsafe handoff and the remaining decision

With old voters `{1,2,3}` and new voters `{1,2,4}`, old voters `{1,3}` can choose A
while new voters `{2,4}` choose B at the same root/index. Each side can even force
its own PROOF quorum and report success. Both isolated single-view checks pass;
the cross-configuration checker rejects the combined history. Higher configuration
numbers or a different claimed predecessor do not repair this conflict.

Consequently, do not activate a configuration from a local status sample, a
membership-file edit, a learner's catch-up completion, or the largest observed
configuration number. Joint quorum arithmetic alone does not establish the
required durable transition and fencing boundaries.

The next model must evaluate an explicit predecessor-certified chain:

| Boundary to specify | Required observation / unresolved question |
| --- | --- |
| Stable intent | Concurrent target descriptors compete in the same old-authority slot; an accepted-only intent survives election selection when required |
| Enter joint | Exact certificate and installed prefix admitting a learner to voting; no use of an unproven target descriptor as authority |
| Joint recovery | Both sides constrain PREPARE, ACCEPT and PROOF; recover partial transition prefixes and reject a second unrelated operation |
| Finalize | Specify the durable seal that fences old-era service and the quorum authorizing the first new-era decision |
| Retirement | Delayed old messages and removed leaders cannot resume strong reads/writes; data cleanup is separately authorized |
| Snapshot/floor | Retain enough certified configuration ancestry to validate every promise, accepted tail and read-token root after compaction |

A conservative candidate is to pause ordinary writes/strong-read barriers while a
serialized transition is unresolved and require both majorities through the final
seal. This is **a candidate for the next multi-slot model**, not an implemented or
accepted availability policy. It must be compared with alternative handoffs before
freezing D02/D06; it must not be described as Raft's finalization rule.

## Follow-up implementation

The [transition-chain research](TRANSITION_CHAIN_RESEARCH.md) now implements and
checks the conservative handoff candidate across multiple slots. It adds local
prefix adoption, competing targets, finalization and removed-voter checks. Its
results are recorded separately; the single-slot receipt below retains its original
scope. Snapshot/floor compaction and production integration remain open.

The later [global-promise adapter](GLOBAL_PROMISE_AND_ACTIVATION_RESEARCH.md) now
adds durable local allocation, cross-slot grants, proposer-inclusive source
selection, installed-quorum binding and fenced barrier publication. It also
separates promise force from basis force and tests incomplete-basis refusal. These
new results do not expand the original single-slot receipt's claims.

## Declared finite matrix and limits

[Schedule driver](../../../scripts/v53/ballot_research.py),
[tests](../../../scripts/v53/test_ballot_model.py),
[receipt](ballot-research.json).

- Seven size/change profiles: 3→3 replacement, 3→4, 4→3, 4→4 replacement,
  4→5, 5→4 and 5→5 replacement. Each runs old/joint/new: 21 contexts.
- Every ordered pair of **inclusion-minimal** valid quorums in each context.
  Superset quorums and every labelled transition are covered arithmetically in the
  earlier model, not repeated as event schedules here.
- Four schedule families per pair: all ACCEPTs forced with lost ACKs, one unforced
  ACCEPT, all ACCEPTs unforced, and a partially forced PROOF. All voters restart,
  a fresh candidate recovers/publishes, then delayed old ACCEPTs arrive.
- 2,884 cases, 340,850 events and 2,884 recovered publications. This is exhaustive
  over that matrix, **not all asynchronous interleavings**. It is not a failover SLA.
- Twelve representative positive histories and two direct-switch histories are
  serialized and replayed from JSON. All generated traces contribute to one
  deterministic digest; the output retains representative traces, not every trace.
- Five deliberate faults are caught: ACK before force, loss of durable state on
  crash, ignoring accepted values, accepting under a stale promise, and publishing
  after ACCEPT alone. An unrelated failure cannot count as detecting a mutant:
  each regression requires its specific safety exception.

Atomic durable force, authentic non-Byzantine identities, a certified configuration
and a consistent predecessor are assumptions. Torn bytes, multiple log slots,
configuration activation, learner installation, network fairness, storage limits,
read semantics, snapshots and compaction are not covered. Production qualification
and Phase 0 acceptance remain false.

The command refuses an existing output directory, retains failure traces when a
case fails, and reports limited traversal as INCOMPLETE with a failing exit. Python
`-O` does not remove safety checks. Small retained receipts bind the parent commit
and exact model/test hashes while honestly recording uncommitted worktree bytes.
