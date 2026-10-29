# Frozen learner obligations and selected installation

The [local obligation ledger](PHASE_3_LEARNER_RETENTION_LOCAL.md) now follows an
actual PROMISE/BASIS into a selected generation. This is a native local component;
learner export remains disabled in the new mode until before-exposure quorum
recording is connected. Phase 3 and the original
[native cancellation qualification](PHASE_3_LEARNER_CANCELLATION_NATIVE.md) remain
**OPEN**.

## Exact source and bounded merge

`MembershipLearnerRetentionSource` captures the original owner-bound ledger bytes
and complete PROMISE as one private indexed source object. Its envelope binds
root, view, ballot, basis ID and permanent voter identity. Interrupted source
capture recovers those same bytes under the existing journal owner. Inclusion
proves which bytes the source froze; it is not a new force observation or learner
acknowledgment. A new owner requires every selected source's snapshot, including
an explicitly empty ledger. Legacy owners reject these snapshots rather than
silently dropping their obligations.

`MembershipSelectedLearnerRetention` includes the original local revision and
each selected source's exact BASIS, inventory envelope and included snapshot.
Verification binds the original selected source list and derives a conservative
union. A remote empty or newer-only ledger cannot erase an endpoint. Conflicting
request/identity/endpoint bindings and a third unresolved endpoint remain refused.
The selected capsule must authenticate the union's exact request and ancestry.

Both peer and learner completion bytes count together against the existing shared
journal reservation before SELECTED is written. The selected generation embeds
the immutable merge intent; after forcing its selector, the owner completes the
local ledger before returning installation acknowledgment. Cold recovery repeats
that completion from the installed original intent. It does not choose a new
pair, adopt an unexposed candidate or roll back a later legitimate local revision.
Learner completion precedes peer/future recovery checks that require the complete
owner state. Normal publication prunes obsolete selected metadata while the local
ledger continues to require the endpoints.

No frozen public record/wire kind, voter eligibility, ancestry bound or aggregate
resource limit changes. Private source and selected objects remain bounded by
the existing packet/frame limits; local plans retain at most two endpoints.

## Executed component history

The native three-voter history publishes BARRIER, RESERVE, PREPARE and BARRIER.
Node 1 locally retains endpoint 3; node 2 retains endpoint 4; node 3 is empty.
A fresh ballot captures those separate originals and installs their union.
The node 3 completion is interrupted after a partial learner candidate write,
then reopened twice. All owners retain endpoints 3 and 4, and continue through
BARRIER and CANCEL at terminal 6. Later publication prunes the selected intent
without deleting either obligation. This deliberately exercises local merge and
publication, not a network learner or a quorum-backed export.

Other checks cover source owner/inventory binding, immutable returned bytes,
three source-capture I/O cuts, missing snapshots, mixed owner modes, tampered
selection/local/included state, and a combined journal budget one byte below
completion. Existing learner storage/plan and peer frozen/selected retention
regressions run on the same production inputs. Exact reports and original physical
snapshots are indexed by the [source-bound receipt](phase3-evidence/learner-retention-selection.json).
All 26 focused Java tests passed across two immutable snapshots with identical
887 production class files and 1,276 checked source/build inputs. The existing
peer capture regression includes 14 halt/SIGKILL cases; its independent replay
and nine exact evidence negatives also passed. The retained compressed originals
occupy 5,940,741 bytes. Those peer results do not qualify the new learner process
path.

The injected failures are synchronous I/O exceptions, not halt/SIGKILL. These
Java component checks do not replace independent original-first physical/force
replay. Before complete acceptance, the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md) still requires actual process
cuts, real quorum recording, forced learner-head confirmation and narrowing,
native READY/CANCEL learner recovery, all profiles, maximum combined resources
and autonomous runtime integration. Continuous histories stay on one runner;
independent histories may run concurrently in the later hosted matrix.
