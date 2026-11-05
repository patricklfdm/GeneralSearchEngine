# Phase 3: slot delivery and dispatcher resource lifetimes

Status: scoped stable-native resource qualification; Phase 3 remains OPEN.

Slot delivery CONTROL and slot dispatcher WAITER names now include the original
request digest and a fresh allocation nonce. These local labels do not change
wire/storage bytes, resource limits, deadlines, retries, voting or scheduling.
The native test producer optionally records the actual direct local PUBLISH
request and returned ACK with `-Dv53.resource.slot.control=true`. Those calls
have no socket and are never represented as network attempts.

## Independent replay

`native_resource_evidence --slot-control` runs the existing physical, publication,
accounting and voting-resource readers first. It then independently checks:

- Each ACCEPT/PROOF/APPLY send or unsent invocation owns one distinct transport
  copy allocated inside exactly one original slot delivery lease. The CONTROL
  byte count comes from the original encoded request, not its allocation label.
- A delivery has at most three identical attempts, ends with an actual correlated
  successful ACK and remains live through that ACK. Earlier attempts require
  observed IO/DEADLINE failure. This success scope excludes cancellation or failed
  delivery completion; it does not infer a deadline proof from resource counters.
- Each observed incoming slot waiter fits a distinct original connected request
  interval. Original voting waiters remain nested inside their slot waiter.
  Concurrent identical retries may overlap; injective matching does not claim
  which identical socket scheduled a particular waiter.
- Direct local calls have their own request/response boundaries and original
  bytes. ACK identity, ballot, trace, certificate, selected authority, published
  cut and generation must match independently validated original publication
  images. A local call cannot borrow a network interval.
- Every physical publication transaction stays inside its original PUBLISH call
  and one dispatcher waiter through all eleven storage boundaries. Its original
  applied-end certificate must equal that call’s certificate: valid calls from
  two different slots cannot be swapped merely because their time ranges fit.
  Local calls
  require actual publication, and every observed slot allocation is consumed.
- Legacy labels, missing calls, extra/reused allocations, incorrect extents,
  premature release and incomplete drain refuse qualification.

Transport validation independently retains any unobserved frame lifetimes as
explicit gaps. A successful slot result does not promote those gaps into complete
transport or whole-runtime qualification. Outer activation dispatch can service
some cached/retention requests without entering a slot; counting all network
requests as slot waiters would be incorrect. The proof covers observed slot
allocations and requires custody of original voting children and publications.

## Capture and replay

Enable the established resource/connection capture properties plus local calls:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53NativeDispatchTest#nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener \
  -Dv53.publication.resources=true -Dv53.resource.transitions=true \
  -Dv53.resource.owner.close=true -Dv53.resource.control.close=true \
  -Dv53.resource.source.control=true -Dv53.resource.export.ownership=true \
  -Dv53.transport.connections=true -Dv53.resource.slot.control=true test
```

Use the newly printed `v53NativeDispatchEvidence` directory:

```bash
python3 -m scripts.v53.native_resource_evidence "$ORIGINAL" \
  --source-control --control-closes --export-ownership --direct-exports --slot-control
python3 -m scripts.v53.slot_control_resource_negatives "$ORIGINAL"
```

The negative driver qualifies the unmodified physical original first, makes only
in-memory mutations and checks exact rejection reasons. It recomputes resource
usage after delta changes and checks the entire retained inventory afterward.
Historical captures without local request/response bytes cannot qualify this new
strict option and are not rewritten. The optional flag is stable-profile only;
other native producers need their own original local-call observations.

## Evidence and remaining work

The fresh two-slot capture has six delivery leases, seven connected delivery
attempts, eight network slot waiters, two direct local waiters and four physical
publication transactions. Original source/connection/publication/cleanup and slot
replay pass; twenty-two exact evidence mutations reject. Eight Java tests and
196 Python tests (including plan checks) pass. Detailed tests, mutations, source
hashes and original paths are in the
[development receipt](phase3-evidence/slot-control-resources.json).

Whole-runtime CONTROL/WAITER ownership, interrupted handler qualification,
joining/required-four coverage, simultaneous physical maxima and the final-source
hosted cohort remain separate obligations. `wholeRuntimeResourcesQualified`,
`physicalPeakQualified`, `finalSourceCohortQualified` and `phase3Complete` remain
false. No hosted or paid-cloud run is included.
