# Native competing-campaign recovery

Phase 3 remains **OPEN**. Three independently started private native node owners
now exercise concurrent election over actual TCP and original durable storage.
This batch corrects defects exposed by that producer; a producer result of
`PARTIAL` is not independent physical/history/network qualification.

## Reproduced mechanisms

- One node can have published a cut while its peers still expose the previous
  cut. Published-generation maintenance must acquire the exact original copies
  before establishing a floor. A completed pass without those copies now has a
  specific unavailable result. Both the pre-grant and local serving paths return
  to bounded election/discovery; they cannot skip maintenance or retire storage.
- A new forced promise can replace the old selection before an outgoing slot
  next checks its captured voting lifetime. The physical owner is checked first,
  then a positively observed higher ballot has its own internal validation type.
  Only the automatic outgoing adapter converts that exact type into campaign
  loss. Incoming validation remains a protocol rejection, and arbitrary errors,
  nested causes and suppressed cleanup failures remain terminal.
- Higher-campaign scope replacement preserves its positively observed loss in
  a dedicated cancellation value. Futures still report cancelled so socket work
  stops; source/discovery reads can report the exact loss instead of a generic
  IO cancellation. Ordinary cancellation and a nested lookalike do not acquire
  retry permission, and no cleanup failure is discarded.
- An obsolete PREPARE/SELECTED/ACCEPT/PROOF/APPLY now receives a correlated
  `STALE_EPOCH` with the actual locally forced higher promise. Authentication,
  current view and physical storage checks precede the negative reply. It creates
  no vote or grant. PREPARE still observes a valid higher ballot before waiting on
  the writer lock. Completed-publication acknowledgements keep their separate
  original-history behavior.
- A peer can become unavailable before its higher promise is forced/reportable.
  Direct exhausted transport IO/request-deadline failures permit bounded fresh
  recovery; protocol, capacity, closed, wrapped and cleanup failures do not.
  Neither this transition nor a negative reply repeats a client mutation.
- Initial grant admission can also collide with already owned source-image
  capacity. Only a structured `CAPACITY_EXCEEDED` / `NOT_SUBMITTED` from opening
  that new campaign returns to bounded wait. Its allocated counter is consumed;
  no PROMISE is sent or fabricated and a fresh round uses a new ballot. General
  slot/capacity errors remain terminal and frozen limits are unchanged.
- A fresh retry must not use a cached, already-expired milestone to immediately
  consume every remaining round. Only subsequent automatic rounds enforce one
  ordinary election interval from re-entry; newly observed contacts still use
  their original timestamps. Initial waiting still honors an old accepted
  heartbeat's actual arrival. Parent deadline and maximum rounds never renew.
- Endpoint shutdown cancels scope exchanges, then gives the control worker its
  existing drain deadline to release owned scratch without interrupting live
  FileChannels. An unresponsive worker is still interrupted after that bound;
  failed drain retains ownership for explicit cleanup. Foreign scratch and failed
  cleanup never count as success.

Every retry retains the original node lifetime, existing maximum round count,
source/resource limits and storage checks. No deadline, election policy, public
API, record/wire schema, POM or workflow changes.

## Validation boundary

`V53MaintenanceCampaignTest` checks exact unchanged authority bytes on unavailable
or invalid copy acquisition, original deadlines and zero newly allocated campaigns
before pre-grant maintenance succeeds. `V53NativeCampaignFenceTest` checks actual
higher grants, stale controls over TCP, physical corruption before cancellation,
non-authoritative rejection, exact error classes and failed-cleanup preservation.
The endpoint lifecycle suite includes a real owned receiving file while close
waits, and retains its existing unresponsive-worker/foreign-file checks.

`V53CompetingNodeQualification` opens all three original nodes before starting all three
owners. It injects no winner, promise, response loss or artificial election jitter.
It observes guarded readiness for two ordinary heartbeat intervals, then submits
exactly one DATA. A readiness observation may lose its campaign; the producer
records that diagnostic loss separately. It never retries the DATA. Closing must
release every native resource. Original files, requests, responses, force events,
failures and diagnostics are retained, including unsuccessful histories.

The complete probe is intentionally an explicit qualification entry, selected
with `-Dtest=V53CompetingNodeQualification`; it is not a passing default regression.
All its local executions so far failed and remain retained. The latest history
reached actual READY, then lost its sole DATA during publication after another
node campaigned. The serialized automatic owner does not send due heartbeats
while a long mutation is running. Integrating liveness during active writes is
required next; increasing timing budgets or replaying that DATA is not a fix.

The final corrected-source execution passes all **97** component/regression
tests across ten suites, with zero failures or skips. It includes full existing
slot-endpoint, source-exchange, discovery, grant-journal, automatic-campaign,
campaign-fence and election-wait checks, plus the new native regressions.
This is scoped component evidence, not a passing competing-owner history.
Two new endpoint checks both fail against the exact pre-correction endpoint
from `d7b1a86f` and pass in the corrected suite. Other candidate files are retained
in that comparison; it is not a complete original-runtime execution. The earlier
pre-grant unavailable-copy regression also failed on its original implementation.
All eight complete competition failures, both intermediate compilation failures,
their source snapshots and the successful component reports remain retained.
The [receipt](phase3-evidence/competing-campaigns.json) binds every execution,
changed Java file and the 17,256,503-byte retained archive. The final component
source adds a closed-discovery parent check and renames the explicit producer
after the last whole-history run; complete competition on those final bytes is
still **NOT_RUN**, not a claimed successful replay.
Full independent replay of arbitrary competing selections,
other membership profiles and the complete Phase 3 closure matrix remain open.
Existing process-crash receipts describe their original runtime artifacts, not
this changed implementation. Heavy whole-history qualification may run later on
independent hosted runners; one continuous history must not be split.

## Rollback

Revert this batch's journal fence/rejection, automatic adapter classification,
maintenance exception and endpoint drain changes together with their tests.
There is no persistent-format migration. Retain all failed and successful raw
histories and their source snapshots; do not replace them with rerun successes.
