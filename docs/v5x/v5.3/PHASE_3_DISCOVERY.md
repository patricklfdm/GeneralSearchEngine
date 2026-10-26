# Phase 3B — read-only root-bound discovery

Status: locally qualified. This implements the STATUS entry of
the [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md). Complete newer-source acquisition,
historical provenance and adoption scheduling remain open.

## Why discovery differs from voting

An old configuration cannot discover a later INTENT/FINAL if every message first
requires equality with the receiver's current view or current-voter eligibility.
The existing transport already retains permanent historical identities. The actual
activation endpoint now accepts STATUS_PROBE before requiring an activation scope.
It checks the exact root, sender/recipient identities and the correlation ballot's
known storage identity, then reads the current forced cut under the journal owner.
It echoes the request's view, ballot, trace, sequence and nonce for correlation.
The newer view is inside the returned cut. No wire format changes.

This read-only request is not a PREPARE or promise observation. Its correlation
ballot does not allocate/fence a campaign at the receiver, grant a vote or establish
eligibility. Actual higher PREPARE/protocol observations retain their existing
immediate fencing. Historical removed identities may query; arbitrary identities,
recycled storage/endpoints and foreign roots cannot. The endpoint returns ready
false because this component has no public READY authority. Receiving a ready hint
from a later runtime would still not authorize a public read or write.

## Query lifetime

The query snapshots the actual owner's observed root fence and already verified
identity directory; it does not ask its caller to invent a ballot or first force a
new grant. It uses the owner's shared resource budget. Each peer query has one
nonce, trace and exact request. Only transient transport IO/DEADLINE failures can
repeat that request, at most three times or the stricter configured retry count.
All attempts share the original deadline. Explicit rejection, capacity, malformed
responses, identity/correlation failure, cancellation and local fencing do not
retry. Close cancels the pending exchange. Local view changes, higher observations,
owner failure and time spent waiting for its writer invalidate late responses.

A returned Hint contains diagnostic bytes only. It does not construct Owned,
verify a capsule, install state, learn a new endpoint, change a promise, cancel an
operation, or publish READY. Even a newer cut mentioning unknown identities must
be acquired and verified through the separate complete-source path before adoption.
Expired incoming activation scopes remain expired after a status query.

## Evidence boundary

The actual TCP matrix uses public offline bootstrap, original journal activation
and a certified/applied/published BARRIER at stable sizes 3/4/5. Every ordered peer
pair queries the actual activation endpoint and journal. The independent reader
first reconstructs the original bootstrap, all phase records, application and
publication; then checks all status envelopes, exact cuts and unchanged authority
directories. The original evidence is validated before any negative mutation.

Separate deterministic tests cover stale-view requests, removed historical callers,
actual adopted stores, wrong identities, replies and nonces, finite identical
retries, deadline/cancellation/fencing, shared capacity, writer waiting and endpoint
scope lifetime. The joint/final adopted-store fixtures use explicit conditional
historical observations; they are not relabelled as a completed network membership
transition. The original-bootstrap TCP matrix uses actual original force evidence.

The first run passed its actual TCP matrix but eight query tests failed because the
initial constructor required a caller-selected campaign ballot. The corrected
implementation snapshots the owner's existing observed fence without a new grant.
Those failed results remain retained.

The [local receipt](phase3-evidence/discovery.json) binds the final isolated build:
46 Java tests in seven suites, including fourteen discovery tests; 573 Python
tests in normal and optimized modes; 38 actual TCP exchanges at sizes 3/4/5;
eleven exact evidence negatives; and identical normal, optimized and portable
replay. Existing endpoint and transport physical evidence also passes independent
negative replay. The preceding 76-test build additionally passed activation-driver
and adopted-storage regressions before the endpoint routing addition; its result
is retained under its original source and not relabelled as the final build.

Remaining work includes complete historical proof/capsule provenance, root-bound
source discovery and cross-view adoption, autonomous election ownership, repeated
source maintenance, learners/joint completion, generalized voting/publication and
the full Phase 3 S/N requirement mapping. No protected CI, paid cloud or release
acceptance is claimed.
