# Phase 3B — native future-target quorum recording

This internal component records an exact unpublished target at a governing
majority. It extends the already-current-target path with the two distinct
[A05 control messages](PHASE_3_CONTRACT_AMENDMENTS.md). It does not yet send a
publication, enable public membership, or close Phase 3.

## Original authority and receiver behavior

The sender binds its installed selection, original certificate, permanent target
identity, prior possible target endpoint, original parent and exact applied end.
The capability comes from its live native application owner. A received digest
cannot construct that capability or create an application acknowledgement.

Every receiver must have its own completed native application under that original
selection and certificate. It forces its own GSFT, including its own selector and
application ACK. A receiving voter may also be the intended target: recording
another proposer's intention is distinct from outgoing self-dispatch, which is
still prohibited. A missing native application returns NOT_READY without writing.

An ambiguous or different prior endpoint returns CAPACITY_EXCEEDED before any
write. Real complete-copy observations must reconcile both participants; the
receiver cannot select an arbitrary older/newer endpoint. An already-published
exact certificate uses the ordinary covered-target ledger and returns CURRENT.
Delayed duplicates preserve genuine newer observations rather than widening them
again. Higher-ballot observation after force suppresses the ACK while retaining
the durable intent; this test observes a fence, not a new durable PROMISE.

## Governing-quorum collection

`MembershipFutureRetentionQuorum` records locally, requests distinct governing
voters, and checks the original owner, selection, certificate, target and deadline
throughout collection. Both old and new majority predicates apply. The qualified
real network histories here are stable 3/4/5 groups; joint arithmetic alone is
not joint-transition qualification.

Only transport IO/deadline failures retry, at most three identical requests per
peer inside the original deadline. Impossible remaining quorums fail promptly.
Malformed or unrelated replies do not become availability retries. Close cancels
even a future returned during the registration race. A returned `Recorded`
object is a live internal prerequisite, with no callback or dispatch method; it
cannot outlive fencing, close or its original native pending target.

## Source-bound local qualification

The [receipt](phase3-evidence/future-quorum.json) binds the retained sources,
attempts and evidence in `target/v53-future-quorum/`.

- The final isolated Maven build passes 19 tests: nine endpoint/quorum tests,
  one ten-case process matrix, four prior local future-retention regressions and
  five format tests. All production Java/resources and selected test sources
  match that immutable snapshot.
- Three actual TCP histories cover stable 3/4/5 groups. In the three-voter case,
  one peer is unavailable and the target voter's first durable ACK is lost;
  the identical retry establishes the node-1/node-3 majority.
- Ten halt/SIGKILL cuts cover prefix write, force, rename, parent force and
  pre-ACK return. Twenty fresh JVMs and five live exclusive-lock probes qualify
  recovery and duplicate acknowledgement, with no power-loss claim.
- Independent replay derives original bootstrap, grants, selection, phased votes
  and native application before checking exact GSFTs, original wire requests,
  force/ACK ordering, quorum membership and interrupted/recovered inventories.
  Twenty-seven network and six process mutations reject for their exact reasons.
  The original histories must pass before negative qualification begins.
- Archived evidence, including failed attempts, is inventory-checked after
  extraction. Relocated optimized-Python replay produces identical successful
  results and all 33 negative outcomes. Three new reader tests pass normally and
  under `-O`; the unchanged format-qualification test also passes. The preceding
  661-test Python run is retained with its earlier source boundary, not relabelled
  as a run of the later new reader.
- The initial build exposed a stale codec wire-kind count. A later build exposed
  the test writer's use of node IDs as JSON keys, prohibited by this repository's
  codec. Both failures and their source snapshots remain recorded; neither is
  counted as a successful qualification.

## Remaining Phase 3 obligations

Actual dispatch must consume this recording together with native voting,
application and publication endpoints. Native pending checkpoint ACKs are not yet
exported by the existing retained-record service, and incoming ACCEPT/PROOF/
PUBLISH/CHECKPOINT_PROPOSE controls are not yet wired. These are concrete next
dependencies, not evidence of completed automatic runtime behavior.

Autonomous election/discovery/maintenance, offline-survivor reconciliation,
maximum completion headroom, ADD/REPLACE learners, all seven joint profiles and
the complete 3B–3E physical/history/network/process gates remain open. Public
factories, protected CI, paid cloud execution and V5.2 are unchanged.
