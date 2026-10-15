# V5.2 read authority and lifecycle

**Status:** design candidate, revision 0.1; governed by
[Phase 0](PHASE_0_CONTRACT.md), not an implemented capability.

Accepted in PR #335; see the [acceptance record](PHASE_0_CHECKLIST.md) and
[current Phase 1 implementation](PHASE_1_FOUNDATION.md). Statements about unexecuted
work below describe the original Phase 0 delivery; runtime qualification remains pending.

## Authority and capture

Represent a captured cut as `(group, history, manifest, publishedIndex,
applicationSequence, materializationGeneration)`. The first three values come from
verified sealed authority. The index comes from the application publication that
was reconstructed from a valid proven prefix; sequence is its application value,
including any imported base. A control-only NO_OP advances index without advancing
sequence. Never sample these values independently from status counters.

The existing implementation serializes `AutomaticApplication.publish`, replacement
and public query work on the application worker. Its `ReplicaApplication.replaceWith`
closes old engines; a read-count field alone does not make cross-worker retention
safe. V5.2 therefore retains this serialization for active explicit callbacks.
It adds a separate bounded waiting/admission mechanism, not concurrent access to a
closing old engine. The callback never runs under the protocol monitor.

Capture must atomically, with respect to publication/state change:

1. Recheck ownership, closing/fatal condition, deadline and the policy/state gate.
2. Read the verified identity and currently published application index/sequence.
3. For `LEADER_STRONG`, require its completed fresh barrier and current activated
   epoch exactly as V5.1; no diagnostic-only shortcut. For `AT_LEAST_INDEX`, compare
   exact token identity before comparing long indices. For `STALE_ALLOWED`, require
   the committed publication without a fresh quorum.
4. Establish one callback-owned live view and record the capture. For a local policy
   a concurrent higher promise alone is not a history mismatch; the state gate still
   applies. A staged replacement, accepted entry or unpublished proof is never a view.
5. Invoke the callback once on that worker, expose only the read-only wrapper, then
   invalidate it and release ownership before completing the caller's Future.

All methods within one callback see the same cut, even if it invokes several
queries. This is a new explicit-view guarantee, not a reinterpretation of separate
old public calls. Strong capture is the read's linearization point. Local capture
fixes an older committed prefix and provides no real-time linearizability claim.
The result token always describes the actual captured cut, not merely the supplied
minimum. Its sequence is reported separately in the result.

## Token issuance and lifetime

A token is generated only after successful callback completion from the previously
captured cut. No token is returned for a failed/cancelled Future. Captured progress
can be independently recorded for failed evidence without counting as client success.
For confirmed-write coverage, the write response must happen-before invocation of
the strong token-producing read. Obtaining a token concurrently with a write is not
a write receipt. An indeterminate write followed by a strong read does not by itself
settle whether that particular operation occurred.

| Event | Token meaning / action |
| --- | --- |
| New leader, retained-disk restart, reconnect | Same compatible manifest/history; old lower bound remains valid |
| Checkpoint, compaction, snapshot catch-up in the same group | Published index at or above the bound suffices; no old entry lookup/pin is required |
| Same sequence at different log indices | Compare log indices; sequence cannot substitute |
| New group, backup import, schema/configuration/manifest mismatch | INCOMPATIBLE_HISTORY; no numeric comparison or waiting |
| Lost voter disk | Existing new-group transfer requirement; no token-authorized same-group replacement |
| Caller invents a larger index in a valid-looking token | Treat as a lower-bound request; wait/reject without advancing authority or allocating history |
| Token created long ago | No time expiry; may remain unsatisfied forever outside this request's deadline |

The token does not bind election epoch, node or process: these may change while
the committed history stays compatible. It binds the manifest digest including
the immutable group/schema/codec/genesis context. No token registry, expiry sweep,
lease extension or retained snapshot is created. A checksum detects accidental
damage, not malicious modification. Untrusted network authorization remains the
embedding application's responsibility; no public token proves an external write.

## Request ownership and waiting

Conceptual states are `VALIDATING -> QUEUED -> WAITING/READY -> CAPTURED -> RELEASED
-> COMPLETED`, with terminal rejection/cancellation before capture. They are internal
states, not new persistent record kinds. Registering a waiter and observing publication
must prevent a lost wakeup: recheck after registration under the same publication
ordering, or use an equivalent generation-and-recheck protocol. Wakeups never skip
the full capture check.

`AT_LEAST_INDEX` with zero wait makes one scheduled capture attempt within the
ordinary operation deadline. If behind, return `PROGRESS_NOT_REACHED`. Zero means
no waiting for progress; it does not mean synchronous execution or no queueing.
With positive wait, the single deadline is invocation plus the smaller of the
requested wait and configured operation timeout. It covers queueing, progress and
capture. The comparison at capture is strict: `now < deadline`; equality expires.
Strong/stale use the existing operation timeout. No phase resets a deadline.

