# Queryable operations, cancellation and maintenance

Historical research note. Current decisions and local closure are recorded in
[PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md) and [the final audit](PHASE_0_CLOSURE_AUDIT.md).
Earlier open items, result counts and limitations below refer to that batch.

**Status:** concrete D05/D07 candidate. The local reducer is tested independently;
joint-consensus integration and the final public/byte inventory are separate work.
This supersedes the earlier admission model's client-ID/exact-data-cut limitation.

## Identity and duplicate behavior

A membership view supplies immutable root, current configuration digest and
`nextOperation`. A caller constructs one request containing that root, operation
number, expected configuration, ADD/REMOVE/REPLACE kind and complete target
descriptors. It retains the same request across timeout, leader change and restart.
The expected configuration is independent of DATA progress. Identity fields of
unchanged voters cannot change. New identities/endpoints/storage generations may
not reuse any live, retired or cancelled reservation.

RESERVE is a certified old-configuration control entry. It allocates the exact
next operation number, reserves any new descriptor and advances the durable counter.
Only one active operation exists. Same number and same full request returns its
retained status; same number and different payload is `OPERATION_CONFLICT`.
A future/gapped number is `STALE_OPERATION_NUMBER`; a different root is incompatible.
Two callers using the same advertised next number compete through consensus, not
through an in-memory UUID cache. A loser must inspect the committed operation.

Requests at/below a durable retired-through watermark return `RESULT_RETIRED` and
can never allocate again, even if detailed request bytes were discarded. Querying
an unused higher number returns `UNKNOWN`, which is not proof that a different
request with that number can be executed. A caller must use the current view.
Operation number `Long.MAX_VALUE` is the exhausted-next sentinel; the highest
allocatable number is `Long.MAX_VALUE-1`. Exhaustion rejects without wrapping.

## Durable operation state machine

| Record | Preconditions | Result |
| --- | --- | --- |
| RESERVE | Stable configuration; exact next number; no active operation; capacities available | RESERVED, immutable request and identity reservation |
| PREPARE | RESERVED/PREPARING/READY; next bounded internal revision | PREPARING; bind revision, certified base index, last data index/digest and configuration; invalidate old readiness |
| READY | Exact forced learner image receipt for this revision (REMOVE needs no learner) | READY; receipt binds root, number, request hash, revision, base and full descriptor |
| SEAL | READY; last data index/digest still current | SEALED; bind complete request/preparation/receipt; pause new DATA until FINAL |
| INTENT | Exact sealed binding | JOINT; old-majority INTENT changes governing authority for the following slot |
| FINAL | Matching joint operation and both-majority proof | COMPLETED; publish target membership, increment membership generation, clear active operation |
| CANCEL | RESERVED/PREPARING/READY, selected and proven through the normal protocol | CANCELLED; retain result and descriptor reservation, clear active operation |
| RETIRE | Contiguous prefix of COMPLETED/CANCELLED records only | Advance retired-through and drop detailed results; preserve counter and identity catalog |

These are logical control records, not application mutations. They consume log
positions but do not advance application sequence. A proof must bind their actual
bytes, not an unverified local command object. D02/D03 must supply certification;
the reducer's `force` is an abstract certified-application boundary, not disk proof.

Ordinary data may continue before SEAL. If it advances after preparation, the
leader commits a higher PREPARE revision under the same immutable client request;
the learner catches up again and supplies a new receipt. An old receipt never
becomes current by changing a counter in memory. Control-only suffixes leave the
prepared application cut unchanged, but the learner must install their verified
authority/catalog before it can vote after INTENT. This explicitly replaces the
earlier exact-predecessor admission shortcut; the integrated gate must test it.

SEAL is the cancellation boundary. It serializes the decision against CANCEL in
one committed history before proposing INTENT. Once selected/accepted SEAL might
commit, a caller cannot be promised cancellation from local state alone: recover
the slot and observe a proven CANCEL or SEAL. Proven SEAL/INTENT cannot roll back
because of a deadline. Recovery completes the matching transition when a quorum
is available; inability to do so is unavailability, not permission to shrink.

## Timeouts, result retention and identity lifetime

