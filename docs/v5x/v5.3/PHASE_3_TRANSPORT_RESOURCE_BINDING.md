# Exact TCP frame reservation lifetimes

Native accounting alone can reconstruct charged bytes without proving which
concurrent identical request owns them. `MembershipTransport` now uses one fresh
local invocation UUID for a socket attempt and its CONTROL frame leases:

- `transport-request-send-<id>`: outgoing copied request;
- `transport-response-read-<id>`: caller's response header/body;
- `transport-request-read-<id>`: receiver's request header/body;
- `transport-response-send-<id>`: receiver's independent outgoing response.

The caller and receiver keep distinct original invocation IDs, joined only by
the existing exact reversed socket/packet reader. Each retry gets a new ID even
when all request/reply bytes are identical. This identifier is process-local
observation, never sent, persisted or used as protocol authority. Admission,
frame bytes, allocation-before-buffer ordering, per-peer limits, deadlines,
retry policy, semaphore ownership and close behavior are unchanged. Internal
lease names stay within the existing 128-character bound.

## Independent derivation

[`transport_resource_evidence.py`](../../../scripts/v53/transport_resource_evidence.py)
first validates the complete original connection transcript. It reconstructs
every typed frame lease from the already validated resource mutation journals.
Original wire bytes determine frame lengths; claimed resource usage is never
the expected message size. Every observed frame boundary must point to the
correct original owner's resource sequence and derived usage.

Outgoing buffers have one exact full-frame reservation and no subsequent growth.
Incoming buffers first reserve the frozen 48-byte header, then grow at most once
before the complete frame observation. Caller response buffers live inside their
outgoing request's lifetime; server response buffers live inside their received
request's lifetime. Successful reads/writes require both buffers to be live at
the corresponding boundary. A caller failure is observed after both buffers
close. A receiver failure is observed after its offered response closes while
its original request is still owned. Timeout after only a partial receive does
not fabricate a complete reply: any recorded body extent must match the offered
original response, and a header-only wait remains header-only.

Reused lease IDs, foreign roles, missing buffers, wrong sizes, uncharged headers,
crossed identical retries, premature release and reversed close order reject.
Old bare random-UUID leases cannot be guessed by length and do not pass this new
scope. Service/export/cache/queue leases remain separately counted, without
claiming their semantic lifetimes from these four transport roles.

The component entry requires all frame leases to bind. The required-four resource
entry invokes this reader after full physical/network/export/maintenance/ledger
admission. It additionally reports any allocation whose attempt never reached a
connected wire boundary as `unobservedFrameLifetimes`; a nonempty list leaves
`allTransportFramesQualified=false`. These are explicit remaining gaps, not
permission to borrow a later successful retry or claim complete control coverage.
`controlLifetimesQualified` and `wholeRuntimeResourcesQualified` remain false.

## Native checks and remaining work

The new native method exercises two original TCP histories: a timed-out request
whose handler fails after an identical retry starts, and a timed-out request
whose response is offered late and then lost. Both use the existing connection
collectors/decorators, exact original storage snapshots and separate real budgets.
The two histories independently bind 7 and 8 frame lifetimes, respectively, with
no missing frame allocations. Thirty-two coherent accounting mutations (16 per
original) all reject with their exact declared reasons after the original passes.
Mutations keep the original wire bytes intact; altered accounting is repaired
where necessary so an unrelated arithmetic mismatch cannot supply the rejection.

All 29 Java transport/resource tests pass. Thirteen new conditional Python tests
cover successful exchange, both failure shapes, original-first admission,
consistent forged counters, exact close order, legacy observations and explicit
pre-boundary gaps. The retained
[development index](phase3-evidence/transport-resource-binding.json) records native
inventories, source/report hashes and the initial conditional-fixture correction:
the reused network fixture's receiver is node 4, not node 2. Native observations
were not rewritten or rerun to fix that test fixture.

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 /opt/maven/bin/mvn -o -B -ntp \
  -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53TransportConnectionTest#identicalRetriesRetainTheirOwnFrameLeasesThroughLateOriginalFailure' test
python3 -m scripts.v53.transport_resource_negatives "$ORIGINAL"
```

No new hosted group is added; twelve subsets / 544 planned histories remain.
Whole required-four corrected-source execution, pre-connection attempts, other
CONTROL and non-publication storage lifetimes, frozen coverage and final-source
admission/execution remain open. No Phase 3 closure, long native run, hosted or
paid cloud execution is claimed by this batch.

Rollback reverts the local transport lease naming and this reader/fixture/entry
integration together. Existing durable and wire formats are unaffected; old
observations retain only the scopes they originally qualified.
