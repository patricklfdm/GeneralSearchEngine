# Phase 3B — bounded peer endpoint projection

This records the original pure projection milestone. Subsequent native ledger,
selected-source and [complete-copy confirmation](PHASE_3_PEER_CONFIRMATION.md)
integration retain its endpoint bounds and add durable observation/renewal
metadata. The historical producer/qualification scope below is unchanged.

Status: **LOCAL COMPONENT QUALIFICATION**, not durable or distributed retention.
The [offline-survivor investigation](PHASE_3_SURVIVOR_RETENTION.md) remains open.
This batch implements the immutable state rules required before persistence and
selected-source integration. The [receipt](phase3-evidence/peer-retention-plan.json)
binds the actual source and focused build evidence.

`MembershipPeerRetentionPlan` begins from an authenticated genesis and keeps one
or two exact possible endpoints for each permanent governing identity. Dispatch
retains the known endpoint and the intended newer endpoint. A second different
target is refused while the previous dispatch remains ambiguous. The plan itself
is never permission to send: durable local and quorum recording are still required.

Only a typed complete `MembershipFloor.Copy` may narrow progress. An older copy
does not cancel a later in-flight target. Imported plans are conservatively merged;
a higher claimed cut alone cannot erase an older possibility. A union exceeding
two endpoints per identity is refused unless actual complete-copy observations
reduce it. Every endpoint must remain on the authenticated original ancestry.

Configuration reconciliation follows the already authenticated configuration.
Learners need a real complete copy at the current joint cut before entering this
projection; a proposed target or transfer offer is insufficient. Old voters remain
in the joint set and can leave only after stable FINAL. Lower configuration ranks,
changed permanent identities, foreign roots and missing ancestry are rejected.

## Validation and limits

The final isolated reactor package passes 22 tests: six new projection tests,
twelve selected-source tests and four generation-copy fault tests. The new tests
cover stable sizes 3/4/5 and all seven ADD/REMOVE/REPLACE profiles. Configuration
histories in those seven profiles are explicit conditional fixtures; they are not
new end-to-end transition qualifications. A separate test uses actual native
three-voter EMPTY bootstrap, BARRIER and DATA publication to obtain complete old
and newer copies and exercise ambiguous merged state. It is a Java component
test, without a new independent full-history replay claim.

The first snapshot was retained but not executed. The intermediate build passed
the earlier five-test projection suite; the final build includes the additional
ADD/REMOVE profiles. The source inventories and logs distinguish these scopes.
No production caller uses this projection yet. No storage/wire catalog, bound,
workflow, public runtime, V5.2 runner or paid-cloud execution changes.

Next: an owner-bound durable container and restart qualification, followed by
quorum intent/selection propagation and actual publication/maintenance integration.
The complete [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md), including 3C–3E, remains open.
