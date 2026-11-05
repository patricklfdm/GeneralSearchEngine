# Reserved requests that fail before a write boundary

Outgoing requests reserve their copied send buffer before worker dispatch and
connection establishment. Previously the transport's terminal callback required
a connected write/read boundary, so a connection refusal or rejected worker
could release a real reservation without retaining its request-to-attempt
binding. The historical required-four original contains 252 such unbound
`request-send` leases. They were reported as gaps, never assigned to later
identical successful requests.

`MembershipTransport.Events.unsent` now observes a classified failure after the
original buffer and peer permit have been released, provided no write-boundary
callback was reached. The same existing invocation UUID identifies the outgoing
lease and terminal observation. Both asynchronous worker failure and synchronous
dispatch rejection are covered. Calls rejected before buffer allocation produce
no such record. Connected failures retain their existing callbacks. This adds no
retry, renews no deadline and changes no wire bytes, authority or resource limits.
Observer failure is suppressed onto the original error; it cannot replace that
error or prevent resource/permit cleanup.

This is a local attempt observation. It does not claim that a previous identical
request did not execute, nor that a connection was never established: the precise
boundary is before `BEFORE_REQUEST_WRITE`. The observer does not invent a socket,
reply, ACK, vote or successful operation.

## Collection and independent binding

The direct connection collector records `NETWORK_UNSENT_FAILED`. Native joining
and old-owner collectors opt in with `v53.transport.unsent=true`, independently
of optional connected-request diagnostics. The joining decorator forwards the
new callback as well. Its row retains original request bytes, digest, kind,
classified reason and local invocation ID; optional scope identifies only the
collector registration.

The existing transport resource reader now derives the request's full size from
those original encoded bytes, validates its root and exact original sender and
recipient, and binds exactly one `transport-request-send-<id>` lifetime. The
lease must be released by the original terminal checkpoint, with its exact
immutable extent. The ID must be distinct from every connected invocation and
every other unsent attempt. A response-read or other transport role on the same
unsent ID is rejected. Coherent resource counters cannot replace original packet
lengths or let an earlier failure borrow a later retry's release.

Unobserved allocations remain explicit gaps, including historical collections
without this callback. Unparsed inbound reads and other CONTROL classes are not
silently qualified. `controlLifetimesQualified`, `wholeRuntimeResourcesQualified`
and `phase3Complete` remain false. The new `unsentAttempts` result is separate
from connected attempts; it never enters the connected response/history oracle.

## Qualification

Four actual TCP component histories cover connection refusal and executor
rejection through both direct and decorated collectors. Each retains two failed
identical requests, then one successful identical connected exchange, over the
same original bootstrap identities and unchanged disk files. An executor-rejected
case restarts the local transport before the successful call. Each history binds
all six transport leases: two unsent buffers and four connected buffers.

Independent original bootstrap/storage, packet/connection and accounting replay
passes for all four histories, followed by twelve exact negative cases per
original (48 rejections). Mutations cover omission, duplicate/crossed/connected
IDs, changed original bytes/size, early terminals, missing leases and invented
response/socket observations. The existing two late-handler/late-response
histories also pass, including all 32 existing exact resource negatives. Combined
independent replay took 3.6 seconds, without rewriting or rerunning any original.

Twenty-seven Java tests pass across the transport, connection and resource suites.
Additional controlled worker-queue cases prove that cancellation keeps the buffer
charged until the worker unwinds, queue delay does not renew the original
deadline, and transport close reports CLOSED after release. Observer failure
preserves the original I/O reason and leaves the permit reusable. These are
component regressions, not performance or whole-history qualification. Conditional
Python counts and raw/source/report hashes are recorded in the
[development index](phase3-evidence/unsent-resource-binding.json).

The initial fixture compilation used the two-argument drain helper incorrectly;
the correction and original failure log are retained. The first expanded Python
command referenced a nonexistent module; its failed collection log is retained
alongside the corrected command's result. Neither failure was treated as a
runtime retry or a successful qualification.

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 /opt/maven/bin/mvn -o -B -ntp \
  -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53UnsentTransportTest,V53QueuedUnsentTest,V53MembershipTransportTest,V53TransportConnectionTest,V53ResourceObservationsTest' test
python3 -m scripts.v53.unsent_resource_negatives "$UNSENT_ORIGINAL"
python3 -m scripts.v53.transport_resource_negatives "$CONNECTED_ORIGINAL"
python3 -m unittest scripts.v53.test_unsent_resource_evidence scripts.v53.test_transport_resource_evidence
```

Use the printed `v53UnsentResourceEvidence` and `v53TransportResourceEvidence`
directories. The larger required-four producer needs new execution with both
`v53.transport.connections=true` and `v53.transport.unsent=true` alongside resource
observation; historical records cannot be retrofitted with these events. Its
14,148 other CONTROL reservations remain a separate lifetime obligation.
Owner-close observation, receiving physical custody, combined maxima, completion
headroom, full negative matrices and final-source qualification remain pending
for that larger history. Twelve hosted subsets / 544 planned histories are
unchanged; no new hosted run or Phase 3 closure is claimed.

Rollback removes the callback, collectors and unsent reader integration together,
preserving original evidence and its previously qualified scopes. Durable/wire
formats, release behavior, POMs, workflows and paid-cloud execution are unchanged.
