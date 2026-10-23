# Pre-ACCEPT publication ancestry capacity

Status: local private Phase 2 integration; Phase 2 remains **OPEN**.

## Reject before acknowledging new work

An enlarged RANGE needs a new bridge for its immediate original parent as well as
renewed older hidden endpoints. Six existing groups can therefore require seven
at the next publication, exceeding the frozen six-group bound. Deferring that
check until certified application is too late for admission.

The application-capable journal now authenticates its original current ancestry,
retained BASIS/source endpoints and governing floor before admitting a new ACCEPT.
It computes the same RANGE start and renewed lower endpoints that checkpoint
construction uses. Conservatively retaining all existing groups, it checks the
next group count and the exact encoded size of private selected coverage. A
64-character placeholder is used only to size the future certificate digest; no
certificate, vote, checkpoint or ownership receipt is inferred from it.

An over-capacity new request returns `CAPACITY_EXCEEDED / NOT_SUBMITTED` before
creating a pending vote, reserving application completion or replaying the core.
It leaves the original journal, source, selection, selector and generation bytes
intact. The owner stays usable for inspection and authorized maintenance. It does
not automatically discard sources or ancestry, change the ballot or retry work.

Exact duplicates of already retained votes preserve their prior result. Recovery
still seals or completes the original request rather than retroactively erasing
it. An older acknowledged certificate that cannot fit its publication is refused
before replay/scratch, with `INDETERMINATE`, retaining its original authority. An
incomplete candidate is likewise never reported as a new `NOT_SUBMITTED` request.
Existing higher-ballot and inode checks remain in force.

## Bounds and validation

Six ancestry groups, five extra local endpoint pairs, the 4 KiB coverage format,
96 KiB ancestry file and shared 32 MiB journal are unchanged. Membership boundaries
remain explicit: INTENT/FINAL do not extend the preceding stable RANGE.

The [evidence index](phase2-evidence/publication-admission.json) records the exact
source, JARs, tests and development failures. The seventh-group regression fails
on the preceding implementation because it returns an actual ACCEPT. Tests cover
six-group admission and exact duplicates, three actual owners completing the
six-group certificate/application/publication path, restart, original SELECTED
preservation, oversized legacy certificates, partial ACCEPT recovery and fencing.
Serialization tests separately cover long-identity coverage overflow; these
synthetic anchors are byte-sizing cases, not authenticated protocol histories.

Earlier checkpoint/bootstrap ancestry remains conditional fixture authority. New
votes, certificates, typed replay, forced ends and selector publication in the
integration test are actual local owner operations. No new disk-write boundary is
introduced by the admission projection. This is not public-runtime, network,
power-loss or maximal-capacity lifetime qualification.

## Subsequent integration

[Original selected-source retention](PHASE_2_SELECTED_SOURCES.md) now permits the
next generation to omit unreferenced groups using the entire selected set. This
page and its evidence index describe the earlier conservative admission batch;
that conservative path remains active for legacy generations without the original
frames. The frozen resource bounds and early admission refusal are unchanged.

## Remaining lifetime work

This conservative check closes the known admission gap, but does not reclaim
ancestry. Safe pruning must account for retained original source/floor and selected
first-choice obligations, preserve exact proof bytes and leave an interrupted
transaction resumable. Same-round stable continuation and full storage lifetime
qualification remain pending; capacity refusal alone is not a long-lived progress
guarantee. See the [Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53PublicationAdmissionTest,V53AncestorCapacityTest,V53CheckpointPlanTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
```