An unsatisfied waiter holds no snapshot, application worker, protocol lock or
ordered writer task. Normal replication/recovery supplies progress; the API does
not force elections, issue a new recovery stream per waiter, or poll remote status.
If the replica enters a non-readable state, uncaptured waiters fail `NOT_READY`
(or the actual fatal/closed reason); they are not silently carried through install.
Clients can issue a new read later, retaining evidence of the failed attempt.

## Races and observable outcomes

| Race | Required boundary |
| --- | --- |
| Higher promise before strong capture | Existing stale-epoch/not-ready failure; never downgrade to local |
| Higher promise after valid strong capture | Overlapping captured read may finish at its earlier linearization point |
| Higher promise around a local capture | Same identity/published-prefix guarantee; no epoch lease. If state is CANDIDATE/RECOVERING before capture, reject |
| Proof forced but application not published | Wait/reject; never return the future proof's index with old documents |
| Publication between waiter check and registration | Recheck observes progress or a later wakeup; no stranded waiter |
| Install/reconstruction before capture | Reject during non-readable state; after verified publication a fresh call may use the new cut |
| Install/write queued after capture | Waits for the cooperative callback release; cannot close/mutate its view |
| Deadline/cancel wins before capture | Callback invocation count zero; later publication cannot complete success |
| Capture wins before cancellation | Callback may finish once; Future stays cancelled if cancel wins completion. Pin/permit remain until real release |
| Close before capture | Reject CLOSED, remove waiter/timer; no new callback |
| Close after capture | Quiesce cooperative callback; incomplete close retains ownership, never close its live engine underneath it |
| Fatal condition after capture | Previously verified immutable cut may finish; new captures fail. No result from a corrupt/unverified cut |

The implementation must distinguish caller Future state from actual work ownership.
It must not free a permit twice, reuse a captured view on cancellation, or count
abandoned asynchronous work as finished. Deadline bounds admission and capture,
not execution of arbitrary Java callbacks. A callback that never returns can delay
publication and close; this inherited cooperation requirement is explicit and tested.

## Finite resources and scheduling

Let `P = bounds.maxPendingClientOperations()` and `R = min(64, P - 1)` (P is positive).
Every explicit read, including strong, consumes one of the existing P permits and
one of R explicit-read permits until callback/work and completion handlers settle.
With P=1, explicit reads reject CAPACITY_EXCEEDED; old APIs still have their slot.
The default P=10,000 gives R=64. This leaves at least one admission slot unavailable
to explicit reads; it is not a guarantee against saturation by other clients.

- At most R explicit requests, R callback references, R tokens and R deadline tasks
  exist per handle. Each encoded token is exactly 112 bytes. Token history causes
  no disk growth or authority pins. Retained caller closures/results are arbitrary
  application objects; count bounds are not an exact JVM heap-byte promise.
- At most one explicit callback is active per handle, with one scoped view and no
  cross-call pin. No extra application engines are allocated for waiting/reading.
  Preserve current runtime materialization, checkpoint, image and transfer limits;
  do not replace their current accounting with older Phase 0 estimates.
- Ready requests are FIFO among eligible requests; an older unsatisfied waiter
  cannot block a ready one. Use at most one coalesced application-read dispatch
  marker, not one task per publication per waiter. Remove cancelled/expired entries.
- Before dispatching another explicit callback, service an already queued
  publication/recovery application task. At a free worker turn, if both classes
  remain eligible, alternate one such task and one read; new work cannot jump the
  existing ready head indefinitely. Timers/cancellation are serviced outside the
  application worker. No progress guarantee while that worker runs a stuck callback.
- Completion handlers run outside application/protocol serialization, under their
  original permit accounting. Same-handle reentrant operations from an active view
  reject; pure schema and cached status remain usable.
- Production diagnostics use fixed policy/reason/state labels, saturating counters
  and current/high-water counts; no token, query or request-ID label. Qualification
  traces are bounded by the declared evidence plan and never silently truncated.

The finite limits are design choices, not observed throughput. Resource tests must
show publication releasing waiters while all R slots are occupied by behind reads,
and must distinguish this from an intentionally blocked active callback.

## Safety arguments and falsifiers

Committed-prefix safety follows from the existing verified publication rule plus
same-worker capture; it does not follow from a role flag. Minimum-progress safety
adds exact identity and `capturedIndex >= token.index`; it does not prove freshness.
Strong safety retains the existing quorum barrier/epoch overlap argument. Bounded
waiting follows from finite registration and no wait-owned publication resources;
completion requires the stated scheduling/cooperation assumptions.

Falsify these arguments with equal index/different history, accepted-only suffix,
unpublished proof, replace/close before capture, expired wakeup, cross-thread escaped
view and saturation suppressing the publication that would satisfy it. The concrete
[evidence matrix](TESTING_AND_EVIDENCE.md) must reject each invalid success. These
arguments and finite-model tests are not a universal formal verification claim.
