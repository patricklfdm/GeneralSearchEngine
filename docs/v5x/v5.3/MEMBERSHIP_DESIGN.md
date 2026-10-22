# V5.3 membership design research

**Status:** proposed choices; not a frozen storage/wire or production protocol.

## Proposed bounded scope

- Automatic mode only. Keep configured-mode V5.0 behavior unchanged.
- Stable voter sets of 3, 4 or 5. A four-voter group needs three votes; it does
  not improve failure tolerance over three voters. Add/remove changes one voter;
  replace changes one identity for another in one serialized transition.
- At most one pending operation and one joining learner. Replacing a member of
  a five-voter set needs a peak union of six physical identities. Numeric memory,
  disk and transfer budgets must account for all six before the contract freezes.
- Joining nodes do not vote or serve public reads until the reviewed admission
  point. No automatic shrink-to-minority, multi-operation batch, arbitrary voter
  weights, mixed-version replication or endpoint identity reuse.
- Stable group/history identity survives a supported reconfiguration. Preserve
  the immutable genesis root used by read tokens and distinguish it from mutable
  configuration certificates. This needs exact new-format and migration review;
  do not mutate V5.2's manifest in place.

These are design selections for the initial model, not already supported APIs.
If later analysis changes the scope, change the declared model domain and evidence
explicitly; do not reuse the old result as coverage of a wider domain.

## Quorum arithmetic to establish first

For a stable voter set C, a quorum contains strictly more than half of C's distinct
voter identities. During a joint view `(old, new)`, require a majority of **each**
set. A voter in their intersection counts once toward each set; duplicate receipt
rows never add votes. Unknown nodes and mismatched certificate contexts reject.

For every declared transition, enumerate all receipt subsets of the union and
check joint/joint, old/joint and new/joint intersection. Direct old/new majorities
can be disjoint during replacement even though the two configurations overlap.
A majority of the union or a majority of either side is not the joint predicate.

This is a necessary arithmetic property. It does not prove that replicas select
the same configuration, remember votes across crashes, agree on a prefix, or
remain available. An ACK set is useful only with its exact history, operation,
configuration, ballot, entry and durability phase. The model's equality checks
do not authenticate a sender or prove that a disk force occurred.

## Protocol questions that arithmetic does not answer

The intended lifecycle is `stable -> learner catch-up -> joint -> final -> stable`.
The final proposal must say when each replica adopts a configuration, which
configuration counts a partially accepted transition, and how a higher ballot
reconstructs that decision. Do not infer these rules from the lifecycle diagram.

In particular, GSE's separate ACCEPT and PROOF force steps and frozen recovery
bases differ from Raft's log/commit model. A complete design must show:

1. Both durable acknowledgement phases use the correct, explicitly bound quorum.
   Accepted-only or one-sided proof tails cannot publish membership or data.
2. A new candidate recovers the committed prefix and unresolved transition from
   sufficient configuration-aware bases before accepting unrelated client work.
3. A leader cannot begin a conflicting transition by forgetting its predecessor's
   uncommitted intent after a crash; any discard must follow the reviewed recovery
   selection rule, not a local timeout or configuration file.
4. Final membership becomes authoritative at a defined durable boundary. A removed
   leader stops strong reads/writes there, and delayed ACKs/old requests cannot
   resurrect it. Local stale reads need a separate explicit removal policy.
5. Snapshot/floor/compaction preserve the complete authority needed to interpret
   the remaining configuration and history. Removal success alone cannot delete
   a directory or clear the last useful history witness.

No finalization quorum rule, ballot byte layout or public success point is frozen
by this entry. They are blocking D02/D03/D06 work, not implementation details.

## Executable ballot research update

[Durable ballot/handoff research](BALLOT_AND_HANDOFF_RESEARCH.md) now gives a
concrete root/configuration separation proposal, an ordered ballot independent of
three-voter rank, and a crash/lost-ACK model for one slot under an established view.
Its direct-switch counterexample shows why these results still do not choose a
safe activation or finalization rule. D01–D03/D06 remain open at the integration,
byte-format and multi-slot transition boundaries described there.

## Executable transition candidate

The [predecessor-certified chain](TRANSITION_CHAIN_RESEARCH.md) now evaluates one
conservative rule: a stable INTENT is certified by the old majority; its matching
FINAL requires both majorities; the first new stable slot requires the final
certificate. Each receiver must force the complete predecessor chain before voting.
No later slot may be pipelined over an uncertified parent. Competing targets are
values in one slot, never separate authority contexts selected by their proposers.

This is a tested research candidate, not the frozen production protocol. The
learner's data materialization, snapshot/floor compaction and adaptation to GSE's
current global promise/activation remain open. The logical entry ID excludes proof
receipt sets and ballots so that re-proof does not fork the successor context.

The [recovery/retention model](RECOVERY_AND_RETENTION_RESEARCH.md) now exercises
checkpoint selection, floors under old/joint/new authority, exact unresolved-tail
preservation and interrupted retirement. Complete authority remains retained under
finite research limits; this does not resolve bounded production history or data
materialization. In particular, its proposed exact-copy retirement of an unresolved
tail extends the current Java refusal rule and is not enabled in production.

## Operation and maintenance requirements

The [authority/learner candidate](AUTHORITY_AND_LEARNER_RESEARCH.md) tests new quorum
endorsements for stable data ranges while retaining original INTENT/FINAL proofs.
Its gate binds the complete prepared request, durable identity, exact materialized
cut and forced image receipt. A receipt alone does not grant a vote: certified
transition installation establishes eligibility, followed by separate global
promise/activation rules. Complete descriptor retention and integration remain open.

Bind the caller's operation ID to group/history, expected configuration identity,
kind and complete target descriptor. Repeating that exact ID/payload should query
or resume the original operation. Reusing it with different contents must reject.
Concurrent new IDs do not bypass serialization. A request timeout means the caller
stopped waiting, not that a durable transition was rolled back. Define cancellation
before/after the first irreversible write and bounded result retention in D05.

Catch-up is a prerequisite, not authority to vote. Replacement uses a new voter
identity in the initial scope; same-NodeId disk loss remains a distinct recovery
operation. A maintenance plan must revalidate the current configuration and
surviving quorum before each stop. Same-version restart qualification cannot imply
mixed-version upgrade support. Do not turn the library into a remote process killer.

## Primary references and their limits

[Raft extended paper, section 6](https://raft.github.io/raft.pdf) motivates the
joint-majority transition and non-voting catch-up. Its configuration activation
and finalization rules depend on its own election/log protocol; they cannot simply
be copied into GSE's current two-basis recovery implementation.

[Ongaro's single-server change counterexample](https://groups.google.com/g/raft-dev/c/t4xj6dJTP6E/m/d2D9LrWRza8J)
shows why limiting changes to one member is not by itself a safe cross-term
protocol. It concerns that single-server algorithm, not a claim that joint quorum
arithmetic fails. The local model records arithmetic counterexamples independently;
it does not reproduce or prove that full distributed execution.
