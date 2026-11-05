# Joining collectors and connection-bound transport replay

Status: **collector/component integration PASS; fresh required-four native
execution PASS, independent replay REJECTED for missing endpoint observations**. This composes the
[connection observation mechanism](PHASE_3_CONNECTION_ATTEMPTS.md) with the old
and joining owner collectors and shared joining readers. It does not add missing
identity to a historical trace or declare Phase 3 closed.

## Capture and compatibility

`-Dv53.transport.connections=true` enables connection metadata in the native
joining test collectors. The ordinary trace format remains the default while
the fresh whole-history gate is pending. Old owners attach the original socket
value to sends, receives, responses, deliveries and terminal failures. Joining
owners do the same through scoped callbacks and diagnostic decorators. Response
inventories retain the exact receiver-side connection as well as original frame
bytes. No field is added to a protocol frame or a durable authority record.

A callback-local context supplies metadata to the existing old-owner collectors.
It is removed on return or exception and restored correctly across nested
callbacks. It is not inherited by another thread, cached by request hash or used
to hold any protocol capability. Diagnostic wrappers forward the same connection
value through both ordinary and failure callbacks. Disabled capture does not
inherit an outer connection accidentally. Two focused Java regressions exercise
these lifetime and forwarding rules.

## Reader composition

`scripts.v53.joining_connections` normalizes the old-owner vocabulary and scoped
joining vocabulary into the connection reader without changing event positions.
The original positions are carried into every send/read/offer/delivery/failure,
so comparisons with storage forces and owner lifetimes still refer to the exact
shared original history. Old response kind labels are checked against the
connection-bound original wire bytes, and old deliveries must name an already
observed client invocation.

Once any connection metadata is present, every transport event and response row
must carry it. Partial stripping cannot fall back to hash/FIFO matching. Both
`joining_phase_evidence.exchanges` and `joining_transcript.causal` use this same
path. Traces without connection observations retain their existing strict
legacy validation, including refusal of ambiguous overlapping retries.

All response offers remain in the transcript. A timed-out invocation's late offer
has `delivered=None` and remains attached to that failed connection; only the
actual retry's client read may satisfy a delivered-ACK requirement. Failure
accounting distinguishes response-less failures from failed attempts that did
offer a response, without relabeling incidental loss as an injected `withheld`
reply. The complete network reader retains both failure classes in its counts.

The existing explicitly declared learner-source loss policy remains mandatory
for failed transfers. It still requires the exact loss boundary, original
response, identical recovered retry and unchanged exporter authority. An
incidental failed transfer with no such evidence is rejected with
`joining connection unqualified transfer attempt`; this change does not silently
admit new transfer-failure schedules. Post-read caller failures also retain their
explicit unqualified status until an appropriate completion observation exists.

## Short validation

The two actual TCP overlap cases now also run through the old unscoped sender
collector and the scoped/decorated joining receiver collector. Original public
bootstrap and unchanged storage are independently replayed before the exact
network schedule and receipt. All eight original-first negative mutations pass
on this collector-produced evidence. The dedicated connection collector and its
eight negatives, plus all six legacy cases and thirteen existing negatives,
remain passing on newly generated evidence.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53TransportConnectionTest,V53TransportAttemptTest,V53JoiningTraceTest' test
python3 -m scripts.v53.joining_connections "$JOINING_CONNECTION_ORIGINAL" --qualify
```

The [retained integration index](phase3-evidence/joining-connections.json) binds
sources, reports and raw inventories. Its results describe transport components,
not complete membership histories. The Java tests passed twelve executions with
no failures or skips. Eight new Python integration tests check mixed vocabularies,
original event positions, exact shared-reader output, stripped metadata, extra
fields, unknown delivery IDs, false transfer-loss claims and corrupted replies.

## Next whole-history gate

Run the existing required-four fixture with both `v53.joining.requiredFour=true`
and `v53.transport.connections=true`, preserving one source/build throughout:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.joining.requiredFour=true \
  -Dv53.transport.connections=true -Dv53.publication.resources=true \
  '-Dtest=V53JoiningIntentExportTest#requiredFourVotersCompleteReplacementFinalAndStableBarrier' test
```

