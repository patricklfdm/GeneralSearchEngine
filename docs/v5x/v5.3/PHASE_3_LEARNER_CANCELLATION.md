# Phase 3 — durable learner cancellation recovery

A prepared learner can now retain an authenticated CANCEL as a local terminal
transaction. This builds on [prepared learner progress](PHASE_3_LEARNER_PROGRESS.md)
and is specified by [A30](PHASE_3_CONTRACT_AMENDMENTS.md). The original joining
identity, complete request, prepared source and its exact ancestor must match.
A timeout, disconnected contact, missing result, READY, SEAL, INTENT or FINAL
cannot stand in for CANCEL.

`MembershipLearnerProgress.retainCancellation` completes the original generation
under the existing receiver lease. `MembershipLearnerCancellation` detaches that
lease before any transaction write, forces a bounded original plan, atomically
moves the complete received source and forces every member and both move parents.
Only then may `result()` expose CANCELLED. These retained historical records do
not become local votes, a local INTENT or deletion authority. The old source and
typed backup remain untouched.

## Ownership and recovery

The fixed sibling `.gse-v53-learner-cancel-<plan digest>` contains the original
plan/candidate and one complete source. Its presence, including an incomplete
transaction, blocks new progress, refresh, successor/slot installation and head
promotion. Existing immutable prepared bytes remain historical data. The original
exclusive learner-store owner also owns the cancellation handle and closes it
before releasing the store.

Cold recovery first reopens the original store and its exact historical typed
owner, then calls `MembershipLearnerCancellation.resume`. This is explicit local
recovery, not automatic runtime integration. Cancelled typed recovery requires all
original plan, backup, receipt and initial prepared-marker bytes: missing or torn
preparation must not be reconstructed to obtain a new recovery capability.

Cancellation recovery checks canonical plan fields, full request/identity, live
prepared anchor, original path and file identities, complete inventory, capsule,
images, generation, ancestral relationship and retained terminal catalog result.
It reserves the same resource pool before replay and validates everything before
any cancellation recovery write. A complete candidate can be resealed; an empty
or torn plan is preserved and refused. There is no retry which rebuilds missing
proof from current API arguments, changes a source or advances a ballot.

The prior receiving directory's parent remains part of the original path binding.
It must remain available through recovery; the received directory itself is moved.
Closing a cancellation owner releases its reservations and revokes `result()`,
but never deletes its retained evidence or makes the learner active again.

## Bounds and qualification

The cancellation source continues to occupy **one LEARNER** slot, with separately
charged original application images. It never claims another GENERATION. Two
64 KiB plan files raise the conservative retained MISC envelope from 1852 to
**1980 KiB**, within the original 2 MiB limit. The two-generation, seven-image,
32 MiB source and original transfer retry/deadline rules remain unchanged.
Acquisition still observes its original deadline; explicit local resealing does
not start another network operation or introduce a new experiment budget.

`V53LearnerCancellationTest` covers all five joining shapes, an initial prepared
head and a promoted current head, 13 injected transaction cuts, terminal-only
retention, damaged/missing/copied originals, unknown inventory, occupied receiving
capacity, two-generation coexistence, closed handles and missing historical typed
materials. Actual TCP and typed backup/force paths run locally. Source quorum
history is explicitly conditional, and injected IOException cuts are not process
death evidence.

The initial five test groups passed. The broader 38-test execution passed 37
checks and retained one promoted-head EOF: that test started a 60-second export
before unrelated local promotion setup and ran for 75.456 seconds. Final targeted
validation passes **20 tests** after moving setup before export and removing
redundant owner traversal from cancellation-path checks. The final idle-handle
negative uses a frozen clock, so timeout cannot count as cancellation rejection.
Production deadlines, retry counts and persisted proof requirements are unchanged.
The final test run recompiles all main/test sources; earlier broader observations
remain explicitly bound to their earlier snapshot.

Execution counts and source-bound observations are retained in
[the component receipt](phase3-evidence/learner-cancellation.json).
The [deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md) still requires
native multi-revision cancellation, original-first physical/force/network replay,
halt/SIGKILL, maximum resources and all original full Phase 3 gates. Matching
locally forced INTENT and autonomous learner continuation remain implementation
work. **Phase 3 remains OPEN.**

## Native follow-up

The first [complete native cancellation entry](PHASE_3_LEARNER_CANCELLATION_NATIVE.md)
failed before retention: the index-5 CANCEL generation no longer contained the
learner's original index-3 PREPARE endpoint. Independent replay confirms all five
native commands and 59 transfers. The earlier conditional component PASS is not
native cancellation acceptance; source-side durable retention remains required.
