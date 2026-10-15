# V5.2 Phase 0: explicit replica-read contract

**Status:** design candidate, revision 0.1, 2026-10-15; protected acceptance pending.
**Reviewed source:** `fd5bf155994887a5d5adc114000afc9e770960ae` (PR #334).
**Immediate predecessor:** published `5.1.0`, source
`516fe1efb54ef0787f38209108f322f258f71696`; inherited search/storage oracle `4.4.0`.

This resolves the [entry plan](PHASE_0_ENTRY_PLAN.md) into reviewable selections.
It does not claim runtime, model, performance or cloud acceptance. Stable remains
5.1.0. The [accepted charter](../DEVELOPMENT_CHARTER.md#v52--replica-reads) governs;
the [addendum](../NEXT_DEVELOPMENT_ADDENDUM.md#v52-explicit-read-policies) is a proposal.
No previously published read or mutation guarantee is weakened.

## Outcome and scope

A caller can explicitly read a chosen automatic replica's published committed
state, or wait for that replica to publish at least a supplied history-bound
position. Existing automatic read methods retain their fresh leader barrier.
New reads return the selected policy and the captured position alongside the value.
They do not redirect, retry application mutations, or silently change consistency.

The three fixed voters, consensus/storage authority, configured-mode 1.1 behavior,
core/processor dependency direction, bootstrap and disk-loss restrictions remain.
This minor adds no membership changes, read lease, cross-node cursor, arbitrary
historical snapshot service, hostile-client authentication or mixed-version rolling
upgrade. A minimum-position read is not a globally latest read or a time-based
freshness bound. A stale read may be arbitrarily old while the node is isolated.

## D01–D10 selections

All ten rows are **RESOLVED IN CANDIDATE**, awaiting protected review. Exact public
declarations and numeric limits are in [API/format](API_FORMAT_AND_COMPATIBILITY.md);
ordering and counterexamples are in [read authority](READ_AUTHORITY_AND_LIFECYCLE.md).

| ID | Selection and rationale | Evidence |
| --- | --- | --- |
| D01 | Add an explicit asynchronous, callback-scoped read to the automatic interface. Policies are `LEADER_STRONG`, `STALE_ALLOWED`, `AT_LEAST_INDEX`. All existing reads remain unchanged. No new capability on configured/core handles. | E01, E02 |
| D02 | Every successful explicit read returns a token for its captured committed publication. To cover a confirmed write, await that write, then complete an explicit strong read. Token binds version, GroupId, history UUID, manifest digest and log index; never infer index from sequence/status. | E02, E03, E04 |
| D03 | Atomically validate and capture one verified published application cut. Strong adds the existing fresh NO_OP/epoch checks; local policies require no new quorum. All callback methods use the same cut, with publication/replacement serialized until release. | E02, E05 |
| D04 | A bounded asynchronous waiter consumes no application worker or snapshot pin while behind. Zero progress-wait rejects a lower cut; positive wait ends at publication, deadline, cancellation, close or loss of readable state. No fallback result. | E03, E06 |
| D05 | Tokens have no wall-clock expiry and allocate no retained history. Same-history restart, leader change and compaction preserve lower-bound meaning. New group/restore identity rejects them. No promise that the exact old view can be reconstructed. | E04 |
| D06 | New explicit views are callback/thread scoped and have no pagination API. Existing leader paging remains unchanged, including its local current-snapshot cursor rules. No escaping pins, transferable cursors or follower page continuation. This narrows new capability without removing published methods. | E01, E07 |
| D07 | Use a finite subset of existing public admission, at most one active explicit callback, bounded waiter/timer records and coalesced wakeups. Waiting readers cannot occupy publication/catch-up work; active query callbacks remain cooperative as in V5.1. | E06, E09 |
| D08 | One default interface method and six new top-level types; default rejects unsupported implementations. New client token encoding only. No GSER/GSRP change, new wire message or durable token registry. Homogeneous deployment and new-group transfer remain the supported cross-minor migration baseline. | E01, E04, E08 |
| D09 | Independently decode accepted history, forces/proofs and application publications; bind every returned token/value to the actual capture. Status or a token checksum alone cannot qualify a success. Reject mutated evidence only after the original passes. | E01–E09 |
| D10 | Foundation precedes runtime/public/fault enablement. Freeze exact measurements before running them; fresh V5.2 source/control/admission evidence is required. Reuse qualified harness infrastructure without re-labelling V5.1 runs. | E09 and phase gates |

The D06 choice avoids a new long-lived snapshot-retention service in this minor.
Clients needing existing pagination use the unchanged leader API. Extending explicit
views with pages later needs a reviewed lifetime/resource contract, not a cast to
the underlying engine. D08 keeps the existing offline verified-backup/new-GroupId
transfer as the supported V5.1-to-V5.2 path; retained-disk restart within V5.2 is
required, but cross-minor in-place restart/downgrade is not promised by equal formats.

## Policy and state matrix

`readable` means started ownership, verified compatible authority, a published
committed application and no known fatal storage/integrity failure. A role name
alone never establishes this condition. Startup reconstructs the verified cut
before exposing any local read. Genesis at index zero is a valid committed base.

| State at capture | LEADER_STRONG | STALE_ALLOWED / AT_LEAST_INDEX |
| --- | --- | --- |
| LEADER_READY and readable | Fresh quorum NO_OP, publication and epoch recheck | Local captured cut; minimum checked if requested |
| FOLLOWER and readable | NOT_LEADER | Local captured cut; wait allowed for minimum |
| UNAVAILABLE and readable | QUORUM_UNAVAILABLE | Local captured cut; minimum may time out |
| CANDIDATE / RECOVERING | NOT_READY | NOT_READY; pending uncaptured requests fail rather than wait through activation/install |
| STOPPED / STARTING | NOT_READY | NOT_READY |
| FAILED or fatal integrity/storage condition | Existing classified failure | Same; no last-good-view fallback for a new request |
| Closing / CLOSED | CLOSED | CLOSED |

The same gate runs at admission, waiter wakeup and capture. A transition to
CANDIDATE/RECOVERING terminates uncaptured local requests, even if a former published
image remains in memory. A role change alone after a valid capture cannot rewrite
that result's policy or cut; see the overlap rules in the lifecycle document.
No-op failure on the strong path is still a failed read even if a local image exists.

## Public guarantee example

1. Client A awaits successful `addAll` on the ready leader. The existing Future
   remains `Void`; success already implies committed publication.
2. A invokes explicit `LEADER_STRONG` and returns `view.currentSequence()` from the
   callback. Its result carries a token whose log index covers that confirmed write.
   If the leader changed, A may discover the new leader and issue a new read; it
   must not replay the write just because this read failed.
3. A sends that token to a chosen follower using `AT_LEAST_INDEX`. The follower
   returns a same-history published cut at or beyond it, or an explicit failure.
4. A concurrent later delete can legitimately remove a document from the returned
   cut. Read-your-writes means history coverage, not permanent visibility of every
   previously written value. Other clients' latest writes need not be present.

Tokens returned by `STALE_ALLOWED` are valid lower bounds for that older cut, but
cannot assert coverage of an unrelated confirmed write. Successive stale reads
across nodes need not be monotonic; carry the previous token with `AT_LEAST_INDEX`
when monotonic progress is required. Tokens are trusted-client constraints, not
signed commit certificates or authorizations to mutate/correct local state.

## Phase ownership and exit

| Phase | Deliverable and exit |
| --- | --- |
| 0 | This six-document design, decisions, signatures, bytes, bounds, schedules and protected review |
| 1 | Declaration/byte fixtures, independent read model, consumer scaffold and CI contract; new runtime read entry still disabled |
| 2 | Atomic published-cut capture and bounded waiter kernel with deterministic race/resource tests; preserve old runtime gates |
| 3 | Complete public policy/view/token path through external three-JVM consumers; all supported read overloads |
| 4 | Complete E01–E08 fault, restart, lifecycle, cursor-rejection and resource qualification |
| 5 | Combined partitions/rejoin/slow callbacks and sustained bounded-resource hardening; consolidate unresolved failures |
| 6 | E09 frozen local measurements, no-GCP replay and separately authorized fresh cloud experiment/failure/canonical evidence |
| 7 | Compatibility consumers, canonical artifacts, reproducibility, release fixtures and final coordinates |
| 8 | Separately authorized signed publication and independent remote reconciliation |

Phases are acceptance boundaries, not a requirement for one PR per small case.
Reuse existing recovery and cloud implementations; V5.2 does not repeat V5.1's
election/storage implementation. Do not open Phase 2 before the independent model
and exact token catalog pass. A counterexample reopens its owning decision.

Phase 0 exit needs review of all six documents, recorded exact accepted master and
CI scope, and resolution of semantic objections. A docs-only pass proves document
checks, not replica-read safety. [Checklist](PHASE_0_CHECKLIST.md) records these
separately. [Phase 1](PHASE_1_ENTRY_PLAN.md) needs the user's subsequent instruction.
Existing [Tiered CI gaps](../../CI_TIERED_ACCEPTANCE.md) stay visible; this design
does not close Nightly observations or retained failures. Paid execution, publication
and commit/push/PR operations retain their existing operator-owned boundaries.
