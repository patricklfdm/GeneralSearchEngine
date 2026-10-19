# V5.2 Phase 6H complete consumer ledger and read ownership

**Status:** the bounded lifecycle validator is integrated into the existing short
consumer qualification. Formal M01–M04 measurements and the complete execution
freeze remain pending. No runtime Java, timing limit, workload rate or paid-cloud
behavior changes in this stage.

## Complete calls, including failures

`measurement_history.validate` binds every controller call, including preparation
and sampler commands, to one received request and its actual response in the same
process. Request bytes, operation identity, process generation, outcome and all
clock-local timing observations must agree. Duplicate calls cannot disappear in a
dictionary; an extra wire call, omitted response or duplicate API invocation fails.
The bound remains 4,096 commands per process and three cleanly stopped processes.
Crash histories and PENDING calls need a separate fault admission.

Read successes require a correlated runtime invocation, captured/entered/released
view and, for the explicit API, the complete callback interval. The original
physical publication, fresh strong barrier, token, generation and actual V4.4
query-result checks still run independently. This lifecycle layer alone is never
physical or measured acceptance.

For a valid, non-crashing workload, observed NOT_LEADER, NOT_READY,
QUORUM_UNAVAILABLE, STALE_EPOCH, CAPACITY_EXCEEDED and DEADLINE_EXCEEDED are reported
as failures with their original NOT_APPLICABLE outcome. They do not increment
success counts. A failed read cannot carry an answer/token or expose a callback.
Where the explicit invocation supplied a deadline, deadline rejection must occur
at or after it. An early public availability rejection can legitimately precede
the runtime invocation; the checker does not fabricate a missing invocation.
Client executor rejection is separately counted and must precede API invocation.

Fatal storage/integrity failures, undeclared token errors, unexpected cancellation,
unknown consumer exceptions and failed control commands reject this qualification.
Reported transient reasons are observations, not proof of a particular network or
scheduler cause. Formal workload admission must separately freeze minimum coverage
and acceptable outcomes; this helper does not make an all-rejected run successful.

Mutation NOT_SUBMITTED and INDETERMINATE remain distinct. The [physical projector](PHASE_6_MEASUREMENT_PROJECTION.md) separately requires successful updates to be
chosen/published, forbids chosen effects for NOT_SUBMITTED, and preserves any chosen
INDETERMINATE effect. Lifecycle classification never proves rollback.

## Reconstruct ownership, do not trust counter totals

For each explicit read, replay the atomic observations:

`ADMITTED → CAPTURE_VALIDATED → SETTLING → OWNERSHIP_RELEASED`

A rejection after admission may go directly from queued to settling. A captured
view must be released before settling. Only after completion handlers have returned,
barrier preparation has finished and cancellation ownership is zero can the permit
be released. Response logging may precede or follow this last transition: the
consumer can attach its completion handler to an already completed future.

The validator derives owned, queued, captured, settling, alarm and high-water counts
from these transitions. It requires R = min(64, P − 1), at most one active captured
callback and one dispatch marker, and complete release before CLIENT_IDLE/CLOSED.
Candidate idle observations must actually include all read counters; missing fields
cannot masquerade as zero. The published V5.1 control lacks these new fields and
retains its separate legacy checks.

Only transitions recorded under the protocol monitor define atomic counter cuts.
The pausable CAPTURED/RELEASED hooks run outside that monitor, so another request
may change global counts between sampling and appending their rows. Those rows
still prove view lifetime, but their sampled totals are not treated as atomic cuts.

## Validation and boundaries

The original and relocated five-mode evidence from `run.oupfL5` is replayed using
the new checker, without rerunning any workload or rebinding the original source.
Existing query/physical results and all original negative results must remain
identical. New negative mutations remove a received command, duplicate a controller
call, omit read admission, forge settling counts or early completion release, and
remove a candidate final counter. The original must pass before any negative counts.

The retained failed `run.xPRxuT` candidate-minimum history is also replayed through
the lifecycle helper: ten successful reads and one NOT_READY rejection, all permits
released. Its original smoke FAIL remains a failure; a complete rejection ledger
does not override that all-success smoke requirement.

All 119 V5.2 Python tests pass. Ten original/relocated physical and V4.4 query
replays pass, retaining all 124 original rejections and adding 46 ledger negatives
(170 total); elapsed replay time is 114.981 seconds. CI inventory,
documentation contract, changed local links, shell syntax and whitespace checks
pass. The standalone replay tool's initial import-path failure and first negative
check-order mismatch remain retained.

Local reports, original failed tool attempts and replay results are retained in
`target/v52-measurement-history`. This stage does not claim a fresh Maven reactor,
hosted protected CI, formal throughput result or complete Phase 6 acceptance.

Next integrate this ledger with the full measured physical/query path and the
M02–M04 schedules, then commit the complete machine execution freeze before formal
windows under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
