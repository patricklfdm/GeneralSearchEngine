# Volatile heartbeat contact for automatic scheduling

Phase 3 remains **OPEN**. The private activation endpoint now exposes the most
recent accepted activated-heartbeat arrival as an in-memory scheduling hint.
This is the input needed by automatic owner/election scheduling, not that
scheduler itself and not evidence that the remote proposer is actually READY.

## Admission and lifetime

The existing root, current-view, permanent sender/recipient, eligible proposer,
cut-view, scratch, owner, ballot and original-deadline checks run before recording
contact. The receiver still observes a higher ballot before waiting for the writer;
contact is recorded only after the actual reply is validated. Its timestamp is the
original arrival time, not the later writer-completion time. Expired/failed work
cannot extend the apparent liveness window.

Only `activated=true` updates this cell. A false flag remains a valid fencing hint
but is not evidence of a live ready proposer. The subsequent
[activation completion milestones](PHASE_3_ELECTION_WAIT.md#admitted-activation-milestones)
are separate admitted progress. Repeated unactivated pulses must not indefinitely
suppress other candidates merely by arriving.

The single bounded atomic cell retains root/view, proposer identity, ballot and
arrival time. A lower-ballot completion cannot replace a higher one; same-ballot
completions advance only to a later monotonic arrival. A tie keeps the earlier
stored observation. The value and ballot map are immutable. It is not a message
queue and retains no application payload or advertised cut.

Reading the cell performs only the existing lock-free current-view/ballot
cancellation check. A different view, higher fence, failed/closed owner or closed
endpoint makes old contact unavailable. This check does not inspect original
files and cannot authorize protocol work. Every campaign, vote, read and public
callback still requires its full authority path.

Close permanently clears the cell. A delayed completion cannot restore it, and a
new endpoint starts empty even while the original journal/fence remains. Nothing
is serialized, granted, selected, installed, published or restored as READY.
Actual process restart/election qualification remains a separate gate; endpoint
recreation is only a component test of volatile ownership.

## Verification

The [receipt](phase3-evidence/heartbeat-contact.json) binds the exact source and
retained tests/native histories.

- Seven new tests cover activated-only observation, immutable fields, original
  arrival across writer waits, deadline rejection, foreign traffic, invalidation
  by a higher fence, delayed same/higher-ballot completion, close and endpoint
  recreation. Some tests contain multiple explicit variants.
- All nine existing inbound heartbeat tests pass on the same source, including
  authentic fencing before the writer and native 3/4/5-node TCP exchanges.
- Independent original-byte replay checks all 38 native exchanges, unchanged
  bootstrap/retention/storage and all 27 existing evidence mutations. That reader
  qualifies the unchanged storage/wire behavior, while the Java assertions cover
  the new volatile contact semantics.

Automatic timers, bounded campaign ownership, active-campaign progress, native
restart/failover histories and the full Phase 3 matrix remain required. No public
API, frozen bytes, time limit, workflow or paid-cloud execution changes. Rollback
removes the endpoint's volatile contact cell and its component tests; inbound
fencing and the previously qualified outgoing sample remain intact.
