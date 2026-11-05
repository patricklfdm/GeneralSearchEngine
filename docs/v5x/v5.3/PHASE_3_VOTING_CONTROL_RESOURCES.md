# Phase 3: original incoming voting control and waiter lifetimes

Status: scoped native resource qualification; Phase 3 remains OPEN.

The incoming voting endpoint now names each CONTROL and WAITER allocation with
the digest of its original ACCEPT, PROOF or APPLY request plus an allocation
nonce. These are local observation identities. No wire/storage bytes, resource
limits, request deadlines, scheduling, duplicate handling or retry counts change.
The longest new owner remains within the existing 128-character limit.

Previously these owners contained only UUIDs. Equal byte sizes or approximate
overlap cannot establish which request owned a writer or waiter. Historical
UUID-only collections remain explicitly unobserved and fail the new strict
option; they are not rewritten or treated as new-source evidence.

## Independent binding

`voting_control_resources` requires prior native physical qualification. The
resource pipeline invokes it only after original storage, publication and
accounting checks. It independently replays the actual socket transcript and:

- Derives each CONTROL extent from the original connected request bytes and
  checks the immutable allocation's request digest, unit, nonce and lifetime.
- Requires exactly one writer allocation for a logical request. Every observed
  original ACCEPT/PROOF parent force or APPLY end force belongs to exactly one
  live writer; that writer remains held through the durable return boundary.
- Requires the original waiter to surround the writer lifetime. Every waiter
  has zero byte charge and fits a distinct actual server-call interval. Matching
  is injective, so one connection cannot justify arbitrarily many waiters.
- Allows a lost ACK's original server call to overlap its identical retry.
  Multiple connections do not create extra durable votes. A separately traced
  cached ACK needs an observed original force for the same statement.
- Rejects missing/legacy bindings, extra allocations, changed extents, failed
  voting handlers without an original ACK, incomplete drain and premature release.

The matcher establishes coverage by original identical-request intervals; it
does not claim which identical socket scheduled an individual waiter when their
intervals overlap. Outbound failures with no observed server admission do not
invent server resource owners. Interrupted handlers and failed writer execution
are outside this successful incoming-voting qualification.

## Capture and replay

The existing two-slot native producer supplies original request/connection,
resource, publication and cleanup observations. Enable the same established
capture properties; the only runtime edit is the two allocation names:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53NativeDispatchTest#nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener \
  -Dv53.publication.resources=true -Dv53.resource.transitions=true \
  -Dv53.resource.owner.close=true -Dv53.resource.control.close=true \
  -Dv53.resource.source.control=true -Dv53.resource.export.ownership=true \
  -Dv53.transport.connections=true test
```

Use the new `v53NativeDispatchEvidence` directory printed by that run:

```bash
python3 -m scripts.v53.native_resource_evidence "$ORIGINAL" \
  --source-control --control-closes --export-ownership --direct-exports \
  --voting-control
python3 -m scripts.v53.voting_control_resource_negatives "$ORIGINAL"
```

The option is currently restricted to the stable native profile. It does not
silently apply stable voting assumptions to joining or required-four histories.
The negative driver validates the entire unmodified original first, then makes
sixteen in-memory mutations with exact rejection reasons. Deltas and usage are
recomputed; original disk and wire bytes remain intact. Force and return can have
the same resource sequence, so the premature-return mutation inserts the release
between their observations instead of mistaking a force failure for a return
failure. The retained original's inventory is checked again after qualification.

## Evidence and limits

The fresh native two-slot history contains six writer allocations, six waiters
and eight connected voting attempts. ACCEPT, PROOF and APPLY each execute twice.
Two repeated attempts overlap their original server call after lost delivery;
they do not add writer executions. Complete physical/resource replay passes,
and all sixteen mutations reject with their specified reasons.

Thirteen focused Python tests include independent exhaustive matching of three
waiters over 1000 deterministic interval sets, original-first failure handling
and malformed evidence. Together with adjacent resource readers, 176 tests pass.
Native capture and adjacent Java results, original path, source/log/report hashes
and exact scope are recorded in the
[development receipt](phase3-evidence/voting-control-resources.json).

This binds the incoming voting executor's two roles. Slot dispatcher waiters,
outbound delivery, activation/control tasks, whole-runtime cancellation, full
physical maxima, joining/process-failure coverage and final-source cohorts remain
separate obligations. `wholeRuntimeResourcesQualified`, `physicalPeakQualified`
and `phase3Complete` stay false. No hosted or paid-cloud execution is included.
