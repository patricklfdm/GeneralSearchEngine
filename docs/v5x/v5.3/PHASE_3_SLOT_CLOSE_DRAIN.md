# Phase 3: native slot drain retries

Status: scoped runtime correction; Phase 3 remains OPEN.

Resource-lifetime review found that `MembershipSlotEndpoint.close()` set its
closed flag before waiting for children, then returned immediately on every
subsequent call. A timeout or interruption could therefore leave a voting writer
and its CONTROL lease alive while another closer reported success. This also
affected simultaneous closers, without requiring an earlier timeout.

The enclosing activation scope detached its slot and source-service references
before cleanup. Retrying parent closure could no longer find the failed child.
Termination of the parent's control and expiry executors alone did not prove
that the slot's separate writer had stopped.

## Correction

* Slot revocation remains immediate and permanent. Every close attempts child
  cleanup and waits for admitted calls, including after an earlier failure.
* Waiter reservation and call admission share the revocation lock. The waiter
  is released before decrementing the admitted-call count, so zero calls cannot
  hide a still-owned admitted WAITER lease.
* The activation scope retains its bounded child references across failed drain.
  Slot handoff keeps the old child until close succeeds, and retains an abandoned
  newly constructed child if its cleanup fails. No retired-child list is added.
* Scope closure cancels children outside registry/journal monitors, waits for
  existing handoffs/calls, then drains the final stable child set. A child created
  during revocation cannot escape the first cleanup snapshot.
* Parent scratch cleanup requires successful child cleanup as well as terminated
  parent executors. A retry can finish cleanup; it cannot revive the campaign.

The original exception categories, interrupt status, bounded per-close waits,
protocol records, vote/publication authority and resource limits are preserved.
This does not add operation retries or extend a campaign's original deadline.

## Reproduction and checks

`V53SlotCloseDrainTest` uses actual native ACCEPT handlers, writers and localhost
source exchanges. The existing injectable clock pauses the voting writer before
it opens pulls or holds the journal monitor. It does not substitute a fake
executor or mutate private runtime state. The response is cancelled while the
original writer remains deliberately blocked with its CONTROL lease.

The initial three isolated regressions fail on the original implementation and
pass after correction. The expanded checks cover timeout, interruption, campaign
abandonment, parent endpoint closure and simultaneous closers. They verify
repeated failure while the writer remains held, successful drain after release,
post-revocation request rejection, waiter release and parent scratch lock custody.
Existing tests cover two-slot handoff, source-session continuity, expiry, higher
ballot fencing, maintenance cancellation and failed scratch cleanup.

The intermediate close correction passes 31 Java tests. After the final waiter
ordering adjustment and scratch-lock assertions, 11 targeted Java tests pass on
the final source; the earlier 31 are recorded separately. Eighteen planning tests
and the document/format contract check also pass. The planning receipt still
reports 12 requirements and 544 scheduled histories with runtime qualification
false.

The first diagnostic test version blocked inside the journal's durable callback;
its parent cleanup consequently waited on that monitor. That retained diagnostic
is not used as the decisive parent-drain reproduction. The corrected original
reproduction uses the clock boundary above and keeps its own log/XML.

The [development receipt](phase3-evidence/slot-close-drain.json) records exact
validation results and hashes. Local logs are under `target/v53-slot-close-drain/`.
This batch does not qualify complete CONTROL/WAITER content/lifetime coverage,
all transfer-service failure paths, simultaneous physical resource maxima, the
544 final-source hosted histories, or Phase 3 closure. Existing long hosted
qualification remains deferred; no hosted or paid-cloud execution is claimed.
