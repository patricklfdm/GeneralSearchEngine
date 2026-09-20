# V5.1 leadership and recovery candidate

**Status:** Phase 0 design accepted through PR #184; revision 0.1, D01-D05/D08.
**Source:** `09d2bf247f004eb134eb81c59ee88005affafe92`.

**Acceptance update:** protected PR [#184](https://github.com/patricklfdm/GeneralSearchEngine/pull/184)
accepted this Phase 0 design at `31b70d08b509ac75037a8eb6386780affc353ed9`.
[Exact-master CI 35487644896](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35487644896)
passed the documentation lane; reactor/compatibility/packaging jobs were skipped.
Original candidate wording below records the reviewed design, not runtime evidence.
The user subsequently authorized Phase 1; see its [foundation record](PHASE_1_FOUNDATION.md).

## Protocol lineage

V5.0 already serializes each operation through private preparation, forced entry,
entry quorum, forced proof, proof quorum and publication. Its activation forces a
new promise quorum, reconciles proven history, readies a follower and commits NO_OP.
Automatic mode extends that pipeline with competing proposers and an explicit rule
for values accepted before proof visibility. It does not replace V4 materialization
with a second live WAL or turn a role flag into authority.

The design uses the prepare/accept safety pattern: a higher proposal preserves the
value reported at the highest accepted proposal number by its prepare quorum.
[Paxos Made Simple, sections 2.2 and 3](https://lamport.azurewebsites.net/pubs/paxos-simple.pdf)
is the primary reference for that pattern. The GSE-specific proof-distribution,
ordered-prefix, snapshot and read rules below require their own evidence; the paper
does not validate these extensions. Stock Raft log election/truncation rules were
not selected because the inspected entry/proof ledgers have different recovery
authority. A name alone does not satisfy D01.

### Inspected assumptions that must change only in automatic mode

Paths in this table are relative to
`general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/`.

| Surface | Existing assumption | Candidate treatment |
| --- | --- | --- |
| `ReplicationGroupConfig`, `ReplicaManifest` | Configured leader is required and hashed into group identity; format is inferred from genesis presence | Separate automatic configuration and explicit mode/version; no nullable leader or automatic format inference |
| `PublicReplicaEngine.leader`, `ReplicaNode.requireLeader/receive` | Only manifest leader can call application methods or send mutation requests | Gate automatic calls by current prepared/activated epoch and voter identity |
| `ReplicaStore.promise/active` and `AdmissionNode` | Promise binds the configured leader and an epoch/incarnation | Promise binds the ranked proposer and incarnation; startup independently verifies the complete accepted/proven state |
| `ReplicaNode.recover` | Maximum proven prefix plus discardable unproven suffix | Frozen prepare quorum plus highest-accepted next value; proof absence alone cannot justify discard |
| `ReplicaEntry`, `ReplicaProof`, `ReplicaSnapshot` | Entry epoch/incarnation equal proof and envelope epoch/incarnation | Preserve immutable entry origin; separate acceptance/proof ballot; validate both identities |
| `ReplicaNode.read`, `ReplicaApplication.read` | Previously activated view remains readable without fresh quorum | Fresh NO_OP per automatic read, then internal pin of its exact view |
| `ReplicaStore.install`, generations/floor | Installation protects local proofs; promise and accepted-tail state have no separate automatic projection | Preserve latest promise, proven prefix and accepted next slot across every install/select/cleanup cut |

The [public 1.1 runtime](../v5.0/PUBLIC_ADMISSION_RUNTIME.md) and all configured-mode
checks remain the compatibility reference. Automatic 1.2 admission cannot silently
reuse a 1.1 decoder by changing only a version constant.

## Durable and visible states

For slot `i`, `V[i]` is the immutable entry value: manifest, origin epoch/incarnation,
slot, operation, predecessor origin/index/digest and canonical payload. Its digest
does not change when a later leader carries it forward. `B` identifies the current
acceptance ballot `(epoch, proposer, incarnation)`; it is separate from entry origin.

| Observation | Meaning |
| --- | --- |
| Prepared privately | Business validation and deterministic application staging; no authority or client success |
| Accepted locally | Complete `(B,i,V[i])` forced before an entry ACK |
| Entry-chosen | Two distinct voters accepted identical `(B,i,V[i])`; no conflicting value may ever be chosen at `i` |
| Proof known | A valid certificate containing those two entry receipt identities exists |
| Proof stored locally | Local proven prefix advances; a lost proof ACK cannot make it discardable |
| Proof durable on quorum | Normal leader may publish/complete after confirming both proof stores |
| Applied/published | Ordered logical application cut; only proof-backed contiguous state is materialized |
| Client acknowledged | Mutation Future succeeded after the preceding normal-leader boundary |

Entry-chosen is an internal safety boundary, not the public success boundary.
Recovery may finish proof distribution for a previously indeterminate operation.
Local proof receipt can protect/apply a value internally without proving that the
originating client received success; no follower application read is exposed.

Each valid voter retains: immutable sealed genesis, highest forced promise, the
complete reconstructible proven prefix `C`, and at most one accepted unresolved
slot `C+1`. Before accepting a new slot, the previous slot must already have a valid
locally forced proof. The leader additionally finishes proof quorum before moving
to the next slot. This serialization is a safety simplification, not a throughput claim.

## Election and frozen recovery basis

Manifest order fixes ranks 0, 1, 2. Epoch 1 is genesis. A candidate at rank `r` issues
`epoch = 3 * round + r + 2`. If its greatest observed/persisted epoch is 1, round is
0; otherwise round is `floor((maxEpoch - 2) / 3) + 1`. Checked arithmetic rejects
overflow. Thus different proposers never issue the same epoch, and the next local
campaign is above every locally known epoch. A fresh nonzero incarnation is bound
to each campaign. Retries preserve exact bytes; restart always campaigns at a newer
epoch, including after a crash before any peer response.

Failure detection only schedules a campaign. A candidate first forces its own
promise, then requests promises from peers. On a valid higher PREPARE a voter
quiesces lower-ballot authority writes, forces its new promise and captures an
immutable recovery basis before replying. Its basis includes the proven-prefix
image and any complete accepted next value with its last acceptance ballot.
Partial/corrupt authority cannot be reported as an empty state.

The response binds voter, manifest, ballot, a fresh basis identity, lengths and
hashes of the frozen image/accepted record. Chunk retrieval is bounded and checks
that identity; unrelated later STATUS replies cannot be substituted. A responder
may advance to a higher promise; old chunk completion then fails or stays a byte-
identical historical basis, while old ballot writes reject. At most one basis per
requesting peer is retained. Duplicate requests cannot create unbounded copies.

A basis identity never refers to newly sampled bytes after restart. If its frozen
inventory cannot be reconstructed exactly, return an unavailable/expired basis;
the requester starts a new prepare epoch. The restarted voter retains its forced
promise and accepted state. It cannot substitute an empty tail or new inventory
under an old basis identity. Selected recovery records are not themselves acceptance
receipts: restart must preserve both the selection and any still-required prior
acceptance until the new ACCEPT is forced.

The candidate freezes one complete quorum containing itself and one remote intact
voter. A third response is diagnostic unless a new complete quorum is selected
before issuing any ACCEPT. Never union independently sampled response fields.
After issuing ACCEPT, a lost campaign resumes exact attempts or starts a new epoch;
it cannot choose a different value under the same ballot.

Higher promises revoke local readiness immediately. Handling a higher valid PREPARE
does not wait behind a synchronous request that is waiting for this voter: the
protocol dispatcher serializes durable writes but never blocks that serialization
thread on network responses. Application callbacks execute outside this control
dispatcher. Their progress is still required when application reconstruction needs them.

## Recovering the prefix and the next slot

Given the two frozen responses, let `H` be their maximum locally proven index.
Obtain a complete valid image through H and verify agreement at every other
response's proven index, including snapshot-covered anchors. Distinct valid proofs
for different values at the same slot fail closed. Missing proven payload/state
prevents admission; raw maximum index cannot substitute for an image.

For each response the unresolved accepted slot is at most `C+1`; therefore any
reported acceptance beyond H must be exactly H+1. Reject a report with a longer
unproven suffix. Accepted values at or below H may be obsolete minority acceptances;
the chosen/proven prefix wins without pretending those old values were committed.

If H+1 appears in the quorum, choose the value with greatest **acceptance epoch**.
Equal-ballot unequal values are a protocol/integrity failure. Preserve the exact
entry bytes and origin fields and require predecessor digest H. If no response has
an acceptance at H+1, the candidate may choose a fresh activation NO_OP there.
Do not choose by entry-origin epoch, longest tail or local preference.

Install the selected proven prefix on the candidate and prepare quorum while
retaining the forced promise. A durable selected-next record must preserve any
H+1 choice before a generation switch could erase its old acceptance. Then run the
normal accept/proof-quorum path at H+1 under the new ballot. If this carried an
older value, whether application or control, commit a separate fresh activation
NO_OP next. Only after this campaign's own fresh NO_OP is published locally does
the node enter leader READY.

An out-of-quorum peer may retain an older minority value or a proof whose ACK was
lost. It never votes by merely receiving a snapshot. Catch-up under a newer ballot
must reconcile its proven prefix, preserve any higher promise, and install chosen
state using the same accepted-slot rules. A valid late proof may protect the same
chosen value; it may not create a different history or downgrade the promise.

Selection pseudocode (all inputs are independently validated immutable bases):

```text
recover(ballot, ownBasis, peerBasis):
    require two distinct voters, including self, promised this exact ballot
    H = max(ownBasis.provenIndex, peerBasis.provenIndex)
    prefix = obtain complete proven image through H
    require every reported proven prefix agrees with prefix
    tails = reported acceptances above H
    require every tail has slot H+1 and predecessor digest prefix.digest
    if tails is not empty:
        next = exact value at greatest acceptance ballot
        require no equal-ballot unequal values
    else:
        next = fresh activation NO_OP with this ballot as its origin
    force selected prefix/next binding before replacing old recovery state
    install prefix while preserving promise and required acceptance
    acceptAndProve(ballot, next)  // same quorum for entry and proof; ordered publish
    if next is not this campaign's fresh activation NO_OP:
        acceptAndProve(ballot, fresh activation NO_OP)
    require local promise still matches ballot
    enter LEADER_READY
```

Every IO/network wait can lose authority; the transition guards below still apply.
An unsuccessful attempt cannot bypass them by resuming this pseudocode halfway.

## Normal transitions

All authority transitions are locally serialized; network waits are asynchronous.
Before responding, recheck that the required ballot is still the durable promise.

| Actor/event | Preconditions | Durable work before success response | Failure/restart rule |
| --- | --- | --- | --- |
| Voter / PREPARE | Exact automatic manifest, eligible ranked proposer, higher epoch or exact retry | Force promise; freeze/bind basis, ACK its exact inventory | Lower/conflicting epoch rejects; ambiguous force quarantines voter |
| Candidate / basis quorum | Two complete matching-ballot bases, local voter included | Persist selected recovery state before replacing a generation | No quorum or unavailable bytes: no service; campaign may retry at a higher epoch |
| Voter / ACCEPT | Current promise matches B; slot is next or an exact retry; predecessor proven; B's proposer matches sender | Force acceptance containing the exact value and B; ACK receipt identity | Same B/slot different value rejects; higher B may replace an unproven lower-ballot value according to recovery |
| Leader / entry quorum | Two distinct matching ACCEPT receipts | Construct exact proof; force it locally and on a matching remote acceptor | No public success on entry quorum alone |
| Voter / PROOF | Current B, matching accepted entry and valid receipt quorum, contiguous predecessor | Force proof, advance local proven state; apply only that proven prefix | A proof force/ACK cut remains protected across restart |
| Leader / proof quorum | Both exact proof acknowledgments, current local promise | Publish private application state atomically; complete client Future | Superseded after dispatch: may be committed, return indeterminate failure |
| Candidate / activation proof | Recovered prefix and own fresh NO_OP completed | Publish control cut; enter READY | No automatic service before activation cut |
| Any node / higher epoch | Valid admitted message with higher promise request | Force higher promise before grant; revoke readiness | An old leader's already chosen value stays chosen; it loses permission for new authority work |
| Any node / checkpoint/install | Verified cut, exact ownership, complete surviving authority | Force staged files, generation selection and parent; retain promise/accepted state | Never roll back promise, lose a local proof or erase sole chosen recovery source |
| Any node / close | Any lifecycle state | Stop admission; settle/quiesce accepted work, transport and writes before unlock | Timeout retains ownership; repeated close can finish |

For ACCEPT retries, compare the full value and ballot, not just the index. PROOF
receipts bind current acceptance B and stable value digest; their epoch need not
equal the entry's original epoch. A voter which did not accept this value first
catches up or accepts it before storing that ballot's proof. The minimal leader
uses the same two voters for entry and proof rounds, preserving reconstructibility.

## Strong read ordering

Automatic `get`, every search/ranking/page/highlight/explain overload,
`currentSequence` and application `metrics` use the following order:

1. Observe invocation; validate pure arguments and reserve bounded read admission.
2. Check local leader READY and enqueue a **new** NO_OP specific to this call.
3. Finish its entry quorum and proof quorum under the current ballot; publish it.
4. On the ordered publication path, pin the corresponding immutable local view
   before allowing a later application publication to substitute another view.
5. Evaluate the requested method against that view on the caller/read execution
   path, then release the internal pin in every completion/error/close path.

No earlier heartbeat, activation NO_OP or another completed call's barrier is reused.
No stale fallback, read lease, clock-based proof or public pin API is introduced.
NO_OP changes LogIndex only; it must not invalidate an otherwise valid application
cursor by changing the underlying document/index snapshot version.

A higher promise before capture rejects the call. A higher promise after capture
does not retroactively invalidate the pinned read: the read overlaps the election
and can be ordered at its barrier. Close/integrity failures may still reject it.
The implementation must preserve that pinned view until evaluation ends, including
across application reconstruction. Existing replacement/close code that closes a
slot without honoring the new pin protocol cannot be reused unchanged.

The barrier is a chosen slot after every earlier completed mutation. A competing
leader cannot choose a conflicting slot; if it fences the old leader first, that
old leader cannot obtain a new barrier quorum. A read whose barrier completes
before the competing leadership may return its pinned cut even if newer writes
complete before the read response, because they overlap the read. These are the
linearization cases the independent E09 checker must distinguish.

No operation runs arbitrary Query/codec code on the control dispatcher. A user
callback holding a view may delay local mutation/materialization; bounded waits
reject pressure instead of mutating the pinned view. Such callbacks cannot be
forcibly terminated; no hard total-method deadline or unbounded pin accumulation
is promised. Reentrant application calls on the same automatic handle reject.

Backup uses the same fresh barrier, then captures a bounded writer-ordered V4
application export; later file publication does not change its logical cut.
Local checkpoint and storage diagnostics are maintenance, not leader-read services.

## Restart, disk loss and rejoin

Retained-disk restart validates seal, promise history, acceptance and proofs before
network participation. It starts as a non-ready follower regardless of its last
role; same-node restart never revives an old incarnation as leader. Catch-up is
automatic and bounded. The current leader periodically probes both configured
peers; a response only schedules recovery and is not quorum authority by itself.

A missing or corrupt required authority component quarantines the node. Do not
recreate genesis, clear promises, restore an old image, clone a live directory or
reuse a healthy node's seal to regain its vote. An intentional rollback of all
durable files cannot be detected from those files alone and violates the stable-
storage assumption; the operator contract forbids it.

V5.1 automatic mode does not support same-group disk-loss re-enrollment. Two intact
survivors may continue within the fixed quorum, but restoring redundancy requires
the explicit new-group backup transition in the compatibility document. Loss of
the majority, or unavailable required committed state, prevents automatic progress.
Configured 1.1 plan/apply replacement and two-survivor reconstruction remain unchanged.

## Snapshots, compaction and safety argument

Snapshot ancestry identifies stable values, not their last acceptance ballots.
A terminal proof binds a chosen prefix; the complete canonical application image,
genesis base sequence and bounded ancestry preserve query truth. Transfer never
lowers a promise or silently drops an unresolved accepted next value. Promise/basis
state remains outside replaceable application snapshots and is forced first.

Physical log deletion still requires two complete durable recovery sources at the
same cut. Local checkpoint alone is insufficient. Every cut retains the immutable
genesis, a proven snapshot/ledger and the still-required accepted next value.
Snapshot publication, generation selection and deletion have separate crash cuts.
Automatic mode initially retains the existing finite full-ancestry and promise
ceilings; compaction does not pretend to remove their lifetime bounds.

Safety obligations, to be tested independently:

- **Unique ballot:** proposer rank and persisted increasing epochs prevent two
  legitimate processes from issuing different choices under one ballot.
- **Chosen-value preservation:** a prepare quorum intersects every earlier choosing
  quorum. Its highest accepted next value carries a previously chosen value forward;
  proven-prefix selection cannot discard it. In-flight lower accepts either occurred
  before the frozen promise cut and are represented, or are rejected afterward.
- **Prefix agreement:** a node accepts only after a proven predecessor and only one
  unresolved next slot. Induction on the slot gives one chosen command chain; a
  snapshot may replace bytes only with that same chain's verified application state.
- **Acknowledged durability:** success requires proof quorum and publication, hence
  a chosen value. Restart/election selection preserves it; missing proof ACKs do not
  justify erasure. Arbitrary later physical loss of the required majority is excluded.
- **Read safety:** fresh chosen barrier plus exact pinned cut orders reads after
  previously completed writes; the quorum intersection fences later old-leader reads.

These are design arguments under stated assumptions, not a claim of formal proof
or executed model checking. Phase 1 must explore the counterexamples below before
production admission, and reopen the candidate if an invariant cannot be realized.

## Required counterexamples

| Wrong shortcut | Falsifying schedule and required handling |
| --- | --- |
| Discard every tail lacking an observed proof | A/B accept X; proof construction/distribution is delayed; B/C elect. Carry X from B's accepted state, never choose Y and later receive an incompatible proof for X. |
| Pick maximum log index | A has a longer private tail, B/C have a proven shorter prefix. Recover the proven prefix and ballot-selected next slot, not A's raw size. |
| Rewrite a carried entry's origin | Re-encoding X with a new epoch changes its digest and all descendants. Retain V bytes; store the new ballot in ACCEPT/PROOF. |
| Promise ACK before force | B grants a new ballot, crashes and forgets it, then ACKs the old leader. Crash-cut evidence must forbid the contradictory grant. |
| Mix unfrozen status pages | Fetch prefix before a lower-ballot proof, then fetch tail after it. A bound immutable basis must detect or eliminate this mixed observation. |
| Select a new value on a same-ballot retry | An earlier ACCEPT reply was lost and a majority may already hold X. Retry exact bytes or use a new prepare epoch. |
| Serve from cached READY | Partition A; B/C activate and acknowledge a write; a later read to A must fail its new barrier. |
| Reject every read completing after an election | A read pinned before step-down may legally overlap the election. The oracle must accept that history while rejecting a read invoked afterward using an old pin. |
| Restore a lost voter as empty | A/B choose X, A loses its disk and votes as fresh with C. Public startup must refuse the unsealed/lost authority. |
| Compact to application state only | Erase an accepted next value or latest promise, then elect from that disk. Independent inspection must reject the incomplete recovery representation. |