`scripts.v53.required_four_network` is the dedicated entry for that new
original. It first completes required-four owner-file and retirement derivation,
then requires original connection observations and replays every attempted
exchange, grant/installation/slot force chain and current-owner lifecycle. Its
PASS is scoped to observed network and durable ACKs; export/control capabilities,
continuous ledgers and whole-runtime resources retain their separate gates.

```bash
python3 -m scripts.v53.required_four_network "$ORIGINAL" --qualify
```

The qualifier preserves all 121 existing network/force/lifecycle mutations and
adds four connection completeness/correlation mutations. Exact transport error
names reflect the new reader; durable authority errors retain their existing
names. Before mutation, the original connection replay selects actual caller and
receiver failures, if present, for missing/foreign/duplicate-terminal mutations.
Late receiver terminals use their bound connection positions, never the latest
matching request hash. A trace without those failures does not invent them.
Every negative preserves all non-observation files and must fail for its declared
reason; unrelated errors or an invalid original cannot count as rejection.

Eight conditional entry tests and 51 related reader tests pass. These prove
admission/mutation behavior only. The entry is not a positive whole-history
qualification receipt.

## Production endpoint follow-up

The fresh native run at runtime source
`2f5cce27ffd2054011ed04fd7791c75bb9e090f9` completed all eleven slots, FINAL,
successor BARRIER and cold reopen in 1442.910 seconds. Its Java sources and
classes remained unchanged across execution. Raw originals are retained at
`general-search-engine-replication/target/v53-native-dispatch/run-178c7357-83bf-44de-a17b-8b7b3e0c0520`;
the source/build inventories, JUnit result and failed replay are retained at
`target/v53-required-four-connections/run-20261104T235253Z`.

The independent reader rejected this original with
`joining connection complete wire metadata`. Of 4833 original responses, twelve
lack socket observations: nine pending checkpoint responses and three retained
head responses. Their 24 corresponding request/offer events also lack them.
Both actual production listener decorators forwarded only the older three-argument
callback, losing metadata supplied by the transport. The earlier collector
component exercised diagnostic decorators, so it did not cover this boundary.
This is an observation failure; the native execution PASS does not confer a
physical/network qualification PASS. Original files remain unchanged, and no
UUID or socket pair is reconstructed from ordering or request hashes.

The correction forwards the same transport `Connection` through both ordinary
and failure callbacks in `MembershipLearnerCheckpointEndpoint` and
`MembershipLearnerHeadEndpoint`. The external callback still executes outside
the lifecycle monitor, followed by the original custody check immediately before
response writing. The old callback overload remains supported. Protocol bytes,
quorums, authority, deadlines and capacity bounds are unchanged.

`V53LearnerEndpointConnectionTest` uses both actual TCP endpoints to cover
checkpoint offer/chunk/commit, head ACK, protocol rejection and owner closure
at the response hook. It checks object identity within a socket invocation,
distinct connection IDs across sockets and reversed sender/receiver endpoints.
The original three-argument rejection/close tests remain separate compatibility
checks. Corrected-source complete native capture and physical/network/negative
replay remain pending; short endpoint tests cannot replace those gates.

The [endpoint validation index](phase3-evidence/endpoint-connections.json) retains
the source hashes, original failures and successful correction: all four new
regressions fail for missing connection observations before the fix, and sixteen
selected Java tests plus 51 Python reader/plan tests pass after it. The first
checkpoint-close test incorrectly expected `PROTOCOL` instead of the existing
`CLOSED`; its corrected expectation was separately verified against the original
implementation before applying the forwarding fix. Both diagnostic reports are
retained, rather than counting the wrong expectation as a product regression.

Its files, source retirements, complete network/phase history and remaining
export/control/resource lifetime obligations must be replayed independently.
A short collector pass cannot stand in for that gate. Process-child propagation
and final-source hosted admission remain separate obligations; this optional
capture flag has not been enabled globally across existing process cohorts.
No existing timeout, frozen capacity, format, hosted subset or acceptance row is
removed or increased. The twelve subsets / 544 planned histories are unchanged.
