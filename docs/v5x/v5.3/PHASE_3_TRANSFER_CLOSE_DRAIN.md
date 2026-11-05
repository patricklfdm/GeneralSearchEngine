# Phase 3: shared transfer-service drain

Status: scoped runtime correction; Phase 3 remains OPEN.

Following the [slot drain correction](PHASE_3_SLOT_CLOSE_DRAIN.md), review found
the shared transfer service cleared its trace registry before exporter cleanup.
A concurrent close could return while the first closer still waited for the
original journal/export. It also released service/trace metadata while an
admitted handler was paused before its reply. Separately, a source session
remembered only its closed flag, so a later close silently succeeded after the
exporter's unchecked cleanup failure.

## Lifetime and failure behavior

Revocation stops new admission immediately. External close cancels shared
learner-quorum work, waits for admitted calls under the existing request timeout,
then serializes child cleanup outside the registry and budget monitors. The
registry and service charge remain until cleanup succeeds. Another closer cannot
skip the active cleanup simply because revocation is already visible.

Expiry/fencing inside a handler revokes the service, then drains after that
handler leaves its admitted call. A direct reentrant close from a handler fails
with `transfer close from active handler`; it cannot certify its own completion.
Nested handling uses a per-service thread-local depth that is removed on exit.
Rejected newcomers do not wait behind an older handler's drain.

Waiting timeout/interruption leaves ownership available for a later close;
interruption remains set. Exporter cleanup itself has no retry contract. Its
unchecked failure is remembered and rethrown on subsequent session closes.
Service cleanup still attempts every trace, aggregates distinct failures and
retains its failed child references and parent charge. It never converts final
zero child accounting into successful parent cleanup. This is fail-closed
shutdown behavior, not permission to resume or recreate the failed scope.

Normal successful cleanup retains the existing BEGIN/RETURNED observation
schema. Failed exporter/service cleanup has no RETURNED observation. The prior
[cleanup observation report](PHASE_3_CONTROL_CLOSE_RESOURCES.md) describes its
original source; its allowance for concurrent no-op close callers does not
describe the new service behavior. Independent readers still require actual
complete intervals and reject incomplete/failed observations.

## Scope of validation

Six new regressions fail against the original runtime: concurrent export release,
interruption at both admission/reply callbacks, self-close from both callbacks,
and repeated session close after exporter failure. The expanded suite adds a
conditional original joining-preparation export test with two real exports;
one wrapper reports cleanup failure after closing its original export. Both
original exports release, while the deliberately separate failed service budget
retains its trace and parent metadata. This injected cleanup failure is not a
native crash, storage failure, or whole-runtime resource qualification.

Final-source tests also generate four original TCP source histories (lost offer,
lost data, lost commit and exhausted offer) for the unchanged physical,
source-resource and cleanup readers. Negative replay first validates the
unmodified evidence and checks exact rejection reasons; original inputs remain
unchanged. Exact test results, source hashes and reports are recorded in the
[development receipt](phase3-evidence/transfer-close-drain.json), with local logs
under `target/v53-transfer-close-drain/`.

The intermediate correction passes 37 Java tests. Final-source validation passes
11 Java tests, including the closed-newcomer fast rejection, continuous two-slot
native publication and shared pending learner-quorum cancellation. Forty-eight
Python checks pass. All four fresh TCP histories pass their original preconditions
and 64 cleanup plus 76 source-resource mutations reject with exact reasons.
Intermediate results are retained separately from the final-source validation.

Wire/storage formats, lease limits, campaign deadlines, POMs and workflows are
unchanged. Complete non-export CONTROL/WAITER authority, all cleanup failure
paths, simultaneous physical maxima and final-source cohort admission/execution
remain open. No hosted or paid-cloud execution is included.
