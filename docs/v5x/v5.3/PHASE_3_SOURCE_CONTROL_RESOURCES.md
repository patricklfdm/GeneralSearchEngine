# Phase 3 source request, response and cache resources

This development qualification binds four CONTROL categories to actual original
source traffic. It is a component qualification, not Phase 3 closure or complete
required-four resource coverage. The retained
[development index](phase3-evidence/source-control-resources.json) records exact
producer inputs, observations, test reports and independent replay results.

## Identity and lifetime

`source-request` and `source-response` reservation owners include the SHA-256 of
the original request bytes and a fresh allocation UUID. `source-session` and
`transfer-trace` owners include a canonical hash of root, exact source identity,
exact reader identity and trace UUID, plus a fresh allocation UUID. The identities
include storage incarnation and endpoint. These are local resource observations:
they add no wire authority, durable record, vote, retry or capacity allowance.
All owner strings fit the existing 128-character limit.

The client holds one logical request reservation across identical TCP retries.
Per-attempt copied transport frames remain separate reservations. The request
must remain charged at every observed link call and terminal result, and be
released before the next logical call or completed pull close. A fresh nonce
cannot disguise releasing and recreating the same logical reservation.

The server retains the last response for an exact retry. Its bytes are derived
from the original response, not its resource counter. On the next sequence the
old cached response remains live through admission, then is released before the
replacement allocation. Session metadata remains charged while this cache is
active. When the export completes, the trace grows to `32768 + reply.size()`
before the final response and session reservations are released. Consequently
the final response reservation may legitimately end before TCP offers that
reply. Completed retries use the retained trace; they do not reopen an export.
An exhausted active pull retains its server cache until actual service close.

## Evidence

The native fixture runs four fresh public-bootstrap TCP histories: lost offer,
lost data, lost commit and exhausted offer retries. Successful pulls also resend
the final commit after the client pull has closed. The original promise, original
source directory, exact endpoints, every socket attempt, withheld response,
service callbacks, budget mutations and close boundaries are retained. The
independent reader first reconstructs the original grants and files, then replays
the exact record protocol and actual attempts before checking resource claims.

Negative replay changes copied journals/checkpoints coherently: wrong lengths or
owners, premature release, late release, renewed deadline, invented service
observations, unbound buffers and invalid final-cache handoff must reject at their
specific obligation. Original evidence must pass before any mutation counts as a
negative. No production retry is added by these tests.

Four histories bind 10 logical requests, 18 TCP attempts and 28 source CONTROL
reservations. Independent replay and all 76 exact negatives pass in 1.942 seconds.
The current suite has 43 passing Java tests (41 existing regressions and two new
tests) and 157 related Python tests. The existing reply-lifetime regression also
covers all 48 declared expiry/close/higher-ballot boundaries. The first run's new
fixture failed because a quiescent snapshot helper was called with the source
owner open; that failure is retained. The fixture now copies the original source
while open and uses the quiescent check only after close; its targeted rerun passes.

## Remaining scope

The short fixture uses a separate source-serving budget; the grant journal and
its exports are independently checked physically but their resource lifetimes
are not newly qualified here. `otherControlReservations` explicitly includes
transport buffers and other service allocations outside these four categories.
The full native reader still needs the general multi-session derivation and
integration on new originals. Historical UUID-only source owners cannot acquire
these bindings by matching byte counts. Existing historical evidence is retained
without relabelling it as current-source qualification.

Export/task/control owners, receiving physical custody, combined maxima and
completion headroom, remaining negative matrices and the final-source hosted
cohort remain open. Phase 3 remains OPEN; the 544-history development cohort and
frozen later-phase acceptance parameters are unchanged.
