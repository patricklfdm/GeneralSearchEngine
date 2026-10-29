# Phase 3 — selected learner slot and covered seed retirement

[A24](PHASE_3_CONTRACT_AMENDMENTS.md#a24--first-rolling-head-selection-and-covered-seed-retirement)
adds a forced original selection after [A23 installation](PHASE_3_LEARNER_SLOT.md).
An actual typed B owner and its live typed predecessor must agree on the exact
source, receipt and member identities. Candidate force, original rename, active
force and parent force precede returning B as current. The selector binds its own
inode, so a byte-identical replacement cannot authorize cold deletion.

Selection revokes the old A source and typed handles. A separate seed owner keeps
A's immutable metadata lock and physical resource charges while the original head
covers removal of its source and typed backup. Partial deletion resumes only for
covered original members; unknown or changed members stop cleanup. Charges release
after all old members are absent and both surviving parents have been forced.
The immutable admission, original successor metadata and retirement roots remain.

Cold recovery authenticates the independent current B source, selector and typed
members before forcing or deleting anything. It does not require the partly or
fully removed A source to reopen. Original absent admission charges are released
only after retirement forces, then B and conservative A are reserved under the
same pool before covered cleanup. Real semantic reopening is still required for
B's typed capability. The conservative metadata envelope is 1,516 KiB of the
existing 2 MiB MISC lease; generation/image limits are unchanged.

## Focused verification

The source-bound [component receipt](phase3-evidence/learner-slot-head.json)
records exact inputs, compiled identities, tests and retained logs. Conditional
voter fixtures exercise actual files and core semantic decoding for 3-voter ADD,
4-voter REPLACE and 5-voter REPLACE. These are component histories, not native
consensus or actual halt/SIGKILL qualification.

The new cases check selection and cold reopening after A is gone, interrupted
covered deletion, a complete original candidate resumed with the same inode,
partial candidate refusal, unknown old members and a byte-identical replaced
selecting inode. Refusals preserve originals and reject recovery force callbacks;
lease observations check two generations before removal forces and one after
release. The positive selection history installs over actual loopback TCP and
closes that transfer before selecting/reclaiming the durable slot. A separate
final-installation cut expires its acquisition guard, refuses return, preserves
the installed originals and resumes them through the cold owner. Existing
preparation and resource-owner tests accompany the new cases.

The first pre-hardening run passed 11 methods. It lacked the selecting record's
self-inode binding and the two corresponding new regression methods, so it is
retained separately and does not qualify the final implementation. An intermediate
13-method build adds inode protection but still predates the acquisition-lifetime
correction. Final measured counts and duration belong to the receipt, not an
estimated native runtime.

Integration review found that the old native installer retained a callback into
the downloading owner, which could reject later selection after transfer close.
The download guard now covers installation through its final cut, then is cleared.
The durable cut callback and current-source/typed guards still apply to all later
operations. This changes ownership of the guard, not its deadline or retry policy.

## Next boundary

B can now be current after covered seed retirement. Another acquisition still
fails before creating a transport because alternate slot reuse is not implemented.
The [rolling plan](PHASE_3_LEARNER_ROLLING_PLAN.md) must supply bounded repeated
plans/selectors and original-only recovery across multiple A/B cycles. Native
revision progression, all five joining profiles, maximal combined resources,
process death, cancellation, matching INTENT and autonomous readiness remain in
the [acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Phase 3 remains **OPEN**.


The integrated 14-method run passed 13 and failed the new acquisition-cut test's
zero-lease fixture assertion: both independent pull clients were still open when
`Fixture.reopen` checked that every owner was closed. The test now closes those
clients before cold reopen. Only that corrected method is rerun; no production
input changes. The receipt compares all production source/resource/POM inputs
and compiled production bytes before combining passed method coverage, and retains
the original failure. This is not a claim that the complete final test tree ran
again, nor a native consensus or complete Phase 3 result.


## Deferred native history and portable snapshots

`V53LearnerSlotHeadNetworkTest` now provides one continuous native three-revision
entry for the first selected B head, covered seed retirement and actual cold typed
reopening. It also retains the earlier A20/A21 handoff snapshots, so a later reader
can account for the original identities before those members are deleted. The
entry is **compiled, not executed**; see the
[queue and commands](PHASE_3_DEFERRED_ACCEPTANCE.md#selected-slot-native-entry).
The portable snapshot parser verifies copies against recorded original identity
observations without reading old absolute paths, and only reports PARTIAL.
[Its receipt](phase3-evidence/learner-slot-native.json) separates Java compilation,
resource-owner regression and parser tests from unexecuted native qualification.
