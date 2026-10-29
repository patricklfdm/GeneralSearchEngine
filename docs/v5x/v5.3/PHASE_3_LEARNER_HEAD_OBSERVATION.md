# Forced learner-head observation and local retention narrowing

This implements a local ownership boundary for the next distributed confirmation
protocol. Phase 3 remains **OPEN**. It does not add a network acknowledgement or
claim that another process has observed a learner head.

`MembershipLearnerHeadObservation.capture` accepts only the existing sealed
`PreparedGeneration` or `CurrentHead` capability. Those implementations check the
real typed files and the forced selection/handoff. An ordinary receipt, decoded
head file, completed download or caller-supplied endpoint cannot construct an
observation. Closing/superseding the typed owner, changing its original bytes or
entering cancellation revokes its use. Each observation reserves 32 KiB from the
learner's actual CONTROL pool before retaining its bounded request/endpoint
metadata; closing releases it without altering the stored head.

The plan requires the same complete original request and permanent learner
identity, and independently authenticates the observed endpoint against the
source owner's current capsule and ancestry. It can then replace older possible
points with the observed head. Later uncertain offered points remain retained.
A late old observation cannot regress an already narrowed plan. A head served
by another owner need not appear in this owner's local offer list: actual forced
ownership plus exact original ancestry provides the authority. Same image,
receipt equality and an arbitrary larger index do not.

`retainLearnerObservation` persists the result under the native journal's
exclusive owner with the existing shared active/candidate allowance. Pending
slots, application references and incomplete/uninstalled selections remain
refused. Identical plans do not advance revisions. After replacement and parent
force, the original observation is rechecked before returning. Failure poisons
the old owner; reopening retains the old conservative plan or the already
selected narrowed plan, according to the original atomic replacement boundary.
No operation or final retained endpoint is erased.

The source-bound results are in
[the validation receipt](phase3-evidence/learner-head-observation.json). Focused
tests use actual typed preparation and promotion with explicit conditional
history fixtures; the separate native case uses a real bootstrap, native
BARRIER/RESERVE/PREPARE, quorum source retention, TCP learner acquisition and
typed selection. Its direct local observation is not described as a remote ACK.
Interrupted candidate writes are preserved and reopened without inventing an
observation or losing the prior uncertainty.

The selected-source merge remains conservative. Old frozen obligations can be
reintroduced by selection, and a local narrowed ledger alone cannot prove to a
different process that an older obligation was discharged. Distributed work must
therefore bind an authenticated forced-head reply to the original request and
incarnation, preserve its discharge authority through selection, handle stale
and lost replies, and bound unions before they exceed two points. Do not merely
serialize this local capability or treat a singleton ledger as confirmation.

No persisted schema, wire kind, public API or frozen resource ceiling changes.
The existing [deferred acceptance gates](PHASE_3_DEFERRED_ACCEPTANCE.md), matching
local INTENT, all profiles, process death and independent original-first replay
remain required. Rollback removes the new observation entry; already narrowed
ledgers remain valid conservative plans rooted in real durable head progress.
