# Original joining network and durable acknowledgements

`scripts.v53.joining_network_evidence` replays the complete observed transport
sequence from the same `9136083f` native `3-ADD` execution used by the
[source-retirement reader](PHASE_3_JOINING_SOURCE_RETIREMENT_REPLAY.md). It first
requires that reader's independent grant, generation, floor, retirement,
publication and cold-storage comparisons to pass. There is no new native
execution and no combination of observations from separate histories.

## Causal transport and transfer integrity

Each original request write, server request read, response write and client
response read is consumed once, in order. The request bytes must match the
observed digest and wire kind. Root, permanent sender/recipient identities,
correlation fields and the response bytes must agree. Scoped callbacks must use
the same client/server lifetime at the matching boundaries. Repeated requests
need distinct observations; overlapping identical attempts are rejected because
the trace cannot identify their individual sockets unambiguously.

All 2,208 exchanges in this healthy fixture complete their four boundaries. This
is a requirement of this fixture, not an assumption that networks always deliver.
An undelivered attempt cannot disappear from this gate or become an ACK. Faulted
histories require their own explicit attempt/loss oracle.

Within a transfer session, endpoint identities, root, view and ballot remain
fixed. Sequences advance by one; only the last exact request and response can be
replayed. Each subsequent request follows the previous observed delivery. The
reader checks offers, bounded chunks, offsets, chunk hashes, aggregate digest and
extent, then the exact commit. A rejected opening attempt is recorded separately
and cannot count as a committed transfer. An empty transfer still needs its
original empty digest and commit.

The original contains 363 transfer sessions, 686 committed transfers totaling
3,897,617 bytes, two exact retries and two rejected opening attempts. The counts
include repeated transfers of the same content; they are not unique storage size.
Transcript integrity alone does not prove that an exporter held the referenced
object at that moment. Complete time-bound export authorization remains open.

## Grant, selection and installation authority

All 19 writer-held grant copies have already been compared with independent
derivation. Their original packet image count determines the required source
force multiplicity. PROMISE, capture intent, packet/images, directories and BASIS
must complete their local durable order before grant return. A remote PREPARE
must name the preceding proposer PROMISE and the exact peer BASIS in the same
view/ballot. Its receive precedes peer capture; completed capture precedes the
PROMISE response. All ten remote grants must be explained by one such exchange.

The six derived selections bind all 14 original local selection-force events.
Each selected source must have its exact original grant. The proposer must have
received each selected remote PROMISE before forcing its decision, and must force
that decision before sending SELECTED. Each of the eight remote INSTALL_ACKs is
bound to that decision, its cut and its receiving owner's force interval. The
independently checked installed generation determines image/member force counts;
generation and selector durability must precede the response. An installation ACK
does not establish public readiness.

The existing [slot-phase reader](PHASE_3_JOINING_PHASE_REPLAY.md) also runs on these
fully paired exchanges: 11 slots, 24 owner transactions, 69 phase responses and
13 future-retention targets retain their force-before-ACK and publication ordering.

## Validation and remaining work

The [batch receipt](phase3-evidence/joining-network-replay.json) records the reused
producer/build identities, original-first result, tests, negative results and
portable archive. The negative driver first validates the unmodified original.
Its 22 variants change observations only and verify that every physical file and
directory is unchanged before reusing the original physical derivation. Each
must fail at its exact declared network boundary. Accepted mutations and unrelated
errors fail qualification.

The first negative run correctly refused to count a mistakenly constructed
`late-request` mutation: the receive had moved past a nested response, not its
own response, and the history remained causally valid. The corrected mutation
locates the response by request digest; a small nested-response regression guards
this construction. The initial failed qualification is retained.

The gate qualifies this history's observed network causality, transfer integrity
and bound durable acknowledgements. It does not establish complete temporal
export authorization, every maintenance/learner control boundary, process death,
all seven profiles or the frozen scenario/negative mapping. Those remain required;
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
and `phase3Complete` stay false. No production Java, workload bounds, workflow,
POM, toolchain or frozen format changes are part of this batch.

```bash
python3 -B -m scripts.v53.joining_network_evidence <collection-v3-raw> --qualify
```