Future cancellation or a client deadline only detaches that caller. It does not
write CANCEL, delete a learner, reset a ballot or roll back a transition. Explicit
cancel requests themselves may have indeterminate outcomes; use the same operation
number to query. Final operation success is only after FINAL proof and publication,
never after a partial/new-only ACK or local role sample.

Detailed terminal results have a bounded window. A leader may propose RETIRE for
the oldest contiguous terminal prefix before admitting another operation. If it
cannot certify retirement, it returns capacity/unavailability and preserves bytes.
RETIRE cannot include an active operation or release an identity reservation.
Queries capture a committed catalog; status observed on an isolated replica is
not an assertion of globally current progress. The public query uses the strong
path; independent offline inspection is a separate capability.

The identity catalog is bounded separately from the result window. Cancelled
reservations remain non-reusable. On identity/change/revision/counter exhaustion,
new admission refuses; ordinary DATA remains possible unless a transition has
already sealed. Completed/cancelled identity reservation is not permission to
erase its disk. Cleanup still needs exact local ownership and an explicit reviewed
cleanup plan. Numerical production limits are frozen in the resource contract;
small reducer limits deliberately exercise exhaustion.

## Removed-node reads and lifecycle

Existing leader methods and `LEADER_STRONG` retain a fresh quorum barrier. Explicit
local policies retain V5.2's lower-bound/staleness meaning; tokens continue to bind
the immutable root manifest, not the current membership generation. New-group
transfer changes group/history/root and rejects old tokens. A token is not a vote,
membership certificate or authorization to reopen a removed node.

| State at new capture | Strong | Stale/minimum |
| --- | --- | --- |
| Current ready leader | Fresh barrier + current fence + published cut | Local verified cut; enforce minimum |
| Current readable follower / isolated unaware former voter | Strong refuses without a fresh authority quorum | Existing explicit local semantics; no claim of current membership or recency |
| Known removed (certified FINAL installed) | Refuse | Refuse |
| Learner / candidate / recovering | Refuse | Refuse |
| Draining / closed / fatal storage failure | Refuse | Refuse |

Do not claim instantaneous revocation at an isolated node: it cannot know FINAL
until it receives verified authority. A callback captured before the local removal
boundary may finish with that pinned cut; no new callback may capture afterwards.
Keep the existing cooperative callback/publication ordering and release ownership
exactly once. Uncaptured waiters fail on local removal/drain. No new lease, token
revocation service or archival read mode is introduced.

## Same-version rolling maintenance

The library provides planning/drain evidence, not remote process termination.
Before each single-node stop, require stable membership, no active change and a
fresh challenge round to a surviving majority **excluding that node**. Responses
must bind the current configuration, same proven cut and exact new challenge;
duplicates, stale challenge/cut, unready or removed responders do not count.

The plan is an observation, not a durable guarantee that the remaining network
will stay healthy. Drain the chosen local handle, reject new work, finish/release
captured work according to the existing close contract, then let the operator
stop it. A new leader can be elected through the existing protocol. Restart the
same-version node with its original identity/disk, catch it up and verify the
group again before planning the next stop. Never reuse the previous plan after
data/configuration progress or for another target. Mixed-version upgrade, disk
deletion and loss-of-quorum membership repair are excluded.

## Executable counterexamples and scope

`operation_model.py` and independent `operation_oracle.py` exercise committed
metadata transitions without importing production code. Tests cover exact retries,
payload conflicts, stale prepared receipts, cancellation around SEAL, identity
tombstones after result retirement, counter exhaustion, forced-prefix crashes,
removed-node capture rules and fresh surviving-majority planning. Future receipt
events cannot validate earlier READY. The oracle never calls the model reducer.

The declared matrix has seven size/kind profiles and three paths: complete,
cancel and reprepare after concurrent DATA. It cuts before/after each control
application: **308 cases**, all retained and replayed after serialization. This
does not cover accepted-only consensus tails; that is the integrated protocol's
obligation, not evidence supplied by this reducer.

```bash
python3 -m unittest scripts.v53.test_operation_model
python3 -m scripts.v53.operation_research \
  --output "target/v53-operation-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Partial matrices are INCOMPLETE. See [source-bound receipt](operation-research.json)
and [closure worklist](PHASE_0_CLOSURE_PLAN.md). Phase 0 remains open until the
remaining protocol, API/format, resource and acceptance decisions are reconciled.
